"""Fixed-size and paragraph-aware chunking with stable IDs."""
import hashlib
import re
from .models import Chunk, DocumentPage

def _chunk(page, kind, number, text):
    identifier=f'{page.document_id}:{page.page}:{kind}:{number}'
    return Chunk(hashlib.sha256(identifier.encode()).hexdigest()[:24],page.document_id,page.source,page.page,text,dict(page.metadata))

def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError('Require size > overlap >= 0')
    result=[]
    for i,start in enumerate(range(0,len(page.text),size-overlap)):
        part=page.text[start:start+size]
        if part.strip(): result.append(_chunk(page,'fixed',i,part))
        if start+size>=len(page.text): break
    return result

def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    if max_size<=0: raise ValueError('max_size must be positive')
    paragraphs=[p.strip() for p in re.split(r'\n\s*\n',page.text) if p.strip()]
    parts=[]; current=''
    for paragraph in paragraphs:
        if len(paragraph)>max_size:
            if current: parts.append(current);current=''
            # Preserve content exactly while splitting long paragraphs.
            for start in range(0,len(paragraph),max_size):
                parts.append(paragraph[start:start+max_size])
        elif not current: current=paragraph
        elif len(current)+2+len(paragraph)<=max_size: current+='\n\n'+paragraph
        else: parts.append(current);current=paragraph
    if current:parts.append(current)
    return [_chunk(page,'paragraph',i,text) for i,text in enumerate(parts)]
