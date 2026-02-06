"""Human-like behavior utilities for Telegram userbot.

Adds randomness to operations to appear more human-like
and avoid triggering Telegram's automated behavior detection.
"""

import asyncio
import random
import logging
import time

logger = logging.getLogger(__name__)


async def human_delay(min_seconds: float = 0.5, max_seconds: float = 2.0):
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f'Human delay: {delay:.2f}s')
    await asyncio.sleep(delay)


async def human_delay_short():
    """Short delay for quick operations (0.3-1.0 seconds)."""
    await human_delay(0.3, 1.0)


async def human_delay_medium():
    """Medium delay for normal operations (1.0-3.0 seconds)."""
    await human_delay(1.0, 3.0)


async def human_delay_long():
    """Long delay for significant operations (2.0-5.0 seconds)."""
    await human_delay(2.0, 5.0)


def get_jittered_interval(base_seconds: float, jitter_percent: float = 0.25) -> float:
    """Get a randomized interval with jitter.
    E.g., base=60, jitter=0.25 => returns 45-75 seconds.
    """
    min_interval = base_seconds * (1 - jitter_percent)
    max_interval = base_seconds * (1 + jitter_percent)
    return random.uniform(min_interval, max_interval)


def get_typing_delay(text_length: int) -> float:
    """Simulate typing time based on message length.
    Average human typing speed: ~40 chars/sec for a fast typist.
    We use 15-40 chars/sec with jitter, clamped between 1.5 and 25 seconds.
    For very long messages (>500 chars), we assume partial copy-paste
    so typing speed increases to 40-80 chars/sec for the excess.
    """
    if text_length <= 500:
        speed = random.uniform(15, 40)
        base_delay = text_length / speed
    else:
        # First 500 chars typed normally
        speed = random.uniform(15, 40)
        base_delay = 500 / speed
        # Rest is "copy-paste" - much faster
        excess = text_length - 500
        paste_speed = random.uniform(40, 80)
        base_delay += excess / paste_speed

    return max(1.5, min(base_delay, 25.0))


def get_message_interval() -> float:
    """Delay between sending messages to the same user (3-8 seconds)."""
    return random.uniform(3.0, 8.0)


def get_first_contact_delay() -> float:
    """Delay before first message to a new student (30-120 seconds).
    Longer delay looks more natural when initiating contact.
    """
    return random.uniform(30.0, 120.0)


def get_read_delay() -> float:
    """Delay after receiving a message before 'reading' it (2-6 seconds)."""
    return random.uniform(2.0, 6.0)


def get_thinking_delay() -> float:
    """Delay to simulate thinking before responding (3-8 seconds)."""
    return random.uniform(3.0, 8.0)


# --- Rate Limiter ---

class MessageRateLimiter:
    """Enforces per-minute and per-hour rate limits for outbound messages.

    Telegram's unofficial limits for userbot DMs:
    - ~30 messages per minute to different users
    - ~50 messages per hour to new users
    - No hard public spec, so we stay well below suspected thresholds.
    """

    def __init__(
        self,
        max_per_minute: int = 8,
        max_per_hour: int = 40,
        max_per_day: int = 200,
    ):
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    def _prune(self, now: float):
        """Remove timestamps older than 24 hours."""
        cutoff = now - 86400
        self._timestamps = [t for t in self._timestamps if t > cutoff]

    def _count_in_window(self, now: float, window_seconds: float) -> int:
        cutoff = now - window_seconds
        return sum(1 for t in self._timestamps if t > cutoff)

    async def acquire(self) -> float:
        """Wait until a message can be sent. Returns the wait time in seconds."""
        async with self._lock:
            now = time.time()
            self._prune(now)

            total_wait = 0.0

            # Check daily limit
            day_count = self._count_in_window(now, 86400)
            if day_count >= self.max_per_day:
                oldest_in_day = min(t for t in self._timestamps if t > now - 86400)
                wait = (oldest_in_day + 86400) - now + random.uniform(1, 5)
                logger.warning(f'Daily limit ({self.max_per_day}) reached. Sleeping {wait:.0f}s')
                await asyncio.sleep(wait)
                total_wait += wait
                now = time.time()
                self._prune(now)

            # Check hourly limit
            hour_count = self._count_in_window(now, 3600)
            if hour_count >= self.max_per_hour:
                oldest_in_hour = min(t for t in self._timestamps if t > now - 3600)
                wait = (oldest_in_hour + 3600) - now + random.uniform(1, 10)
                logger.warning(f'Hourly limit ({self.max_per_hour}) reached. Sleeping {wait:.0f}s')
                await asyncio.sleep(wait)
                total_wait += wait
                now = time.time()
                self._prune(now)

            # Check per-minute limit
            min_count = self._count_in_window(now, 60)
            if min_count >= self.max_per_minute:
                oldest_in_min = min(t for t in self._timestamps if t > now - 60)
                wait = (oldest_in_min + 60) - now + random.uniform(0.5, 3)
                logger.info(f'Per-minute limit ({self.max_per_minute}). Sleeping {wait:.1f}s')
                await asyncio.sleep(wait)
                total_wait += wait
                now = time.time()

            self._timestamps.append(now)
            return total_wait

    @property
    def stats(self) -> dict:
        now = time.time()
        self._prune(now)
        return {
            'last_minute': self._count_in_window(now, 60),
            'last_hour': self._count_in_window(now, 3600),
            'last_day': self._count_in_window(now, 86400),
        }


def split_long_message(text: str, max_length: int = 2000) -> list[str]:
    """Split a long message into smaller parts at natural break points.
    Humans don't send 4000-char messages in one go.
    """
    if len(text) <= max_length:
        return [text]

    parts = []
    # Try splitting on double newlines first, then single, then sentences
    separators = ['\n\n', '\n', '. ', ' ']

    remaining = text
    while len(remaining) > max_length:
        # Find best split point
        split_at = max_length
        for sep in separators:
            idx = remaining[:max_length].rfind(sep)
            if idx > max_length * 0.3:  # Don't split too early
                split_at = idx + len(sep)
                break

        parts.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()

    if remaining.strip():
        parts.append(remaining.strip())

    return parts
