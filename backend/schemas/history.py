"""Schemas do histórico de análises."""

from pydantic import BaseModel, Field

from schemas.agent import PointXY, RetouchMarker


class HistorySummary(BaseModel):
    """Item na listagem do histórico."""

    id: str = Field(..., description="Identificador do registro")
    created_at: str = Field(..., description="ISO 8601 (UTC)")
    image_url: str = Field(..., description="URL da imagem em /uploads/")
    preview: str = Field(..., description="Trecho do laudo")
    marker_count: int = Field(0, description="Quantidade de pontos")
    status: str = Field("done", description="done | processing | failed")
    job_id: str | None = Field(None, description="Id do job (quando processing)")
    error_message: str | None = Field(None, description="Resumo do erro (quando failed)")


class HistoryDetailResponse(BaseModel):
    """Laudo completo para reabrir na UI (mesmo formato do analyze/persist)."""

    id: str
    created_at: str
    analysis: str
    point_queries: list[str] = Field(default_factory=list)
    points_by_query: dict[str, list[PointXY]] = Field(default_factory=dict)
    markers: list[RetouchMarker] = Field(default_factory=list)
    image_url: str
    saved_filename: str
    status: str = Field("done", description="done | processing | failed")
    job_id: str | None = Field(None, description="Id do job (quando processing)")
    error_message: str | None = Field(None, description="Mensagem de erro (quando failed)")
