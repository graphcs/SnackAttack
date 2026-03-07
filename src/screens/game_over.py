"""Game over / results screen with celebratory animations."""

import pygame
import os
import math
import random
from typing import Dict, Any, Optional, List, Tuple
from .base_screen import BaseScreen
from ..core.state_machine import GameState
from ..core.event_bus import GameEvent


# ---------------------------------------------------------------------------
# Festive palette for balloons & confetti
# ---------------------------------------------------------------------------

_FESTIVE_COLORS: List[Tuple[int, int, int]] = [
    (255, 80, 80),    # Red
    (80, 200, 255),   # Sky blue
    (255, 220, 60),   # Gold
    (120, 255, 120),  # Green
    (255, 140, 200),  # Pink
    (180, 120, 255),  # Purple
    (255, 160, 60),   # Orange
]


# ---------------------------------------------------------------------------
# Balloon particle
# ---------------------------------------------------------------------------

class _Balloon:
    """A single buoyant balloon that floats upward with gentle sway."""

    __slots__ = ("x", "y", "color", "radius", "speed", "sway_amp",
                 "sway_freq", "sway_phase", "string_len")

    def __init__(self, x: float, y: float, screen_height: int):
        self.x = x
        self.y = y
        self.color = random.choice(_FESTIVE_COLORS)
        self.radius = random.randint(18, 28)
        self.speed = random.uniform(40, 75)  # px/s upward
        self.sway_amp = random.uniform(15, 35)
        self.sway_freq = random.uniform(0.8, 1.6)
        self.sway_phase = random.uniform(0, math.pi * 2)
        self.string_len = random.randint(20, 35)

    def update(self, dt: float, screen_height: int) -> None:
        self.y -= self.speed * dt
        # Respawn at bottom when exiting top
        if self.y + self.radius < -40:
            self.y = screen_height + random.randint(20, 80)
            self.color = random.choice(_FESTIVE_COLORS)

    def render(self, surface: pygame.Surface, time: float) -> None:
        sway_x = self.x + math.sin(time * self.sway_freq + self.sway_phase) * self.sway_amp
        bx, by = int(sway_x), int(self.y)

        # Balloon body (slightly oval)
        balloon_surf = pygame.Surface(
            (self.radius * 2 + 4, int(self.radius * 2.4) + 4), pygame.SRCALPHA
        )
        bw = self.radius * 2
        bh = int(self.radius * 2.4)
        pygame.draw.ellipse(balloon_surf, self.color, (2, 2, bw, bh))

        # Highlight (shiny spot)
        hl_r = max(3, self.radius // 4)
        hl_x = 2 + bw // 3
        hl_y = 2 + bh // 4
        pygame.draw.circle(balloon_surf, (255, 255, 255, 120), (hl_x, hl_y), hl_r)

        # Knot (tiny triangle at bottom)
        knot_cx = 2 + bw // 2
        knot_y = 2 + bh
        pygame.draw.polygon(balloon_surf, self.color, [
            (knot_cx - 3, knot_y - 2), (knot_cx + 3, knot_y - 2), (knot_cx, knot_y + 3)
        ])

        surface.blit(balloon_surf, (bx - self.radius - 2, by - int(self.radius * 1.2) - 2))

        # String (thin curvy line)
        string_start = (bx, by + self.radius + 3)
        string_end = (bx + int(math.sin(time * 1.5 + self.sway_phase) * 5),
                      by + self.radius + 3 + self.string_len)
        pygame.draw.line(surface, (180, 180, 180), string_start, string_end, 1)


# ---------------------------------------------------------------------------
# Confetti / streamer particle
# ---------------------------------------------------------------------------

class _Confetti:
    """A small rotating rectangle confetti piece falling from above."""

    __slots__ = ("x", "y", "color", "w", "h", "speed", "drift_x",
                 "rotation", "rot_speed")

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.color = random.choice(_FESTIVE_COLORS)
        self.w = random.randint(4, 9)
        self.h = random.randint(8, 16)
        self.speed = random.uniform(60, 130)  # px/s downward
        self.drift_x = random.uniform(-30, 30)  # horizontal drift
        self.rotation = random.uniform(0, 360)
        self.rot_speed = random.uniform(120, 360)  # deg/s

    def update(self, dt: float) -> bool:
        """Update confetti. Returns False if off-screen (dead)."""
        self.y += self.speed * dt
        self.x += self.drift_x * dt
        self.rotation += self.rot_speed * dt
        return self.y < 1200  # generous off-screen threshold

    def render(self, surface: pygame.Surface) -> None:
        piece = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        piece.fill(self.color)
        rotated = pygame.transform.rotate(piece, self.rotation)
        rx = int(self.x) - rotated.get_width() // 2
        ry = int(self.y) - rotated.get_height() // 2
        surface.blit(rotated, (rx, ry))


class GameOverScreen(BaseScreen):
    """Game over screen showing results."""

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        self.winner = None
        self.p1_score = 0
        self.p2_score = 0
        self.p1_rounds = 0
        self.p2_rounds = 0
        self.game_mode = "1p"
        self.vs_ai = True
        self.p1_name = "Player 1"
        self.p2_name = "Player 2"

        self.selected_option = 0  # 0 = Play Again, 1 = Main Menu
        self.menu_option_rects = []  # Store rects for hover detection

        # Background image
        self.background_image: Optional[pygame.Surface] = None
        self.menu_square_image: Optional[pygame.Surface] = None
        self.wins_image: Optional[pygame.Surface] = None
        self.menu_bar_image: Optional[pygame.Surface] = None
        self.select_icon: Optional[pygame.Surface] = None

        # Custom font
        self.daydream_font: Optional[pygame.font.Font] = None
        self.daydream_font_large: Optional[pygame.font.Font] = None
        self.daydream_font_score: Optional[pygame.font.Font] = None
        self.daydream_font_small: Optional[pygame.font.Font] = None
        self.daydream_font_winner: Optional[pygame.font.Font] = None
        self.daydream_font_footer: Optional[pygame.font.Font] = None

        # Colors
        self.bg_color = (20, 20, 40)
        self.title_color = (255, 200, 0)
        self.text_color = (255, 255, 255)
        self.p1_color = (100, 150, 255)
        self.p2_color = (255, 100, 100)
        self.highlight_color = (255, 200, 0)

        # Celebration particle systems
        self._balloons: List[_Balloon] = []
        self._confetti: List[_Confetti] = []
        self._celebration_time = 0.0
        self._confetti_spawn_accum = 0.0

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize game over screen with results."""
        self.initialize_fonts()
        self._load_custom_font()
        self._load_background()
        self._start_background_music()

        data = data or {}
        self.winner = data.get("winner")
        self.p1_score = data.get("p1_score", 0)
        self.p2_score = data.get("p2_score", 0)
        self.p1_rounds = data.get("p1_rounds", 0)
        self.p2_rounds = data.get("p2_rounds", 0)
        self.game_mode = data.get("mode", "1p")
        self.vs_ai = data.get("vs_ai", True)
        self.p1_name = data.get("p1_name", "Player 1")
        self.p2_name = data.get("p2_name", "Player 2")

        self.selected_option = 0

        # Initialize celebration particles
        self._celebration_time = 0.0
        self._confetti_spawn_accum = 0.0
        self._confetti.clear()
        self._balloons.clear()
        for _ in range(12):
            x = random.uniform(30, self.screen_width - 30)
            y = random.uniform(-self.screen_height * 0.3, self.screen_height * 0.95)
            self._balloons.append(_Balloon(x, y, self.screen_height))

    def _load_custom_font(self) -> None:
        """Load custom Daydream font."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(base_dir, "ui")
        font_path = os.path.join(ui_dir, "Daydream.ttf")

        if os.path.exists(font_path):
            self.daydream_font = pygame.font.Font(font_path, 28)
            self.daydream_font_large = pygame.font.Font(font_path, 43)  # 0.95x for names
            self.daydream_font_score = pygame.font.Font(font_path, 61)  # 0.95x for scores
            self.daydream_font_small = pygame.font.Font(font_path, 24)  # 0.95x for "score" label
            self.daydream_font_winner = pygame.font.Font(font_path, 80)  # Large for winner name (1.2x again)
            self.daydream_font_footer = pygame.font.Font(font_path, 18)  # Footer instructions

    def _load_background(self) -> None:
        """Load the win screen background image and UI elements."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(base_dir, "ui")

        bg_path = os.path.join(ui_dir, "Win screen.png")
        if os.path.exists(bg_path):
            self.background_image = pygame.image.load(bg_path).convert()
            self.background_image = pygame.transform.scale(
                self.background_image, (self.screen_width, self.screen_height)
            )

        # Load menu square for score boxes
        menu_square_path = os.path.join(ui_dir, "Menu square.png")
        if os.path.exists(menu_square_path):
            self.menu_square_image = pygame.image.load(menu_square_path).convert_alpha()
            # Scale to 0.95x of previous size
            box_width = int(self.screen_width * 0.469)  # 0.4939 * 0.95
            box_height = int(self.screen_height * 0.521)  # 0.5489 * 0.95
            self.menu_square_image = pygame.transform.scale(
                self.menu_square_image, (box_width, box_height)
            )

        # Load wins image
        wins_path = os.path.join(ui_dir, "Wins!.png")
        if os.path.exists(wins_path):
            self.wins_image = pygame.image.load(wins_path).convert_alpha()
            # Scale to 0.6 (1.2x of previous 0.5)
            new_width = int(self.wins_image.get_width() * 0.6)
            new_height = int(self.wins_image.get_height() * 0.6)
            self.wins_image = pygame.transform.scale(self.wins_image, (new_width, new_height))

        # Load menu bar image
        menu_bar_path = os.path.join(ui_dir, "Menu bar.png")
        if os.path.exists(menu_bar_path):
            self.menu_bar_image = pygame.image.load(menu_bar_path).convert_alpha()
            # Scale to fit screen width (0.9x of previous)
            bar_width = int(self.screen_width * 0.76)
            bar_height = int(self.menu_bar_image.get_height() * (bar_width / self.menu_bar_image.get_width()))
            self.menu_bar_image = pygame.transform.scale(self.menu_bar_image, (bar_width, bar_height))

        # Load select icon
        select_path = os.path.join(ui_dir, "Select.png")
        if os.path.exists(select_path):
            self.select_icon = pygame.image.load(select_path).convert_alpha()
            # Scale to appropriate size
            icon_height = 30
            icon_width = int(self.select_icon.get_width() * (icon_height / self.select_icon.get_height()))
            self.select_icon = pygame.transform.scale(self.select_icon, (icon_width, icon_height))

    def _start_background_music(self) -> None:
        """Start playing background music."""
        audio_settings = self.config.get_config("audio_settings")
        music_enabled = audio_settings.get("music_enabled", True)
        if not music_enabled:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
            return

        master_volume = audio_settings.get("master_volume", 0.8)
        music_volume = audio_settings.get("music_volume", 0.6)
        effective_volume = max(0.0, min(1.0, master_volume * music_volume))

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        music_path = os.path.join(base_dir, "Sound effect", "background.mp3")
        if os.path.exists(music_path):
            try:
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.set_volume(effective_volume)
                pygame.mixer.music.play(-1)  # Loop indefinitely
            except pygame.error as e:
                print(f"Could not play background music: {e}")

    def on_exit(self) -> None:
        """Clean up when leaving screen."""
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                self.selected_option = 1 - self.selected_option  # Toggle between 0 and 1
                # Play select sound
                self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "select"})
            elif event.key == pygame.K_RETURN:
                self._select_option()
            elif event.key == pygame.K_ESCAPE:
                self.state_machine.change_state(GameState.MAIN_MENU)

        elif event.type == pygame.MOUSEMOTION:
            # Handle hover on menu options
            for i, rect in enumerate(self.menu_option_rects):
                if rect and rect.collidepoint(event.pos):
                    if self.selected_option != i:
                        self.selected_option = i
                        # Play select sound
                        self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "select"})
                    break

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                for i, rect in enumerate(self.menu_option_rects):
                    if rect and rect.collidepoint(event.pos):
                        self.selected_option = i
                        self._select_option()
                        break

    def _select_option(self) -> None:
        """Handle option selection."""
        if self.selected_option == 0:
            # Play again - go to character select
            self.state_machine.change_state(GameState.CHARACTER_SELECT, {
                "mode": self.game_mode,
                "vs_ai": self.vs_ai
            })
        else:
            # Main menu
            self.state_machine.change_state(GameState.MAIN_MENU)

    def update(self, dt: float) -> None:
        """Update screen state and celebration particles."""
        self._celebration_time += dt

        # Update balloons
        for balloon in self._balloons:
            balloon.update(dt, self.screen_height)

        # Spawn confetti continuously (~18 per second)
        self._confetti_spawn_accum += dt * 18
        while self._confetti_spawn_accum >= 1.0:
            self._confetti_spawn_accum -= 1.0
            x = random.uniform(0, self.screen_width)
            self._confetti.append(_Confetti(x, random.uniform(-20, -5)))

        # Update confetti (remove dead ones)
        self._confetti = [c for c in self._confetti if c.update(dt)]

        # Cap confetti count to avoid slowdowns
        if len(self._confetti) > 200:
            self._confetti = self._confetti[-200:]

    def render(self, surface: pygame.Surface) -> None:
        """Render the game over screen with proportional positioning."""
        if self.background_image:
            surface.blit(self.background_image, (0, 0))
        else:
            surface.fill(self.bg_color)

        # Render balloons behind UI elements
        for balloon in self._balloons:
            balloon.render(surface, self._celebration_time)

        # Title with proportional positioning
        title_y = int(self.screen_height * 0.18)
        winner_color = (147, 76, 48)  # #934C30
        winner_font = self.daydream_font_winner if self.daydream_font_winner else self.title_font
        if self.winner:
            # Draw winner name with Daydream font and #934C30 color
            winner_name = self.winner
            self.draw_text(surface, winner_name, winner_font, winner_color,
                           (self.screen_width // 2, title_y))
            # Draw wins image below the winner name
            if self.wins_image:
                wins_rect = self.wins_image.get_rect()
                wins_x = (self.screen_width - wins_rect.width) // 2
                wins_y = title_y + 50
                surface.blit(self.wins_image, (wins_x, wins_y))
            else:
                self.draw_text(surface, "WINS!", self.title_font, title_color,
                               (self.screen_width // 2, title_y + 40))
        else:
            title = "IT'S A TIE!"
            title_color = self.title_color
            self.draw_text(surface, title, self.title_font, title_color,
                           (self.screen_width // 2, title_y))

        # Draw menu bar above score cards
        if self.menu_bar_image:
            bar_x = (self.screen_width - self.menu_bar_image.get_width()) // 2
            bar_y = int(self.screen_height * 0.28) + 50
            surface.blit(self.menu_bar_image, (bar_x, bar_y))

            # Round results inside the menu bar
            rounds_y = bar_y + self.menu_bar_image.get_height() // 2
        else:
            rounds_y = int(self.screen_height * 0.30)

        rounds_color = (77, 43, 31)  # #4D2B1F

        # Render parts separately - player names/scores larger, "vs" smaller
        rounds_font = self.daydream_font if self.daydream_font else self.menu_font
        vs_font = self.daydream_font_small if self.daydream_font_small else self.small_font

        single_dog_mode = self.game_mode == "single_dog"

        if single_dog_mode:
            rounds_text = f"{self.p1_name}  rounds {self.p1_rounds}"
            rounds_surface = rounds_font.render(rounds_text, True, rounds_color)
            rounds_rect = rounds_surface.get_rect(center=(self.screen_width // 2, rounds_y))
            surface.blit(rounds_surface, rounds_rect)
        else:
            p1_text = f"{self.p1_name}  {self.p1_rounds}"
            vs_text = "vs"
            p2_text = f"{self.p2_name}  {self.p2_rounds}"

            p1_surface = rounds_font.render(p1_text, True, rounds_color)
            vs_surface = vs_font.render(vs_text, True, rounds_color)
            p2_surface = rounds_font.render(p2_text, True, rounds_color)

            # Calculate total width and positions
            spacing = 80
            total_width = p1_surface.get_width() + vs_surface.get_width() + p2_surface.get_width() + spacing * 2
            start_x = (self.screen_width - total_width) // 2

            # Draw each part centered vertically
            p1_rect = p1_surface.get_rect(midleft=(start_x, rounds_y))
            vs_rect = vs_surface.get_rect(midleft=(p1_rect.right + spacing, rounds_y))
            p2_rect = p2_surface.get_rect(midleft=(vs_rect.right + spacing, rounds_y))

            surface.blit(p1_surface, p1_rect)
            surface.blit(vs_surface, vs_rect)
            surface.blit(p2_surface, p2_rect)

        # Score boxes - side by side with proportional sizing (0.95x of previous)
        box_width = int(self.screen_width * 0.469)  # 0.4939 * 0.95
        box_height = int(self.screen_height * 0.521)  # 0.5489 * 0.95
        box_y = int(self.screen_height * 0.30) + 50  # Moved down 50 pixels
        box_gap = -70  # Overlap cards more to bring them closer

        # Color for dog names and scores
        name_color = (147, 76, 48)  # #934C30
        name_font = self.daydream_font_large if self.daydream_font_large else self.menu_font
        score_font = self.daydream_font_score if self.daydream_font_score else pygame.font.Font(None, 80)
        score_label_font = self.daydream_font_small if self.daydream_font_small else self.small_font

        # P1 score box
        p1_box_x = self.screen_width // 2 - box_width - box_gap // 2
        if single_dog_mode:
            p1_box_x = (self.screen_width - box_width) // 2
        if self.menu_square_image:
            surface.blit(self.menu_square_image, (p1_box_x, box_y))
        else:
            pygame.draw.rect(surface, (40, 40, 60),
                             (p1_box_x, box_y, box_width, box_height), border_radius=12)
            pygame.draw.rect(surface, self.p1_color,
                             (p1_box_x, box_y, box_width, box_height), 4, border_radius=12)
        # Dog name with Daydream font (1.2x) and #934C30 color
        self.draw_text(surface, self.p1_name, name_font, name_color,
                       (p1_box_x + box_width // 2, box_y + int(box_height * 0.38)))
        # "score" label (small)
        self.draw_text(surface, "score", score_label_font, name_color,
                       (p1_box_x + box_width // 2, box_y + int(box_height * 0.50)))
        # Score number with Daydream font and #934C30 color
        score_surface = score_font.render(str(self.p1_score), True, name_color)
        score_rect = score_surface.get_rect(center=(p1_box_x + box_width // 2, box_y + int(box_height * 0.62)))
        surface.blit(score_surface, score_rect)

        if not single_dog_mode:
            # P2 score box
            p2_box_x = self.screen_width // 2 + box_gap // 2
            if self.menu_square_image:
                surface.blit(self.menu_square_image, (p2_box_x, box_y))
            else:
                pygame.draw.rect(surface, (40, 40, 60),
                                 (p2_box_x, box_y, box_width, box_height), border_radius=12)
                pygame.draw.rect(surface, self.p2_color,
                                 (p2_box_x, box_y, box_width, box_height), 4, border_radius=12)
            # Dog name with Daydream font (1.2x) and #934C30 color
            self.draw_text(surface, self.p2_name, name_font, name_color,
                           (p2_box_x + box_width // 2, box_y + int(box_height * 0.38)))
            # "score" label (small)
            self.draw_text(surface, "score", score_label_font, name_color,
                           (p2_box_x + box_width // 2, box_y + int(box_height * 0.50)))
            # Score number with Daydream font and #934C30 color
            score_surface = score_font.render(str(self.p2_score), True, name_color)
            score_rect = score_surface.get_rect(center=(p2_box_x + box_width // 2, box_y + int(box_height * 0.62)))
            surface.blit(score_surface, score_rect)

        # Menu options with proportional positioning - below score cards
        options_y = int(self.screen_height * 0.85)
        option_spacing = int(self.screen_height * 0.06)
        options = ["Play Again", "Main Menu"]
        menu_color_normal = (77, 43, 31)  # #4D2B1F
        menu_color_hover = (147, 76, 48)  # #934C30
        menu_font = self.daydream_font if self.daydream_font else self.menu_font

        # Clear and rebuild menu option rects
        self.menu_option_rects = []

        for i, option in enumerate(options):
            option_y = options_y + i * option_spacing

            # Use hover color if selected
            menu_color = menu_color_hover if i == self.selected_option else menu_color_normal

            # Render text
            text_surface = menu_font.render(option, True, menu_color)
            text_rect = text_surface.get_rect(center=(self.screen_width // 2, option_y))
            surface.blit(text_surface, text_rect)

            # Store rect for hover detection (with some padding)
            hover_rect = text_rect.inflate(20, 10)
            self.menu_option_rects.append(hover_rect)

            # Draw select icon next to selected option
            if i == self.selected_option and self.select_icon:
                icon_x = text_rect.left - self.select_icon.get_width() - 10
                icon_y = option_y - self.select_icon.get_height() // 2
                surface.blit(self.select_icon, (icon_x, icon_y))

        # Render confetti in front of all UI elements
        for confetti in self._confetti:
            confetti.render(surface)

