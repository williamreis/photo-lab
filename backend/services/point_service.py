"""Serviço de localização de pontos em imagens via Fal AI Point."""

from datetime import datetime
from pathlib import Path
from typing import BinaryIO

import fal_client
from PIL import Image, ImageDraw

from config import (
    FAL_MODEL_POINT,
    IMAGES_DIR,
    OUTPUT_POINT_DIR,
    POINT_FILL,
    POINT_OUTLINE,
    POINT_OUTLINE_WIDTH,
    POINT_RADIUS,
    UPLOADS_DIR,
)
from config import validate_fal_key


class PointService:
    """Localiza pontos em imagens usando o modelo Point da Fal AI."""

    def __init__(self) -> None:
        validate_fal_key()

    def _draw_points_on_image(self, image: Image.Image, points: list[dict]) -> Image.Image:
        """Desenha círculos nos pontos da imagem."""
        img = image.convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size

        for pt in points:
            x_norm = pt.get("x", 0)
            y_norm = pt.get("y", 0)
            px = int(x_norm * w)
            py = int(y_norm * h)
            draw.ellipse(
                (
                    px - POINT_RADIUS,
                    py - POINT_RADIUS,
                    px + POINT_RADIUS,
                    py + POINT_RADIUS,
                ),
                fill=POINT_FILL,
                outline=POINT_OUTLINE,
                width=POINT_OUTLINE_WIDTH,
            )
        return img

    def locate_from_path(
        self,
        image_path: str | Path,
        query: str,
        preview: bool = False,
        output_path: str | Path | None = None,
    ) -> dict:
        """
        Localiza pontos na imagem a partir de um caminho local.

        Args:
            image_path: Caminho da imagem (relativo a images/ ou absoluto).
            query: O que localizar (ex: "bottle caps", "woman").
            preview: Se a API deve retornar preview.
            output_path: Onde salvar a imagem com pontos (opcional).

        Returns:
            Dict com points, image_drawn (PIL.Image), result (resposta bruta).
        """
        path = Path(image_path)
        if not path.is_absolute():
            path = IMAGES_DIR / path

        if not path.exists():
            raise FileNotFoundError(f"Imagem não encontrada: {path}")

        image_url = fal_client.upload_file(path)
        result = fal_client.subscribe(
            FAL_MODEL_POINT,
            arguments={
                "image_url": image_url,
                "prompt": query,
                "preview": preview,
            },
            with_logs=True,
        )

        points = result.get("points", [])
        img = Image.open(path).convert("RGB")
        img_drawn = self._draw_points_on_image(img, points)

        if output_path:
            img_drawn.save(output_path)

        # Salvar sempre em backend/output/point/
        OUTPUT_POINT_DIR.mkdir(parents=True, exist_ok=True)
        out_name = datetime.now().strftime("%Y%m%d_%H%M%S") + "_point.png"
        img_drawn.save(OUTPUT_POINT_DIR / out_name)

        return {
            "points": points,
            "image_drawn": img_drawn,
            "result": result,
        }

    def locate_from_file(
        self,
        file: BinaryIO,
        query: str,
        preview: bool = False,
    ) -> dict:
        """
        Localiza pontos na imagem a partir de um arquivo enviado (upload).
        A imagem gerada é salva em backend/output/point/.
        """
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = UPLOADS_DIR / "temp_point.jpg"
        try:
            with open(temp_path, "wb") as f:
                f.write(file.read())
            return self.locate_from_path(temp_path, query, preview=preview)
        finally:
            if temp_path.exists():
                temp_path.unlink()
