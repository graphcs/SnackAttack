"""Settings screen for audio and game options."""

import pygame
import os
from typing import Dict, Any, List, Optional
from .base_screen import BaseScreen
from ..core.state_machine import GameState
from ..core.event_bus import GameEvent


class SettingItem:
    """A settings menu item."""

    def __init__(self, name: str, setting_key: str, item_type: str,
                 y_position: int, current_value: Any):
        self.name = name
        self.setting_key = setting_key
        self.item_type = item_type  # "toggle" or "slider"
        self.y_position = y_position
        self.value = current_value
        self.selected = False
        self.rect: Optional[pygame.Rect] = None


class SettingsScreen(BaseScreen):
    """Settings screen for adjusting game options."""

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        self.settings_items: List[SettingItem] = []
        self.selected_index = 0

        # Colors
        self.bg_color = (20, 20, 40)
        self.title_color = (255, 200, 0)
        self.text_color = (77, 43, 31)  # #4D2B1F
        self.selected_color = (147, 76, 48)  # #934C30
        self.inactive_color = (100, 100, 100)

        # Images
        self.background_image: Optional[pygame.Surface] = None
        self.title_image: Optional[pygame.Surface] = None
        self.menu_tall_image: Optional[pygame.Surface] = None

        # Back button
        self.back_font: Optional[pygame.font.Font] = None
        self.back_button_rect: Optional[pygame.Rect] = None
        self.back_color = (77, 43, 31)  # #4D2B1F
        self.back_selected = False
        self.select_indicator: Optional[pygame.Surface] = None

        # Daydream font for footer (same size as main menu)
        self.daydream_font_small: Optional[pygame.font.Font] = None

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize settings screen."""
        self.initialize_fonts()
        self._load_custom_font()
        self._load_images()
        self._create_settings_items()
        self.selected_index = 0
        if self.settings_items:
            self.settings_items[0].selected = True

    def _load_custom_font(self) -> None:
        """Load custom Daydream font."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(base_dir, "ui")
        font_path = os.path.join(ui_dir, "Daydream.ttf")

        if os.path.exists(font_path):
            self.menu_font = pygame.font.Font(font_path, 28)
            self.small_font = pygame.font.Font(font_path, 20)
            self.back_font = pygame.font.Font(font_path, 32)
            self.daydream_font_small = pygame.font.Font(font_path, 18)

    def _load_images(self) -> None:
        """Load background and title images."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(base_dir, "ui")

        # Load background image
        bg_path = os.path.join(ui_dir, "Settings background.png")
        if os.path.exists(bg_path):
            self.background_image = pygame.image.load(bg_path).convert()
            self.background_image = pygame.transform.scale(
                self.background_image, (self.screen_width, self.screen_height)
            )

        # Load title image
        title_path = os.path.join(ui_dir, "settings text.png")
        if os.path.exists(title_path):
            self.title_image = pygame.image.load(title_path).convert_alpha()
            # Scale title appropriately
            title_max_width = int(self.screen_width * 0.6)
            title_max_height = int(self.screen_height * 0.12)
            title_rect = self.title_image.get_rect()
            scale = min(title_max_width / title_rect.width, title_max_height / title_rect.height)
            new_width = int(title_rect.width * scale)
            new_height = int(title_rect.height * scale)
            self.title_image = pygame.transform.scale(self.title_image, (new_width, new_height))

        # Load menu tall image
        menu_tall_path = os.path.join(ui_dir, "Menu tall.png")
        if os.path.exists(menu_tall_path):
            self.menu_tall_image = pygame.image.load(menu_tall_path).convert_alpha()
            # Scale to fit nicely
            menu_max_width = int(self.screen_width * 0.8)
            menu_max_height = int(self.screen_height * 0.7)
            menu_rect = self.menu_tall_image.get_rect()
            scale = min(menu_max_width / menu_rect.width, menu_max_height / menu_rect.height)
            new_width = int(menu_rect.width * scale)
            new_height = int(menu_rect.height * scale)
            self.menu_tall_image = pygame.transform.scale(self.menu_tall_image, (new_width, new_height))

        # Load select indicator image (same size as main menu)
        select_path = os.path.join(ui_dir, "Select.png")
        if os.path.exists(select_path):
            self.select_indicator = pygame.image.load(select_path).convert_alpha()
            # Scale to match main menu button size
            select_scale = 0.576
            new_width = int(self.select_indicator.get_width() * select_scale)
            new_height = int(self.select_indicator.get_height() * select_scale)
            self.select_indicator = pygame.transform.scale(self.select_indicator, (new_width, new_height))

    def _create_settings_items(self) -> None:
        """Create settings items with proportional positioning."""
        audio_config = self.config.get_config("audio_settings")

        start_y = int(self.screen_height * 0.38) + 24
        spacing = int(self.screen_height * 0.07)

        self.settings_items = [
            SettingItem(
                "Music",
                "music_enabled",
                "toggle",
                start_y,
                audio_config.get("music_enabled", True)
            ),
            SettingItem(
                "Sound Effects",
                "sfx_enabled",
                "toggle",
                start_y + spacing,
                audio_config.get("sfx_enabled", True)
            ),
            SettingItem(
                "Music Volume",
                "music_volume",
                "slider",
                start_y + spacing * 2,
                audio_config.get("music_volume", 0.6)
            ),
            SettingItem(
                "SFX Volume",
                "sfx_volume",
                "slider",
                start_y + spacing * 3,
                audio_config.get("sfx_volume", 0.8)
            ),
            SettingItem(
                "Master Volume",
                "master_volume",
                "slider",
                start_y + spacing * 4,
                audio_config.get("master_volume", 0.8)
            )
        ]

    def on_exit(self) -> None:
        """Save settings when leaving."""
        # Update config with current values
        for item in self.settings_items:
            self.config.update_audio_setting(item.setting_key, item.value)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self._move_selection(-1)
            elif event.key == pygame.K_DOWN:
                self._move_selection(1)
            elif event.key == pygame.K_LEFT:
                self._adjust_value(-1)
            elif event.key == pygame.K_RIGHT:
                self._adjust_value(1)
            elif event.key == pygame.K_RETURN:
                if self.back_selected:
                    self.state_machine.change_state(GameState.MAIN_MENU)
                else:
                    self._toggle_value()
            elif event.key == pygame.K_ESCAPE:
                self.state_machine.change_state(GameState.MAIN_MENU)

        elif event.type == pygame.MOUSEMOTION:
            # Check hover on settings items
            hovered_item = False
            for i, item in enumerate(self.settings_items):
                if item.rect and item.rect.collidepoint(event.pos):
                    hovered_item = True
                    if self.selected_index != i or self.back_selected:
                        # Deselect previous item
                        if self.back_selected:
                            self.back_selected = False
                        elif self.selected_index < len(self.settings_items):
                            self.settings_items[self.selected_index].selected = False
                        # Select new item
                        self.selected_index = i
                        item.selected = True
                    break

            # Handle hover on back button
            if not hovered_item and self.back_button_rect and self.back_button_rect.collidepoint(event.pos):
                if not self.back_selected:
                    # Deselect current settings item
                    if self.settings_items and self.selected_index < len(self.settings_items):
                        self.settings_items[self.selected_index].selected = False
                    self.back_selected = True
            elif not hovered_item and self.back_selected:
                # Deselect back button when mouse moves away (but not to a settings item)
                self.back_selected = False
                # Reselect the current settings item
                if self.settings_items and self.selected_index < len(self.settings_items):
                    self.settings_items[self.selected_index].selected = True

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                if self.back_button_rect and self.back_button_rect.collidepoint(event.pos):
                    self.state_machine.change_state(GameState.MAIN_MENU)

    def _move_selection(self, direction: int) -> None:
        """Move menu selection up or down."""
        total_items = len(self.settings_items) + 1  # +1 for back button

        # Deselect current item
        if self.back_selected:
            self.back_selected = False
        elif self.settings_items:
            self.settings_items[self.selected_index].selected = False

        # Calculate new index (back button is at index len(settings_items))
        current = len(self.settings_items) if self.back_selected else self.selected_index
        new_index = (current + direction) % total_items

        # Select new item
        if new_index == len(self.settings_items):
            self.back_selected = True
        else:
            self.selected_index = new_index
            self.settings_items[self.selected_index].selected = True

        # Play select sound
        self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "select"})

    def _adjust_value(self, direction: int) -> None:
        """Adjust the current setting value."""
        if not self.settings_items:
            return

        item = self.settings_items[self.selected_index]

        if item.item_type == "toggle":
            item.value = not item.value
        elif item.item_type == "slider":
            step = 0.1
            item.value = max(0.0, min(1.0, item.value + direction * step))
            item.value = round(item.value, 1)

    def _toggle_value(self) -> None:
        """Toggle the current setting (for toggle items)."""
        if not self.settings_items:
            return

        item = self.settings_items[self.selected_index]
        if item.item_type == "toggle":
            item.value = not item.value

    def update(self, dt: float) -> None:
        """Update settings screen."""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """Render the settings screen with proportional positioning."""
        # Background
        if self.background_image:
            surface.blit(self.background_image, (0, 0))
        else:
            surface.fill(self.bg_color)

        # Menu tall image (drawn under the title)
        menu_bottom_y = 0
        if self.menu_tall_image:
            menu_rect = self.menu_tall_image.get_rect()
            menu_x = (self.screen_width - menu_rect.width) // 2
            menu_y = int(self.screen_height * 0.22)
            surface.blit(self.menu_tall_image, (menu_x, menu_y))
            menu_bottom_y = menu_y + menu_rect.height

        # Back button (same position as character select screen)
        if self.back_font:
            back_y = int(self.screen_height * 0.92) - 40
            back_text_color = self.selected_color if self.back_selected else self.back_color
            self.back_button_rect = self.draw_text(surface, "Back", self.back_font, back_text_color,
                                                    (self.screen_width // 2, back_y))

            # Draw select indicator when back is selected
            if self.back_selected and self.select_indicator and self.back_button_rect:
                select_rect = self.select_indicator.get_rect()
                select_x = self.back_button_rect.left - select_rect.width - 6
                select_y = self.back_button_rect.centery - select_rect.height // 2
                surface.blit(self.select_indicator, (select_x, select_y))

        # Title image
        if self.title_image:
            title_rect = self.title_image.get_rect()
            title_x = (self.screen_width - title_rect.width) // 2
            title_y = int(self.screen_height * 0.12)
            surface.blit(self.title_image, (title_x, title_y))

        # Settings items
        for item in self.settings_items:
            self._render_setting_item(surface, item)

        # Instructions - same as main menu
        footer_font = self.daydream_font_small if self.daydream_font_small else self.small_font
        self.draw_text(surface, "Arrow Keys + Enter to Select",
                       footer_font, (147, 76, 48),
                       (self.screen_width // 2, self.screen_height - 40))

    def _render_setting_item(self, surface: pygame.Surface, item: SettingItem) -> None:
        """Render a single setting item with proportional positioning."""
        # Selection indicator
        if item.selected:
            color = self.selected_color
        else:
            color = self.text_color

        # Item name with proportional positioning
        name_x = int(self.screen_width * 0.22)  # Moved slightly right
        text_rect = self.draw_text(surface, item.name, self.menu_font, color,
                       (name_x, item.y_position), center=False)
        # Create a wider hover area that covers the whole row
        item.rect = pygame.Rect(name_x, item.y_position - 15, int(self.screen_width * 0.65), 40)

        # Value display with proportional positioning
        value_x = int(self.screen_width * 0.62)

        if item.item_type == "toggle":
            value_text = "ON" if item.value else "OFF"
            value_color = (81, 180, 71) if item.value else (222, 97, 91)  # ON: #51B447, OFF: #DE615B
            self.draw_text(surface, value_text, self.menu_font, value_color,
                           (value_x, item.y_position), center=False)

        elif item.item_type == "slider":
            # Draw slider background with proportional width
            slider_width = int(self.screen_width * 0.18)
            slider_height = 20
            slider_x = value_x
            slider_y = item.y_position - slider_height // 2 + 24

            # Background
            pygame.draw.rect(surface, (220, 165, 86),  # #DCA556
                             (slider_x, slider_y, slider_width, slider_height), border_radius=4)

            # Fill
            fill_width = int(slider_width * item.value)
            if fill_width > 0:
                pygame.draw.rect(surface, color,
                                 (slider_x, slider_y, fill_width, slider_height), border_radius=4)

            # Border
            pygame.draw.rect(surface, color,
                             (slider_x, slider_y, slider_width, slider_height), 2, border_radius=4)
