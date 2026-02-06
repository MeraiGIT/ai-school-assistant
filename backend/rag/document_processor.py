"""Document processing: load, chunk, embed, and store course materials."""

import logging
import os
from typing import Optional

from openai import OpenAI
from PyPDF2 import PdfReader
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def _read_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    return "\n\n".join(text_parts)


def _read_docx(file_path: str) -> str:
    doc = DocxDocument(file_path)
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _read_txt(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_document(file_path: str) -> str:
    """Load document content from PDF, DOCX, or TXT file."""
    ext = os.path.splitext(file_path)[1].lower()
    loaders = {
        '.pdf': _read_pdf,
        '.docx': _read_docx,
        '.txt': _read_txt,
    }
    loader = loaders.get(ext)
    if not loader:
        raise ValueError(f"Unsupported file type: {ext}. Use .pdf, .docx, or .txt")
    text = loader(file_path)
    logger.info(f"Loaded {ext} document: {len(text)} characters")
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks using sentence-aware splitting."""
    if len(text) <= chunk_size:
        return [text]

    separators = ["\n\n", "\n", ". ", " "]
    chunks = []

    def _split_recursive(text: str, seps: list[str]) -> list[str]:
        if not seps:
            # No more separators; split by chunk_size
            result = []
            for i in range(0, len(text), chunk_size - overlap):
                result.append(text[i:i + chunk_size])
            return result

        sep = seps[0]
        parts = text.split(sep)

        current_chunk = ""
        result = []

        for part in parts:
            candidate = current_chunk + sep + part if current_chunk else part
            if len(candidate) <= chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    result.append(current_chunk)
                if len(part) > chunk_size:
                    result.extend(_split_recursive(part, seps[1:]))
                    current_chunk = ""
                else:
                    current_chunk = part

        if current_chunk:
            result.append(current_chunk)

        return result

    raw_chunks = _split_recursive(text, separators)

    # Add overlap between chunks
    for i, chunk in enumerate(raw_chunks):
        if i > 0 and overlap > 0:
            prev_end = raw_chunks[i - 1][-overlap:]
            chunk = prev_end + chunk
        chunks.append(chunk.strip())

    chunks = [c for c in chunks if len(c) > 50]
    logger.info(f"Split into {len(chunks)} chunks (size={chunk_size}, overlap={overlap})")
    return chunks


def generate_embeddings(texts: list[str], api_key: str) -> list[list[float]]:
    """Generate embeddings for a list of texts using OpenAI."""
    client = OpenAI(api_key=api_key)
    embeddings = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        for item in response.data:
            embeddings.append(item.embedding)
        logger.info(f"Embedded batch {i // batch_size + 1} ({len(batch)} texts)")

    return embeddings


async def process_document(
    file_path: str,
    openai_api_key: str,
    db,
    title: Optional[str] = None,
    module: str = 'general',
) -> dict:
    """Full pipeline: load -> chunk -> embed -> store in Supabase."""
    from database import insert_document, insert_chunks, update_document_chunk_count

    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lstrip('.')

    # Load and chunk
    text = load_document(file_path)
    chunks = chunk_text(text)

    # Create document record
    doc = await insert_document(db, filename, ext, title or filename, module)
    doc_id = doc['id']

    # Generate embeddings
    embeddings = generate_embeddings(chunks, openai_api_key)

    # Prepare chunk records
    chunk_records = []
    for i, (chunk_text_item, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_records.append({
            'document_id': doc_id,
            'content': chunk_text_item,
            'chunk_index': i,
            'metadata': {'module': module, 'filename': filename},
            'embedding': embedding,
        })

    # Store in Supabase
    await insert_chunks(db, chunk_records)
    await update_document_chunk_count(db, doc_id, len(chunks))

    logger.info(f"Processed '{filename}': {len(chunks)} chunks stored")
    return {'document_id': doc_id, 'chunks': len(chunks), 'filename': filename}
