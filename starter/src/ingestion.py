"""PDF extraction preserving physical page identifiers."""
import logging
import re
import unicodedata
from pathlib import Path
from .models import DocumentPage

logger = logging.getLogger(__name__)

def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFC', text.replace('\r\n','\n').replace('\r','\n'))
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    import fitz
    pages=[]
    with fitz.open(path) as pdf:
        for index, page in enumerate(pdf):
            try:
                content=normalize_text(page.get_text('text', sort=True))
            except Exception:
                logger.exception('Extraction error: %s page %s',path,index+1)
                continue
            if not content:
                logger.warning('Empty/scanned page: %s page %s',path,index+1)
            pages.append(DocumentPage(document_id,source,index+1,content))
    return pages
