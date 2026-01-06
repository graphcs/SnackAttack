"""Settings screen for audio and game options."""

import pygame
from typing import Dict, Any, List
from .base_screen import BaseScreen
from ..core.state_machine import GameState


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


class SettingsScreen(BaseScreen):
    """Settings screen for adjusting game options."""

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        self.settings_items: List[SettingItem] = []
        self.selected_index = 0

        # Colors
        self.bg_color = (20, 20, 40)
        self.title_color = (255, 200, 0)
        self.text_color = (255, 255, 255)
        self.selected_color = (255, 200, 0)
        self.inactive_color = (100, 100, 100)

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize settings screen."""
        self.initialize_fonts()
        self._create_settings_items()
        self.selected_index = 0
        if self.settings_items:
            self.settings_items[0].selected = True

    def _create_settings_items(self) -> None:
        """Create settings items for 960x720 display."""
        audio_config = self.config.get_config("audio_settings")

        start_y = 200
        spacing = 80  # Spacing for 960x720

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
                self._toggle_value()
            elif event.key == pygame.K_ESCAPE:
                self.state_machine.change_state(GameState.MAIN_MENU)

    def _move_selection(self, direction: int) -> None:
        """Move menu selection up or down."""
        if self.settings_items:
            self.settings_items[self.selected_index].selected = False
            self.selected_index = (self.selected_index + direction) % len(self.settings_items)
            self.settings_items[self.selected_index].selected = True

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
        """Render the settings screen for 960x720 display."""
        surface.fill(self.bg_color)

        # Title
        self.draw_text(surface, "SETTINGS", self.title_font, self.title_color,
                       (self.screen_width // 2, 80))

        # Settings items
        for item in self.settings_items:
            self._render_setting_item(surface, item)

        # Instructions
        self.draw_text(surface, "Up/Down to Navigate, Left/Right to Adjust",
                       self.small_font, (150, 150, 150),
                       (self.screen_width // 2, self.screen_height - 60))
        self.draw_text(surface, "Press ESC to Save and Return",
                       self.small_font, (150, 150, 150),
                       (self.screen_width // 2, self.screen_height - 30))

    def _render_setting_item(self, surface: pygame.Surface, item: SettingItem) -> None:
        """Render a single setting item for 960x720."""
        # Selection indicator
        if item.selected:
            indicator = "> "
            color = self.selected_color
        else:
            indicator = "  "
            color = self.text_color

        # Item name
        name_x = 200
        self.draw_text(surface, f"{indicator}{item.name}", self.menu_font, color,
                       (name_x, item.y_position), center=False)

        # Value display
        value_x = 550

        if item.item_type == "toggle":
            value_text = "ON" if item.value else "OFF"
            value_color = (100, 255, 100) if item.value else (255, 100, 100)
            self.draw_text(surface, value_text, self.menu_font, value_color,
                           (value_x, item.y_position), center=False)

        elif item.item_type == "slider":
            # Draw slider background
            slider_width = 200
            slider_height = 20
            slider_x = value_x
            slider_y = item.y_position - slider_height // 2

            # Background
            pygame.draw.rect(surface, (60, 60, 80),
                             (slider_x, slider_y, slider_width, slider_height), border_radius=4)

            # Fill
            fill_width = int(slider_width * item.value)
            if fill_width > 0:
                pygame.draw.rect(surface, color,
                                 (slider_x, slider_y, fill_width, slider_height), border_radius=4)

            # Border
            pygame.draw.rect(surface, color,
                             (slider_x, slider_y, slider_width, slider_height), 2, border_radius=4)

            # Value percentage
            percentage = f"{int(item.value * 100)}%"
            self.draw_text(surface, percentage, self.menu_font, color,
                           (slider_x + slider_width + 20, item.y_position), center=False)
