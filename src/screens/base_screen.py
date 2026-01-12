"""Base screen class for all game screens."""

import pygame
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.state_machine import StateMachine
    from ..core.config_manager import ConfigManager
    from ..core.event_bus import EventBus


# Display dimensions - wider for chat simulator panel
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 1000
GAME_AREA_WIDTH = 1000  # Main game area width (two arenas side by side)


class BaseScreen(ABC):
    """Abstract base class for all game screens."""

    def __init__(self, state_machine: 'StateMachine', config: 'ConfigManager',
                 event_bus: 'EventBus'):
        """
        Initialize the screen.

        Args:
            state_machine: Game state machine for screen transitions
            config: Configuration manager
            event_bus: Event bus for game-wide communication
        """
        self.state_machine = state_machine
        self.config = config
        self.event_bus = event_bus

        # Screen dimensions - full resolution for detailed pixel art
        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT

        # Common fonts
        self.title_font: Optional[pygame.font.Font] = None
        self.menu_font: Optional[pygame.font.Font] = None
        self.small_font: Optional[pygame.font.Font] = None

    def initialize_fonts(self) -> None:
        """Initialize fonts. Call after pygame.init()."""
        self.title_font = pygame.font.Font(None, 72)
        self.menu_font = pygame.font.Font(None, 42)
        self.small_font = pygame.font.Font(None, 28)

    @abstractmethod
    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Called when transitioning to this screen."""
        pass

    @abstractmethod
    def on_exit(self) -> None:
        """Called when transitioning away from this screen."""
        pass

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle pygame events."""
        pass

    @abstractmethod
    def update(self, dt: float) -> None:
        """Update screen state."""
        pass

    @abstractmethod
    def render(self, surface: pygame.Surface) -> None:
        """Render the screen."""
        pass

    def draw_text(self, surface: pygame.Surface, text: str, font: pygame.font.Font,
                  color: tuple, position: tuple, center: bool = True) -> pygame.Rect:
        """
        Draw text on surface.

        Args:
            surface: Surface to draw on
            text: Text to draw
            font: Font to use
            color: Text color
            position: Position (x, y)
            center: If True, center text at position

        Returns:
            Rectangle of the rendered text
        """
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()

        if center:
            text_rect.center = position
        else:
            text_rect.topleft = position

        surface.blit(text_surface, text_rect)
        return text_rect
