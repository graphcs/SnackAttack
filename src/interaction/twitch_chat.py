"""Twitch chat integration for audience voting."""

import asyncio
import threading
import pygame
from typing import Optional

# Custom pygame event type for Twitch votes
TWITCH_VOTE_EVENT = pygame.USEREVENT + 100


class TwitchChatManager:
    """Bridges Twitch chat with the game's voting system.

    Uses a background thread to run the async TwitchIO event loop,
    posting pygame events when votes are received.
    """

    def __init__(self, channel: str, token: str):
        """Initialize the Twitch chat manager.

        Args:
            channel: The Twitch channel to connect to
            token: OAuth token (format: 'oauth:xxxxx' or just the token)
        """
        self.channel = channel
        # Ensure token has oauth: prefix for twitchio 2.x
        self.token = token if token.startswith('oauth:') else f'oauth:{token}'
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.bot = None
        self.connected = False
        self.error_message: Optional[str] = None

    def start(self) -> bool:
        """Start the Twitch connection in a background thread.

        Returns:
            True if connection started successfully, False otherwise.
        """
        try:
            self.thread = threading.Thread(target=self._run_bot, daemon=True)
            self.thread.start()

            # Wait for connection (up to 5 seconds)
            import time
            for _ in range(50):
                time.sleep(0.1)
                if self.connected:
                    return True
                if self.error_message:
                    return False

            # Timeout
            if not self.connected:
                self.error_message = "Connection timeout"
            return self.connected

        except Exception as e:
            self.error_message = str(e)
            return False

    def _run_bot(self) -> None:
        """Run the bot in a background thread."""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # Create bot instance
            self.bot = _VotingBot(
                token=self.token,
                channel=self.channel,
                on_ready_callback=self._on_ready,
                on_error_callback=self._on_error
            )

            self.loop.run_until_complete(self.bot.start())

        except Exception as e:
            self.error_message = str(e)
            self.connected = False

    def _on_ready(self) -> None:
        """Called when bot successfully connects."""
        self.connected = True

    def _on_error(self, error: str) -> None:
        """Called when an error occurs."""
        self.error_message = error

    def stop(self) -> None:
        """Stop the Twitch connection."""
        if self.bot and self.loop and self.loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.bot.close(), self.loop
                )
                future.result(timeout=2)
            except Exception:
                pass
        self.connected = False

    def is_connected(self) -> bool:
        """Check if currently connected to Twitch."""
        return self.connected

    def get_error(self) -> Optional[str]:
        """Get the last error message, if any."""
        return self.error_message


class _VotingBot:
    """Internal TwitchIO bot for handling vote commands."""

    def __init__(self, token: str, channel: str, on_ready_callback=None, on_error_callback=None):
        self.token = token
        self.channel = channel
        self.on_ready_callback = on_ready_callback
        self.on_error_callback = on_error_callback
        self._bot = None

    async def start(self) -> None:
        """Start the bot."""
        from twitchio.ext import commands

        manager = self  # Reference for inner class

        class BotImpl(commands.Bot):
            def __init__(bot_self):
                super().__init__(
                    token=manager.token,
                    prefix='!',
                    initial_channels=[manager.channel]
                )

            async def event_ready(bot_self):
                print(f'Twitch bot connected as {bot_self.nick}')
                print(f'Joined: {bot_self.connected_channels}')
                if manager.on_ready_callback:
                    manager.on_ready_callback()

            async def event_message(bot_self, message):
                # Ignore our own messages
                if message.echo:
                    return

                # Check for vote commands
                content = message.content.strip().lower()
                author_name = message.author.name if message.author else "anonymous"

                if content == '!extend':
                    pygame.event.post(pygame.event.Event(
                        TWITCH_VOTE_EVENT,
                        vote_type="extend",
                        voter_id=author_name
                    ))
                elif content == '!yank':
                    pygame.event.post(pygame.event.Event(
                        TWITCH_VOTE_EVENT,
                        vote_type="yank",
                        voter_id=author_name
                    ))

            async def event_error(bot_self, error, data=None):
                print(f'Twitch error: {error}')
                if manager.on_error_callback:
                    manager.on_error_callback(str(error))

        self._bot = BotImpl()
        await self._bot.start()

    async def close(self) -> None:
        """Close the bot connection."""
        if self._bot:
            await self._bot.close()
