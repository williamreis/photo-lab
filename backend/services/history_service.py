import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from config import HISTORY_DIR
from services.queue_service import get_queue

_ID_RE = re.compile(r"^[a-f0-9]{32}$")

_PROVIDER_ERROR_HINTS = (
    "requires more credits",
    "openrouter.ai/settings/keys",
    "fewer max_tokens",
    "can only afford",
    "rate limit",
    "429",
    "insufficient",
)


def _safe_id(entry_id: str) -> bool:
    return bool(entry_id and _ID_RE.match(entry_id))


def _looks_like_provider_error(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return False
    return any(h in s for h in _PROVIDER_ERROR_HINTS)


def save_analysis(
        *,
        image_url: str,
        saved_filename: str,
        analysis: str,
        markers: list[dict[str, Any]],
        point_queries: list[str],
        points_by_query: dict[str, list[dict[str, float]]],
) -> str:
    """Grava um registro de histórico. Retorna o id (hex 32)."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    hid = uuid.uuid4().hex
    record = {
        "id": hid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "done",
        "image_url": image_url,
        "saved_filename": saved_filename,
        "analysis": analysis,
        "error_message": None,
        "markers": markers,
        "point_queries": point_queries,
        "points_by_query": points_by_query,
    }
    path = HISTORY_DIR / f"{hid}.json"
    tmp = HISTORY_DIR / f".{hid}.tmp"
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return hid


def create_processing_entry(
        *,
        image_url: str,
        saved_filename: str,
        job_id: str,
) -> str:
    """Cria uma entrada no histórico marcada como processing. Retorna o id (hex 32)."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    hid = uuid.uuid4().hex
    record = {
        "id": hid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "processing",
        "job_id": job_id,
        "image_url": image_url,
        "saved_filename": saved_filename,
        "analysis": "",
        "error_message": None,
        "markers": [],
        "point_queries": [],
        "points_by_query": {},
    }
    path = HISTORY_DIR / f"{hid}.json"
    tmp = HISTORY_DIR / f".{hid}.tmp"
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return hid


def update_entry(entry_id: str, patch: dict[str, Any]) -> bool:
    """Atualiza um registro existente (merge superficial)."""
    if not _safe_id(entry_id):
        return False
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORY_DIR / f"{entry_id}.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {"id": entry_id}
    data.update(patch or {})
    tmp = HISTORY_DIR / f".{entry_id}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return True


def delete_entry(entry_id: str) -> bool:
    """Remove um registro do histórico (arquivo JSON)."""
    if not _safe_id(entry_id):
        return False
    path = HISTORY_DIR / f"{entry_id}.json"
    if not path.is_file():
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False


def list_summaries(limit: int = 80) -> list[dict[str, Any]]:
    """Lista entradas mais recentes primeiro."""
    if not HISTORY_DIR.is_dir():
        return []
    q = None
    files = sorted(
        HISTORY_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[: max(1, min(limit, 200))]
    out: list[dict[str, Any]] = []
    for p in files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        hid = data.get("id") or p.stem
        if not _safe_id(str(hid)):
            continue

        status = (data.get("status") or "done").strip() or "done"
        job_id = data.get("job_id")

        # Se o job já terminou, sincroniza o histórico para não ficar "Processando"
        # (evita corrida/atualizações perdidas e também corrige jobs antigos).
        if status == "processing" and job_id:
            try:
                if q is None:
                    q = get_queue()
                job = q.fetch_job(job_id)
                if job and job.is_finished:
                    payload = job.result or {}
                    update_entry(
                        str(hid),
                        {
                            "status": "done",
                            "job_id": None,
                            "analysis": payload.get("analysis") or "",
                            "markers": payload.get("markers") or [],
                            "point_queries": payload.get("point_queries") or [],
                            "points_by_query": payload.get("points_by_query") or {},
                            "image_url": payload.get("image_url") or data.get("image_url") or "",
                            "saved_filename": payload.get("saved_filename") or data.get("saved_filename") or "",
                            "error_message": None,
                        },
                    )
                    data.update(
                        {
                            "status": "done",
                            "job_id": None,
                            "analysis": payload.get("analysis") or data.get("analysis") or "",
                            "markers": payload.get("markers") or [],
                            "point_queries": payload.get("point_queries") or [],
                            "points_by_query": payload.get("points_by_query") or {},
                            "error_message": None,
                            "image_url": payload.get("image_url") or data.get("image_url") or "",
                            "saved_filename": payload.get("saved_filename") or data.get("saved_filename") or "",
                        }
                    )
                    status = "done"
                    job_id = None
                elif job and job.is_failed:
                    err = (job.exc_info or "").strip()
                    update_entry(
                        str(hid),
                        {
                            "status": "failed",
                            "job_id": None,
                            "analysis": "",
                            "markers": [],
                            "point_queries": [],
                            "points_by_query": {},
                            "error_message": err[:500] if err else (data.get("error_message") or None),
                        },
                    )
                    data.update({"status": "failed", "job_id": None,
                                 "error_message": err[:500] if err else data.get("error_message")})
                    status = "failed"
                    job_id = None
            except Exception:
                # Se falhar ao sincronizar, mantemos o conteúdo do arquivo.
                pass

        analysis = (data.get("analysis") or "").strip()
        preview = analysis.replace("\n", " ").strip()
        if len(preview) > 140:
            preview = preview[:137] + "…"
        markers = data.get("markers") or []
        # status e job_id já podem ter sido sincronizados acima
        # Backfill: entradas antigas que têm mensagem de erro, mas status "done"
        if status == "done" and _looks_like_provider_error(analysis):
            status = "failed"
        err = (data.get("error_message") or "").strip()
        if status == "failed" and not err and analysis:
            err = analysis
        if status == "failed":
            prev = ("Falhou: " + err.replace("\n", " ").strip()) if err else "Falhou."
            if len(prev) > 140:
                prev = prev[:137] + "…"
        else:
            prev = preview or ("Processando…" if status == "processing" else "(Sem texto)")
        out.append(
            {
                "id": hid,
                "created_at": data.get("created_at") or "",
                "image_url": data.get("image_url") or "",
                "preview": prev,
                "marker_count": len(markers),
                "status": status,
                "job_id": job_id,
                "error_message": err or None,
            }
        )
    return out


def get_by_id(entry_id: str) -> dict[str, Any] | None:
    if not _safe_id(entry_id):
        return None
    path = HISTORY_DIR / f"{entry_id}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        status = (data.get("status") or "done").strip() or "done"
        job_id = data.get("job_id")

        # Sincroniza status em tempo de leitura para não ficar "processing" após job done.
        if status == "processing" and job_id:
            try:
                q = get_queue()
                job = q.fetch_job(job_id)
                if job and job.is_finished:
                    payload = job.result or {}
                    update_entry(
                        str(entry_id),
                        {
                            "status": "done",
                            "job_id": None,
                            "analysis": payload.get("analysis") or "",
                            "markers": payload.get("markers") or [],
                            "point_queries": payload.get("point_queries") or [],
                            "points_by_query": payload.get("points_by_query") or {},
                            "image_url": payload.get("image_url") or data.get("image_url") or "",
                            "saved_filename": payload.get("saved_filename") or data.get("saved_filename") or "",
                            "error_message": None,
                        },
                    )
                    data.update(
                        {
                            "status": "done",
                            "job_id": None,
                            "analysis": payload.get("analysis") or data.get("analysis") or "",
                            "markers": payload.get("markers") or [],
                            "point_queries": payload.get("point_queries") or [],
                            "points_by_query": payload.get("points_by_query") or {},
                            "error_message": None,
                            "image_url": payload.get("image_url") or data.get("image_url") or "",
                            "saved_filename": payload.get("saved_filename") or data.get("saved_filename") or "",
                        }
                    )
                    status = "done"
                    job_id = None
                elif job and job.is_failed:
                    err = (job.exc_info or "").strip()
                    update_entry(
                        str(entry_id),
                        {
                            "status": "failed",
                            "job_id": None,
                            "analysis": "",
                            "markers": [],
                            "point_queries": [],
                            "points_by_query": {},
                            "error_message": err[:500] if err else (data.get("error_message") or None),
                        },
                    )
                    data.update({"status": "failed", "job_id": None,
                                 "error_message": err[:500] if err else data.get("error_message")})
                    status = "failed"
                    job_id = None
            except Exception:
                pass

        # Backfill status em tempo de leitura
        st = (data.get("status") or "done").strip() or "done"
        if st == "done" and _looks_like_provider_error((data.get("analysis") or "")):
            data["status"] = "failed"
            if not data.get("error_message"):
                data["error_message"] = data.get("analysis") or "Falha do provedor."
        return data
    except (json.JSONDecodeError, OSError):
        return None
