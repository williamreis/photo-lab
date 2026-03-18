"""Schemas Pydantic para request/response da API."""

from .detect import DetectRequest, DetectResponse, DetectedObject
from .point import PointRequest, PointResponse, PointCoord

__all__ = [
    "DetectRequest",
    "DetectResponse",
    "DetectedObject",
    "PointRequest",
    "PointResponse",
    "PointCoord",
]
