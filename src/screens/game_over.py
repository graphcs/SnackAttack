"""Game over / results screen."""

import pygame
from typing import Dict, Any
from .base_screen import BaseScreen
from ..core.state_machine import GameState


class GameOverScreen(BaseScreen):
    """Game over screen showing results."""

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        self.winner = None
        self.p1_score = 0
        self.p2_score = 0
        self.p1_rounds = 0
        self.p2_rounds = 0
        self.vs_ai = True

        self.selected_option = 0  # 0 = Play Again, 1 = Main Menu

        # Colors
        self.bg_color = (20, 20, 40)
        self.title_color = (255, 200, 0)
        self.text_color = (255, 255, 255)
        self.p1_color = (100, 150, 255)
        self.p2_color = (255, 100, 100)
        self.highlight_color = (255, 200, 0)

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize game over screen with results."""
        self.initialize_fonts()

        data = data or {}
        self.winner = data.get("winner")
        self.p1_score = data.get("p1_score", 0)
        self.p2_score = data.get("p2_score", 0)
        self.p1_rounds = data.get("p1_rounds", 0)
        self.p2_rounds = data.get("p2_rounds", 0)
        self.vs_ai = data.get("vs_ai", True)

        self.selected_option = 0

    def on_exit(self) -> None:
        """Clean up when leaving screen."""
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                self.selected_option = 1 - self.selected_option  # Toggle between 0 and 1
            elif event.key == pygame.K_RETURN:
                self._select_option()
            elif event.key == pygame.K_ESCAPE:
                self.state_machine.change_state(GameState.MAIN_MENU)

    def _select_option(self) -> None:
        """Handle option selection."""
        if self.selected_option == 0:
            # Play again - go to character select
            self.state_machine.change_state(GameState.CHARACTER_SELECT, {
                "mode": "1p" if self.vs_ai else "2p",
                "vs_ai": self.vs_ai
            })
        else:
            # Main menu
            self.state_machine.change_state(GameState.MAIN_MENU)

    def update(self, dt: float) -> None:
        """Update screen state."""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """Render the game over screen for 960x720 display."""
        surface.fill(self.bg_color)

        # Title
        if self.winner:
            title = f"{self.winner} WINS!"
            title_color = self.p1_color if self.winner == "Player 1" else self.p2_color
        else:
            title = "IT'S A TIE!"
            title_color = self.title_color

        self.draw_text(surface, title, self.title_font, title_color,
                       (self.screen_width // 2, 100))

        # Round results
        p2_label = "AI" if self.vs_ai else "P2"
        rounds_text = f"Rounds Won: P1 {self.p1_rounds} - {self.p2_rounds} {p2_label}"
        self.draw_text(surface, rounds_text, self.menu_font, self.text_color,
                       (self.screen_width // 2, 180))

        # Score boxes - side by side
        box_width = 200
        box_height = 140
        box_y = 240

        # P1 score box
        p1_box_x = self.screen_width // 2 - box_width - 40
        pygame.draw.rect(surface, (40, 40, 60),
                         (p1_box_x, box_y, box_width, box_height), border_radius=12)
        pygame.draw.rect(surface, self.p1_color,
                         (p1_box_x, box_y, box_width, box_height), 4, border_radius=12)
        self.draw_text(surface, "Player 1", self.menu_font, self.p1_color,
                       (p1_box_x + box_width // 2, box_y + 35))
        # Large score font
        score_font = pygame.font.Font(None, 80)
        score_surface = score_font.render(str(self.p1_score), True, self.text_color)
        score_rect = score_surface.get_rect(center=(p1_box_x + box_width // 2, box_y + 90))
        surface.blit(score_surface, score_rect)

        # P2 score box
        p2_box_x = self.screen_width // 2 + 40
        pygame.draw.rect(surface, (40, 40, 60),
                         (p2_box_x, box_y, box_width, box_height), border_radius=12)
        pygame.draw.rect(surface, self.p2_color,
                         (p2_box_x, box_y, box_width, box_height), 4, border_radius=12)
        self.draw_text(surface, p2_label, self.menu_font, self.p2_color,
                       (p2_box_x + box_width // 2, box_y + 35))
        score_surface = score_font.render(str(self.p2_score), True, self.text_color)
        score_rect = score_surface.get_rect(center=(p2_box_x + box_width // 2, box_y + 90))
        surface.blit(score_surface, score_rect)

        # Menu options
        options_y = 450
        options = ["Play Again", "Main Menu"]

        for i, option in enumerate(options):
            if i == self.selected_option:
                color = self.highlight_color
                prefix = "> "
            else:
                color = self.text_color
                prefix = "  "

            self.draw_text(surface, f"{prefix}{option}", self.menu_font, color,
                           (self.screen_width // 2, options_y + i * 60))

        # Instructions
        self.draw_text(surface, "Up/Down + Enter to Select",
                       self.small_font, (150, 150, 150),
                       (self.screen_width // 2, self.screen_height - 40))
