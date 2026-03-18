"""Schemas para o endpoint de localização de pontos."""

from pydantic import BaseModel, Field


class PointCoord(BaseModel):
    """Coordenada normalizada (0-1) de um ponto."""

    x: float = Field(..., description="Coordenada X normalizada")
    y: float = Field(..., description="Coordenada Y normalizada")


class PointRequest(BaseModel):
    """Request para localização de pontos (usado quando query vem em JSON)."""

    query: str = Field(..., min_length=1, description="O que localizar na imagem")
    preview: bool = Field(default=False, description="Retornar preview da API")


class PointResponse(BaseModel):
    """Response com pontos detectados."""

    points: list[PointCoord] = Field(default_factory=list)
    image_url: str | None = Field(None, description="URL da imagem com pontos (se preview=True)")
