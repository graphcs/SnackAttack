"""Avatar showcase screen — hero display for a selected dog character."""

import pygame
import os
import math
from typing import Dict, Any, Optional, List
from .base_screen import BaseScreen
from ..core.state_machine import GameState
from ..core.event_bus import GameEvent
from ..sprites.sprite_sheet_loader import SpriteSheetLoader


class AvatarShowcaseScreen(BaseScreen):
    """Full-screen hero showcase for a dog character with animated sprites and stats."""

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        # Character data
        self.character_config: Dict[str, Any] = {}
        self.character_id: str = ""
        self.character_name: str = ""
        self.is_custom: bool = False

        # Images
        self.background_image: Optional[pygame.Surface] = None
        self.portrait: Optional[pygame.Surface] = None
        self.run_frames: List[pygame.Surface] = []
        self.eat_frames: List[pygame.Surface] = []

        # Fonts
        self.daydream_font_huge: Optional[pygame.font.Font] = None
        self.daydream_font_large: Optional[pygame.font.Font] = None
        self.daydream_font: Optional[pygame.font.Font] = None
        self.daydream_font_small: Optional[pygame.font.Font] = None
        self.daydream_font_tiny: Optional[pygame.font.Font] = None

        # Animation state
        self.run_frame_index: int = 0
        self.eat_frame_index: int = 0
        self.anim_timer: float = 0.0
        self.run_frame_duration: float = 0.12
        self.eat_frame_duration: float = 0.15

        # Visual effects
        self.time_elapsed: float = 0.0
        self.glow_alpha: float = 0.0
        self.entrance_progress: float = 0.0  # 0→1 over first second

        # UI elements
        self.select_indicator: Optional[pygame.Surface] = None
        self.menu_bar_image: Optional[pygame.Surface] = None
        self.back_rect: Optional[pygame.Rect] = None
        self.back_hovered: bool = False

        # Colors
        self.bg_color = (15, 12, 30)
        self.accent_color = (255, 200, 60)
        self.text_color = (255, 255, 255)
        self.stat_bar_bg = (40, 35, 60)
        self.stat_bar_fill = (255, 200, 60)
        self.subtitle_color = (180, 160, 120)

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize showcase with character data."""
        self.initialize_fonts()
        self._load_custom_font()
        self._load_ui_assets()

        data = data or {}
        self.character_config = data.get("character", {})
        self.character_id = self.character_config.get("id", "jazzy")
        self.character_name = self.character_config.get("display_name",
                              self.character_config.get("name", "Unknown"))
        self.is_custom = self.character_config.get("custom", False)

        # Reset animation
        self.time_elapsed = 0.0
        self.entrance_progress = 0.0
        self.run_frame_index = 0
        self.eat_frame_index = 0
        self.anim_timer = 0.0

        # Load sprites
        self._load_sprites()

    def on_exit(self) -> None:
        pass

    def _load_custom_font(self) -> None:
        """Load Daydream font at various sizes."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        font_path = os.path.join(base_dir, "ui", "Daydream.ttf")

        if os.path.exists(font_path):
            self.daydream_font_huge = pygame.font.Font(font_path, 52)
            self.daydream_font_large = pygame.font.Font(font_path, 32)
            self.daydream_font = pygame.font.Font(font_path, 22)
            self.daydream_font_small = pygame.font.Font(font_path, 16)
            self.daydream_font_tiny = pygame.font.Font(font_path, 12)

    def _load_ui_assets(self) -> None:
        """Load background, indicators, etc."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(base_dir, "ui")

        # Background — use choose your dog or win screen background
        bg_path = os.path.join(ui_dir, "Choose your dog background.png")
        if os.path.exists(bg_path):
            self.background_image = pygame.image.load(bg_path).convert()
            self.background_image = pygame.transform.scale(
                self.background_image, (self.screen_width, self.screen_height)
            )

        # Select indicator
        select_path = os.path.join(ui_dir, "Select.png")
        if os.path.exists(select_path):
            self.select_indicator = pygame.image.load(select_path).convert_alpha()
            scale = 0.576
            w = int(self.select_indicator.get_width() * scale)
            h = int(self.select_indicator.get_height() * scale)
            self.select_indicator = pygame.transform.scale(self.select_indicator, (w, h))

    def _load_sprites(self) -> None:
        """Load character portrait and animation frames."""
        loader = SpriteSheetLoader()

        # Portrait (large for showcase)
        self.portrait = loader.get_portrait(self.character_id)

        # Run animation frames
        self.run_frames = loader.get_animation_frames(
            self.character_id, 'run', facing_right=True)

        # Eat animation frames
        self.eat_frames = loader.get_animation_frames(
            self.character_id, 'eat', facing_right=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input — back navigation."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_BACKSPACE):
                self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "select"})
                self.state_machine.change_state(GameState.CHARACTER_SELECT)

        elif event.type == pygame.MOUSEMOTION:
            if self.back_rect and self.back_rect.collidepoint(event.pos):
                self.back_hovered = True
            else:
                self.back_hovered = False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.back_rect and self.back_rect.collidepoint(event.pos):
                    self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "select"})
                    self.state_machine.change_state(GameState.CHARACTER_SELECT)

    def update(self, dt: float) -> None:
        """Update animations and effects."""
        self.time_elapsed += dt

        # Entrance animation (first 0.8s)
        if self.entrance_progress < 1.0:
            self.entrance_progress = min(1.0, self.entrance_progress + dt / 0.8)

        # Glow pulsing
        self.glow_alpha = 0.5 + 0.5 * math.sin(self.time_elapsed * 2.0)

        # Sprite animation
        self.anim_timer += dt
        if self.run_frames and self.anim_timer >= self.run_frame_duration:
            self.anim_timer -= self.run_frame_duration
            self.run_frame_index = (self.run_frame_index + 1) % len(self.run_frames)
        if self.eat_frames:
            self.eat_frame_index = int(self.time_elapsed / self.eat_frame_duration) % len(self.eat_frames)

    def render(self, surface: pygame.Surface) -> None:
        """Render the hero showcase screen."""
        # --- Background ---
        if self.background_image:
            # Darken the background for dramatic effect
            surface.blit(self.background_image, (0, 0))
            overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            surface.blit(overlay, (0, 0))
        else:
            surface.fill(self.bg_color)

        cx = self.screen_width // 2
        ease = self._ease_out_back(self.entrance_progress)

        # --- Spotlight / radial glow behind portrait ---
        glow_radius = int(220 + 20 * self.glow_alpha)
        glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        glow_center = (glow_radius, glow_radius)
        for r in range(glow_radius, 0, -3):
            alpha = int(40 * (r / glow_radius) * self.glow_alpha)
            color = (255, 200, 60, alpha)
            pygame.draw.circle(glow_surface, color, glow_center, r)
        portrait_cy = int(self.screen_height * 0.32)
        surface.blit(glow_surface, (cx - glow_radius, portrait_cy - glow_radius))

        # --- Large portrait (hero shot) ---
        if self.portrait:
            # Scale portrait big for showcase (280x280)
            showcase_size = 280
            big_portrait = pygame.transform.smoothscale(
                self.portrait, (showcase_size, showcase_size))

            # Entrance: slide up + scale
            offset_y = int((1.0 - ease) * 60)
            portrait_x = cx - showcase_size // 2
            portrait_y = portrait_cy - showcase_size // 2 + offset_y

            surface.blit(big_portrait, (portrait_x, portrait_y))

            # Golden border around portrait
            border_rect = pygame.Rect(portrait_x - 4, portrait_y - 4,
                                      showcase_size + 8, showcase_size + 8)
            border_alpha = int(180 + 75 * self.glow_alpha)
            border_color = (255, 200, 60)
            pygame.draw.rect(surface, border_color, border_rect, 4, border_radius=16)

        # --- Character name (huge, centered above portrait) ---
        if self.daydream_font_huge:
            name_y = int(self.screen_height * 0.06)
            name_offset = int((1.0 - ease) * -40)
            self.draw_text(surface, self.character_name.upper(),
                           self.daydream_font_huge, self.accent_color,
                           (cx, name_y + name_offset))

        # --- Breed / subtitle ---
        breed = self.character_config.get("breed", "")
        # For custom dogs, show a short breed label instead of the full AI description
        if self.is_custom and len(breed) > 40:
            breed = "Custom Champion"
        if breed and self.daydream_font_small:
            breed_y = int(self.screen_height * 0.14)
            self.draw_text(surface, breed, self.daydream_font_small,
                           self.subtitle_color, (cx, breed_y))

        # --- Star decoration ---
        if self.daydream_font_tiny:
            star_y = int(self.screen_height * 0.19)
            stars = "★  ★  ★  ★  ★"
            self.draw_text(surface, stars, self.daydream_font,
                           self.accent_color, (cx, star_y))

        # --- Stats panel (below portrait) ---
        stats_top = int(self.screen_height * 0.56)
        self._render_stats_panel(surface, cx, stats_top, ease)

        # --- Animated sprite previews (bottom area) ---
        preview_y = int(self.screen_height * 0.82)
        self._render_animation_previews(surface, cx, preview_y)

        # --- Back button ---
        if self.daydream_font:
            back_y = int(self.screen_height * 0.94)
            back_color = (147, 76, 48) if not self.back_hovered else (200, 120, 70)
            self.back_rect = self.draw_text(surface, "Back",
                                            self.daydream_font, back_color,
                                            (cx, back_y))
            if self.back_hovered and self.select_indicator and self.back_rect:
                sr = self.select_indicator.get_rect()
                sx = self.back_rect.left - sr.width - 6
                sy = self.back_rect.centery - sr.height // 2
                surface.blit(self.select_indicator, (sx, sy))

        # --- Footer ---
        if self.daydream_font_tiny:
            self.draw_text(surface, "Press ESC or Enter to go back",
                           self.daydream_font_tiny, (100, 80, 60),
                           (cx, self.screen_height - 20))

    def _render_stats_panel(self, surface: pygame.Surface,
                            cx: int, top_y: int, ease: float) -> None:
        """Render the stats panel with animated bars."""
        # Panel background
        panel_w = 500
        panel_h = 200
        panel_x = cx - panel_w // 2
        panel_y = top_y

        # Slide-in from bottom
        offset_y = int((1.0 - ease) * 80)
        panel_y += offset_y

        # Semi-transparent panel
        panel_surface = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surface.fill((20, 15, 40, 180))
        pygame.draw.rect(panel_surface, (255, 200, 60, 120),
                         (0, 0, panel_w, panel_h), 2, border_radius=12)
        surface.blit(panel_surface, (panel_x, panel_y))

        # Stat definitions
        speed = self.character_config.get("base_speed", 1.0)
        # Normalize speed to 0-1 range (speeds typically range 0.8–1.3)
        speed_pct = max(0.0, min(1.0, (speed - 0.6) / 0.8))

        stats = [
            ("Speed", speed_pct),
            ("Agility", min(1.0, speed_pct * 0.9 + 0.1)),
            ("Appetite", 0.85 if not self.is_custom else 0.75),
            ("Charm", 1.0 if self.is_custom else 0.7),
        ]

        bar_x = panel_x + 140
        bar_w = 300
        bar_h = 18
        spacing = 42

        font = self.daydream_font_small or self.small_font
        for i, (label, value) in enumerate(stats):
            y = panel_y + 25 + i * spacing

            # Animate stat bars filling in
            fill_progress = min(1.0, self.time_elapsed / (0.8 + i * 0.2))
            animated_value = value * self._ease_out_cubic(fill_progress)

            # Label
            if font:
                self.draw_text(surface, label, font, self.text_color,
                               (panel_x + 70, y + bar_h // 2))

            # Bar background
            pygame.draw.rect(surface, self.stat_bar_bg,
                             (bar_x, y, bar_w, bar_h), border_radius=4)

            # Bar fill (golden gradient effect)
            fill_w = int(bar_w * animated_value)
            if fill_w > 0:
                # Main fill
                pygame.draw.rect(surface, self.stat_bar_fill,
                                 (bar_x, y, fill_w, bar_h), border_radius=4)
                # Highlight stripe at top of bar
                highlight = pygame.Surface((fill_w, bar_h // 3), pygame.SRCALPHA)
                highlight.fill((255, 255, 255, 50))
                surface.blit(highlight, (bar_x, y))

            # Percentage text
            pct_text = f"{int(animated_value * 100)}%"
            if self.daydream_font_tiny:
                self.draw_text(surface, pct_text, self.daydream_font_tiny,
                               (220, 200, 160),
                               (bar_x + bar_w + 30, y + bar_h // 2))

    def _render_animation_previews(self, surface: pygame.Surface,
                                   cx: int, y: int) -> None:
        """Render small animated sprite previews at the bottom."""
        preview_scale = 96  # Size of preview sprites
        gap = 160  # Space between the two previews

        # Run animation preview (left side)
        if self.run_frames:
            frame = self.run_frames[self.run_frame_index]
            scaled = pygame.transform.smoothscale(frame, (preview_scale, preview_scale))
            rx = cx - gap - preview_scale // 2
            surface.blit(scaled, (rx, y - preview_scale // 2))

            if self.daydream_font_tiny:
                self.draw_text(surface, "RUN", self.daydream_font_tiny,
                               self.subtitle_color, (rx + preview_scale // 2, y + preview_scale // 2 + 14))

        # Eat animation preview (right side)
        if self.eat_frames:
            frame = self.eat_frames[self.eat_frame_index]
            scaled = pygame.transform.smoothscale(frame, (preview_scale, preview_scale))
            ex = cx + gap - preview_scale // 2
            surface.blit(scaled, (ex, y - preview_scale // 2))

            if self.daydream_font_tiny:
                self.draw_text(surface, "EAT", self.daydream_font_tiny,
                               self.subtitle_color, (ex + preview_scale // 2, y + preview_scale // 2 + 14))

    @staticmethod
    def _ease_out_back(t: float) -> float:
        """Ease-out-back curve for bouncy entrance."""
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)

    @staticmethod
    def _ease_out_cubic(t: float) -> float:
        """Ease-out-cubic for smooth deceleration."""
        return 1 - pow(1 - t, 3)
