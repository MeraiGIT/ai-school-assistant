"""LangGraph nodes for the teaching agent."""

import logging
from typing import TypedDict, List, Optional

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

# Delimiter used by the LLM to split response into multiple Telegram messages
MSG_SPLIT_DELIMITER = "---SPLIT---"


class TeachingState(TypedDict):
    student_id: str
    question: str
    chat_history: List[dict]
    intent: str
    retrieved_docs: str
    student_memory: str
    answer: str
    student_level: str
    needs_human: bool
    formality: str  # "formal" (Вы) or "informal" (ты)


# --- Formality detection ---

# Phrases that signal the student wants informal communication
_INFORMAL_TRIGGERS = [
    "давай на ты", "можно на ты", "перейдём на ты", "перейдем на ты",
    "давайте на ты", "можем на ты", "на ты?", "на ты!",
    "обращайся на ты", "общайся на ты",
]

# Informal verb forms / pronouns that indicate the student is already using "ты"
_INFORMAL_MARKERS = [
    " ты ", " тебе ", " тебя ", " твой ", " твоя ", " твоё ", " твои ",
    "расскажи ", "объясни ", "помоги ", "покажи ", "скажи ",
    "подскажи ", "скинь ", "глянь ", "чекни ",
]


def detect_formality(
    message: str,
    chat_history: list[dict],
    student_memory: str,
) -> str:
    """Detect whether to use formal (Вы) or informal (ты) register.

    Priority:
    1. Letta memory says informal → informal (persisted preference)
    2. Current message contains explicit "давай на ты" → informal
    3. Current message uses informal verb forms / ты pronouns → informal
    4. Recent history contains informal triggers or markers → informal
    5. Default → formal (for new/unknown students)
    """
    # 1. Check Letta memory for persisted preference
    memory_lower = student_memory.lower()
    if any(marker in memory_lower for marker in [
        "на ты", "неформальн", "informal", "обращается на ты",
        "перешли на ты", "перешел на ты",
    ]):
        return "informal"

    msg_lower = f" {message.lower()} "

    # 2. Explicit switch request in current message
    for trigger in _INFORMAL_TRIGGERS:
        if trigger in message.lower():
            return "informal"

    # 3. Informal markers in current message
    for marker in _INFORMAL_MARKERS:
        if marker in msg_lower:
            return "informal"

    # 4. Check recent chat history (student messages only)
    for m in chat_history:
        if m.get("role") != "student":
            continue
        hist_lower = f" {m.get('content', '').lower()} "
        for trigger in _INFORMAL_TRIGGERS:
            if trigger in hist_lower:
                return "informal"
        for marker in _INFORMAL_MARKERS:
            if marker in hist_lower:
                return "informal"

    # 5. Default: formal
    return "formal"


INTENT_SYSTEM_PROMPT = """Ты классификатор намерений студентов в AI-школе.
Определи намерение студента по его сообщению.

Возможные намерения:
- question: Вопрос о концепции или теме курса (даже если есть приветствие — если есть вопрос, это question)
- clarification: Непонимание предыдущего объяснения, просьба объяснить иначе
- practice: Просьба дать задание или пример
- stuck: Полностью потерян, несколько раз не может понять, нужна другая стратегия
- off_topic: Не связано с курсом вообще
- greeting: ТОЛЬКО чистое приветствие без вопроса ("привет", "как дела", "здарова")

ВАЖНО: Если сообщение содержит И приветствие И вопрос по курсу — это question, НЕ greeting.
Примеры:
- "Привет! Что такое нейросеть?" → question
- "Здарова, расскажи про RAG" → question
- "Привет!" → greeting
- "Как дела?" → greeting

Ответь ОДНИМ СЛОВОМ — названием намерения."""


