# AI School Assistant

Russian-speaking AI teaching assistant for a generative AI course. Operates as a Telegram userbot with RAG-powered answers from uploaded course materials.

## How It Works

1. **Admin uploads course materials** (PDF, DOCX, TXT) via the web UI
2. Documents are chunked, embedded (OpenAI), and stored in Supabase pgvector
3. **Admin adds students** by their Telegram @username
4. The userbot sends them a greeting and starts listening for DMs
5. **Students ask questions** in Russian via Telegram
6. The LangGraph agent classifies intent, retrieves relevant course material via RAG, and generates a teaching response using Claude

## Architecture

```
┌──────────────────┐      ┌───────────────────────┐      ┌──────────────┐
│   Next.js Admin  │─────▶│   FastAPI Backend      │─────▶│   Supabase   │
│   (port 3000)    │      │   (port 8000)          │      │  (pgvector)  │
└──────────────────┘      │                         │      └──────────────┘
                          │  ┌───────────────────┐  │
                          │  │ Telegram Userbot   │  │
                          │  │ (Telethon)         │  │
                          │  └───────────────────┘  │
                          │  ┌───────────────────┐  │
                          │  │ LangGraph Agent    │──┼──── Claude (Anthropic)
                          │  │ classify→retrieve  │  │
                          │  │ →answer→practice   │  │
                          │  └───────────────────┘  │
                          └───────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.14, FastAPI, Telethon |
| Agent | LangGraph + Claude (Anthropic) |
| Embeddings | OpenAI text-embedding-3-small (1536d) |
| Vector DB | Supabase pgvector with HNSW index |
| Frontend | Next.js 16, TypeScript, Tailwind CSS |
| Document parsing | PyPDF2, python-docx |

## Setup

### 1. Environment

```bash
cp .env.example .env
# Fill in your keys (see .env.example for descriptions)
```

Required keys:
- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE` — from [my.telegram.org](https://my.telegram.org)
- `SUPABASE_URL`, `SUPABASE_ANON_KEY` — from your Supabase dashboard
- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
- `OPENAI_API_KEY` — from [platform.openai.com](https://platform.openai.com)

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Telegram Session

```bash
cd backend
source venv/bin/activate
python telegram/export_session.py
# Follow prompts, then copy the session string to .env as TELEGRAM_SESSION
```

### 4. Frontend

```bash
cd frontend
npm install
```

### 5. Run

Terminal 1 — Backend:
```bash
cd backend
source venv/bin/activate
python main.py
```

Terminal 2 — Frontend:
```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) for the admin panel.

## Admin Panel

| Page | Purpose |
|------|---------|
| `/` | Dashboard — document, student, and message counts |
| `/upload` | Upload course materials (PDF/DOCX/TXT), view/delete documents |
| `/students` | Add students by @username, manage level/status, view conversations |

## Agent Flow

```
Student message
    │
    ▼
classify_node ──► intent: question, clarification, practice, stuck, off_topic, greeting
    │
    ├── greeting/off_topic ──► greeting_node ──► static Russian greeting
    ├── stuck ──► escalate_node ──► offers to connect with teacher
    └── question/clarification/practice ──► retrieve_node (RAG search)
                                                │
                                                ▼
                                          answer_node (Claude generates Russian response)
                                                │
                                                ├── if practice ──► practice_node ──► exercise appended
                                                └── else ──► END
```

## Userbot Safety

The Telegram userbot includes anti-detection safeguards to avoid account restrictions:

- **Rate limiting**: 8 messages/min, 40/hour, 200/day
- **Concurrency control**: Only 1 message processed at a time (semaphore)
- **Human-like delays**: Random read (2-6s), thinking (3-8s), and typing (1.5-25s) delays
- **Message splitting**: Long responses split at 2000 chars with inter-part delays
- **Device spoofing**: Desktop / Windows 10 / Russian locale
- **Flood protection**: Auto-sleep on FloodWaitError, max 3 retries
- **Greeting queue**: New student greetings processed sequentially with 30-120s gaps

## Database

Uses Supabase with pgvector extension. All tables prefixed with `sc_`:

- `sc_documents` — uploaded file metadata
- `sc_chunks` — document chunks with vector embeddings (HNSW index)
- `sc_students` — registered students with Telegram info and level
- `sc_conversations` — full message history (student + assistant)

Vector search via `sc_match_chunks()` RPC function (cosine similarity).

## Testing

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for a step-by-step guide covering database verification, RAG pipeline, agent responses, API endpoints, Telegram session setup, and end-to-end integration testing.
