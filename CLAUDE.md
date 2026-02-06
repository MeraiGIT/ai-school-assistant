# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AI School Assistant — a Russian-speaking teaching assistant for a generative AI course. Operates as a Telegram userbot (Telethon, not Bot API) with a LangGraph agent that uses RAG over course materials stored in Supabase pgvector. Admin panel built with Next.js.

## Commands

### Backend
```bash
cd backend
source venv/bin/activate
python main.py                          # Starts FastAPI (port 8000) + Telegram userbot
uvicorn api:app --port 8000 --reload    # API-only mode (no Telegram)
python telegram/export_session.py       # Export Telegram StringSession for deployment
```

### Frontend
```bash
cd frontend
npm run dev       # Dev server on port 3000
npm run build     # Production build
```

### Verify imports
```bash
cd backend && source venv/bin/activate
python -c "from api import app; from agent.teaching_agent import TeachingAgentRunner; print('OK')"
```

## Architecture

```
Student (Telegram DM)
    │
    ▼
SchoolUserbot (Telethon)  ──────────────────────────────────────┐
    │  rate limiter, semaphore(1), human delays                 │
    ▼                                                           │
handle_student_message (main.py)                                │
    │  DB lookup, save message, get history                     │
    ▼                                                           │
TeachingAgentRunner.respond()                                   │
    │                                                           │
    ▼                                                           │
LangGraph StateGraph                                            │
    classify_node ──┬── greeting_node ──► END                   │
                    ├── escalate_node ──► END                   │
                    └── retrieve_node ──► answer_node ──┬► END  │
                          (RAG)              (Claude)   │       │
                                                        └► practice_node ► END
                                                                │
Admin (Next.js :3000) ──► FastAPI (:8000) ──► Supabase ◄───────┘
```

### Key data flow
- **Incoming DM**: userbot → semaphore gate → read delay → read ack → think delay → agent pipeline → rate limiter → typing sim → split & send
- **Document upload**: file → chunk (1000 chars, 200 overlap) → OpenAI embed (text-embedding-3-small, 1536d) → store in `sc_chunks`
- **RAG search**: query → embed → `sc_match_chunks` RPC (cosine similarity > 0.7) → top-5 chunks → context string

### LangGraph state
`TeachingState` (TypedDict): student_id, question, chat_history, intent, retrieved_docs, answer, student_level, needs_human. **Node names must use `*_node` suffix** — LangGraph forbids node names that match state key names.

## Supabase

Project ID: `wzbdcjlpjvclismncjtq` (shared with other projects). All tables prefixed with `sc_` to avoid conflicts. pgvector extension already installed.

Tables: `sc_documents`, `sc_chunks` (HNSW index), `sc_students`, `sc_conversations`. RPC: `sc_match_chunks()`.

**Never touch non-`sc_` tables** — they belong to other projects (copy-trading-bot, influencer-analytics, etc.).

## Telegram Userbot Safety

The userbot has layered anti-detection safeguards — do not bypass them:
- `flood_sleep_threshold=60` on TelegramClient
- `asyncio.Semaphore(1)` — max 1 message processed concurrently
- `MessageRateLimiter` — 8/min, 40/hour, 200/day outbound message caps
- `split_long_message()` — splits >2000 char responses with 3-8s inter-part delays
- Greeting queue — sequential processing with 30-120s gaps between students
- Device spoofing: Desktop / Windows 10 / v4.16.8 / lang=ru
- All delays are randomized (never fixed intervals)

## Important Constraints

- **Python 3.14**: tiktoken doesn't build. Pydantic V1 warnings are harmless — ignore them.
- **All student communication must be in Russian only**. System prompts in `nodes.py` enforce this.
- **LLMs**: Claude (Anthropic) for teaching responses, OpenAI for embeddings only.
- **Config**: Never use `os.getenv` directly — always use `get_config()` from `config.py`.
- **Frontend API base**: `http://localhost:8000` (configurable via `NEXT_PUBLIC_API_URL`).
