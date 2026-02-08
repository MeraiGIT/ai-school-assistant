"""Telegram userbot for AI School Assistant.

Handles DMs from registered students and proactive outreach to new students.
Uses Telethon with device spoofing and human-like behavior safeguards.

Safety measures:
- flood_sleep_threshold: auto-sleep on minor FloodWaitErrors
- Concurrency semaphore: max 1 message processed at a time
- Per-minute/hour/day rate limiter on outbound messages
- Long messages split into parts with inter-part delays
- Greeting queue: new students greeted sequentially, not in parallel
- Proper unknown sender rejection
- Max retry limits on all operations
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional, Callable, Awaitable

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User
from telethon.errors import (
    SessionRevokedError,
    AuthKeyUnregisteredError,
    UserDeactivatedError,
    PhoneNumberBannedError,
    FloodWaitError,
    UsernameNotOccupiedError,
    PeerIdInvalidError,
)

from telegram.human_behavior import (
    human_delay_medium,
    get_typing_delay,
    get_read_delay,
    get_thinking_delay,
    get_first_contact_delay,
    get_message_interval,
    get_split_message_delay,
    MessageRateLimiter,
    split_long_message,
    split_response_messages,
)

logger = logging.getLogger(__name__)

# Max retry attempts for any operation
MAX_RETRIES = 3


class SchoolUserbot:
    """Telegram userbot that communicates with students."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        session_name: str = 'school_assistant_userbot',
        session_string: str = '',
        password: str = '',
        device_model: str = 'Desktop',
        system_version: str = 'Windows 10',
        app_version: str = '4.16.8',
        lang_code: str = 'ru',
        system_lang_code: str = 'ru-RU',
    ):
        self.phone = phone
        self.password = password

        if session_string:
            session = StringSession(session_string)
        else:
            session = session_name

        self.client = TelegramClient(
            session,
            api_id,
            api_hash,
            device_model=device_model,
            system_version=system_version,
            app_version=app_version,
            lang_code=lang_code,
            system_lang_code=system_lang_code,
            # Auto-sleep on FloodWaitErrors up to 60 seconds
            flood_sleep_threshold=60,
            connection_retries=5,
            retry_delay=1,
            auto_reconnect=True,
        )

        self._running = False
        self._on_student_message: Optional[Callable] = None
        self._known_student_ids: set[int] = set()

        # Concurrency: process only 1 incoming message at a time
        # This prevents API call bursts when multiple students message simultaneously
        self._message_semaphore = asyncio.Semaphore(1)

        # Track new incoming messages per user — allows interrupting response
        # delivery when the student sends a follow-up mid-response
        self._incoming_event: dict[int, asyncio.Event] = {}

        # Rate limiter: conservative limits to stay well below Telegram thresholds
        self._rate_limiter = MessageRateLimiter(
            max_per_minute=8,
            max_per_hour=40,
            max_per_day=200,
        )

        # Inbound rate limiter: per-student message timestamps.
        # Prevents API cost explosion from spam. Generous limits:
        # max 10 messages/min per student, min 2s between messages.
        self._inbound_timestamps: dict[int, list[float]] = defaultdict(list)
        self._inbound_max_per_min = 10
        self._inbound_min_gap_s = 2.0

        # Greeting queue: greetings are processed one-at-a-time
        self._greeting_queue: asyncio.Queue = asyncio.Queue()
        self._greeting_task: Optional[asyncio.Task] = None

    def on_student_message(self, callback: Callable[[int, str, str], Awaitable[str]]):
        """Register callback for student messages.
        callback(telegram_id, username, message_text) -> response_text
        """
        self._on_student_message = callback

    def register_student_id(self, telegram_id: int):
        """Register a known student's telegram_id for DM filtering."""
        self._known_student_ids.add(telegram_id)

    async def start(self):
        """Connect and authenticate."""
        logger.info('Connecting to Telegram...')

        def password_callback():
            if self.password:
                return self.password
            return input('Enter your 2FA password: ')

        try:
            await self.client.start(
                phone=self.phone,
                password=password_callback,
            )
        except (SessionRevokedError, AuthKeyUnregisteredError):
            logger.error('Session revoked or invalid. Re-authenticate with export_session.py')
            raise
        except UserDeactivatedError:
            logger.error('Telegram account has been deactivated.')
            raise
        except PhoneNumberBannedError:
            logger.error('Phone number has been banned by Telegram.')
            raise

        me = await self.client.get_me()
        logger.info(f'Logged in as: {me.first_name} (@{me.username})')

        # Register DM handler
        @self.client.on(events.NewMessage(incoming=True))
        async def _handle_incoming(event):
            await self._handle_message(event)

        # Start greeting queue processor
        self._greeting_task = asyncio.create_task(self._process_greeting_queue())

        self._running = True
        logger.info('Userbot started, listening for messages')

    async def _handle_message(self, event):
        """Handle an incoming message. Only process private DMs from known students."""
        # Only handle private messages (DMs)
        if not event.is_private:
            return

        sender = await event.get_sender()
        if not isinstance(sender, User) or sender.bot:
            return

        sender_id = sender.id
        username = sender.username or ''
        text = event.message.text
        if not text:
            return

        if not self._on_student_message:
            return

        # --- Unknown sender gate ---
        # Known students get full human-like processing (semaphore, delays, etc.).
        # Unknown senders get a lightweight username check WITHOUT acquiring the
        # semaphore or simulating behavior — prevents DoS from strangers blocking
        # real students and avoids leaking read receipts to non-students.
        if sender_id not in self._known_student_ids:
            if not username:
                logger.debug(f'Ignoring unknown sender {sender_id} (no username)')
                return
            try:
                response = await self._on_student_message(sender_id, username, text)
                if response:
                    # Resolved by username — register for future fast-path
                    self._known_student_ids.add(sender_id)
                    await self._send_response_as_messages(sender_id, response)
                else:
                    logger.debug(f'Ignoring unregistered sender {sender_id} (@{username})')
            except Exception as e:
                logger.error(f'Error checking unknown sender {sender_id}: {e}')
            return

        # --- Inbound rate limit check ---
        # Drop messages from students who are sending too fast.
        now = time.monotonic()
        timestamps = self._inbound_timestamps[sender_id]
        # Prune entries older than 60s
        timestamps[:] = [t for t in timestamps if now - t < 60]
        # Check minimum gap
        if timestamps and (now - timestamps[-1]) < self._inbound_min_gap_s:
            logger.debug(f'Rate limit: {sender_id} sending too fast (gap < {self._inbound_min_gap_s}s)')
            return
        # Check per-minute cap
        if len(timestamps) >= self._inbound_max_per_min:
            logger.warning(f'Rate limit: {sender_id} exceeded {self._inbound_max_per_min} msgs/min')
            return
        timestamps.append(now)

        # --- Known student: full human-like processing ---

        # Signal that a new message arrived from this user.
        # If _send_response_as_messages is currently sending parts for an
        # older response, it will detect this and stop early.
        self._incoming_event.setdefault(sender_id, asyncio.Event()).set()

        # Acquire semaphore - only 1 message processed at a time
        async with self._message_semaphore:
            try:
                # Clear interrupt flag — we are now the active message
                self._incoming_event[sender_id].clear()

                logger.info(f'Message from @{username} (ID:{sender_id}): {text[:80]}...')

                # Simulate reading delay (varies by message length)
                read_delay = get_read_delay(len(text))
                await asyncio.sleep(read_delay)

                # Mark as read
                await self.client.send_read_acknowledge(event.chat_id)

                # Show typing indicator while thinking + generating response.
                # Without this there's a 10-20s dead gap between the read ack
                # and the first response message.
                typing_task = asyncio.create_task(self._keep_typing(sender_id))
                try:
                    think_delay = get_thinking_delay(len(text))
                    await asyncio.sleep(think_delay)

                    # Get response from the teaching agent
                    response = await self._on_student_message(sender_id, username, text)
                finally:
                    typing_task.cancel()
                    try:
                        await typing_task
                    except asyncio.CancelledError:
                        pass

                if response:
                    await self._send_response_as_messages(sender_id, response)

            except FloodWaitError as e:
                logger.warning(f'Flood wait: sleeping {e.seconds}s')
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f'Error handling message: {e}')

    async def _keep_typing(self, user_id: int):
        """Maintain 'typing...' indicator until cancelled.

        Refreshes every 4.5 seconds (Telegram's typing indicator
        expires after ~5s).
        """
        try:
            while True:
                async with self.client.action(user_id, 'typing'):
                    await asyncio.sleep(4.5)
        except asyncio.CancelledError:
            pass

    async def _send_response_as_messages(self, user_id: int, text: str):
        """Send an LLM response as multiple Telegram messages.

        Uses ---SPLIT--- delimiter from the LLM to determine message boundaries.
        Each part gets human-like typing simulation with variable delays
        that mimic how a real person sends bursts of messages.

        If a new message arrives from the student while we're sending,
        we stop early — a real person would notice the incoming message
        and switch to addressing it instead of finishing their old thought.
        """
        parts = split_response_messages(text)

        for i, part in enumerate(parts):
            # Check if the student sent a new message — stop sending the
            # old response so we can process the new one promptly.
            # Always send at least the first part (i > 0).
            if i > 0:
                event = self._incoming_event.get(user_id)
                if event and event.is_set():
                    logger.info(
                        f'Interrupting response to {user_id}: new message received '
                        f'(sent {i}/{len(parts)} parts)'
                    )
                    break

            await self._rate_limiter.acquire()

            try:
                # Simulate typing — proportional to message length
                typing_time = get_typing_delay(len(part))
                # Refresh typing indicator every 4.5s for long typing times
                remaining = typing_time
                while remaining > 0:
                    chunk = min(remaining, 4.5)
                    async with self.client.action(user_id, 'typing'):
                        await asyncio.sleep(chunk)
                    remaining -= chunk

                await self.client.send_message(user_id, part)
                logger.info(
                    f'Sent message to {user_id} (part {i+1}/{len(parts)}, '
                    f'{len(part)} chars). Rate: {self._rate_limiter.stats}'
                )

                # Variable delay between parts based on content
                if i < len(parts) - 1:
                    next_part = parts[i + 1]
                    interval = get_split_message_delay(next_part)
                    await asyncio.sleep(interval)

            except FloodWaitError as e:
                logger.warning(f'Flood wait on send: sleeping {e.seconds}s')
                await asyncio.sleep(e.seconds)
                try:
                    await self.client.send_message(user_id, part)
                except Exception as retry_err:
                    logger.error(f'Retry failed for {user_id}: {retry_err}')
                    return
            except PeerIdInvalidError:
                logger.error(f'Invalid peer ID: {user_id}')
                return
            except Exception as e:
                logger.error(f'Error sending message to {user_id}: {e}')
                return

    async def _send_message_human_like(self, user_id: int, text: str):
        """Send a single text with human-like typing simulation.
        Used for greetings and simple one-off messages.
        Long messages are split into parts with delays between them.
        """
        parts = split_long_message(text, max_length=2000)

        for i, part in enumerate(parts):
            await self._rate_limiter.acquire()

            try:
                typing_time = get_typing_delay(len(part))
                async with self.client.action(user_id, 'typing'):
                    await asyncio.sleep(typing_time)

                await self.client.send_message(user_id, part)
                logger.info(
                    f'Sent message to {user_id} (part {i+1}/{len(parts)}, '
                    f'{len(part)} chars). Rate: {self._rate_limiter.stats}'
                )

                if i < len(parts) - 1:
                    interval = get_message_interval()
                    await asyncio.sleep(interval)

            except FloodWaitError as e:
                logger.warning(f'Flood wait on send: sleeping {e.seconds}s')
                await asyncio.sleep(e.seconds)
                try:
                    await self.client.send_message(user_id, part)
                except Exception as retry_err:
                    logger.error(f'Retry failed for {user_id}: {retry_err}')
                    return
            except PeerIdInvalidError:
                logger.error(f'Invalid peer ID: {user_id}')
                return
            except Exception as e:
                logger.error(f'Error sending message to {user_id}: {e}')
                return

    async def queue_greeting(self, username: str) -> None:
        """Add a greeting to the queue. Processed sequentially by background task."""
        await self._greeting_queue.put(username)
        logger.info(f'Queued greeting for @{username} (queue size: {self._greeting_queue.qsize()})')

    async def _process_greeting_queue(self):
        """Background task: sends greetings one at a time with delays."""
        while True:
            try:
                username = await self._greeting_queue.get()
                telegram_id = await self._send_greeting_internal(username)
                if telegram_id:
                    # Notify via a callback if needed - handled by the caller
                    pass
                self._greeting_queue.task_done()

                # Wait between greetings to avoid burst pattern
                if not self._greeting_queue.empty():
                    delay = get_first_contact_delay()
                    logger.info(f'Waiting {delay:.0f}s before next greeting')
                    await asyncio.sleep(delay)

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f'Error in greeting queue: {e}')
                await asyncio.sleep(5)

    async def send_greeting(self, username: str) -> Optional[int]:
        """Send initial greeting to a new student. Returns their telegram_id.
        This is the synchronous version - waits for completion.
        """
        return await self._send_greeting_internal(username)

    async def _send_greeting_internal(self, username: str, attempt: int = 0) -> Optional[int]:
        """Internal greeting logic with retry limit."""
        if attempt >= MAX_RETRIES:
            logger.error(f'Max retries ({MAX_RETRIES}) reached for greeting @{username}')
            return None

        username = username.lstrip('@')

        try:
            entity = await self.client.get_entity(username)
            if not isinstance(entity, User):
                logger.error(f'{username} is not a user')
                return None

            # Wait before first contact
            delay = get_first_contact_delay()
            logger.info(f'Waiting {delay:.0f}s before contacting @{username}')
            await asyncio.sleep(delay)

            greeting = (
                "Здравствуйте! Я Павел, буду помогать Вам разобраться в курсе по генеративному AI)"
            )

            await self._send_response_as_messages(entity.id, greeting)
            return entity.id

        except UsernameNotOccupiedError:
            logger.error(f'Username not found: @{username}')
            return None
        except FloodWaitError as e:
            logger.warning(f'Flood wait on greeting @{username}: sleeping {e.seconds}s (attempt {attempt+1})')
            await asyncio.sleep(e.seconds)
            return await self._send_greeting_internal(username, attempt + 1)
        except Exception as e:
            logger.error(f'Error greeting @{username}: {e}')
            return None

    async def run_forever(self):
        """Keep the client running."""
        await self.client.run_until_disconnected()

    async def stop(self):
        """Graceful shutdown."""
        self._running = False
        if self._greeting_task:
            self._greeting_task.cancel()
            try:
                await self._greeting_task
            except asyncio.CancelledError:
                pass
        if self.client.is_connected():
            await self.client.disconnect()
        logger.info(f'Userbot stopped. Message stats: {self._rate_limiter.stats}')
