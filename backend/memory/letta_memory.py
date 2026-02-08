"""Letta ai-memory-sdk integration for persistent student memory.

Provides per-student memory blocks that persist across sessions:
- student_profile: name, level, preferences, learning style
- learning_progress: topics covered, weak areas, exercises done
- teaching_notes: what approaches work for this student

The SDK is synchronous, so all calls are wrapped in run_in_executor.
All public methods catch exceptions internally — if Letta is unavailable,
the bot continues working without memory (graceful degradation).
"""

import asyncio
import logging
from functools import partial
from typing import Optional

from ai_memory_sdk import Memory

logger = logging.getLogger(__name__)

# Memory block definitions — descriptions are in Russian so the Letta
# agent (which processes conversations in Russian) writes in Russian too.
MEMORY_BLOCKS = [
    {
        "label": "student_profile",
        "description": (
            "Информация о студенте: имя, уровень (beginner/intermediate/advanced), "
            "стиль обучения, предпочтения (код vs теория, аналогии vs формулы), "
            "личные детали упомянутые в разговорах. Пиши на русском."
        ),
        "char_limit": 5000,
    },
    {
        "label": "learning_progress",
        "description": (
            "Темы которые студент изучил, вопросы которые задавал, "
            "концепции которые понял хорошо и с которыми трудности. "
            "Результаты практических заданий. Пиши на русском."
        ),
        "char_limit": 5000,
    },
    {
        "label": "teaching_notes",
        "description": (
            "Заметки о том какие подходы к обучению работают для этого студента: "
            "какие объяснения помогли, какие запутали, предпочитает ли пошаговые "
            "разборы или общую картину. Пиши на русском."
        ),
        "char_limit": 3000,
    },
]


class StudentMemoryManager:
    """Async wrapper around Letta ai-memory-sdk for per-student memory."""

    def __init__(self, api_key: str, byok_model: str = ""):
        self._memory = Memory(api_key=api_key)
        self._initialized_subjects: set[str] = set()
        # The SDK hardcodes "openai/gpt-4.1" (Letta-hosted, costs credits).
        # BYOK models use the provider name from the dashboard (e.g. "open-ai-api")
        # and do NOT consume Letta credits — billed directly to your LLM provider.
        self._byok_model = byok_model
        logger.info("Letta StudentMemoryManager initialized")

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous SDK call in a thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, partial(func, *args, **kwargs)
        )

    async def ensure_student(self, student_id: str) -> None:
        """Idempotently initialize Letta subject and memory blocks for a student.

        Safe to call multiple times — skips if already initialized.
        """
        if student_id in self._initialized_subjects:
            return

        try:
            # Initialize subject (creates the Letta sleeptime agent)
            is_new = False
            try:
                await self._run_sync(
                    self._memory.initialize_subject, student_id, False
                )
                is_new = True
                logger.info(f"Letta subject created: {student_id}")
            except ValueError:
                # Subject already exists — that's fine
                pass

            # Switch newly created agents from Letta-hosted to BYOK model
            if is_new and self._byok_model:
                agent = await self._run_sync(
                    self._memory._get_agent_for_subject, student_id
                )
                if agent:
                    await self._run_sync(
                        self._memory.letta_client.agents.modify,
                        agent_id=agent.id,
                        model=self._byok_model,
                    )
                    logger.info(f"Switched agent to BYOK model: {self._byok_model}")

            # Initialize each memory block (no-op if already exists)
            for block in MEMORY_BLOCKS:
                await self._run_sync(
                    self._memory.initialize_memory,
                    block["label"],
                    block["description"],
                    "",  # value (empty initially)
                    block["char_limit"],
                    False,  # reset
                    student_id,
                )

            self._initialized_subjects.add(student_id)
            logger.info(f"Letta memory blocks ready for student {student_id}")

        except Exception as e:
            logger.error(f"Letta ensure_student failed for {student_id}: {e}")

    async def get_student_context(self, student_id: str) -> str:
        """Retrieve all memory blocks for a student, formatted for prompt injection.

        Returns concatenated XML-formatted blocks, or empty string on failure.
        """
        try:
            await self.ensure_student(student_id)

            parts = []
            for block in MEMORY_BLOCKS:
                value = await self._run_sync(
                    self._memory.get_memory,
                    block["label"],
                    True,  # prompt_formatted (wraps in XML tags)
                    student_id,
                )
                if value:
                    parts.append(value)

            context = "\n\n".join(parts)
            if context:
                logger.info(
                    f"Letta memory retrieved for {student_id}: {len(context)} chars"
                )
            return context

        except Exception as e:
            logger.error(f"Letta get_student_context failed for {student_id}: {e}")
            return ""

    async def update_memory_background(
        self, student_id: str, user_msg: str, assistant_msg: str
    ) -> None:
        """Send a conversation exchange to Letta for memory processing.

        Fire-and-forget — does not block the response to the student.
        The Letta agent processes messages asynchronously and updates
        the memory blocks in the background.
        """
        try:
            await self.ensure_student(student_id)

            messages = [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ]

            run_id = await self._run_sync(
                self._memory.add_messages_for_subject,
                student_id,
                messages,
                True,  # skip_vector_storage (we have our own RAG)
            )

            logger.info(
                f"Letta memory update queued for {student_id} (run_id={run_id})"
            )

        except Exception as e:
            logger.error(f"Letta update_memory failed for {student_id}: {e}")
