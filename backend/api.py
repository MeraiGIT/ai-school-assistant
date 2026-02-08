"""FastAPI routes for AI School Assistant admin panel."""

import asyncio
import logging
import os
import shutil
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_config
from database import (
    get_db,
    list_documents,
    delete_document,
    list_students,
    get_student_by_username,
    insert_student,
    update_student,
    delete_student,
    get_conversation_history,
    get_stats,
    save_message,
)
from rag.document_processor import process_document

logger = logging.getLogger(__name__)

app = FastAPI(title="AI School Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3700",
        "http://localhost:3800",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Will be set by main.py after startup
_userbot = None
_memory_manager = None
_db = None
_config = None


def get_database():
    global _db, _config
    if _db is None:
        _config = get_config()
        _db = get_db(_config.SUPABASE_URL, _config.SUPABASE_ANON_KEY)
    return _db


def set_userbot(userbot):
    global _userbot
    _userbot = userbot


def set_memory_manager(manager):
    global _memory_manager
    _memory_manager = manager


# --- Documents ---


@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    module: str = Form("general"),
):
    allowed_ext = {".pdf", ".docx", ".txt"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"Unsupported file type: {ext}. Use .pdf, .docx, or .txt")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        config = get_config()
        db = get_database()
        result = await process_document(
            file_path=file_path,
            openai_api_key=config.OPENAI_API_KEY,
            db=db,
            title=title or file.filename,
            module=module,
        )
        return result

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(500, f"Processing failed: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@app.get("/api/documents")
async def get_documents():
    db = get_database()
    return await list_documents(db)


@app.delete("/api/documents/{doc_id}")
async def remove_document(doc_id: str):
    db = get_database()
    await delete_document(db, doc_id)
    return {"status": "deleted"}


# --- Students ---


class StudentCreate(BaseModel):
    telegram_username: str
    display_name: Optional[str] = None


class StudentUpdate(BaseModel):
    level: Optional[str] = None
    status: Optional[str] = None
    display_name: Optional[str] = None


@app.get("/api/students")
async def get_students():
    db = get_database()
    return await list_students(db)


@app.post("/api/students")
async def add_student(data: StudentCreate):
    db = get_database()
    username = data.telegram_username.lstrip("@")

    existing = await get_student_by_username(db, username)
    if existing:
        raise HTTPException(400, f"Student @{username} already exists")

    student = await insert_student(db, username, data.display_name)

    # Initialize Letta memory for this student (if enabled)
    if _memory_manager:
        await _memory_manager.ensure_student(student["id"])

    # Save welcome message to conversation history (must match what Telegram sends)
    welcome_msg = (
        "Здравствуйте! Я Павел, буду помогать Вам разобраться "
        "в курсе по генеративному AI)"
    )
    await save_message(db, student["id"], "assistant", welcome_msg, intent="greeting")

    # Send Telegram greeting in background (has 30-120s anti-detection delay)
    if _userbot:
        async def _greet_in_background(student_id: str, uname: str):
            try:
                telegram_id = await _userbot.send_greeting(uname)
                if telegram_id:
                    await update_student(db, student_id, {
                        "telegram_id": telegram_id,
                        "status": "active",
                    })
                    _userbot.register_student_id(telegram_id)
                    logger.info(f"Greeting sent to @{uname} (telegram_id={telegram_id})")
            except Exception as e:
                logger.error(f"Failed to greet @{uname}: {e}")

        asyncio.create_task(_greet_in_background(student["id"], username))

    return student


@app.patch("/api/students/{student_id}")
async def modify_student(student_id: str, data: StudentUpdate):
    db = get_database()
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No updates provided")
    await update_student(db, student_id, updates)
    return {"status": "updated"}


@app.delete("/api/students/{student_id}")
async def remove_student(student_id: str):
    db = get_database()
    await delete_student(db, student_id)
    return {"status": "deleted"}


# --- Conversations ---


@app.get("/api/conversations/{student_id}")
async def get_conversations(student_id: str, limit: int = 50):
    db = get_database()
    return await get_conversation_history(db, student_id, limit)


# --- Stats ---


@app.get("/api/stats")
async def get_dashboard_stats():
    db = get_database()
    return await get_stats(db)
