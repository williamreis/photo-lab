"""Endpoints do agente de análise de pele."""

import base64
import io
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from schemas.agent import (
    AgentAnalysisResponse,
    AgentImageWithAnalysisResponse,
    AgentPersistAnalysisResponse,
    PointXY,
    RetouchMarker,
)
from jobs.agent_jobs import analyze_persist_job
from services.agent_service import AgentService
from services.history_service import create_processing_entry, save_analysis
from services.queue_service import get_queue
from config import UPLOADS_DIR

router = APIRouter()


@router.post(
    "/analyze",
    response_model=AgentAnalysisResponse,
    summary="Analisar imagem e marcar pontos",
    description="Agente analisa a imagem com prompt de pele, extrai itens de retoque e marca os pontos com moondream.",
)
async def agent_analyze(
    image: UploadFile = File(..., description="Imagem para análise de pele"),
) -> AgentAnalysisResponse:
    """Analisa a imagem e retorna laudo + pontos localizados."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(400, "Arquivo deve ser uma imagem")

    try:
        service = AgentService()
        content = await image.read()
        result = service.analyze_and_mark(content, image.filename or "image.jpg")
    except ValueError as e:
        raise HTTPException(500, str(e))
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))

    # Garantir que analysis é o texto completo da LLM (nunca vazio)
    analysis_text = (result.get("analysis") or "").strip()
    if not analysis_text:
        analysis_text = "(Nenhum texto retornado pelo agente.)"

    # Converter points_by_query para o schema (list[PointXY])
    points_by_query = {
        k: [{"x": p["x"], "y": p["y"]} for p in v]
        for k, v in result["points_by_query"].items()
    }

    return AgentAnalysisResponse(
        analysis=analysis_text,
        point_queries=result["point_queries"],
        points_by_query=points_by_query,
    )


@router.post(
    "/analyze/image",
    response_model=AgentImageWithAnalysisResponse,
    summary="Imagem com pontos + descritivo da análise",
    description="Analisa a imagem e retorna a imagem com os pontos/marcações (base64) e o laudo completo da LLM.",
)
async def agent_analyze_return_image(
    image: UploadFile = File(..., description="Imagem para análise de pele"),
) -> AgentImageWithAnalysisResponse:
    """Retorna a imagem com os pontos marcados (base64) e o descritivo da análise da LLM."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(400, "Arquivo deve ser uma imagem")

    try:
        service = AgentService()
        content = await image.read()
        result = service.analyze_and_mark(content, image.filename or "image.jpg")
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(500, str(e))

    analysis_text = (result.get("analysis") or "").strip()
    if not analysis_text:
        analysis_text = "(Nenhum texto retornado pelo agente.)"

    img = result["image_drawn"]
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    return AgentImageWithAnalysisResponse(
        analysis=analysis_text,
        image_base64=image_base64,
        point_queries=result.get("point_queries", []),
    )


@router.post(
    "/analyze/persist",
    response_model=AgentPersistAnalysisResponse,
    summary="Upload persistente + análise IA + marcadores",
    description=(
        "Salva a imagem em uploads/, executa o agente e moondream, "
        "retorna URL da foto, laudo e marcadores (x,y) com texto para tooltips."
    ),
)
async def agent_analyze_persist(
    image: UploadFile = File(..., description="Imagem para análise"),
) -> AgentPersistAnalysisResponse:
    """Persiste o upload e devolve dados para o app (foto + pontos + tooltips)."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(400, "Arquivo deve ser uma imagem")

    try:
        service = AgentService()
        content = await image.read()
        result = service.analyze_persist(content, image.filename or "image.jpg")
    except ValueError as e:
        raise HTTPException(500, str(e))
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))

    analysis_text = (result.get("analysis") or "").strip()
    if not analysis_text:
        analysis_text = "(Nenhum texto retornado pelo agente.)"

    points_by_query = {
        k: [PointXY(x=p["x"], y=p["y"]) for p in v]
        for k, v in result["points_by_query"].items()
    }
    markers = [RetouchMarker(**m) for m in result.get("markers", [])]
    markers_dicts = [
        m.model_dump() if hasattr(m, "model_dump") else m.dict() for m in markers
    ]
    pbq_plain = {
        k: [{"x": p.x, "y": p.y} for p in v] for k, v in points_by_query.items()
    }
    history_id = save_analysis(
        image_url=result["image_url"],
        saved_filename=result["saved_filename"],
        analysis=analysis_text,
        markers=markers_dicts,
        point_queries=list(result["point_queries"]),
        points_by_query=pbq_plain,
    )

    return AgentPersistAnalysisResponse(
        analysis=analysis_text,
        point_queries=result["point_queries"],
        points_by_query=points_by_query,
        markers=markers,
        image_url=result["image_url"],
        saved_filename=result["saved_filename"],
        history_id=history_id,
    )


@router.post(
    "/analyze/persist_async",
    status_code=202,
    summary="Upload persistente + enfileirar análise IA (async)",
    description=(
        "Salva a imagem e cria um job RQ para processar a análise em background. "
        "Retorna job_id imediatamente para o frontend fazer polling em /api/v1/jobs/{job_id}."
    ),
)
async def agent_analyze_persist_async(
    image: UploadFile = File(..., description="Imagem para análise"),
) -> dict:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(400, "Arquivo deve ser uma imagem")

    q = get_queue()

    # 1) Persistir upload imediatamente (rápido) para ter thumbnail/entrada no histórico
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    content = await image.read()
    uid = uuid.uuid4().hex[:12]
    base = Path(image.filename or "image.jpg").name
    safe = "".join(c for c in base if c.isalnum() or c in "._-")[:100] or "image.jpg"
    if "." not in safe:
        safe += ".jpg"
    saved_filename = f"{uid}_{safe}"
    out_path = UPLOADS_DIR / saved_filename
    out_path.write_bytes(content)
    image_url = f"/uploads/{saved_filename}"

    # 2) Criar job e entrada "processing" no histórico
    job = q.enqueue(
        analyze_persist_job,
        saved_filename,
        image.filename or "image.jpg",
        "pending",  # placeholder, será substituído abaixo
        job_timeout=900,  # 15 min
        result_ttl=60 * 60 * 24,  # 24h
        failure_ttl=60 * 60 * 24,
    )
    history_id = create_processing_entry(
        image_url=image_url,
        saved_filename=saved_filename,
        job_id=job.id,
    )

    # 3) Atualizar args do job com o history_id real
    job.args = (saved_filename, image.filename or "image.jpg", history_id)
    job.save()

    return {"job_id": job.id, "history_id": history_id, "status": "queued"}
