"""Histórico de análises salvas."""

from fastapi import APIRouter, HTTPException, Query

from schemas.agent import PointXY, RetouchMarker
from schemas.history import HistoryDetailResponse, HistorySummary
from services.history_service import delete_entry, get_by_id, list_summaries

router = APIRouter()


@router.get(
    "",
    response_model=list[HistorySummary],
    summary="Listar histórico de laudos",
)
def history_list(limit: int = Query(50, ge=1, le=100)) -> list[HistorySummary]:
    rows = list_summaries(limit=limit)
    return [HistorySummary(**r) for r in rows]


@router.get(
    "/{entry_id}",
    response_model=HistoryDetailResponse,
    summary="Obter laudo salvo por id",
)
def history_get(entry_id: str) -> HistoryDetailResponse:
    raw = get_by_id(entry_id)
    if not raw:
        raise HTTPException(404, "Registro não encontrado")
    points_by_query = {
        k: [PointXY(x=p["x"], y=p["y"]) for p in v]
        for k, v in (raw.get("points_by_query") or {}).items()
    }
    markers_raw = raw.get("markers") or []
    markers = []
    for m in markers_raw:
        try:
            markers.append(RetouchMarker(**m))
        except Exception:
            continue
    return HistoryDetailResponse(
        id=raw["id"],
        created_at=raw.get("created_at") or "",
        analysis=raw.get("analysis") or "",
        point_queries=list(raw.get("point_queries") or []),
        points_by_query=points_by_query,
        markers=markers,
        image_url=raw.get("image_url") or "",
        saved_filename=raw.get("saved_filename") or "",
        status=raw.get("status") or "done",
        job_id=raw.get("job_id"),
        error_message=raw.get("error_message"),
    )


@router.delete(
    "/{entry_id}",
    summary="Remover registro do histórico",
    description="Remove um registro do histórico de análises já salvo.",
)
def history_delete(entry_id: str) -> dict[str, bool]:
    ok = delete_entry(entry_id)
    if not ok:
        raise HTTPException(404, "Registro não encontrado")
    return {"deleted": True}
