from __future__ import annotations
from typing import Any
from schemas.agent import PointXY, RetouchMarker
from services.agent_service import AgentService
from services.history_service import update_entry


def analyze_persist_job(saved_filename: str, original_filename: str, history_id: str) -> dict[str, Any]:
    """
    Executa a análise persistente fora do request.

    Retorna um payload JSON-safe compatível com o que o frontend espera em `showResult()`.
    """
    service = AgentService()
    try:
        result = service.analyze_existing_upload(saved_filename)
    except Exception as e:
        update_entry(
            history_id,
            {
                "status": "failed",
                "analysis": "",
                "error_message": str(e)[:500],
                "markers": [],
                "point_queries": [],
                "points_by_query": {},
            },
        )
        raise

    analysis_text = (result.get("analysis") or "").strip()
    if not analysis_text:
        analysis_text = "(Nenhum texto retornado pelo agente.)"

    points_by_query = {
        k: [PointXY(x=p["x"], y=p["y"]) for p in v]
        for k, v in (result.get("points_by_query") or {}).items()
    }
    markers = [RetouchMarker(**m) for m in result.get("markers", [])]

    markers_dicts = [
        m.model_dump() if hasattr(m, "model_dump") else m.dict() for m in markers
    ]
    pbq_plain = {
        k: [{"x": p.x, "y": p.y} for p in v] for k, v in points_by_query.items()
    }

    update_entry(
        history_id,
        {
            "status": "done",
            "job_id": None,
            "analysis": analysis_text,
            "markers": markers_dicts,
            "point_queries": list(result.get("point_queries") or []),
            "points_by_query": pbq_plain,
        },
    )

    return {
        "analysis": analysis_text,
        "point_queries": list(result.get("point_queries") or []),
        "points_by_query": pbq_plain,
        "markers": markers_dicts,
        "image_url": result["image_url"],
        "saved_filename": result["saved_filename"],
        "history_id": history_id,
    }
