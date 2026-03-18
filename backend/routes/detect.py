"""Endpoints de detecção de objetos em imagens."""

import io

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from schemas.detect import DetectRequest, DetectResponse, DetectedObject
from services.detect_service import DetectService

router = APIRouter()


@router.post(
    "/upload",
    response_model=DetectResponse,
    summary="Detectar objetos via upload de imagem",
)
async def detect_from_upload(
    image: UploadFile = File(..., description="Imagem para análise"),
    prompt: str = Form(..., description="O que detectar (ex: orange, person)"),
    preview: bool = Form(default=True),
) -> DetectResponse:
    """Detecta objetos na imagem enviada via multipart/form-data."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(400, "Arquivo deve ser uma imagem")

    service = DetectService()
    content = await image.read()
    result = service.detect_from_file(io.BytesIO(content), prompt, preview=preview)

    objects = [
        DetectedObject(
            x_min=o["x_min"],
            y_min=o["y_min"],
            x_max=o["x_max"],
            y_max=o["y_max"],
        )
        for o in result.get("objects", [])
    ]
    image_url = result.get("image", {}).get("url") if result.get("image") else None

    return DetectResponse(objects=objects, image_url=image_url)


@router.post(
    "/url",
    response_model=DetectResponse,
    summary="Detectar objetos via URL da imagem",
)
async def detect_from_url(request: DetectRequest) -> DetectResponse:
    """Detecta objetos em imagem a partir de URL pública."""
    if not request.image_url:
        raise HTTPException(400, "image_url é obrigatório para este endpoint")

    service = DetectService()
    result = service.detect_from_url(
        request.image_url,
        request.prompt,
        preview=request.preview,
    )

    objects = [
        DetectedObject(
            x_min=o["x_min"],
            y_min=o["y_min"],
            x_max=o["x_max"],
            y_max=o["y_max"],
        )
        for o in result.get("objects", [])
    ]
    image_url = result.get("image", {}).get("url") if result.get("image") else None

    return DetectResponse(objects=objects, image_url=image_url)
