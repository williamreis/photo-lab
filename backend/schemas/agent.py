from typing import Literal, Optional
from pydantic import BaseModel, Field


class ReportItem(BaseModel):
    """Schema de saída estruturada do agente para um item de retoque."""

    description: str = Field(
        ...,
        description="Descrição do problema"
    )
    relevance: Literal["ESSENCIAL", "RECOMENDADO", "OPCIONAL"] = Field(
        ...,
        description="Relevância do retoque (essencial, recomendado ou opcional)",
    )
    photoshop_technique: str = Field(
        ...,
        description="Técnica de Photoshop sugerida para resolver o problema",
    )
    query: str = Field(
        ...,
        description="A query para a ferramenta Fal AI para localizar a área na imagem",
    )
    x_point: Optional[float] = Field(
        None,
        description="Coordenada x normalizada (0-1) do ponto na imagem",
        ge=0.0,
        le=1.0,
    )
    y_point: Optional[float] = Field(
        None,
        description="Coordenada y normalizada (0-1) do ponto na imagem",
        ge=0.0,
        le=1.0,
    )


class SkinAnalysisSchema(BaseModel):
    report: list[ReportItem] = Field(
        ...,
        description="O relatório da análise da imagem",
    )


class PointXY(BaseModel):
    """Coordenada normalizada (0-1)."""

    x: float
    y: float


class AgentAnalysisResponse(BaseModel):
    """Response com análise do agente e pontos localizados."""

    analysis: str = Field(
        ...,
        description="Laudo técnico completo gerado pela LLM (análise de pele, zonas da face, itens de retoque, técnicas sugeridas)",
    )
    point_queries: list[str] = Field(
        default_factory=list,
        description="Frases usadas para localizar pontos na imagem (moondream)",
    )
    points_by_query: dict[str, list[PointXY]] = Field(
        default_factory=dict,
        description="Pontos (x, y normalizados) por query",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "analysis": "## Avaliação Geral\nQualidade suficiente para retoque...\n\n## Zona T\nPoros visíveis no nariz...\n\n## LOCALIZAÇÃO\n- under-eye dark circle\n- forehead spot",
                    "point_queries": ["under-eye dark circle", "forehead spot"],
                    "points_by_query": {
                        "under-eye dark circle": [{"x": 0.45, "y": 0.32}, {"x": 0.55, "y": 0.33}],
                        "forehead spot": [{"x": 0.5, "y": 0.18}],
                    },
                }
            ]
        }
    }


class AgentImageWithAnalysisResponse(BaseModel):
    """Response com imagem (base64) e descritivo da análise da LLM."""

    analysis: str = Field(
        ...,
        description="Laudo técnico completo gerado pela LLM (análise de pele, zonas, itens de retoque, técnicas)",
    )
    image_base64: str = Field(
        ...,
        description="Imagem com pontos/marcações em PNG, codificada em base64",
    )
    point_queries: list[str] = Field(
        default_factory=list,
        description="Frases usadas para localizar os pontos na imagem",
    )


class RetouchMarker(BaseModel):
    """Um ponto na imagem com metadados para tooltip."""

    id: int = Field(..., description="Índice do marcador")
    x: float = Field(..., description="X normalizado 0–1")
    y: float = Field(..., description="Y normalizado 0–1")
    query: str = Field(..., description="Frase de localização")
    description: str = Field("", description="Descrição do problema")
    relevance: str = Field("", description="ESSENCIAL | RECOMENDADO | OPCIONAL")
    photoshop_technique: str = Field("", description="Técnica sugerida")


class AgentPersistAnalysisResponse(BaseModel):
    """Análise completa com imagem persistida em uploads e marcadores para o frontend."""

    analysis: str = Field(..., description="Laudo / relatório de retoque")
    point_queries: list[str] = Field(default_factory=list)
    points_by_query: dict[str, list[PointXY]] = Field(default_factory=dict)
    markers: list[RetouchMarker] = Field(
        default_factory=list,
        description="Lista plana de pontos com texto para tooltip",
    )
    image_url: str = Field(
        ...,
        description="URL para exibir a foto enviada (ex.: /uploads/abc_foto.jpg)",
    )
    saved_filename: str = Field(..., description="Nome do arquivo salvo em uploads/")
    history_id: str = Field(
        default="",
        description="Id no histórico para reabrir este laudo depois",
    )
