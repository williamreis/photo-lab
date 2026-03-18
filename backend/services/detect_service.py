"""Serviço de detecção de objetos em imagens via Fal AI Detect."""

from datetime import datetime
from pathlib import Path
from typing import BinaryIO

import fal_client
import httpx

from config import FAL_MODEL_DETECT, OUTPUT_DETECT_DIR, UPLOADS_DIR, validate_fal_key


class DetectService:
    """Detecta objetos em imagens usando o modelo Detect da Fal AI."""

    def __init__(self) -> None:
        validate_fal_key()

    def detect_from_url(
        self,
        image_url: str,
        prompt: str,
        preview: bool = True,
    ) -> dict:
        """
        Detecta objetos em uma imagem a partir de URL.

        Args:
            image_url: URL pública da imagem.
            prompt: O que detectar (ex: "orange", "person").
            preview: Se retornar imagem com caixas desenhadas.

        Returns:
            Dict com objects (lista de bbox) e image (URL se preview).
        """
        result = fal_client.subscribe(
            FAL_MODEL_DETECT,
            arguments={
                "image_url": image_url,
                "prompt": prompt,
                "preview": preview,
            },
            with_logs=True,
        )

        # Salvar imagem com caixas em backend/output/detect/
        if preview and result.get("image", {}).get("url"):
            OUTPUT_DETECT_DIR.mkdir(parents=True, exist_ok=True)
            out_path = OUTPUT_DETECT_DIR / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_detect.png")
            try:
                resp = httpx.get(result["image"]["url"], timeout=30.0)
                resp.raise_for_status()
                out_path.write_bytes(resp.content)
            except Exception:
                pass  # não falhar o fluxo se o download falhar

        return result

    def detect_from_file(
        self,
        file: BinaryIO,
        prompt: str,
        preview: bool = True,
    ) -> dict:
        """
        Detecta objetos em uma imagem a partir de upload.

        Args:
            file: Objeto file-like (UploadFile).
            prompt: O que detectar na imagem.
            preview: Se retornar imagem com caixas.

        Returns:
            Dict com objects e image (URL se preview).
        """
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = UPLOADS_DIR / "temp_detect.jpg"
        try:
            with open(temp_path, "wb") as f:
                f.write(file.read())
            image_url = fal_client.upload_file(temp_path)
            return self.detect_from_url(image_url, prompt, preview)
        finally:
            if temp_path.exists():
                temp_path.unlink()
