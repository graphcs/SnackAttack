"""Game state machine for managing screen transitions."""

from enum import Enum, auto
from typing import Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..screens.base_screen import BaseScreen


class GameState(Enum):
    """All possible game states."""
    MAIN_MENU = auto()
    CHARACTER_SELECT = auto()
    GAMEPLAY = auto()
    TREAT_ATTACK = auto()  # New Treat Attack mode
    PAUSED = auto()
    SETTINGS = auto()
    GAME_OVER = auto()


class StateMachine:
    """Manages game state transitions and screen lifecycle."""

    def __init__(self):
        self._states: Dict[GameState, 'BaseScreen'] = {}
        self._current_state: Optional[GameState] = None
        self._previous_state: Optional[GameState] = None
        self._transition_data: Dict[str, Any] = {}

    def register_state(self, state: GameState, screen: 'BaseScreen') -> None:
        """Register a screen for a game state."""
        self._states[state] = screen

    def change_state(self, new_state: GameState, data: Dict[str, Any] = None) -> None:
        """
        Change to a new state.

        Args:
            new_state: The state to transition to
            data: Optional data to pass to the new state
        """
        # Exit current state
        if self._current_state is not None and self._current_state in self._states:
            self._states[self._current_state].on_exit()

        # Store transition data
        self._transition_data = data or {}

        # Update state tracking
        self._previous_state = self._current_state
        self._current_state = new_state

        # Enter new state
        if new_state in self._states:
            self._states[new_state].on_enter(self._transition_data)

    def get_current_screen(self) -> Optional['BaseScreen']:
        """Get the current screen instance."""
        if self._current_state is not None:
            return self._states.get(self._current_state)
        return None

    def get_current_state(self) -> Optional[GameState]:
        """Get the current state enum."""
        return self._current_state

    def get_previous_state(self) -> Optional[GameState]:
        """Get the previous state enum."""
        return self._previous_state

    def go_back(self) -> None:
        """Return to the previous state."""
        if self._previous_state is not None:
            self.change_state(self._previous_state)

    def get_transition_data(self) -> Dict[str, Any]:
        """Get data passed during the last transition."""
        return self._transition_data
