"""Main menu screen."""

import pygame
from typing import Dict, Any, List
from .base_screen import BaseScreen
from ..core.state_machine import GameState


class MenuItem:
    """A menu item that can be selected."""

    def __init__(self, text: str, action: str, y_position: int):
        self.text = text
        self.action = action
        self.y_position = y_position
        self.rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.selected = False


class MainMenuScreen(BaseScreen):
    """Main menu screen with game mode selection."""

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        self.menu_items: List[MenuItem] = []
        self.selected_index = 0

        # Colors
        self.bg_color = (20, 20, 40)
        self.title_color = (255, 200, 0)
        self.text_color = (255, 255, 255)
        self.selected_color = (255, 200, 0)

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize menu when entering screen."""
        self.initialize_fonts()

        # Create menu items
        center_x = self.screen_width // 2
        start_y = 340

        self.menu_items = [
            MenuItem("1 Player vs AI", "1p_game", start_y),
            MenuItem("2 Players", "2p_game", start_y + 70),
            MenuItem("Settings", "settings", start_y + 140),
            MenuItem("Quit", "quit", start_y + 210)
        ]

        self.selected_index = 0
        self.menu_items[0].selected = True

    def on_exit(self) -> None:
        """Clean up when leaving screen."""
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self._move_selection(-1)
            elif event.key == pygame.K_DOWN:
                self._move_selection(1)
            elif event.key == pygame.K_RETURN:
                self._activate_selection()
            elif event.key == pygame.K_ESCAPE:
                # Quit on escape from main menu
                pygame.event.post(pygame.event.Event(pygame.QUIT))

        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_hover(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                self._handle_mouse_click(event.pos)

    def _move_selection(self, direction: int) -> None:
        """Move menu selection up or down."""
        self.menu_items[self.selected_index].selected = False
        self.selected_index = (self.selected_index + direction) % len(self.menu_items)
        self.menu_items[self.selected_index].selected = True

    def _handle_mouse_hover(self, pos: tuple) -> None:
        """Handle mouse hover over menu items."""
        for i, item in enumerate(self.menu_items):
            if item.rect.collidepoint(pos):
                if self.selected_index != i:
                    self.menu_items[self.selected_index].selected = False
                    self.selected_index = i
                    item.selected = True
                break

    def _handle_mouse_click(self, pos: tuple) -> None:
        """Handle mouse click on menu items."""
        for item in self.menu_items:
            if item.rect.collidepoint(pos):
                self._activate_selection()
                break

    def _activate_selection(self) -> None:
        """Activate the currently selected menu item."""
        action = self.menu_items[self.selected_index].action

        if action == "1p_game":
            self.state_machine.change_state(GameState.CHARACTER_SELECT,
                                            {"mode": "1p", "vs_ai": True})
        elif action == "2p_game":
            self.state_machine.change_state(GameState.CHARACTER_SELECT,
                                            {"mode": "2p", "vs_ai": False})
        elif action == "settings":
            self.state_machine.change_state(GameState.SETTINGS)
        elif action == "quit":
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def update(self, dt: float) -> None:
        """Update menu state."""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """Render the main menu."""
        # Background
        surface.fill(self.bg_color)

        # Title
        self.draw_text(surface, "JAZZY'S", self.title_font, self.title_color,
                       (self.screen_width // 2, 120))
        self.draw_text(surface, "SNACK ATTACK", self.title_font, self.title_color,
                       (self.screen_width // 2, 200))

        # Subtitle
        self.draw_text(surface, "Collect snacks, avoid broccoli!", self.small_font,
                       self.text_color, (self.screen_width // 2, 270))

        # Menu items
        center_x = self.screen_width // 2

        for item in self.menu_items:
            color = self.selected_color if item.selected else self.text_color

            # Draw selection indicator
            if item.selected:
                indicator_text = "> "
                self.draw_text(surface, indicator_text, self.menu_font, color,
                               (center_x - 120, item.y_position))

            # Draw menu text
            item.rect = self.draw_text(surface, item.text, self.menu_font, color,
                                       (center_x, item.y_position))

        # Footer
        self.draw_text(surface, "Use Arrow Keys + Enter to select",
                       self.small_font, (150, 150, 150),
                       (self.screen_width // 2, self.screen_height - 60))

        # Version
        self.draw_text(surface, "v1.0", self.small_font, (100, 100, 100),
                       (self.screen_width - 50, self.screen_height - 30))
