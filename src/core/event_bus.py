"""Event bus for pub/sub communication between game systems."""

from enum import Enum, auto
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
import time


class GameEvent(Enum):
    """All game events."""
    # Gameplay Events
    SNACK_SPAWNED = auto()
    SNACK_COLLECTED = auto()
    SNACK_DESPAWNED = auto()

    # Effect Events
    POWERUP_ACTIVATED = auto()
    POWERUP_EXPIRED = auto()
    PENALTY_APPLIED = auto()
    CHAOS_TRIGGERED = auto()
    CHAOS_ENDED = auto()

    # Score Events
    SCORE_CHANGED = auto()

    # Game Flow Events
    GAME_START = auto()
    ROUND_START = auto()
    ROUND_END = auto()
    LEVEL_COMPLETE = auto()
    GAME_OVER = auto()
    GAME_PAUSED = auto()
    GAME_RESUMED = auto()

    # Player Events
    PLAYER_COLLISION = auto()
    PLAYER_MOVED = auto()

    # UI Events
    SCREEN_TRANSITION = auto()
    SETTINGS_CHANGED = auto()

    # Audio Events
    PLAY_SOUND = auto()
    PLAY_MUSIC = auto()
    STOP_MUSIC = auto()


@dataclass
class EventData:
    """Container for event data."""
    event_type: GameEvent
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "system"


@dataclass
class EventListener:
    """Container for event listener info."""
    callback: Callable[[EventData], None]
    priority: int = 0


class EventBus:
    """Singleton event bus for game-wide pub/sub communication."""

    _instance: Optional['EventBus'] = None

    def __new__(cls) -> 'EventBus':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._listeners: Dict[GameEvent, List[EventListener]] = {}
            cls._instance._queued_events: List[EventData] = []
        return cls._instance

    def subscribe(self, event_type: GameEvent, callback: Callable[[EventData], None],
                  priority: int = 0) -> None:
        """
        Register a listener for an event type.
        Higher priority listeners are called first.
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []

        listener = EventListener(callback=callback, priority=priority)
        self._listeners[event_type].append(listener)
        # Sort by priority (higher first)
        self._listeners[event_type].sort(key=lambda x: x.priority, reverse=True)

    def unsubscribe(self, event_type: GameEvent, callback: Callable) -> None:
        """Remove a listener."""
        if event_type in self._listeners:
            self._listeners[event_type] = [
                l for l in self._listeners[event_type]
                if l.callback != callback
            ]

    def emit(self, event_type: GameEvent, payload: Dict[str, Any] = None,
             source: str = "system") -> None:
        """Emit an event immediately to all listeners."""
        event = EventData(
            event_type=event_type,
            payload=payload or {},
            source=source
        )

        if event_type in self._listeners:
            for listener in self._listeners[event_type]:
                try:
                    listener.callback(event)
                except Exception as e:
                    print(f"Error in event listener for {event_type}: {e}")

    def queue_event(self, event_type: GameEvent, payload: Dict[str, Any] = None,
                    source: str = "system") -> None:
        """Queue an event for deferred processing."""
        event = EventData(
            event_type=event_type,
            payload=payload or {},
            source=source
        )
        self._queued_events.append(event)

    def process_queue(self) -> None:
        """Process all queued events (call this each frame)."""
        events_to_process = self._queued_events.copy()
        self._queued_events.clear()

        for event in events_to_process:
            if event.event_type in self._listeners:
                for listener in self._listeners[event.event_type]:
                    try:
                        listener.callback(event)
                    except Exception as e:
                        print(f"Error processing queued event {event.event_type}: {e}")

    def clear_all(self) -> None:
        """Clear all listeners and queued events."""
        self._listeners.clear()
        self._queued_events.clear()

    def clear_listeners(self, event_type: GameEvent) -> None:
        """Clear all listeners for a specific event type."""
        if event_type in self._listeners:
            self._listeners[event_type].clear()
