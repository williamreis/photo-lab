import json
import re
import uuid
import fal_client
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
from pathlib import Path
from typing import Any
from agno.agent import Agent
from agno.media import Image
from agno.models.openai import OpenAIChat
from PIL import Image as PILImage
from config import (
    AGENT_MODEL,
    OPENROUTER_BASE_URL,
    OPENROUTER_API_KEY,
    FAL_MODEL_POINT,
    POINT_QUERY_LIMIT,
    POINTS_PER_QUERY_LIMIT,
    MARKERS_TOTAL_LIMIT,
    FAL_IMAGE_MAX_SIDE,
    FAL_IMAGE_JPEG_QUALITY,
    PROMPTS_DIR,
    UPLOADS_DIR,
    validate_fal_key,
)
from schemas.agent import ReportItem, SkinAnalysisSchema


def _load_skin_prompt() -> str:
    """Carrega o prompt de análise de pele."""
    path = PROMPTS_DIR / "skin.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt não encontrado: {path}")
    return path.read_text(encoding="utf-8")


def _format_analysis_from_report(items: list[ReportItem]) -> str:
    """Monta texto de laudo a partir do schema estruturado."""
    parts: list[str] = ["## Itens de retoque\n"]
    for r in items:
        parts.append(
            f"### [{r.relevance}] {r.description}\n\n"
            f"- **Técnica Photoshop:** {r.photoshop_technique}\n"
            f"- **Localização:** `{r.query}`\n"
        )
    return "\n".join(parts)


def _normalize_agent_output(raw: Any) -> tuple[str, list[ReportItem]]:
    """Retorna (texto da análise, itens do relatório) a partir da saída do agente."""
    if raw is None:
        return "", []

    if isinstance(raw, SkinAnalysisSchema):
        items = list(raw.report)
        return _format_analysis_from_report(items), items

    if isinstance(raw, dict) and "report" in raw:
        try:
            sch = SkinAnalysisSchema.model_validate(raw)
            items = list(sch.report)
            return _format_analysis_from_report(items), items
        except Exception:
            pass

    s = str(raw).strip() if not isinstance(raw, str) else raw.strip()
    if s.startswith("{") and '"report"' in s:
        try:
            sch = SkinAnalysisSchema.model_validate(json.loads(s))
            items = list(sch.report)
            return _format_analysis_from_report(items), items
        except Exception:
            pass

    return s, []


