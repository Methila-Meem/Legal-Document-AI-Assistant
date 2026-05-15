from dataclasses import dataclass
from importlib.util import find_spec
import os
from threading import Lock

import numpy as np
from PIL import Image

from app.core.config import settings


class OcrUnavailableError(Exception):
    pass


class OcrExecutionError(Exception):
    pass


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    bbox: list[list[float]]


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None
    lines: list[OcrLine]


class PaddleOCRService:
    _ocr_instance: object | None = None
    _init_error: str | None = None
    _lock = Lock()

    @classmethod
    def health(cls) -> dict[str, object]:
        if settings.ocr_engine.lower() != "paddleocr":
            return {
                "engine": "PaddleOCR",
                "available": False,
                "message": f"Unsupported OCR_ENGINE value: {settings.ocr_engine}.",
            }

        if cls._ocr_instance is not None:
            return {
                "engine": "PaddleOCR",
                "available": True,
                "message": "PaddleOCR is initialized.",
            }

        if cls._init_error:
            return {
                "engine": "PaddleOCR",
                "available": False,
                "message": cls._init_error,
            }

        missing = [
            package
            for package in ("paddleocr", "paddle")
            if find_spec(package) is None
        ]
        if missing:
            return {
                "engine": "PaddleOCR",
                "available": False,
                "message": f"Missing Python package(s): {', '.join(missing)}.",
            }

        return {
            "engine": "PaddleOCR",
            "available": True,
            "message": "PaddleOCR dependencies are installed. Model loads on first OCR request.",
        }

    def extract_text(self, image: Image.Image) -> OcrResult:
        ocr = self._get_ocr()
        image_array = np.array(image.convert("RGB"))
        try:
            if hasattr(ocr, "ocr"):
                raw_result = ocr.ocr(image_array, cls=True)
            else:
                raw_result = ocr.predict(image_array)
        except Exception as exc:
            raise OcrExecutionError("PaddleOCR failed while reading the image.") from exc

        return self._parse_result(raw_result)

    @classmethod
    def _get_ocr(cls) -> object:
        with cls._lock:
            if cls._ocr_instance is not None:
                return cls._ocr_instance

            try:
                cls._configure_cache_environment()
                from paddleocr import PaddleOCR

                cls._ocr_instance = cls._create_ocr(PaddleOCR)
            except Exception as exc:
                cls._init_error = (
                    "PaddleOCR is unavailable. Install paddleocr and paddlepaddle; "
                    "the first run may download model weights."
                )
                raise OcrUnavailableError(cls._init_error) from exc

            cls._init_error = None
            return cls._ocr_instance

    @classmethod
    def _configure_cache_environment(cls) -> None:
        cache_dir = settings.storage_dir / "processed" / "ocr_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(os.path.expanduser("~"), os.W_OK):
            os.environ.setdefault("HOME", str(cache_dir))
            os.environ.setdefault("USERPROFILE", str(cache_dir))
        os.environ.setdefault("PADDLE_HOME", str(cache_dir / "paddle"))
        os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(cache_dir / "paddlex"))
        os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
        os.environ.setdefault("HF_HOME", str(cache_dir / "huggingface"))
        os.environ.setdefault("MODEL_SCOPE_CACHE", str(cache_dir / "modelscope"))

    @classmethod
    def _create_ocr(cls, paddle_ocr_class: object) -> object:
        constructor_attempts = [
            {"lang": settings.ocr_lang, "use_angle_cls": True, "show_log": False},
            {"lang": settings.ocr_lang, "use_textline_orientation": True},
            {"lang": settings.ocr_lang},
        ]
        last_error: Exception | None = None
        for kwargs in constructor_attempts:
            try:
                return paddle_ocr_class(**kwargs)  # type: ignore[misc]
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise RuntimeError("Unable to initialize PaddleOCR.")

    def _parse_result(self, raw_result: object) -> OcrResult:
        lines: list[OcrLine] = []
        pages = raw_result if isinstance(raw_result, list) else []
        for page in pages:
            if not page:
                continue
            if isinstance(page, dict):
                lines.extend(self._parse_result_dict(page))
                continue
            for item in page:
                if isinstance(item, dict):
                    lines.extend(self._parse_result_dict(item))
                    continue
                parsed_line = self._parse_line(item)
                if parsed_line:
                    lines.append(parsed_line)

        text = "\n".join(line.text for line in lines).strip()
        confidence = (
            round(sum(line.confidence for line in lines) / len(lines), 4)
            if lines
            else None
        )
        return OcrResult(text=text, confidence=confidence, lines=lines)

    def _parse_result_dict(self, item: dict[str, object]) -> list[OcrLine]:
        texts = item.get("rec_texts") or item.get("texts") or []
        scores = item.get("rec_scores") or item.get("scores") or []
        boxes = item.get("rec_polys") or item.get("dt_polys") or item.get("boxes") or []

        if hasattr(texts, "tolist"):
            texts = texts.tolist()
        if hasattr(scores, "tolist"):
            scores = scores.tolist()
        if hasattr(boxes, "tolist"):
            boxes = boxes.tolist()

        if not isinstance(texts, list):
            return []

        parsed_lines: list[OcrLine] = []
        for index, text_value in enumerate(texts):
            text = str(text_value).strip()
            if not text:
                continue

            score_value = scores[index] if isinstance(scores, list) and index < len(scores) else 0.0
            try:
                confidence = float(score_value)
            except (TypeError, ValueError):
                confidence = 0.0

            raw_bbox = boxes[index] if isinstance(boxes, list) and index < len(boxes) else []
            parsed_lines.append(
                OcrLine(
                    text=text,
                    confidence=confidence,
                    bbox=self._normalize_bbox(raw_bbox),
                )
            )
        return parsed_lines

    def _parse_line(self, item: object) -> OcrLine | None:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            return None

        raw_bbox = item[0]
        raw_text_score = item[1]
        if not isinstance(raw_text_score, (list, tuple)) or len(raw_text_score) < 2:
            return None

        text = str(raw_text_score[0]).strip()
        if not text:
            return None

        try:
            confidence = float(raw_text_score[1])
        except (TypeError, ValueError):
            confidence = 0.0

        bbox = self._normalize_bbox(raw_bbox)
        return OcrLine(text=text, confidence=confidence, bbox=bbox)

    def _normalize_bbox(self, raw_bbox: object) -> list[list[float]]:
        if not isinstance(raw_bbox, (list, tuple)):
            return []

        points: list[list[float]] = []
        for point in raw_bbox:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                points.append([float(point[0]), float(point[1])])
            except (TypeError, ValueError):
                continue
        return points
