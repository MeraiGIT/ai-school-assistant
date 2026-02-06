"""Supabase database client for AI School Assistant."""

import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

_client: Optional[Client] = None


def get_db(url: str, key: str) -> Client:
    """Get or create Supabase client singleton."""
    global _client
    if _client is None:
        _client = create_client(url, key)
        logger.info("Supabase client initialized")
    return _client


# --- Documents ---

async def insert_document(db: Client, filename: str, file_type: str, title: str, module: str = 'general') -> dict:
    result = db.table('sc_documents').insert({
        'filename': filename,
        'file_type': file_type,
        'title': title or filename,
        'module': module,
    }).execute()
    return result.data[0]


async def update_document_chunk_count(db: Client, doc_id: str, count: int):
    db.table('sc_documents').update({'chunk_count': count}).eq('id', doc_id).execute()


async def list_documents(db: Client) -> list:
    result = db.table('sc_documents').select('*').order('uploaded_at', desc=True).execute()
    return result.data


async def delete_document(db: Client, doc_id: str):
    db.table('sc_documents').delete().eq('id', doc_id).execute()


# --- Chunks ---

async def insert_chunks(db: Client, chunks: list[dict]):
    """Insert document chunks in batches."""
    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        db.table('sc_chunks').insert(batch).execute()
    logger.info(f"Inserted {len(chunks)} chunks")


async def search_chunks(db: Client, query_embedding: list[float], match_count: int = 5, threshold: float = 0.2) -> list:
    result = db.rpc('sc_match_chunks', {
        'query_embedding': query_embedding,
        'match_threshold': threshold,
        'match_count': match_count,
    }).execute()
    return result.data


# --- Students ---

async def list_students(db: Client) -> list:
    result = db.table('sc_students').select('*').order('created_at', desc=True).execute()
    return result.data


async def get_student_by_username(db: Client, username: str) -> Optional[dict]:
    result = db.table('sc_students').select('*').eq('telegram_username', username).execute()
    return result.data[0] if result.data else None


async def get_student_by_telegram_id(db: Client, telegram_id: int) -> Optional[dict]:
    result = db.table('sc_students').select('*').eq('telegram_id', telegram_id).execute()
    return result.data[0] if result.data else None


async def insert_student(db: Client, username: str, display_name: str = None) -> dict:
    data = {'telegram_username': username.lstrip('@')}
    if display_name:
        data['display_name'] = display_name
    result = db.table('sc_students').insert(data).execute()
    return result.data[0]


async def update_student(db: Client, student_id: str, updates: dict):
    db.table('sc_students').update(updates).eq('id', student_id).execute()


async def delete_student(db: Client, student_id: str):
    db.table('sc_students').delete().eq('id', student_id).execute()


# --- Conversations ---

async def save_message(db: Client, student_id: str, role: str, content: str, intent: str = None):
    db.table('sc_conversations').insert({
        'student_id': student_id,
        'role': role,
        'content': content,
        'intent': intent,
    }).execute()


async def get_conversation_history(db: Client, student_id: str, limit: int = 20) -> list:
    result = (
        db.table('sc_conversations')
        .select('*')
        .eq('student_id', student_id)
        .order('created_at', desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed(result.data))


# --- Stats ---

async def get_stats(db: Client) -> dict:
    docs = db.table('sc_documents').select('id', count='exact').execute()
    students = db.table('sc_students').select('id', count='exact').execute()
    messages = db.table('sc_conversations').select('id', count='exact').execute()
    return {
        'documents_count': docs.count or 0,
        'students_count': students.count or 0,
        'messages_count': messages.count or 0,
    }
