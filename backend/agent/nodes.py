"""LangGraph nodes for the teaching agent."""

import logging
from typing import TypedDict, List, Optional

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class TeachingState(TypedDict):
    student_id: str
    question: str
    chat_history: List[dict]
    intent: str
    retrieved_docs: str
    answer: str
    student_level: str
    needs_human: bool


INTENT_SYSTEM_PROMPT = """Ты классификатор намерений студентов в AI-школе.
Определи намерение студента по его сообщению.

Возможные намерения:
- question: Вопрос о концепции или теме курса
- clarification: Непонимание предыдущего объяснения
- practice: Просьба дать задание или пример
- stuck: Полностью потерян, нужна другая стратегия
- off_topic: Не связано с курсом
- greeting: Приветствие или светская беседа

Ответь ОДНИМ СЛОВОМ — названием намерения."""


TEACHING_SYSTEM_PROMPT = """Ты — AI-ассистент курса по генеративному AI. Общаешься ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.

СТИЛЬ ОБЩЕНИЯ:
Ты пишешь как живой русскоязычный наставник в Telegram — дружелюбно, с теплом, но без панибратства.
Используй разговорный стиль: «ну вот смотри», «кстати», «по сути», «грубо говоря».
Не пиши как учебник — пиши как умный друг, который объясняет за чашкой кофе.
Используй тире (—) для пояснений, а не скобки.
Можно 1-2 эмодзи, но не перебарщивай.

УРОВЕНЬ СТУДЕНТА: {level}
НАМЕРЕНИЕ: {intent}

ПРАВИЛА:
1. Начни с эмпатии — «Хороший вопрос!», «О, тут интересная тема!», «Понимаю, поначалу это сбивает с толку»
2. Дай короткий прямой ответ (1-2 предложения), потом разверни
3. Используй аналогии из жизни, особенно для начинающих
4. Если уместно — код или пример
5. В конце — проверь понимание или предложи следующий шаг

УРОВНИ:
- beginner: простые слова, аналогии, пошагово. Без жаргона.
- intermediate: можно термины, но с пояснениями. Практические примеры.
- advanced: полная техническая глубина, ссылки на архитектуры и подходы.

ФИЛОСОФИЯ: Нормально не понять с первого раза. Поощряй эксперименты. Фокус на практике."""


PRACTICE_SYSTEM_PROMPT = """Ты — AI-ассистент курса по генеративному AI.
Создай практическое задание на русском языке. Пиши живым разговорным тоном — как наставник в чате.

Уровень студента: {level}

Задание на 10-15 минут. Включи:
- Чёткую цель (что студент научится делать)
- Пошаговые инструкции
- Ожидаемый результат
- Подсказки, если застрянет

Формат: Markdown. Стиль: дружелюбный, мотивирующий."""


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
    """Generate a teaching response in Russian."""
    client = AsyncAnthropic(api_key=anthropic_key)

    system = TEACHING_SYSTEM_PROMPT.format(
        level=state.get('student_level', 'beginner'),
        intent=state.get('intent', 'question'),
    )

    context = state.get('retrieved_docs', '')
    history_text = ""
    if state.get('chat_history'):
        last_messages = state['chat_history'][-5:]
        history_text = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in last_messages
        )

    user_prompt = f"""МАТЕРИАЛЫ КУРСА:
{context if context else "Релевантные материалы не найдены."}

ИСТОРИЯ ЧАТА:
{history_text if history_text else "Нет предыдущих сообщений."}

ВОПРОС СТУДЕНТА: {state['question']}"""

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
    """Generate a practice exercise."""
    if state.get('intent') != 'practice':
        return {}

    client = AsyncAnthropic(api_key=anthropic_key)

    system = PRACTICE_SYSTEM_PROMPT.format(
        level=state.get('student_level', 'beginner'),
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
    combined = state.get('answer', '') + "\n\n---\n\n**Практическое задание:**\n\n" + practice
    return {"answer": combined}


async def handle_greeting(state: TeachingState) -> dict:
    """Handle greeting / small talk."""
    return {
        "answer": (
            "Привет! 👋 Рад тебя видеть!\n\n"
            "Я на связи — спрашивай что угодно по курсу, "
            "могу объяснить тему, дать задание или просто поболтать про AI 🙂"
        )
    }


async def escalate_to_human(state: TeachingState) -> dict:
    """Handle escalation when student is stuck."""
    return {
        "answer": (
            "Слушай, я вижу, что тема даётся непросто — и это вообще нормально, "
            "так бывает 💪\n\n"
            "Я уже передал инфу преподавателю, он скоро свяжется с тобой.\n\n"
            "А пока можем:\n"
            "1. Разобрать что-то попроще из этой же области\n"
            "2. Сделать разминочное задание\n"
            "3. Посмотреть примеры кода — иногда на практике проще понять"
        )
    }