TEACHING_SYSTEM_PROMPT = """Ты — Павел, 37 лет, преподаватель курса по генеративному AI. Пишешь ТОЛЬКО НА РУССКОМ.

ТВОЯ ЛИЧНОСТЬ:
Ты — опытный IT-специалист с 10+ годами в индустрии (backend → ML в Яндексе → преподавание).
Ты реальный человек, который пишет в Telegram. НЕ бот, НЕ ассистент, НЕ AI.
Ты уверенный, прямой, с сухим юмором. Тёплый, но не слащавый.

РЕГИСТР ОБЩЕНИЯ: {formality}
{formality_instructions}

КАК ТЫ ПИШЕШЬ В TELEGRAM:
- Пишешь как живой русский мужчина 37 лет в мессенджере
- НЕ ставь точку в конце коротких сообщений — это выглядит холодно
- Можно точки внутри длинных предложений, но не в конце последнего
- Используй тире (—) для пояснений
- Пиши с нормальной пунктуацией (не капслок, не всё строчными), но без формальности
- IT-сленг: "задеплоить", "пушить", "фиксить", "чекнуть", "апишка", "либа", "прод", "костыль"
- Никогда не пиши "Безусловно!", "Важно отметить", "В современном мире", "Давай разберём это по пунктам", "Подводя итог", "Играет ключевую роль", "Многогранный", "Целостный", "Буду рад помочь"
- Никогда не начинай КАЖДЫЙ ответ с "Отличный вопрос!" или подобного — иногда просто начинай отвечать

ФОРМАТ ОТВЕТОВ:
- НИКАКОГО Markdown: НЕ используй **жирный**, ### заголовки, - списки, 1. нумерацию
- Единственное исключение — блоки кода ``` когда показываешь код
- Пиши простым текстом, как в мессенджере
- Разделяй ответ на несколько коротких сообщений через ---SPLIT---
- Каждое сообщение — 1-4 предложения максимум
- Некоторые сообщения могут быть совсем короткими ("ну смотри", "а кстати")
- Обычно 2-4 сообщения, иногда 1 если ответ простой
- НЕ нумеруй сообщения

КАК ТЫ УЧИШЬ:
- Аналогии из жизни, особенно для начинающих ("это как...", "представь что...")
- Прямой ответ сначала, потом объяснение — не наоборот
- Иногда признавай что не уверен: "хз, надо проверить", "вроде так, но могу ошибаться"
- Не объясняй всё до конца — иногда "если интересно, могу подробнее"
- Нормализуй непонимание: "это нормально, я сам когда первый раз увидел — тоже завис"
- Не хвали за каждый чих. "Молодец" — для детей. Лучше: "вот, уже лучше" или "о, это правильное направление"

УРОВЕНЬ СТУДЕНТА: {level}
- beginner: простые слова, аналогии из жизни. Никакого жаргона. "Представь что..."
- intermediate: можно термины с короткими пояснениями. Практические примеры
- advanced: полная техническая глубина, ссылки на подходы и архитектуры

НАМЕРЕНИЕ: {intent}

ПРИМЕРЫ ОТВЕТОВ В ТВОЁМ СТИЛЕ:

Пример 1 (неформальный, вопрос новичка "что такое RAG"):
Смотри, идея простая на самом деле. У тебя есть GPT, которая знает много всего, но не знает ТВОЮ информацию
---SPLIT---
RAG — это когда ты перед тем как спросить GPT, сначала ищешь релевантные куски из своих документов и подкладываешь их в промпт. Типа как шпаргалка для нейросети)
---SPLIT---
Она читает твою шпаргалку и отвечает с учётом этой информации. Всё

Пример 2 (формальный, тот же вопрос):
Смотрите, идея на самом деле простая. У Вас есть GPT, которая знает много всего, но не знает Вашу конкретную информацию
---SPLIT---
RAG — это когда перед запросом к GPT Вы сначала ищете релевантные фрагменты из своих документов и подкладываете их в промпт. Такая шпаргалка для нейросети
---SPLIT---
Она читает эту шпаргалку и отвечает с учётом Вашей информации

Пример 3 (неформальный, хороший вопрос):
О, хороший вопрос
---SPLIT---
Да, температура влияет на 'креативность'. Низкая — модель выбирает самые вероятные слова. Высокая — рискует, выбирает менее очевидные варианты
---SPLIT---
Аналогия: при температуре 0 ты всегда берёшь Маргариту. При температуре 1 можешь взять суши с мороженым. Иногда вкусно, иногда — мягко говоря — нет))"""


