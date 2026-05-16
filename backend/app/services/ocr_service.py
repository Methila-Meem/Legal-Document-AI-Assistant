from dataclasses import dataclass
from importlib.util import find_spec
from threading import Lock
from typing import Any

import numpy as np
from PIL import Image

from app.core.config import settings


SUPPORTED_OCR_ENGINES = {"easyocr", "tesseract", "auto"}


class OcrUnavailableError(Exception):
    def __init__(self, message: str, detail: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.detail = detail


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
    engine_used: str


class EasyOCRService:
    engine_name = "easyocr"
    _reader: object | None = None
    _init_error: str | None = None
    _lock = Lock()

    @classmethod
    def status(cls) -> dict[str, object]:
        if cls._reader is not None:
            return cls._status(True, None, "EasyOCR is ready.")
        if cls._init_error:
            return cls._status(False, cls._init_error, "EasyOCR is unavailable.")
        if find_spec("torch") is None:
            return cls._status(False, "No module named 'torch'", "EasyOCR is unavailable.")
        if find_spec("easyocr") is None:
            return cls._status(False, "No module named 'easyocr'", "EasyOCR is unavailable.")
        try:
            import easyocr  # noqa: F401
        except Exception as exc:
            cls._init_error = f"EasyOCR import failed: {exc}"
            return cls._status(False, cls._init_error, "EasyOCR is unavailable.")
        return cls._status(
            True,
            None,
            "EasyOCR dependencies are installed. Model loads on first OCR request.",
        )

    @classmethod
    def reset_for_tests(cls) -> None:
        cls._reader = None
        cls._init_error = None

    @classmethod
    def initialize(cls) -> object:
        with cls._lock:
            if cls._reader is not None:
                return cls._reader
            try:
                import easyocr

                cls._reader = easyocr.Reader([settings.ocr_lang], gpu=False)
                cls._init_error = None
                return cls._reader
            except Exception as exc:
                cls._init_error = f"EasyOCR failed to initialize: {exc}"
                raise OcrUnavailableError(
                    cls._init_error,
                    OCRManager.diagnostic_detail(error=cls._init_error),
                ) from exc

    def extract_text(self, image: Image.Image) -> OcrResult:
        reader = self.initialize()
        image_array = np.array(image.convert("RGB"))
        try:
            raw_result = reader.readtext(image_array, detail=1, paragraph=False)  # type: ignore[attr-defined]
        except Exception as exc:
            raise OcrExecutionError("EasyOCR failed while reading the image.") from exc

        lines: list[OcrLine] = []
        for item in raw_result or []:
            parsed = self._parse_line(item)
            if parsed:
                lines.append(parsed)

        text = "\n".join(line.text for line in lines).strip()
        confidence = _average_confidence(lines)
        return OcrResult(
            text=text,
            confidence=confidence,
            lines=lines,
            engine_used=self.engine_name,
        )

    @classmethod
    def _status(
        cls,
        available: bool,
        error_message: str | None,
        message: str,
    ) -> dict[str, object]:
        return {
            "engine": cls.engine_name,
            "available": available,
            "error_message": error_message,
            "message": message,
        }

    def _parse_line(self, item: object) -> OcrLine | None:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            return None
        bbox = _normalize_bbox(item[0])
        text = str(item[1]).strip()
        if not text:
            return None
        confidence = _normalize_confidence(item[2])
        return OcrLine(text=text, confidence=confidence, bbox=bbox)


class TesseractOCRService:
    engine_name = "tesseract"
    _available: bool | None = None
    _init_error: str | None = None
    _lock = Lock()

    @classmethod
    def status(cls) -> dict[str, object]:
        if cls._available:
            return cls._status(True, None, "Tesseract is ready.")
        if cls._init_error:
            return cls._status(False, cls._init_error, "Tesseract is unavailable.")
        if find_spec("pytesseract") is None:
            return cls._status(
                False,
                "No module named 'pytesseract'",
                "Tesseract is unavailable.",
            )
        try:
            cls.initialize()
        except OcrUnavailableError:
            return cls._status(False, cls._init_error, "Tesseract is unavailable.")
        return cls._status(True, None, "Tesseract is ready.")

    @classmethod
    def reset_for_tests(cls) -> None:
        cls._available = None
        cls._init_error = None

    @classmethod
    def initialize(cls) -> object:
        with cls._lock:
            if cls._available:
                import pytesseract

                return pytesseract
            try:
                import pytesseract

                if settings.tesseract_cmd:
                    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
                pytesseract.get_tesseract_version()
                cls._available = True
                cls._init_error = None
                return pytesseract
            except Exception as exc:
                cls._available = False
                cls._init_error = f"Tesseract failed to initialize: {exc}"
                raise OcrUnavailableError(
                    cls._init_error,
                    OCRManager.diagnostic_detail(error=cls._init_error),
                ) from exc

    def extract_text(self, image: Image.Image) -> OcrResult:
        pytesseract = self.initialize()
        try:
            output = pytesseract.Output.DICT
            raw_data = pytesseract.image_to_data(
                image.convert("RGB"),
                output_type=output,
                lang=self._tesseract_lang(settings.ocr_lang),
            )
        except Exception as exc:
            raise OcrExecutionError("Tesseract failed while reading the image.") from exc

        lines = self._parse_data(raw_data)
        text = "\n".join(line.text for line in lines).strip()
        confidence = _average_confidence(lines)
        return OcrResult(
            text=text,
            confidence=confidence,
            lines=lines,
            engine_used=self.engine_name,
        )

    @classmethod
    def _status(
        cls,
        available: bool,
        error_message: str | None,
        message: str,
    ) -> dict[str, object]:
        return {
            "engine": cls.engine_name,
            "available": available,
            "error_message": error_message,
            "message": message,
        }

    def _parse_data(self, data: dict[str, list[Any]]) -> list[OcrLine]:
        grouped: dict[tuple[int, int, int], list[dict[str, object]]] = {}
        text_values = data.get("text", [])
        for index, raw_text in enumerate(text_values):
            text = str(raw_text).strip()
            if not text:
                continue
            confidence = _normalize_tesseract_confidence(_list_get(data.get("conf", []), index))
            if confidence < 0:
                continue
            key = (
                _safe_int(_list_get(data.get("block_num", []), index)),
                _safe_int(_list_get(data.get("par_num", []), index)),
                _safe_int(_list_get(data.get("line_num", []), index)),
            )
            grouped.setdefault(key, []).append(
                {
                    "text": text,
                    "confidence": confidence,
                    "left": _safe_int(_list_get(data.get("left", []), index)),
                    "top": _safe_int(_list_get(data.get("top", []), index)),
                    "width": _safe_int(_list_get(data.get("width", []), index)),
                    "height": _safe_int(_list_get(data.get("height", []), index)),
                }
            )

        lines: list[OcrLine] = []
        for words in grouped.values():
            if not words:
                continue
            text = " ".join(str(word["text"]) for word in words).strip()
            left = min(int(word["left"]) for word in words)
            top = min(int(word["top"]) for word in words)
            right = max(int(word["left"]) + int(word["width"]) for word in words)
            bottom = max(int(word["top"]) + int(word["height"]) for word in words)
            confidence = round(
                sum(float(word["confidence"]) for word in words) / len(words),
                4,
            )
            lines.append(
                OcrLine(
                    text=text,
                    confidence=confidence,
                    bbox=[
                        [float(left), float(top)],
                        [float(right), float(top)],
                        [float(right), float(bottom)],
                        [float(left), float(bottom)],
                    ],
                )
            )
        return lines

    def _tesseract_lang(self, language: str) -> str:
        return "eng" if language.lower() == "en" else language


class OCRManager:
    fallback_engine = "tesseract"

    def __init__(self) -> None:
        selected = settings.ocr_engine.lower().strip()
        self.selected_engine = selected if selected else "easyocr"

    @classmethod
    def health(cls) -> dict[str, object]:
        return cls().status()

    @classmethod
    def diagnostic_detail(cls, error: str | None = None) -> dict[str, object]:
        manager = cls()
        status = manager.status()
        return {
            "message": "OCR is unavailable.",
            "selected_engine": status["selected_engine"],
            "active_engine": status.get("active_engine"),
            "fallback_engine": status.get("fallback_engine"),
            "error": error or status.get("error_message") or status.get("message"),
            "hint": (
                "Activate backend/venv and run: pip install -r requirements.txt. "
                "If PyTorch fails on Windows, install CPU PyTorch with the command in README. "
                "For Tesseract fallback, install the system Tesseract engine and set TESSERACT_CMD."
            ),
        }

    def status(self) -> dict[str, object]:
        if self.selected_engine not in SUPPORTED_OCR_ENGINES:
            return self._status(
                available=False,
                active_engine=None,
                error_message=(
                    f"Unsupported OCR_ENGINE value: {settings.ocr_engine}. "
                    "Use easyocr, tesseract, or auto."
                ),
                message="OCR is unavailable.",
            )

        if self.selected_engine == "easyocr":
            easy_status = EasyOCRService.status()
            return self._status_from_engine(
                easy_status,
                active_engine="easyocr" if easy_status["available"] else None,
                message_success="EasyOCR is ready.",
            )

        if self.selected_engine == "tesseract":
            tess_status = TesseractOCRService.status()
            return self._status_from_engine(
                tess_status,
                active_engine="tesseract" if tess_status["available"] else None,
                message_success="Tesseract is ready.",
            )

        easy_status = EasyOCRService.status()
        if easy_status["available"]:
            return self._status(
                available=True,
                active_engine="easyocr",
                error_message=None,
                message=str(easy_status["message"]),
            )

        tess_status = TesseractOCRService.status()
        if tess_status["available"]:
            return self._status(
                available=True,
                active_engine="tesseract",
                error_message=str(easy_status["error_message"]),
                message="EasyOCR unavailable; using Tesseract fallback.",
            )

        errors = "; ".join(
            error
            for error in (
                str(easy_status["error_message"]),
                str(tess_status["error_message"]),
            )
            if error and error != "None"
        )
        return self._status(
            available=False,
            active_engine=None,
            error_message=errors or "No OCR engine is available.",
            message="OCR is unavailable.",
        )

    def extract_text(self, image: Image.Image) -> OcrResult:
        if self.selected_engine == "easyocr":
            return self._extract_with_easyocr(image)
        if self.selected_engine == "tesseract":
            return self._extract_with_tesseract(image)
        if self.selected_engine == "auto":
            errors: list[str] = []
            try:
                return self._extract_with_easyocr(image)
            except OcrUnavailableError as exc:
                errors.append(str(exc))
            try:
                return self._extract_with_tesseract(image)
            except OcrUnavailableError as exc:
                errors.append(str(exc))
                error = "; ".join(errors)
                raise OcrUnavailableError(
                    "OCR is unavailable.",
                    self.diagnostic_detail(error=error),
                ) from exc
        raise OcrUnavailableError(
            f"Unsupported OCR_ENGINE value: {settings.ocr_engine}.",
            self.diagnostic_detail(
                error=f"Unsupported OCR_ENGINE value: {settings.ocr_engine}."
            ),
        )

    def _extract_with_easyocr(self, image: Image.Image) -> OcrResult:
        return EasyOCRService().extract_text(image)

    def _extract_with_tesseract(self, image: Image.Image) -> OcrResult:
        return TesseractOCRService().extract_text(image)

    def _status_from_engine(
        self,
        engine_status: dict[str, object],
        active_engine: str | None,
        message_success: str,
    ) -> dict[str, object]:
        return self._status(
            available=bool(engine_status["available"]),
            active_engine=active_engine,
            error_message=(
                str(engine_status["error_message"])
                if engine_status.get("error_message") is not None
                else None
            ),
            message=(
                message_success
                if engine_status["available"]
                else str(engine_status["message"])
            ),
        )

    def _status(
        self,
        *,
        available: bool,
        active_engine: str | None,
        error_message: str | None,
        message: str,
    ) -> dict[str, object]:
        return {
            "selected_engine": self.selected_engine,
            "available": available,
            "active_engine": active_engine,
            "fallback_engine": self.fallback_engine,
            "error_message": error_message,
            "message": message,
        }


def _average_confidence(lines: list[OcrLine]) -> float | None:
    if not lines:
        return None
    return round(sum(line.confidence for line in lines) / len(lines), 4)


def _normalize_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    if confidence > 1.0:
        confidence = confidence / 100.0
    return max(0.0, min(1.0, confidence))


def _normalize_tesseract_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return -1.0
    if confidence < 0:
        return -1.0
    return max(0.0, min(1.0, confidence / 100.0))


def _normalize_bbox(raw_bbox: object) -> list[list[float]]:
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


def _list_get(values: list[Any], index: int) -> object:
    return values[index] if index < len(values) else None


def _safe_int(value: object) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0
