# -*- coding: utf-8 -*-
"""
Módulo de OCR para PDFs escaneados — fallback quando pypdf não consegue extrair texto.

Depende de:
  - pytesseract   (pip install pytesseract)
  - pdf2image     (pip install pdf2image)
  - Pillow        (pip install Pillow)
  - Tesseract-OCR (binário do sistema — https://github.com/UB-Mannheim/tesseract/wiki)

Se qualquer dependência estiver ausente, is_ocr_available() retorna False
e a extração falha silenciosamente (sem exception).
"""

from __future__ import annotations

import os
from typing import Optional

from core.error_monitor import log_exception, log_event


# ---------------------------------------------------------------------------
# Verificação de disponibilidade
# ---------------------------------------------------------------------------

def is_ocr_available() -> bool:
    """Retorna True somente se pytesseract, pdf2image e Tesseract estão prontos."""
    try:
        import pytesseract
        import pdf2image  # noqa: F401
        from PIL import Image  # noqa: F401
        # Verifica se o binário Tesseract está acessível
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def get_ocr_hint() -> str:
    """Retorna mensagem de diagnóstico quando OCR não está disponível."""
    try:
        import pytesseract
        import pdf2image  # noqa: F401
        pytesseract.get_tesseract_version()
        return "OCR disponível."
    except ImportError as ex:
        return f"Biblioteca Python ausente: {ex} — instale com: pip install pytesseract pdf2image Pillow"
    except Exception as ex:
        return (
            f"Tesseract não encontrado: {ex}\n"
            "Instale o Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki"
        )


# ---------------------------------------------------------------------------
# Extração com OCR
# ---------------------------------------------------------------------------

def extract_text_with_ocr(
    pdf_path: str,
    max_pages: int = 20,
    lang: str = "por+eng",
    dpi: int = 200,
) -> str:
    """
    Converte cada página do PDF em imagem e aplica OCR via Tesseract.

    Args:
        pdf_path:  Caminho absoluto para o arquivo PDF.
        max_pages: Limite de páginas a processar (para performance).
        lang:      Idiomas Tesseract (ex: "por", "eng", "por+eng").
        dpi:       Resolução das imagens geradas (180-300 é bom equilíbrio).

    Returns:
        Texto extraído (concatenado de todas as páginas) ou "" em caso de falha.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return ""

    try:
        import pytesseract
        from pdf2image import convert_from_path
        from pdf2image.exceptions import PDFInfoNotInstalledError
    except ImportError as ex:
        log_exception(ex, "pdf_ocr.extract_text_with_ocr.import")
        return ""

    try:
        # Converte as primeiras max_pages páginas em imagens
        try:
            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=1,
                last_page=max_pages,
                fmt="jpeg",
                thread_count=2,
            )
        except PDFInfoNotInstalledError:
            # poppler não instalado — tenta sem thread_count
            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=1,
                last_page=max_pages,
                fmt="jpeg",
            )

        if not images:
            return ""

        pages_text: list[str] = []
        ocr_config = "--oem 3 --psm 6"  # modo de layout padrão

        for i, img in enumerate(images):
            try:
                page_text = pytesseract.image_to_string(
                    img,
                    lang=lang,
                    config=ocr_config,
                )
                stripped = (page_text or "").strip()
                if stripped:
                    pages_text.append(stripped)
            except Exception as ex_page:
                log_exception(ex_page, f"pdf_ocr.extract_text_with_ocr.page_{i + 1}")
                continue

        result = "\n\n".join(pages_text)
        total_chars = len(result)
        log_event(
            "ocr_extraction",
            f"pages={len(images)} extracted_pages={len(pages_text)} chars={total_chars} path={os.path.basename(pdf_path)}",
        )
        # Limite de 24.000 chars (compatível com o limite do file_helpers)
        return result[:24000]

    except Exception as ex:
        log_exception(ex, "pdf_ocr.extract_text_with_ocr")
        return ""


# ---------------------------------------------------------------------------
# Wrapper conveniente (pypdf + OCR fallback)
# ---------------------------------------------------------------------------

def read_pdf_with_ocr_fallback(
    pdf_path: str,
    max_pages_pypdf: int = 20,
    max_pages_ocr: int = 20,
    ocr_lang: str = "por+eng",
    ocr_dpi: int = 200,
) -> str:
    """
    Tenta extrair texto via pypdf. Se o resultado for vazio/insuficiente,
    usa OCR como fallback automático.

    Returns:
        Texto extraído ou "" se ambas as tentativas falharem.
    """
    # 1. Tentativa via pypdf
    pypdf_text = ""
    try:
        from pypdf import PdfReader
        with open(pdf_path, "rb") as fh:
            reader = PdfReader(fh, strict=False)
            try:
                if bool(getattr(reader, "is_encrypted", False)):
                    reader.decrypt("")
            except Exception:
                pass
            pages: list[str] = []
            for page_obj in reader.pages[:max_pages_pypdf]:
                try:
                    pages.append((page_obj.extract_text() or "").strip())
                except Exception:
                    continue
            pypdf_text = "\n".join([p for p in pages if p])[:24000]
    except Exception as ex:
        log_exception(ex, "pdf_ocr.read_pdf_with_ocr_fallback.pypdf")

    if pypdf_text.strip():
        return pypdf_text

    # 2. Fallback OCR — apenas se disponível
    if is_ocr_available():
        log_event("ocr_fallback_triggered", os.path.basename(pdf_path))
        return extract_text_with_ocr(
            pdf_path,
            max_pages=max_pages_ocr,
            lang=ocr_lang,
            dpi=ocr_dpi,
        )

    return ""
