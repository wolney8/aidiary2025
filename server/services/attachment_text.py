from __future__ import annotations

from io import BytesIO
import re
from typing import Literal
from PIL import ImageOps, ImageFilter


MAX_PDF_EXTRACTION_PAGES = 8
MAX_PDF_EXTRACTION_CHARS = 6000
MIN_EMBEDDED_TEXT_CHARS_FOR_SUCCESS = 120
OCR_RENDER_DPI = 260
OCR_CONFIGS = (
    "--oem 3 --psm 6 -c preserve_interword_spaces=1",
    "--oem 3 --psm 11 -c preserve_interword_spaces=1",
)


PdfTextSource = Literal["pdf-text-extraction", "pdf-ocr"]


def extract_pdf_attachment_content(
    file_bytes: bytes,
) -> tuple[str | None, PdfTextSource | None]:
    if not file_bytes:
        return None, None

    embedded_text = _extract_embedded_pdf_text(file_bytes)
    if embedded_text and len(embedded_text) >= MIN_EMBEDDED_TEXT_CHARS_FOR_SUCCESS:
        return embedded_text, "pdf-text-extraction"

    ocr_text = _extract_pdf_text_via_ocr(file_bytes)
    if ocr_text:
        return ocr_text, "pdf-ocr"

    if embedded_text:
        return embedded_text, "pdf-text-extraction"

    return None, None


def extract_pdf_attachment_text(file_bytes: bytes) -> str | None:
    text, _source = extract_pdf_attachment_content(file_bytes)
    return text


def looks_like_low_quality_ocr_text(text: str) -> bool:
    normalised = _normalise_ocr_text(text)
    if not normalised:
        return True

    words = re.findall(r"[A-Za-z']+", normalised)
    if len(words) < 20:
        return True

    low_vowel_words = 0
    punctuation_noise = 0
    short_garbage_words = 0
    for word in words:
        lowered = word.lower()
        vowel_count = sum(1 for char in lowered if char in "aeiou")
        if len(lowered) >= 5 and vowel_count == 0:
            low_vowel_words += 1
        if len(lowered) <= 3 and not lowered.isalpha():
            short_garbage_words += 1

    punctuation_noise = len(re.findall(r"[\"'`]{2,}|[|_~^]{1,}", normalised))
    suspicious_ratio = low_vowel_words / max(len(words), 1)
    return suspicious_ratio >= 0.12 or punctuation_noise >= 4 or short_garbage_words >= 4


def _extract_embedded_pdf_text(file_bytes: bytes) -> str | None:
    if not file_bytes:
        return None

    try:
        from pypdf import PdfReader
    except Exception:
        return None

    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception:
        return None

    chunks: list[str] = []
    current_chars = 0
    for page in reader.pages[:MAX_PDF_EXTRACTION_PAGES]:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            continue

        normalised = re.sub(r"\s+", " ", page_text).strip()
        if not normalised:
            continue

        remaining = MAX_PDF_EXTRACTION_CHARS - current_chars
        if remaining <= 0:
            break

        clipped = normalised[:remaining].strip()
        if not clipped:
            continue

        chunks.append(clipped)
        current_chars += len(clipped) + 1

        if current_chars >= MAX_PDF_EXTRACTION_CHARS:
            break

    combined = " ".join(chunks).strip()
    return combined or None


def _extract_pdf_text_via_ocr(file_bytes: bytes) -> str | None:
    if not file_bytes:
        return None

    try:
        import pypdfium2 as pdfium
        import pytesseract
    except Exception:
        return None

    try:
        document = pdfium.PdfDocument(file_bytes)
    except Exception:
        return None

    chunks: list[str] = []
    current_chars = 0

    try:
        scale = OCR_RENDER_DPI / 72
        page_count = min(len(document), MAX_PDF_EXTRACTION_PAGES)
        for page_index in range(page_count):
            try:
                page = document.get_page(page_index)
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil().convert("L")
                image = ImageOps.autocontrast(image)
                image = image.filter(ImageFilter.MedianFilter(size=3))
                image = image.point(lambda value: 255 if value > 170 else 0)
                page_text = _extract_best_ocr_candidate(pytesseract, image)
            except Exception:
                continue
            finally:
                try:
                    page.close()
                except Exception:
                    pass

            normalised = _normalise_ocr_text(page_text)
            if not normalised:
                continue

            remaining = MAX_PDF_EXTRACTION_CHARS - current_chars
            if remaining <= 0:
                break

            clipped = normalised[:remaining].strip()
            if not clipped:
                continue

            chunks.append(clipped)
            current_chars += len(clipped) + 1

            if current_chars >= MAX_PDF_EXTRACTION_CHARS:
                break
    finally:
        try:
            document.close()
        except Exception:
            pass

    combined = " ".join(chunks).strip()
    return combined or None


def _extract_best_ocr_candidate(pytesseract_module, image) -> str:
    best_text = ""
    best_score = float("-inf")

    for config in OCR_CONFIGS:
        candidate = pytesseract_module.image_to_string(image, config=config) or ""
        normalised = _normalise_ocr_text(candidate)
        if not normalised:
            continue
        score = _score_ocr_candidate(normalised)
        if score > best_score:
            best_score = score
            best_text = normalised

    return best_text


def _score_ocr_candidate(text: str) -> float:
    if not text:
        return float("-inf")

    words = re.findall(r"[A-Za-z']+", text)
    if not words:
        return float("-inf")

    alpha_chars = sum(1 for char in text if char.isalpha())
    bad_chars = sum(1 for char in text if char in "_|~`^")
    long_words = sum(1 for word in words if len(word) >= 4)
    vowels = sum(1 for char in text.lower() if char in "aeiou")
    total_chars = max(len(text), 1)

    return (
        len(words) * 1.5
        + long_words * 2.0
        + (alpha_chars / total_chars) * 60.0
        + (vowels / total_chars) * 25.0
        - bad_chars * 6.0
    )


def _normalise_ocr_text(text: str) -> str:
    if not text:
        return ""

    normalised = text
    normalised = normalised.replace("‘", "'").replace("’", "'")
    normalised = normalised.replace("“", '"').replace("”", '"')
    normalised = normalised.replace("—", "-").replace("–", "-")
    normalised = normalised.replace("•", " ")
    normalised = re.sub(r"[|]{2,}", " ", normalised)
    normalised = re.sub(r"[_]{2,}", " ", normalised)
    normalised = re.sub(r"[^\w\s.,:;!?()/'\"%-]+", " ", normalised)
    normalised = re.sub(r"[^\S\r\n]+", " ", normalised)

    cleaned_lines: list[str] = []
    for raw_line in normalised.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"\s+", " ", line)
        line = re.sub(r"^[\"'`.,:;!?-]+\s*", "", line)
        line = re.sub(r"\s*[\"'`.,:;!?-]+$", "", line)
        line = re.sub(r"\b([A-Za-z])\s+([A-Za-z])\b", r"\1\2", line)
        line = re.sub(r"([a-z])([A-Z])", r"\1 \2", line)
        line = re.sub(r"([A-Za-z]{3,})[:;]([A-Za-z]{3,})", r"\1 \2", line)
        if len(line) < 3:
            continue
        cleaned_lines.append(line)

    merged = " ".join(cleaned_lines)
    merged = re.sub(r"\s+", " ", merged).strip()
    return merged
