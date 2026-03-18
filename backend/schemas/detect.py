"""Schemas para o endpoint de detecção de objetos."""

from pydantic import BaseModel, Field


class DetectedObject(BaseModel):
    """Objeto detectado com bbox normalizada (0-1)."""

    x_min: float = Field(..., description="X mínimo da bbox")
    y_min: float = Field(..., description="Y mínimo da bbox")
    x_max: float = Field(..., description="X máximo da bbox")
    y_max: float = Field(..., description="Y máximo da bbox")


class DetectRequest(BaseModel):
    """Request para detecção de objetos."""

    image_url: str | None = Field(None, description="URL da imagem (alternativa ao upload)")
    prompt: str = Field(..., min_length=1, description="O que detectar na imagem")
    preview: bool = Field(default=True, description="Retornar imagem com caixas desenhadas")


class DetectResponse(BaseModel):
    """Response com objetos detectados."""

    objects: list[DetectedObject] = Field(default_factory=list)
    image_url: str | None = Field(None, description="URL da imagem com caixas (se preview=True)")
