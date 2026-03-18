"""Endpoints de localização de pontos em imagens."""

import io

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from config import IMAGES_DIR
from schemas.point import PointCoord, PointResponse
from services.point_service import PointService

router = APIRouter()


@router.post(
    "/upload",
    response_model=PointResponse,
    summary="Localizar pontos via upload de imagem",
    description="Envia uma imagem e uma query para localizar pontos correspondentes.",
)
async def point_from_upload(
    image: UploadFile = File(..., description="Imagem para análise"),
    query: str = Form(..., description="O que localizar (ex: bottle caps, woman)"),
    preview: bool = Form(default=False),
) -> PointResponse:
    """Localiza pontos na imagem enviada via multipart/form-data."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(400, "Arquivo deve ser uma imagem")

    service = PointService()
    content = await image.read()
    result = service.locate_from_file(io.BytesIO(content), query, preview=preview)

    points = [PointCoord(x=p["x"], y=p["y"]) for p in result["points"]]
    image_url = None
    if result.get("result", {}).get("image", {}).get("url"):
        image_url = result["result"]["image"]["url"]

    return PointResponse(points=points, image_url=image_url)


@router.post(
    "/upload/image",
    summary="Retornar imagem com pontos desenhados",
    description="Upload de imagem + query, retorna a imagem com os pontos desenhados.",
)
async def point_from_upload_return_image(
    image: UploadFile = File(...),
    query: str = Form(...),
) -> Response:
    """Retorna a imagem com os pontos desenhados (PNG)."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(400, "Arquivo deve ser uma imagem")

    service = PointService()
    content = await image.read()
    result = service.locate_from_file(io.BytesIO(content), query, preview=False)

    img = result["image_drawn"]
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return Response(content=buffer.getvalue(), media_type="image/png")


@router.post(
    "/path",
    response_model=PointResponse,
    summary="Localizar pontos via caminho local",
    description="Usa imagem já existente no servidor (pasta images/).",
)
async def point_from_path(
    image_path: str = Form(..., description="Caminho relativo em images/ (ex: foto.jpg)"),
    query: str = Form(..., description="O que localizar"),
    preview: bool = Form(default=False),
) -> PointResponse:
    """Localiza pontos em imagem pelo caminho (relativo a images/)."""
    path = IMAGES_DIR / image_path
    if not path.exists():
        raise HTTPException(404, f"Imagem não encontrada: {image_path}")

    service = PointService()
    result = service.locate_from_path(path, query, preview=preview)

    points = [PointCoord(x=p["x"], y=p["y"]) for p in result["points"]]
    image_url = None
    if result.get("result", {}).get("image", {}).get("url"):
        image_url = result["result"]["image"]["url"]

    return PointResponse(points=points, image_url=image_url)