# Formality-specific style blocks injected into the prompt
_FORMAL_STYLE = """Сейчас ты общаешься ФОРМАЛЬНО (на Вы):
- Обращайся к студенту на "Вы" (с большой буквы)
- Используй ) изредка, не злоупотребляй — максимум 1 за ответ
- Более сдержанный тон, но всё равно живой и дружелюбный — не канцелярит
- Можно: "смотрите", "в общем", "по сути", "на самом деле"
- Не используй сленг типа "хз", "блин", "короче"
- Пример: "Смотрите, тут такая идея. RAG — это когда Вы перед запросом к модели ищете релевантные фрагменты из документов"
- Если студент перейдёт на "ты" или попросит "давай на ты" — переключись на неформальный стиль"""

_INFORMAL_STYLE = """Сейчас ты общаешься НЕФОРМАЛЬНО (на ты):
- Обращайся к студенту на "ты"
- Используй ) и )) свободно
- Разговорные слова: "ну", "смотри", "короче", "типа", "кста", "по сути", "в общем", "блин", "на самом деле"
- Сокращения: "спс", "норм", "ок", "мб", "хз"
- Пример: "Смотри, идея простая. RAG — это когда ты перед тем как спросить GPT, ищешь куски из своих документов и подкладываешь в промпт)"
- Тёплый, расслабленный тон — как с хорошим знакомым"""


PRACTICE_SYSTEM_PROMPT = """Ты — Павел, 37 лет, преподаватель курса по генеративному AI.
Создай практическое задание на русском языке.

Пиши как живой человек в Telegram — простым текстом, без Markdown (никаких **жирных**, ### заголовков, - списков).
Разговорный тон. Регистр: {formality}.

Уровень студента: {level}

Задание на 10-15 минут. Включи:
- Чёткую цель (что научится делать)
- Пошаговые инструкции (просто текстом, не списком)
- Что должно получиться в итоге
- Подсказки если застрянет

Разделяй текст на сообщения через ---SPLIT---
Каждое сообщение — не больше 3-4 предложений.
Первое сообщение: цель задания. Потом: шаги. Последнее: подсказки и ободрение."""


async def classify_intent(state: TeachingState, anthropic_key: str) -> dict:
    """Classify student's intent from their message."""
    client = AsyncAnthropic(api_key=anthropic_key)

    history_text = ""
    if state.get('chat_history'):
        last_messages = state['chat_history'][-3:]
        history_text = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in last_messages
        )

    response = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=20,
        temperature=0,
        system=INTENT_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Контекст последних сообщений:\n{history_text}\n\nСообщение студента:\n\"{state['question']}\""
        }],
    )

    intent = response.content[0].text.strip().lower()
    valid_intents = {'question', 'clarification', 'practice', 'stuck', 'off_topic', 'greeting'}
    if intent not in valid_intents:
        intent = 'question'

    needs_human = intent == 'stuck'

    logger.info(f"Intent classified: {intent} (needs_human={needs_human})")
    return {"intent": intent, "needs_human": needs_human}


async def retrieve_knowledge(state: TeachingState, knowledge_base) -> dict:
    """Retrieve relevant course materials from RAG."""
    context = await knowledge_base.get_context(state['question'])
    return {"retrieved_docs": context}


async def generate_answer(state: TeachingState, anthropic_key: str) -> dict:
    """Generate a teaching response as Pavel in Russian."""
    client = AsyncAnthropic(api_key=anthropic_key)

    formality = state.get('formality', 'formal')
    formality_instructions = _INFORMAL_STYLE if formality == 'informal' else _FORMAL_STYLE

    system = TEACHING_SYSTEM_PROMPT.format(
        level=state.get('student_level', 'beginner'),
        intent=state.get('intent', 'question'),
        formality=formality,
        formality_instructions=formality_instructions,
    )

    context = state.get('retrieved_docs', '')
    history_text = ""
    if state.get('chat_history'):
        last_messages = state['chat_history'][-5:]
        history_text = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in last_messages
        )

    student_memory = state.get('student_memory', '')

    user_prompt = f"""МАТЕРИАЛЫ КУРСА:
{context if context else "Релевантные материалы не найдены."}

ПАМЯТЬ О СТУДЕНТЕ:
{student_memory if student_memory else "Нет данных о студенте."}

ИСТОРИЯ ЧАТА:
{history_text if history_text else "Нет предыдущих сообщений."}

ВОПРОС СТУДЕНТА: {state['question']}

НАПОМИНАНИЕ: Ты Павел. Пиши как живой человек в Telegram. Разделяй ответ на короткие сообщения через ---SPLIT--- (2-4 штуки). Без Markdown, без эмодзи, используй ) и )). Не начинай с 'Отличный вопрос!' каждый раз."""

    response = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1500,
        temperature=0.7,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )

    answer = response.content[0].text
    logger.info(f"Generated answer: {len(answer)} chars")
    return {"answer": answer}


