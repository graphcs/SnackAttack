"""Main menu screen."""

import pygame
import os
from typing import Dict, Any, List, Optional
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

        # Images
        self.background_image: Optional[pygame.Surface] = None
        self.logo_image: Optional[pygame.Surface] = None
        self.menu_ui_image: Optional[pygame.Surface] = None
        self.button_images: Dict[str, Optional[pygame.Surface]] = {
            "1p_game": None,
            "2p_game": None,
            "settings": None,
            "quit": None
        }
        self.select_indicator: Optional[pygame.Surface] = None

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize menu when entering screen."""
        self.initialize_fonts()
        self._load_images()

        # Create menu items with proportional positioning
        center_x = self.screen_width // 2
        start_y = int(self.screen_height * 0.62) - 4

        # Calculate spacing based on button height + 10 pixel gap
        btn_height = 40  # Default height
        if self.button_images.get("1p_game"):
            btn_height = self.button_images["1p_game"].get_height()
        item_spacing = btn_height + 8

        self.menu_items = [
            MenuItem("1 Player vs AI", "1p_game", start_y),
            MenuItem("2 Players", "2p_game", start_y + item_spacing),
            MenuItem("Settings", "settings", start_y + item_spacing * 2),
            MenuItem("Quit", "quit", start_y + item_spacing * 3)
        ]

        self.selected_index = 0
        self.menu_items[0].selected = True

    def on_exit(self) -> None:
        """Clean up when leaving screen."""
        pass

    def _load_images(self) -> None:
        """Load background and logo images."""
        # Get the base directory
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(base_dir, "ui")

        # Load background image
        bg_path = os.path.join(ui_dir, "Home background.png")
        if os.path.exists(bg_path):
            self.background_image = pygame.image.load(bg_path).convert()
            self.background_image = pygame.transform.scale(
                self.background_image, (self.screen_width, self.screen_height)
            )

        # Load logo image
        logo_path = os.path.join(ui_dir, "logo.png")
        if os.path.exists(logo_path):
            self.logo_image = pygame.image.load(logo_path).convert_alpha()
            # Scale logo to fit in top half while maintaining aspect ratio
            logo_max_width = int(self.screen_width * 0.7)
            logo_max_height = int(self.screen_height * 0.35)
            logo_rect = self.logo_image.get_rect()
            scale = min(logo_max_width / logo_rect.width, logo_max_height / logo_rect.height)
            scale *= 1.2  # Make logo 1.2x bigger
            new_width = int(logo_rect.width * scale)
            new_height = int(logo_rect.height * scale)
            self.logo_image = pygame.transform.scale(self.logo_image, (new_width, new_height))

        # Load menu UI image
        menu_ui_path = os.path.join(ui_dir, "Menu ui.png")
        if os.path.exists(menu_ui_path):
            self.menu_ui_image = pygame.image.load(menu_ui_path).convert_alpha()
            # Scale to fit in lower portion while maintaining aspect ratio
            menu_ui_max_width = int(self.screen_width * 0.8)
            menu_ui_max_height = int(self.screen_height * 0.25)
            menu_ui_rect = self.menu_ui_image.get_rect()
            scale = min(menu_ui_max_width / menu_ui_rect.width, menu_ui_max_height / menu_ui_rect.height)
            scale *= 1.35  # Make menu UI 1.35x bigger
            new_width = int(menu_ui_rect.width * scale)
            new_height = int(menu_ui_rect.height * scale)
            self.menu_ui_image = pygame.transform.scale(self.menu_ui_image, (new_width, new_height))

        # Load button images
        button_files = {
            "1p_game": "1 play vs ai.png",
            "2p_game": "2 players.png",
            "settings": "settings button.png",
            "quit": "quit button.png"
        }
        button_scale = 0.576  # Scale factor for buttons
        for action, filename in button_files.items():
            btn_path = os.path.join(ui_dir, filename)
            if os.path.exists(btn_path):
                btn_img = pygame.image.load(btn_path).convert_alpha()
                new_width = int(btn_img.get_width() * button_scale)
                new_height = int(btn_img.get_height() * button_scale)
                self.button_images[action] = pygame.transform.scale(btn_img, (new_width, new_height))

        # Load select indicator image
        select_path = os.path.join(ui_dir, "Select.png")
        if os.path.exists(select_path):
            self.select_indicator = pygame.image.load(select_path).convert_alpha()
            # Scale to match button size
            new_width = int(self.select_indicator.get_width() * button_scale)
            new_height = int(self.select_indicator.get_height() * button_scale)
            self.select_indicator = pygame.transform.scale(self.select_indicator, (new_width, new_height))

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
        if self.background_image:
            surface.blit(self.background_image, (0, 0))
        else:
            surface.fill(self.bg_color)

        # Logo in top half
        if self.logo_image:
            logo_rect = self.logo_image.get_rect()
            logo_x = (self.screen_width - logo_rect.width) // 2
            logo_y = int(self.screen_height * 0.08)
            surface.blit(self.logo_image, (logo_x, logo_y))

        # Menu UI image (drawn before buttons so buttons appear on top)
        if self.menu_ui_image:
            menu_ui_rect = self.menu_ui_image.get_rect()
            menu_ui_x = (self.screen_width - menu_ui_rect.width) // 2
            menu_ui_y = int(self.screen_height * 0.50)
            surface.blit(self.menu_ui_image, (menu_ui_x, menu_ui_y))

        # Menu items (button images on top of menu UI)
        center_x = self.screen_width // 2

        for item in self.menu_items:
            btn_img = self.button_images.get(item.action)
            if btn_img:
                # Draw button image
                btn_rect = btn_img.get_rect()
                btn_x = center_x - btn_rect.width // 2
                btn_y = item.y_position - btn_rect.height // 2
                surface.blit(btn_img, (btn_x, btn_y))
                item.rect = pygame.Rect(btn_x, btn_y, btn_rect.width, btn_rect.height)

                # Draw selection indicator
                if item.selected and self.select_indicator:
                    # Draw select image to the left of the button
                    select_rect = self.select_indicator.get_rect()
                    select_x = btn_x - select_rect.width - 6
                    select_y = btn_y + (btn_rect.height - select_rect.height) // 2
                    surface.blit(self.select_indicator, (select_x, select_y))
            else:
                # Fallback to text if no image
                color = self.selected_color if item.selected else self.text_color
                if item.selected:
                    self.draw_text(surface, "> ", self.menu_font, color,
                                   (center_x - 120, item.y_position))
                item.rect = self.draw_text(surface, item.text, self.menu_font, color,
                                           (center_x, item.y_position))

        # Footer
        self.draw_text(surface, "Use Arrow Keys + Enter to select",
                       self.small_font, (150, 150, 150),
                       (self.screen_width // 2, self.screen_height - 60))

        # Version
        self.draw_text(surface, "v1.0", self.small_font, (100, 100, 100),
                       (self.screen_width - 50, self.screen_height - 30))