def _looks_like_provider_error(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return False
    hints = (
        "requires more credits",
        "openrouter.ai/settings/keys",
        "fewer max_tokens",
        "can only afford",
        "rate limit",
        "429",
        "insufficient",
    )
    return any(h in s for h in hints)


def _parse_point_queries_from_analysis(analysis: str) -> list[str]:
    """
    Extrai as queries de localização da análise do agente.
    Espera seção ## LOCALIZAÇÃO com frases em inglês, uma por linha.
    """
    queries = []
    in_section = False
    for line in analysis.splitlines():
        line = line.strip()
        if line.startswith("## LOCALIZAÇÃO") or line.startswith("## LOCALIZACAO"):
            in_section = True
            continue
        if in_section:
            if line.startswith("##"):
                break
            cleaned = line.lstrip("- ").strip()
            if cleaned and not cleaned.startswith("#"):
                queries.append(cleaned)
    return queries


def _extract_queries_from_report_fallback(analysis: str) -> list[str]:
    """Fallback: extrai áreas do formato [PRIORIDADE] Área: Descrição."""
    queries = []
    pattern = r"\[(?:🔴|🟡|🟢)?\s*(?:ESSENCIAL|RECOMENDADO|OPCIONAL)\s*\]\s*Área:\s*(.+?)(?:\n|$)"
    for match in re.finditer(pattern, analysis, re.IGNORECASE):
        area = match.group(1).strip()
        if area and len(area) > 2:
            queries.append(area)
    return queries[:10]


def _build_markers(
        points_by_query: dict[str, list[dict]],
        report_items: list[ReportItem],
) -> list[dict]:
    """Une pontos (x,y) a descrições do relatório pela query."""
    by_query = {
        (r.query or "").strip().lower(): r
        for r in report_items
        if (r.query or "").strip()
    }
    markers: list[dict] = []
    mid = 0
    for query, pts in points_by_query.items():
        qk = query.strip().lower()
        item = by_query.get(qk)
        if not item and report_items:
            item = next(
                (
                    r
                    for r in report_items
                    if qk in (r.query or "").lower()
                       or (r.query or "").lower() in qk
                ),
                None,
            )
        for pt in pts:
            mid += 1
            markers.append(
                {
                    "id": mid,
                    "x": float(pt["x"]),
                    "y": float(pt["y"]),
                    "query": query,
                    "description": item.description if item else query,
                    "relevance": item.relevance if item else "",
                    "photoshop_technique": item.photoshop_technique if item else "",
                }
            )
            if isinstance(MARKERS_TOTAL_LIMIT, int) and MARKERS_TOTAL_LIMIT > 0 and mid >= MARKERS_TOTAL_LIMIT:
                return markers
    return markers


def _prepare_image_for_fal(image_path: Path) -> Path:
    """
    Cria uma versão otimizada (redimensionada/comprimida) para enviar ao Fal,
    reduzindo latência e tokens de entrada. Não desenha overlays.
    """
    try:
        max_side = int(FAL_IMAGE_MAX_SIDE or 0)
    except Exception:
        max_side = 0
    if max_side <= 0:
        return image_path

    try:
        img = PILImage.open(image_path).convert("RGB")
        w, h = img.size
        if max(w, h) <= max_side:
            return image_path
        scale = max_side / float(max(w, h))
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        img = img.resize((nw, nh), resample=PILImage.Resampling.LANCZOS)

        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = UPLOADS_DIR / f"temp_fal_{uuid.uuid4().hex[:10]}.jpg"
        q = 85
        try:
            q = int(FAL_IMAGE_JPEG_QUALITY or 85)
        except Exception:
            q = 85
        q = max(50, min(95, q))
        img.save(out_path, format="JPEG", quality=q, optimize=True, progressive=True)
        return out_path
    except Exception:
        return image_path


class AgentService:
    """Agente de análise de pele para retoque fotográfico."""

    def __init__(self) -> None:
        validate_fal_key()
        if not OPENROUTER_API_KEY:
            raise ValueError(
                "Defina OPENROUTER_API_KEY no .env para usar o agente (OpenRouter)"
            )
        skin_prompt = _load_skin_prompt()
        self._system_prompt = skin_prompt.replace(
            "IMG_PATH: {img_path}",
            "Você está analisando a imagem anexada a esta mensagem.",
        )
        self._system_prompt += """

---
## LOCALIZAÇÃO (obrigatório)

Ao final do seu relatório, inclua uma seção exatamente assim:

## LOCALIZAÇÃO
- frase1 em inglês para localizar na imagem
- frase2 em inglês para localizar na imagem
...

Use frases curtas e descritivas em inglês para cada item que você identificou (ex: "under-eye dark circle", "forehead spot", "visible pore on nose", "lip asymmetry"). Uma frase por item de retoque.
"""
        model = OpenAIChat(
            id=AGENT_MODEL,
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        self._agent = Agent(
            model=model,
            instructions=self._system_prompt,
            markdown=True,
        )

    def analyze_and_mark(
            self,
            image_content: bytes,
            filename: str = "image.jpg",
    ) -> dict:
        """Analisa bytes temporários (arquivo não persistido)."""
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = UPLOADS_DIR / "temp_agent.jpg"
        try:
            temp_path.write_bytes(image_content)
            return self._analyze_and_mark_from_path(temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def analyze_persist(
            self,
            image_content: bytes,
            filename: str = "image.jpg",
    ) -> dict:
        """
        Salva a imagem em uploads/ com nome único e executa análise + marcação.
        Retorna dict com saved_filename, image_url (path relativo), markers, etc.
        """
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        uid = uuid.uuid4().hex[:12]
        base = Path(filename or "image.jpg").name
        safe = "".join(c for c in base if c.isalnum() or c in "._-")[:100] or "image.jpg"
        if "." not in safe:
            safe += ".jpg"
        out_path = UPLOADS_DIR / f"{uid}_{safe}"
        out_path.write_bytes(image_content)
        result = self._analyze_and_mark_from_path(out_path)
        result["saved_filename"] = out_path.name
        result["image_url"] = f"/uploads/{out_path.name}"
        result["markers"] = _build_markers(
            result["points_by_query"], result.get("report_items", [])
        )
        return result

    def analyze_existing_upload(self, saved_filename: str) -> dict:
        """
        Executa análise + marcação para um arquivo que já está em uploads/.
        Retorna no mesmo formato do analyze_persist (incluindo image_url/saved_filename/markers).
        """
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        image_path = UPLOADS_DIR / saved_filename
        if not image_path.exists():
            raise FileNotFoundError(f"Upload não encontrado: {image_path}")
        result = self._analyze_and_mark_from_path(image_path)
        result["saved_filename"] = image_path.name
        result["image_url"] = f"/uploads/{image_path.name}"
        result["markers"] = _build_markers(
            result["points_by_query"], result.get("report_items", [])
        )
        return result

    def _analyze_and_mark_from_path(self, image_path: Path) -> dict:
        """Analisa e marca a partir de um caminho local."""
        run_output = self._agent.run(
            "Analise esta fotografia seguindo o processo definido nas suas instruções. "
            "Gere o laudo técnico completo e a seção LOCALIZAÇÃO ao final.",
            images=[Image(filepath=str(image_path))],
            output_schema=SkinAnalysisSchema,
        )
        raw = run_output.content if run_output else None
        analysis, report_items = _normalize_agent_output(raw)

        if not analysis:
            raise ValueError(
                "O agente (LLM) não retornou análise. Verifique OPENROUTER_API_KEY e o modelo."
            )

        # Alguns provedores retornam falhas como texto "OK" (sem exceção / sem schema).
        # Nesses casos, tratamos como erro para a UI não considerar como análise concluída.
        if not report_items and _looks_like_provider_error(analysis):
            raise ValueError(
                "Falha no provedor do modelo (limite de tokens/créditos). "
                "Tente novamente mais tarde ou ajuste o limite do provedor."
            )

        if report_items:
            seen: set[str] = set()
            point_queries = []
            # Prioriza ESSENCIAL -> RECOMENDADO -> OPCIONAL e limita
            # o total de queries para reduzir o número de chamadas ao Fal /point.
            prio = {"ESSENCIAL": 0, "RECOMENDADO": 1, "OPCIONAL": 2}
            ordered = sorted(
                report_items,
                key=lambda r: (prio.get(str(r.relevance).upper(), 9)),
            )
            for r in ordered:
                q = (r.query or "").strip()
                if q and q not in seen:
                    seen.add(q)
                    point_queries.append(q)
        else:
            point_queries = _parse_point_queries_from_analysis(analysis)
        if not point_queries:
            point_queries = _extract_queries_from_report_fallback(analysis)

        # Aplica limite global (mesmo no fallback).
        if isinstance(POINT_QUERY_LIMIT, int) and POINT_QUERY_LIMIT > 0:
            point_queries = point_queries[:POINT_QUERY_LIMIT]

        # Upload da imagem para um URL público que o Fal consiga acessar.
        # Observação: como precisamos apenas das coordenadas (x,y), não
        # precisamos do preview/imagem desenhada.
        fal_path = _prepare_image_for_fal(image_path)
        try:
            fal_image_url = fal_client.upload_file(str(fal_path))
        finally:
            # Remove o arquivo temporário otimizado (se foi criado)
            try:
                if fal_path != image_path and fal_path.exists():
                    fal_path.unlink()
            except Exception:
                pass

        points_by_query: dict[str, list[dict[str, Any]]] = {}
        # Otimização: chamadas ao Fal em paralelo
        # Limite para evitar saturar rede/provedor.
        max_workers = max(1, min(2, len(point_queries)))

        def _locate_one(q: str) -> tuple[str, list[dict[str, Any]]]:
            # Retry leve quando estourar limite de concorrência/429.
            attempts = 3
            for i in range(attempts):
                try:
                    fal_result = fal_client.subscribe(
                        FAL_MODEL_POINT,
                        arguments={
                            "image_url": fal_image_url,
                            "prompt": q,
                            "preview": False,
                        },
                    )
                    pts = fal_result.get("points") or []
                    if isinstance(POINTS_PER_QUERY_LIMIT, int) and POINTS_PER_QUERY_LIMIT > 0:
                        pts = list(pts)[:POINTS_PER_QUERY_LIMIT]
                    return q, pts
                except Exception as e:
                    msg = str(e).lower()
                    too_many = "too many" in msg or "simultaneously" in msg or "429" in msg or "rate limit" in msg
                    if not too_many or i == attempts - 1:
                        raise
                    # backoff com jitter
                    time.sleep((0.8 * (2 ** i)) + random.random() * 0.35)
            return q, []

        if point_queries:
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = {ex.submit(_locate_one, q): q for q in point_queries}
                for fut in as_completed(futures):
                    q = futures[fut]
                    try:
                        qq, pts = fut.result()
                        points_by_query[qq] = pts
                    except Exception:
                        points_by_query[q] = []

        return {
            "analysis": analysis,
            "point_queries": point_queries,
            "points_by_query": points_by_query,
            "report_items": report_items,
        }