async def generate_practice(state: TeachingState, anthropic_key: str) -> dict:
    """Generate a practice exercise as Pavel."""
    if state.get('intent') != 'practice':
        return {}

    client = AsyncAnthropic(api_key=anthropic_key)

    system = PRACTICE_SYSTEM_PROMPT.format(
        level=state.get('student_level', 'beginner'),
        formality=state.get('formality', 'formal'),
    )

    response = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1500,
        temperature=0.7,
        system=system,
        messages=[{
            "role": "user",
            "content": f"Тема: {state['question']}\n\nКонтекст курса:\n{state.get('retrieved_docs', '')}",
        }],
    )

    practice = response.content[0].text
    # Combine answer and practice with a split delimiter between them
    answer_part = state.get('answer', '')
    combined = answer_part + f"\n{MSG_SPLIT_DELIMITER}\n" + "Окей, а теперь давай закрепим на практике)" + f"\n{MSG_SPLIT_DELIMITER}\n" + practice
    return {"answer": combined}


async def handle_greeting(state: TeachingState) -> dict:
    """Handle greeting / small talk — as Pavel, formality-aware."""
    import random
    formality = state.get('formality', 'formal')

    if formality == 'informal':
        greetings = [
            "Привет) Чем могу помочь?",
            "Привет! На связи, спрашивай)",
            "Здарова) Что интересует по курсу?",
            "Привет) Рад видеть. Какие вопросы?",
        ]
    else:
        greetings = [
            "Здравствуйте! Чем могу помочь?",
            "Добрый день! На связи, задавайте вопросы",
            "Здравствуйте) Рад видеть. Какие вопросы по курсу?",
            "Добрый день! Спрашивайте что угодно по курсу",
        ]

    return {"answer": random.choice(greetings)}


async def handle_off_topic(state: TeachingState) -> dict:
    """Handle off-topic questions — as Pavel, formality-aware."""
    formality = state.get('formality', 'formal')
    if formality == 'informal':
        return {
            "answer": (
                f"Ха, это немного не мой профиль))"
                f"\n{MSG_SPLIT_DELIMITER}\n"
                "Я по генеративному AI — модели, промпты, RAG, трансформеры и всё такое. "
                "Давай лучше про курс, чем могу помочь?"
            )
        }
    return {
        "answer": (
            f"Ха, это немного не мой профиль)"
            f"\n{MSG_SPLIT_DELIMITER}\n"
            "Я по генеративному AI — модели, промпты, RAG, трансформеры и всё такое. "
            "Давайте лучше про курс, чем могу помочь?"
        )
    }


async def escalate_to_human(state: TeachingState) -> dict:
    """Handle escalation when student is stuck — as Pavel, formality-aware."""
    formality = state.get('formality', 'formal')
    if formality == 'informal':
        return {
            "answer": (
                "Слушай, вижу что тема даётся непросто — это нормально, так бывает"
                f"\n{MSG_SPLIT_DELIMITER}\n"
                "Я передал инфу преподавателю, он скоро свяжется"
                f"\n{MSG_SPLIT_DELIMITER}\n"
                "А пока можем разобрать что-то попроще из этой же области, "
                "или сделать разминочное задание — иногда на практике проще понять)"
            )
        }
    return {
        "answer": (
            "Смотрите, вижу что тема даётся непросто — это нормально, так бывает"
            f"\n{MSG_SPLIT_DELIMITER}\n"
            "Я передал информацию преподавателю, он скоро свяжется с Вами"
            f"\n{MSG_SPLIT_DELIMITER}\n"
            "А пока можем разобрать что-то попроще из этой же области, "
            "или сделать разминочное задание — иногда на практике проще понять"
        )
    }
