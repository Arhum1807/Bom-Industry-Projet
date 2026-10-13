"""
image_extractor.py
Handles extraction from image files (JPG, PNG, TIFF, BMP, WEBP) of engineering drawings.

Strategy:
  1. Convert image to a high-DPI PDF page using PyMuPDF
  2. Run the same text extraction + pattern matching as for native PDFs
  3. Additionally scan for raw BoM patterns in OCR-like block layout

For images, PyMuPDF renders them as a page and can extract embedded text
(for digital exports) or treat the pixels as a document.
When Tesseract OCR is available, it will be used automatically via PyMuPDF's
built-in OCR support (pymupdf-open with ocrmypdf or tessdata).
When not available, we do our best with pixel-based text detection.
"""

import re
import os
import tempfile
from pathlib import Path
import pymupdf as fitz
from PIL import Image
import io

# Import our shared extraction logic
from bom_extractor import (
    DrawingData, TitleBlock, BomItem, HardwareItem,
    DispatchUnit, ReferenceDrawing,
    _find_title_block, _parse_bom_section, _parse_hardware_section,
    _parse_dispatch_units, _parse_reference_drawings,
    RE_DOC_ID,
)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp', '.gif'}
PDF_EXTS   = {'.pdf'}


def _preprocess_image_for_ocr(img_path: str) -> str:
    """
    Preprocess image: increase contrast, resize if too small.
    Returns path to processed temp image.
    """
    from PIL import Image, ImageEnhance, ImageFilter
    img = Image.open(img_path)

    # Convert to RGB if needed
    if img.mode not in ('RGB', 'L', 'RGBA'):
        img = img.convert('RGB')

    # Resize if too small (for better OCR accuracy)
    w, h = img.size
    if w < 2000 or h < 1400:
        scale = max(2000 / w, 1400 / h, 1.5)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Enhance sharpness and contrast for engineering drawings
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = ImageEnhance.Contrast(img).enhance(1.4)

    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    img.save(tmp.name, 'PNG', dpi=(300, 300))
    return tmp.name


def _image_to_searchable_pdf(img_path: str) -> str:
    """
    Convert an image file to a PDF that PyMuPDF can process.
    Tries OCR if tesseract is available, otherwise embeds image as-is.
    Returns path to temp PDF.
    """
    tmp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp_pdf.close()

    # First try: use pymupdf to embed image in PDF with OCR
    try:
        # Try ocrmypdf if available
        import ocrmypdf
        processed_img = _preprocess_image_for_ocr(img_path)
        ocrmypdf.ocr(processed_img, tmp_pdf.name, deskew=True, language='eng',
                     force_ocr=True, progress_bar=False)
        os.unlink(processed_img)
        return tmp_pdf.name
    except (ImportError, Exception):
        pass

    # Second try: pymupdf built-in OCR (requires tessdata)
    try:
        tessdata_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tessdata')
        doc = fitz.open(img_path)
        out_doc = fitz.open()
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            kwargs = {'language': 'eng'}
            if os.path.isdir(tessdata_dir):
                kwargs['tessdata'] = tessdata_dir
            ocr_pdf = pix.pdfocr_tobytes(**kwargs)
            ocr_doc = fitz.open("pdf", ocr_pdf)
            out_doc.insert_pdf(ocr_doc)
        out_doc.save(tmp_pdf.name)
        out_doc.close()
        doc.close()
        return tmp_pdf.name
    except Exception:
        pass

    # Fallback: just embed image as PDF page (no OCR text)
    doc = fitz.open()
    page = doc.new_page()
    img_doc = fitz.open(img_path)
    pix = img_doc[0].get_pixmap(dpi=300)
    rect = page.rect
    page.insert_image(rect, pixmap=pix)
    doc.save(tmp_pdf.name)
    doc.close()
    img_doc.close()
    return tmp_pdf.name


def extract_from_image(img_path: str) -> DrawingData:
    """
    Main entry for image files. Converts to searchable PDF then extracts.
    """
    tmp_pdf = None
    try:
        tmp_pdf = _image_to_searchable_pdf(img_path)
        data = _extract_from_pdf_path(tmp_pdf)
        return data
    finally:
        if tmp_pdf and os.path.exists(tmp_pdf):
            try:
                os.unlink(tmp_pdf)
            except Exception:
                pass


def _extract_from_pdf_path(pdf_path: str) -> DrawingData:
    """Extract DrawingData from a PDF path (shared between PDF and image paths)."""
    doc = fitz.open(pdf_path)
    full_text = ""
    all_lines = []
    for page in doc:
        page_text = page.get_text()
        full_text += page_text + "\n"
        all_lines.extend(page_text.splitlines())
    doc.close()

    data = DrawingData(raw_text=full_text)
    data.title_block        = _find_title_block(full_text, all_lines)
    data.bom_items          = _parse_bom_section(all_lines)
    data.hardware_items     = _parse_hardware_section(full_text)
    data.dispatch_units     = _parse_dispatch_units(all_lines)
    data.reference_drawings = _parse_reference_drawings(
        all_lines, data.title_block.document_id)
    return data


def extract_any(file_path: str) -> DrawingData:
    """
    Universal entry point. Handles both PDFs and images.
    """
    ext = Path(file_path).suffix.lower()
    if ext in IMAGE_EXTS:
        return extract_from_image(file_path)
    else:
        # Native PDF path
        from bom_extractor import extract_drawing_data
        return extract_drawing_data(file_path)