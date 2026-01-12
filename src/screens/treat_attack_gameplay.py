"""Treat Attack gameplay screen - Tetris-style catching game with audience interaction."""

import pygame
from typing import Dict, Any, List, Optional
from .base_screen import BaseScreen
from ..core.state_machine import GameState
from ..core.event_bus import GameEvent
from ..entities.falling_treat import FallingTreat, TreatSpawner
from ..entities.catcher_dog import CatcherDog, LeashState


class VotingMeter:
    """Visual meter showing current vote split."""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

        # Vote counts
        self.extend_votes = 0
        self.yank_votes = 0

        # Visual settings
        self.extend_color = (100, 200, 100)  # Green
        self.yank_color = (200, 100, 100)    # Red
        self.neutral_color = (100, 100, 100)  # Gray
        self.border_color = (50, 50, 50)

    def reset_votes(self) -> None:
        """Reset vote counts."""
        self.extend_votes = 0
        self.yank_votes = 0

    def add_vote(self, vote_type: str) -> None:
        """Add a vote."""
        if vote_type == "extend":
            self.extend_votes += 1
        elif vote_type == "yank":
            self.yank_votes += 1

    def get_winner(self) -> Optional[str]:
        """Get the winning vote type, or None if tied."""
        if self.extend_votes > self.yank_votes:
            return "extend"
        elif self.yank_votes > self.extend_votes:
            return "yank"
        return None

    def get_percentages(self) -> tuple:
        """Get vote percentages."""
        total = self.extend_votes + self.yank_votes
        if total == 0:
            return (50, 50)
        return (
            int(self.extend_votes / total * 100),
            int(self.yank_votes / total * 100)
        )

    def render(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        """Render the voting meter."""
        # Background
        pygame.draw.rect(surface, self.border_color,
                        (self.x - 2, self.y - 2, self.width + 4, self.height + 4),
                        border_radius=5)

        total = self.extend_votes + self.yank_votes
        if total == 0:
            # No votes - show neutral
            pygame.draw.rect(surface, self.neutral_color,
                           (self.x, self.y, self.width, self.height),
                           border_radius=3)
        else:
            # Show vote split
            extend_width = int(self.width * self.extend_votes / total)
            yank_width = self.width - extend_width

            if extend_width > 0:
                pygame.draw.rect(surface, self.extend_color,
                               (self.x, self.y, extend_width, self.height),
                               border_radius=3)
            if yank_width > 0:
                pygame.draw.rect(surface, self.yank_color,
                               (self.x + extend_width, self.y, yank_width, self.height),
                               border_radius=3)

        # Labels
        extend_pct, yank_pct = self.get_percentages()
        extend_text = font.render(f"EXTEND {extend_pct}%", True, (255, 255, 255))
        yank_text = font.render(f"{yank_pct}% YANK", True, (255, 255, 255))

        surface.blit(extend_text, (self.x + 10, self.y + (self.height - extend_text.get_height()) // 2))
        surface.blit(yank_text, (self.x + self.width - yank_text.get_width() - 10,
                                self.y + (self.height - yank_text.get_height()) // 2))


class ChatInput:
    """Local text input for chat commands."""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

        self.text = ""
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0.0

        # Visual settings
        self.bg_color = (40, 40, 40)
        self.active_color = (60, 60, 80)
        self.text_color = (255, 255, 255)
        self.border_color = (100, 100, 100)
        self.placeholder = "Type !extend or !yank..."

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """
        Handle input events.

        Returns:
            Submitted command string, or None
        """
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Check if clicked on input
            rect = pygame.Rect(self.x, self.y, self.width, self.height)
            self.active = rect.collidepoint(event.pos)

        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                # Submit command
                command = self.text.strip()
                self.text = ""
                return command
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.active = False
                self.text = ""
            else:
                # Add character (limit length)
                if len(self.text) < 50 and event.unicode.isprintable():
                    self.text += event.unicode

        return None

    def update(self, dt: float) -> None:
        """Update cursor blink."""
        self.cursor_timer += dt
        if self.cursor_timer >= 0.5:
            self.cursor_timer = 0.0
            self.cursor_visible = not self.cursor_visible

    def render(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        """Render the chat input."""
        # Background
        bg = self.active_color if self.active else self.bg_color
        pygame.draw.rect(surface, bg, (self.x, self.y, self.width, self.height),
                        border_radius=5)
        pygame.draw.rect(surface, self.border_color, (self.x, self.y, self.width, self.height),
                        width=2, border_radius=5)

        # Text or placeholder
        if self.text:
            display_text = self.text
            if self.active and self.cursor_visible:
                display_text += "|"
            text_surface = font.render(display_text, True, self.text_color)
        else:
            text_surface = font.render(self.placeholder, True, (128, 128, 128))

        # Clip text to input area
        text_x = self.x + 10
        text_y = self.y + (self.height - text_surface.get_height()) // 2
        surface.blit(text_surface, (text_x, text_y))


class TreatAttackGameplay(BaseScreen):
    """Main Treat Attack gameplay screen."""

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        # Override screen dimensions for 1:1 aspect ratio
        self.game_width = 720
        self.game_height = 720

        # Game state
        self.score = 0
        self.round_time = 60.0
        self.time_remaining = 60.0
        self.game_over = False
        self.paused = False

        # Entities
        self.dog: Optional[CatcherDog] = None
        self.treats: List[FallingTreat] = []
        self.spawner: Optional[TreatSpawner] = None

        # Voting
        self.voting_meter: Optional[VotingMeter] = None
        self.vote_window_duration = 10.0
        self.vote_timer = 0.0
        self.vote_cooldown = 5.0
        self.cooldown_timer = 0.0
        self.voting_active = False

        # Chat input
        self.chat_input: Optional[ChatInput] = None

        # UI fonts
        self.score_font: Optional[pygame.font.Font] = None
        self.timer_font: Optional[pygame.font.Font] = None

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize the gameplay screen."""
        self.initialize_fonts()

        # Load Treat Attack settings
        settings = self.config.get("treat_attack_settings", {})
        if not settings:
            # Fallback defaults
            settings = {
                "screen": {"width": 720, "height": 720},
                "gameplay": {
                    "round_duration_seconds": 60,
                    "base_fall_speed": 150,
                    "spawn_interval_seconds": 1.5
                },
                "treats": {
                    "types": [
                        {"id": "normal", "point_value": 100, "spawn_weight": 60, "color": [255, 210, 80]},
                        {"id": "power", "point_value": 500, "spawn_weight": 15, "spawn_bias_right": True, "color": [255, 215, 0]},
                        {"id": "bad", "point_value": -200, "spawn_weight": 25, "color": [100, 150, 100]}
                    ]
                },
                "dog": {"ground_y": 650, "move_speed": 300},
                "leash": {"default_min_x": 50, "default_max_x": 550, "extended_max_x": 670, "yanked_max_x": 350},
                "voting": {"window_duration_seconds": 10, "cooldown_seconds": 5}
            }

        gameplay = settings.get("gameplay", {})
        voting = settings.get("voting", {})
        ui = settings.get("ui", {})

        # Initialize game state
        self.round_time = gameplay.get("round_duration_seconds", 60)
        self.time_remaining = self.round_time
        self.score = 0
        self.game_over = False
        self.paused = False
        self.treats = []

        # Initialize dog
        character_id = data.get("character", "jazzy") if data else "jazzy"
        self.dog = CatcherDog(settings, character_id)

        # Initialize spawner
        treat_types = settings.get("treats", {}).get("types", [])
        spawn_interval = gameplay.get("spawn_interval_seconds", 1.5)
        self.spawner = TreatSpawner(
            self.game_width, self.game_height,
            treat_types, spawn_interval
        )
        self.spawner.set_fall_speed(gameplay.get("base_fall_speed", 150))

        # Initialize voting
        meter_margin = ui.get("meter_margin", 10)
        meter_height = ui.get("meter_height", 40)
        self.voting_meter = VotingMeter(
            meter_margin, meter_margin,
            self.game_width - 2 * meter_margin, meter_height
        )
        self.vote_window_duration = voting.get("window_duration_seconds", 10)
        self.vote_cooldown = voting.get("cooldown_seconds", 5)
        self.vote_timer = 0.0
        self.cooldown_timer = 0.0
        self.voting_active = True

        # Initialize chat input (at bottom of screen)
        self.chat_input = ChatInput(
            10, self.game_height - 40,
            self.game_width - 20, 30
        )

        # Initialize fonts
        self.score_font = pygame.font.Font(None, ui.get("score_font_size", 32))
        self.timer_font = pygame.font.Font(None, ui.get("timer_font_size", 28))

    def on_exit(self) -> None:
        """Cleanup when leaving the screen."""
        self.treats = []
        self.dog = None
        self.spawner = None

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.game_over:
                    self.state_machine.change_state(GameState.MAIN_MENU)
                else:
                    self.paused = not self.paused

            elif event.key == pygame.K_RETURN and self.game_over:
                self.state_machine.change_state(GameState.MAIN_MENU)

        # Handle chat input
        if self.chat_input and not self.game_over:
            command = self.chat_input.handle_event(event)
            if command:
                self._process_command(command)

        # Handle dog movement (only when chat not focused)
        if not self.game_over and not self.paused:
            if self.chat_input and not self.chat_input.active:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self.dog.move_left()
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.dog.move_right()
                elif event.type == pygame.KEYUP:
                    if event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                        self.dog.stop()

    def _process_command(self, command: str) -> None:
        """Process a chat command."""
        command = command.lower().strip()

        if command in ("!extend", "!help"):
            if self.voting_active:
                self.voting_meter.add_vote("extend")
        elif command in ("!yank", "!hinder"):
            if self.voting_active:
                self.voting_meter.add_vote("yank")

    def update(self, dt: float) -> None:
        """Update game state."""
        if self.game_over or self.paused:
            return

        # Update timer
        self.time_remaining -= dt
        if self.time_remaining <= 0:
            self.time_remaining = 0
            self.game_over = True
            return

        # Update voting system
        self._update_voting(dt)

        # Update chat input cursor
        if self.chat_input:
            self.chat_input.update(dt)

        # Update dog (handle continuous key presses)
        keys = pygame.key.get_pressed()
        if self.chat_input and not self.chat_input.active:
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.dog.move_left()
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.dog.move_right()
            else:
                self.dog.stop()

        self.dog.update(dt)

        # Spawn new treats
        new_treat = self.spawner.update(dt)
        if new_treat:
            self.treats.append(new_treat)

        # Update treats and check collisions
        active_treats = []
        for treat in self.treats:
            if treat.update(dt):
                # Check collision with dog
                if self.dog.check_collision(treat.rect):
                    result = treat.collect()
                    self.score += result["point_value"]
                    self.dog.trigger_eat()

                    # Emit event
                    self.event_bus.emit(GameEvent.SNACK_COLLECTED, result)
                else:
                    active_treats.append(treat)

        self.treats = active_treats

    def _update_voting(self, dt: float) -> None:
        """Update voting timer and apply results."""
        if self.voting_active:
            self.vote_timer += dt

            if self.vote_timer >= self.vote_window_duration:
                # Apply voting result
                winner = self.voting_meter.get_winner()
                if winner == "extend":
                    self.dog.extend_leash()
                elif winner == "yank":
                    self.dog.yank_leash()

                # Start cooldown
                self.voting_active = False
                self.vote_timer = 0.0
                self.cooldown_timer = 0.0
                self.voting_meter.reset_votes()
        else:
            self.cooldown_timer += dt
            if self.cooldown_timer >= self.vote_cooldown:
                self.voting_active = True
                self.cooldown_timer = 0.0

    def render(self, surface: pygame.Surface) -> None:
        """Render the game."""
        # Create game surface (720x720)
        game_surface = pygame.Surface((self.game_width, self.game_height))

        # Background (sky gradient effect)
        self._draw_background(game_surface)

        # Ground
        ground_y = 650
        pygame.draw.rect(game_surface, (101, 67, 33),
                        (0, ground_y + 64, self.game_width, self.game_height - ground_y - 64))
        # Grass on top
        pygame.draw.rect(game_surface, (34, 139, 34),
                        (0, ground_y + 60, self.game_width, 8))

        # Render treats
        for treat in self.treats:
            treat.render(game_surface)

        # Render dog
        if self.dog:
            self.dog.render(game_surface)

        # Render voting meter
        if self.voting_meter and self.score_font:
            self.voting_meter.render(game_surface, self.score_font)

            # Show voting status
            if self.voting_active:
                time_left = int(self.vote_window_duration - self.vote_timer)
                status_text = f"Voting: {time_left}s"
            else:
                time_left = int(self.vote_cooldown - self.cooldown_timer)
                status_text = f"Next vote: {time_left}s"

            status_surface = self.small_font.render(status_text, True, (200, 200, 200))
            game_surface.blit(status_surface, (self.game_width // 2 - status_surface.get_width() // 2, 55))

        # Render score and timer
        self._render_ui(game_surface)

        # Render chat input
        if self.chat_input and self.small_font:
            self.chat_input.render(game_surface, self.small_font)

        # Render pause overlay
        if self.paused:
            self._render_pause(game_surface)

        # Render game over overlay
        if self.game_over:
            self._render_game_over(game_surface)

        # Blit game surface to main surface (centered if needed)
        x_offset = (surface.get_width() - self.game_width) // 2
        y_offset = (surface.get_height() - self.game_height) // 2
        surface.fill((0, 0, 0))  # Black letterboxing
        surface.blit(game_surface, (x_offset, y_offset))

    def _draw_background(self, surface: pygame.Surface) -> None:
        """Draw sky background with gradient."""
        # Simple vertical gradient (light blue to darker blue)
        for y in range(self.game_height):
            # Gradient from light sky blue to medium blue
            ratio = y / self.game_height
            r = int(135 - ratio * 30)
            g = int(206 - ratio * 50)
            b = int(235 - ratio * 30)
            pygame.draw.line(surface, (r, g, b), (0, y), (self.game_width, y))

    def _render_ui(self, surface: pygame.Surface) -> None:
        """Render score and timer."""
        # Score (top right, below voting meter)
        score_text = f"Score: {self.score}"
        score_surface = self.score_font.render(score_text, True, (255, 255, 255))
        score_shadow = self.score_font.render(score_text, True, (0, 0, 0))
        surface.blit(score_shadow, (self.game_width - score_surface.get_width() - 18, 72))
        surface.blit(score_surface, (self.game_width - score_surface.get_width() - 20, 70))

        # Timer (top left, below voting meter)
        time_text = f"Time: {int(self.time_remaining)}s"
        time_surface = self.timer_font.render(time_text, True, (255, 255, 255))
        time_shadow = self.timer_font.render(time_text, True, (0, 0, 0))
        surface.blit(time_shadow, (12, 72))
        surface.blit(time_surface, (10, 70))

    def _render_pause(self, surface: pygame.Surface) -> None:
        """Render pause overlay."""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.game_width, self.game_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        surface.blit(overlay, (0, 0))

        # Pause text
        pause_text = self.title_font.render("PAUSED", True, (255, 255, 255))
        x = (self.game_width - pause_text.get_width()) // 2
        y = (self.game_height - pause_text.get_height()) // 2
        surface.blit(pause_text, (x, y))

        # Instructions
        resume_text = self.menu_font.render("Press ESC to resume", True, (200, 200, 200))
        surface.blit(resume_text, ((self.game_width - resume_text.get_width()) // 2, y + 60))

    def _render_game_over(self, surface: pygame.Surface) -> None:
        """Render game over overlay."""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.game_width, self.game_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        # Game over text
        game_over_text = self.title_font.render("TIME'S UP!", True, (255, 215, 0))
        x = (self.game_width - game_over_text.get_width()) // 2
        y = self.game_height // 2 - 80
        surface.blit(game_over_text, (x, y))

        # Final score
        final_score_text = self.menu_font.render(f"Final Score: {self.score}", True, (255, 255, 255))
        surface.blit(final_score_text, ((self.game_width - final_score_text.get_width()) // 2, y + 70))

        # Instructions
        continue_text = self.small_font.render("Press ENTER to continue", True, (200, 200, 200))
        surface.blit(continue_text, ((self.game_width - continue_text.get_width()) // 2, y + 120))
