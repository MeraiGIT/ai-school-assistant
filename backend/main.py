"""Entry point: starts FastAPI server and Telegram userbot."""

import asyncio
import logging
import signal
import sys

import uvicorn

from config import get_config, Config, ConfigurationError
from database import (
    get_db,
    get_student_by_username,
    get_student_by_telegram_id,
    update_student,
    save_message,
    get_conversation_history,
    list_students,
)
from agent.teaching_agent import TeachingAgentRunner
from rag.knowledge_base import KnowledgeBase
from telegram.userbot import SchoolUserbot
from api import app, set_userbot, get_database

logger = logging.getLogger(__name__)


async def handle_student_message(
    telegram_id: int,
    username: str,
    text: str,
    agent_runner: TeachingAgentRunner,
    db,
) -> str:
    """Process an incoming student message through the teaching agent."""
    # Find student in DB
    student = await get_student_by_telegram_id(db, telegram_id)
    if not student and username:
        student = await get_student_by_username(db, username)
        if student and not student.get("telegram_id"):
            await update_student(db, student["id"], {
                "telegram_id": telegram_id,
                "status": "active",
            })

    if not student:
        return ""

    # Don't respond to paused students
    if student.get("status") == "paused":
        logger.info(f"Ignoring message from paused student {student['id']}")
        return ""

    student_id = student["id"]
    level = student.get("level", "beginner")

    # Save incoming message
    await save_message(db, student_id, "student", text)

    # Get chat history
    history = await get_conversation_history(db, student_id, limit=10)
    chat_history = [{"role": m["role"], "content": m["content"]} for m in history]

    # Get teaching response
    response = await agent_runner.respond(
        student_id=student_id,
        question=text,
        chat_history=chat_history,
        student_level=level,
    )

    # Save assistant response
    await save_message(db, student_id, "assistant", response)

    # Update last active
    await update_student(db, student_id, {"last_active_at": "now()"})

    return response


async def start_userbot(config, db, agent_runner: TeachingAgentRunner) -> SchoolUserbot:
    """Initialize and start the Telegram userbot."""
    userbot = SchoolUserbot(
        api_id=config.TELEGRAM_API_ID,
        api_hash=config.TELEGRAM_API_HASH,
        phone=config.TELEGRAM_PHONE,
        session_name=config.SESSION_NAME,
        session_string=config.TELEGRAM_SESSION,
        password=config.TELEGRAM_2FA_PASSWORD,
        device_model=config.DEVICE_MODEL,
        system_version=config.SYSTEM_VERSION,
        app_version=config.APP_VERSION,
        lang_code=config.LANG_CODE,
        system_lang_code=config.SYSTEM_LANG_CODE,
    )

    # Register message handler
    async def on_message(telegram_id: int, username: str, text: str) -> str:
        return await handle_student_message(telegram_id, username, text, agent_runner, db)

    userbot.on_student_message(on_message)

    # Load known student IDs
    students = await list_students(db)
    for s in students:
        if s.get("telegram_id"):
            userbot.register_student_id(s["telegram_id"])
    logger.info(f"Registered {len(students)} students")

    await userbot.start()
    return userbot


async def main():
    config = get_config()

    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info(f"Starting AI School Assistant")
    logger.info(f"Config: {config}")

    # Initialize services
    db = get_db(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
    knowledge_base = KnowledgeBase(db, config.OPENAI_API_KEY)
    agent_runner = TeachingAgentRunner(config.ANTHROPIC_API_KEY, knowledge_base)

    # Start userbot (only if Telegram vars are configured)
    userbot = None
    try:
        Config.validate_telegram()
        userbot = await start_userbot(config, db, agent_runner)
        set_userbot(userbot)
        logger.info("Telegram userbot started")
    except ConfigurationError as e:
        logger.warning(f"Telegram not configured: {e}")
    except Exception as e:
        logger.warning(f"Userbot failed to start: {e}. Running API-only mode.")

    # Start FastAPI in background
    uvicorn_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=config.FASTAPI_PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
    server = uvicorn.Server(uvicorn_config)

    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    # Run server and userbot concurrently
    tasks = [asyncio.create_task(server.serve())]
    if userbot:
        tasks.append(asyncio.create_task(userbot.run_forever()))

    # Wait for shutdown signal or any task to complete
    done, pending = await asyncio.wait(
        [*tasks, asyncio.create_task(shutdown_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cleanup
    logger.info("Shutting down...")
    if userbot:
        await userbot.stop()
    server.should_exit = True

    for task in pending:
        task.cancel()

    logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
