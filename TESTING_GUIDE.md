# AI School Assistant - Testing Guide

Step-by-step guide to test every component of the system.

---

## Prerequisites

1. Copy `.env.example` to `.env` and fill in your real values:
   ```bash
   cp .env.example .env
   ```

2. Required keys:
   - `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from https://my.telegram.org
   - `TELEGRAM_PHONE` - your phone number with country code
   - `SUPABASE_URL` and `SUPABASE_ANON_KEY` from your Supabase dashboard
   - `ANTHROPIC_API_KEY` from https://console.anthropic.com
   - `OPENAI_API_KEY` from https://platform.openai.com (for embeddings only)

3. Activate the Python venv:
   ```bash
   cd backend
   source venv/bin/activate
   ```

---

## Phase 1: Database Verification

Confirm the `sc_` tables exist and are writable.

```bash
cd backend
source venv/bin/activate
python -c "
import asyncio
from config import get_config
from database import get_db, get_stats

async def test():
    config = get_config()
    db = get_db(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
    stats = await get_stats(db)
    print('Database connected!')
    print(f'  Documents: {stats[\"documents_count\"]}')
    print(f'  Students: {stats[\"students_count\"]}')
    print(f'  Messages: {stats[\"messages_count\"]}')

asyncio.run(test())
"
```

**Expected:** Prints counts (all 0 for a fresh setup). No errors.

---

## Phase 2: Document Upload & RAG Pipeline

### 2a. Create a test document

```bash
cat > /tmp/test_course_material.txt << 'EOF'
Генеративный AI - Модуль 1: Введение

Генеративный искусственный интеллект (Generative AI) — это класс моделей машинного обучения,
способных создавать новый контент: текст, изображения, код, музыку и видео.

Ключевые концепции:
1. Большие языковые модели (LLM) — нейронные сети с миллиардами параметров,
   обученные на огромных объёмах текстовых данных.
2. Трансформеры — архитектура, лежащая в основе современных LLM (GPT, Claude, Gemini).
3. Токенизация — процесс разбиения текста на минимальные единицы (токены).
4. Промпт-инжиниринг — искусство составления запросов к LLM для получения нужного результата.

RAG (Retrieval-Augmented Generation):
RAG — это метод, при котором модель сначала ищет релевантную информацию в базе знаний,
а затем генерирует ответ на основе найденного контекста. Это позволяет модели давать
актуальные и точные ответы, не ограничиваясь только обучающими данными.

Применение генеративного AI:
- Чат-боты и виртуальные ассистенты
- Генерация кода (GitHub Copilot, Cursor)
- Создание изображений (DALL-E, Midjourney, Stable Diffusion)
- Суммаризация и анализ документов
- Перевод и локализация
EOF

echo "Test file created at /tmp/test_course_material.txt"
```

### 2b. Test document processing (chunking + embedding + storage)

```bash
python -c "
import asyncio
from config import get_config
from database import get_db
from rag.document_processor import process_document

async def test():
    config = get_config()
    db = get_db(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

    result = await process_document(
        file_path='/tmp/test_course_material.txt',
        openai_api_key=config.OPENAI_API_KEY,
        db=db,
        title='Модуль 1: Введение в GenAI',
        module='intro',
    )
    print(f'Document processed!')
    print(f'  Document ID: {result[\"document_id\"]}')
    print(f'  Chunks stored: {result[\"chunks\"]}')
    print(f'  Filename: {result[\"filename\"]}')

asyncio.run(test())
"
```

**Expected:** Prints document ID and chunk count (likely 1-3 chunks for this small file).

### 2c. Test RAG search

```bash
python -c "
import asyncio
from config import get_config
from database import get_db
from rag.knowledge_base import KnowledgeBase

async def test():
    config = get_config()
    db = get_db(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
    kb = KnowledgeBase(db, config.OPENAI_API_KEY)

    # Test search
    results = await kb.search('Что такое RAG?')
    print(f'Search returned {len(results)} results:')
    for r in results:
        print(f'  Similarity: {r[\"similarity\"]:.3f} | Content: {r[\"content\"][:80]}...')

    # Test context formatting
    context = await kb.get_context('Что такое трансформеры?')
    print(f'\nFormatted context ({len(context)} chars):')
    print(context[:300] + '...')

asyncio.run(test())
"
```

**Expected:** Returns chunks with similarity scores > 0.7. The RAG question about "RAG" should match the test document.

---

## Phase 3: LangGraph Teaching Agent

### 3a. Test the full agent pipeline (requires Anthropic key)

```bash
python -c "
import asyncio
from config import get_config
from database import get_db
from rag.knowledge_base import KnowledgeBase
from agent.teaching_agent import TeachingAgentRunner

async def test():
    config = get_config()
    db = get_db(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
    kb = KnowledgeBase(db, config.OPENAI_API_KEY)
    agent = TeachingAgentRunner(config.ANTHROPIC_API_KEY, kb)

    # Test 1: Course question (should trigger: classify -> retrieve -> answer)
    print('=== Test 1: Course question ===')
    response = await agent.respond(
        student_id='test-student',
        question='Что такое RAG и как он работает?',
        student_level='beginner',
    )
    print(f'Response ({len(response)} chars):')
    print(response[:500])
    print()

    # Test 2: Greeting (should trigger: classify -> greeting)
    print('=== Test 2: Greeting ===')
    response = await agent.respond(
        student_id='test-student',
        question='Привет!',
        student_level='beginner',
    )
    print(f'Response: {response}')
    print()

    # Test 3: Practice request (should trigger: classify -> retrieve -> answer -> practice)
    print('=== Test 3: Practice request ===')
    response = await agent.respond(
        student_id='test-student',
        question='Дай мне практическое задание по промпт-инжинирингу',
        student_level='intermediate',
    )
    print(f'Response ({len(response)} chars):')
    print(response[:500])

asyncio.run(test())
"
```

**Expected:**
- Test 1: A detailed Russian answer about RAG using content from the uploaded document
- Test 2: A greeting response in Russian
- Test 3: A teaching answer followed by a practice exercise (separated by `---`)

---

## Phase 4: FastAPI Backend

### 4a. Start the API server (without Telegram userbot)

For API-only testing, you can temporarily modify main.py or just start uvicorn directly:

```bash
cd backend
source venv/bin/activate
uvicorn api:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
echo "API started with PID $API_PID"
```

### 4b. Test API endpoints with curl

```bash
# Stats
curl -s http://localhost:8000/api/stats | python -m json.tool

# List documents
curl -s http://localhost:8000/api/documents | python -m json.tool

# Upload a document
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@/tmp/test_course_material.txt" \
  -F "title=Test Upload via API" \
  -F "module=intro" | python -m json.tool

# Add a student
curl -X POST http://localhost:8000/api/students \
  -H "Content-Type: application/json" \
  -d '{"telegram_username": "test_student_123"}' | python -m json.tool

# List students
curl -s http://localhost:8000/api/students | python -m json.tool

# Update student level
# Replace STUDENT_ID with the actual ID from the response above
curl -X PATCH http://localhost:8000/api/students/STUDENT_ID \
  -H "Content-Type: application/json" \
  -d '{"level": "intermediate"}' | python -m json.tool

# Delete test student
curl -X DELETE http://localhost:8000/api/students/STUDENT_ID | python -m json.tool

# Stop the API server
kill $API_PID
```

**Expected:** All endpoints return valid JSON. Upload creates chunks. Student CRUD works.

---

## Phase 5: Telegram Session Export

### 5a. Export your Telegram session (one-time setup)

```bash
cd backend
source venv/bin/activate
python telegram/export_session.py
```

**What happens:**
1. Sends a verification code to your Telegram app
2. You enter the code
3. If 2FA is enabled, enter your password
4. Prints a `TELEGRAM_SESSION` string

**Copy the string and add it to your `.env` file:**
```
TELEGRAM_SESSION=1BVtsO...your_long_string...
```

---

## Phase 6: Full System Integration

### 6a. Start everything

Terminal 1 - Backend:
```bash
cd backend
source venv/bin/activate
python main.py
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

### 6b. Test via the Admin UI

1. Open http://localhost:3000 in your browser
2. **Dashboard** (`/`): Should show stats cards (documents, students, messages)
3. **Upload** (`/upload`):
   - Upload a PDF or TXT file
   - Verify it appears in the documents table below
   - Check that chunk count > 0
4. **Students** (`/students`):
   - Add a real Telegram username (someone you can test with)
   - The userbot should send them a greeting in Russian
   - Their status should change from "pending" to "active"

### 6c. Test the Telegram conversation

Have the registered student send these messages via Telegram DM:

| Message | Expected Behavior |
|---------|-------------------|
| `Привет!` | Greeting response in Russian |
| `Что такое генеративный AI?` | RAG-powered answer using uploaded materials |
| `Можешь объяснить проще?` | Clarification with simpler language |
| `Дай задание по промптам` | Teaching answer + practice exercise |
| `Как приготовить борщ?` | Off-topic: polite redirect to course topics |
| `Я вообще ничего не понимаю, помогите` | Escalation: offers to connect with teacher |

**What to verify:**
- All responses are in Russian
- There's a visible typing delay before each response (human-like)
- RAG answers reference content from your uploaded documents
- Messages are saved in `sc_conversations` (check via Students page chat panel)

---

## Phase 7: Verify Data in Supabase

After testing, check that data was stored correctly:

```bash
cd backend
source venv/bin/activate
python -c "
import asyncio
from config import get_config
from database import get_db, list_documents, list_students, get_stats

async def verify():
    config = get_config()
    db = get_db(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

    # Stats
    stats = await get_stats(db)
    print(f'Documents: {stats[\"documents_count\"]}')
    print(f'Students: {stats[\"students_count\"]}')
    print(f'Messages: {stats[\"messages_count\"]}')

    # Documents
    docs = await list_documents(db)
    print(f'\nDocuments:')
    for d in docs:
        print(f'  {d[\"title\"]} ({d[\"file_type\"]}) - {d[\"chunk_count\"]} chunks')

    # Students
    students = await list_students(db)
    print(f'\nStudents:')
    for s in students:
        print(f'  @{s[\"telegram_username\"]} [{s[\"status\"]}] level={s[\"level\"]}')

asyncio.run(verify())
"
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ConfigurationError: Missing: ...` | Fill in all required vars in `.env` |
| `FloodWaitError` on Telegram | Wait the required time. Reduce message frequency |
| `Session revoked or invalid` | Re-run `python telegram/export_session.py` |
| RAG returns 0 results | Upload documents first. Check similarity threshold (default 0.7) |
| Frontend can't reach API | Make sure backend runs on port 8000. Check CORS |
| `'answer' is already being used as a state key` | Already fixed. Pull latest code |
| Pydantic V1 warning with Python 3.14 | Harmless warning, can be ignored |
| Agent responds in English | Check that the system prompts in `nodes.py` are in Russian |

---

## Cleanup

To remove test data from Supabase:

```bash
python -c "
import asyncio
from config import get_config
from database import get_db

async def cleanup():
    config = get_config()
    db = get_db(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

    # Delete all test data (careful - this deletes everything!)
    db.table('sc_conversations').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    db.table('sc_students').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    db.table('sc_chunks').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    db.table('sc_documents').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    print('All sc_ tables cleared.')

asyncio.run(cleanup())
"
```
