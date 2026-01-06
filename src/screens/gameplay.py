"""Main gameplay screen with split-screen support."""

import pygame
import random
from typing import Dict, Any, List, Optional
from .base_screen import BaseScreen
from ..core.state_machine import GameState
from ..core.event_bus import GameEvent
from ..entities.player import Player
from ..entities.ai_player import AIPlayer
from ..entities.snack import Snack


class Arena:
    """A single player's game arena for 960x720 display."""

    def __init__(self, bounds: pygame.Rect, player: Player, level_config: Dict[str, Any]):
        self.bounds = bounds
        self.player = player
        self.level_config = level_config
        self.snacks: List[Snack] = []
        self.background_color = tuple(level_config.get("background_color", [200, 200, 200]))

        # Spawn settings
        self.spawn_timer = 0.0
        self.base_spawn_interval = 1.5
        self.spawn_rate_multiplier = level_config.get("spawn_rate_multiplier", 1.0)
        self.snack_pool = level_config.get("snack_pool", ["pizza"])
        self.max_snacks = 10  # More snacks for larger arena

        # Create surface for this arena
        self.surface = pygame.Surface((bounds.width, bounds.height))

    def spawn_snack(self, snack_configs: List[Dict[str, Any]]) -> Optional[Snack]:
        """Spawn a new snack in the arena."""
        if len(self.snacks) >= self.max_snacks:
            return None

        # Filter available snacks by pool
        available = [s for s in snack_configs if s["id"] in self.snack_pool]
        if not available:
            return None

        # Weighted random selection
        weights = [s.get("spawn_weight", 1) for s in available]
        total_weight = sum(weights)
        r = random.uniform(0, total_weight)

        cumulative = 0
        selected = available[0]
        for snack_config, weight in zip(available, weights):
            cumulative += weight
            if r <= cumulative:
                selected = snack_config
                break

        # Random position within arena (with padding for 960x720 display)
        padding = 40
        snack_size = 48  # Snack sprite size
        x = random.randint(self.bounds.left + padding,
                           self.bounds.right - padding - snack_size)
        y = random.randint(self.bounds.top + padding,
                           self.bounds.bottom - padding - snack_size)

        snack = Snack(selected, (x, y), self.bounds)
        self.snacks.append(snack)
        return snack

    def update(self, dt: float, snack_configs: List[Dict[str, Any]]) -> None:
        """Update arena state."""
        # Update spawn timer
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_snack(snack_configs)
            interval = self.base_spawn_interval / self.spawn_rate_multiplier
            self.spawn_timer = interval + random.uniform(-0.3, 0.3)

        # Update snacks (remove inactive ones)
        self.snacks = [s for s in self.snacks if s.update(dt)]

    def render(self) -> pygame.Surface:
        """Render the arena with wooden floor and fence border for 960x720."""
        from ..sprites.pixel_art import draw_wooden_floor, draw_fence_border

        # Draw wooden plank floor
        floor_rect = pygame.Rect(0, 0, self.bounds.width, self.bounds.height)
        draw_wooden_floor(self.surface, floor_rect)

        # Draw blue wooden fence border
        border_rect = pygame.Rect(0, 0, self.bounds.width, self.bounds.height)
        draw_fence_border(self.surface, border_rect, thickness=12)

        # Draw snacks
        for snack in self.snacks:
            snack.render(self.surface)

        # Draw player
        self.player.render(self.surface)

        return self.surface


class GameplayScreen(BaseScreen):
    """Split-screen gameplay screen."""

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        self.arena1: Optional[Arena] = None
        self.arena2: Optional[Arena] = None
        self.player1: Optional[Player] = None
        self.player2: Optional[Player] = None

        self.game_mode = "1p"
        self.vs_ai = True
        self.difficulty = "medium"

        self.current_level = 1
        self.current_round = 1
        self.max_rounds = 3

        self.round_timer = 0.0
        self.round_duration = 60.0
        self.round_active = False
        self.countdown = 0
        self.countdown_timer = 0.0

        self.paused = False

        # Round scores
        self.p1_round_wins = 0
        self.p2_round_wins = 0

        # Screen shake effect
        self.shake_intensity = 0
        self.shake_duration = 0

        # Colors
        self.bg_color = (30, 30, 50)
        self.hud_color = (255, 255, 255)
        self.p1_color = (100, 150, 255)
        self.p2_color = (255, 100, 100)

        # Snack configs cache
        self.snack_configs: List[Dict[str, Any]] = []

        # Control key states
        self.p1_keys = {"up": False, "down": False, "left": False, "right": False}
        self.p2_keys = {"up": False, "down": False, "left": False, "right": False}

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize gameplay."""
        self.initialize_fonts()

        data = data or {}
        self.game_mode = data.get("mode", "1p")
        self.vs_ai = data.get("vs_ai", True)
        self.difficulty = data.get("difficulty", "medium")
        p1_char = data.get("p1_character", self.config.get_all_characters()[0])
        p2_char = data.get("p2_character", self.config.get_all_characters()[1])

        # Load snack configs
        self.snack_configs = self.config.get_all_snacks()

        # Reset game state
        self.current_level = 1
        self.current_round = 1
        self.p1_round_wins = 0
        self.p2_round_wins = 0
        self.paused = False

        # Create arenas and players
        self._setup_arenas(p1_char, p2_char)

        # Start countdown
        self._start_countdown()

    def _setup_arenas(self, p1_char: Dict, p2_char: Dict) -> None:
        """Set up the game arenas and players for 960x720 display."""
        # Arena dimensions for 960x720 display (split-screen)
        # Width: 960 - gap(20) = 940, each arena = 450
        # Height: 720 - header(70) - hud(60) - margins = ~550
        arena_width = 450
        arena_height = 520
        gap = 20

        # Calculate positions (centered)
        total_width = arena_width * 2 + gap
        start_x = (self.screen_width - total_width) // 2
        arena_y = 70  # Below header

        # Create arena bounds
        arena1_bounds = pygame.Rect(start_x, arena_y, arena_width, arena_height)
        arena2_bounds = pygame.Rect(start_x + arena_width + gap, arena_y,
                                    arena_width, arena_height)

        # Get level config
        level_config = self.config.get_level(self.current_level)
        if not level_config:
            level_config = {"background_color": [200, 200, 200], "snack_pool": ["pizza"],
                            "round_duration_seconds": 60, "spawn_rate_multiplier": 1.0}

        self.round_duration = level_config.get("round_duration_seconds", 60)

        # Create player 1
        self.player1 = Player(p1_char, arena1_bounds, player_num=1)

        # Create player 2 (AI or human)
        if self.vs_ai:
            difficulty_config = self.config.get_difficulty(self.difficulty)
            self.player2 = AIPlayer(p2_char, arena2_bounds, difficulty_config)
        else:
            self.player2 = Player(p2_char, arena2_bounds, player_num=2)

        # Create arenas
        self.arena1 = Arena(arena1_bounds, self.player1, level_config)
        self.arena2 = Arena(arena2_bounds, self.player2, level_config)

    def _start_countdown(self) -> None:
        """Start the pre-round countdown."""
        self.countdown = 3
        self.countdown_timer = 1.0
        self.round_active = False

    def _start_round(self) -> None:
        """Start the actual round."""
        self.round_timer = self.round_duration
        self.round_active = True
        self.player1.reset()
        self.player2.reset()
        self.arena1.snacks.clear()
        self.arena2.snacks.clear()

    def _end_round(self) -> None:
        """End the current round."""
        self.round_active = False

        # Determine winner
        if self.player1.score > self.player2.score:
            self.p1_round_wins += 1
        elif self.player2.score > self.player1.score:
            self.p2_round_wins += 1
        # Tie = no one wins the round

        # Check for game over
        wins_needed = (self.max_rounds // 2) + 1
        if self.p1_round_wins >= wins_needed or self.p2_round_wins >= wins_needed:
            self._end_game()
        elif self.current_round >= self.max_rounds:
            self._end_game()
        else:
            # Next round
            self.current_round += 1
            # Progress level every round
            if self.current_round <= 3:
                self.current_level = self.current_round
                level_config = self.config.get_level(self.current_level) or {}
                self.arena1.level_config = level_config
                self.arena2.level_config = level_config
                self.arena1.snack_pool = level_config.get("snack_pool", ["pizza"])
                self.arena2.snack_pool = level_config.get("snack_pool", ["pizza"])
                self.arena1.background_color = tuple(level_config.get("background_color", [200, 200, 200]))
                self.arena2.background_color = tuple(level_config.get("background_color", [200, 200, 200]))
                self.round_duration = level_config.get("round_duration_seconds", 60)
            self._start_countdown()

    def _end_game(self) -> None:
        """End the game and go to results screen."""
        winner = None
        if self.p1_round_wins > self.p2_round_wins:
            winner = "Player 1"
        elif self.p2_round_wins > self.p1_round_wins:
            winner = "Player 2" if not self.vs_ai else "AI"

        self.state_machine.change_state(GameState.GAME_OVER, {
            "winner": winner,
            "p1_score": self.player1.score,
            "p2_score": self.player2.score,
            "p1_rounds": self.p1_round_wins,
            "p2_rounds": self.p2_round_wins,
            "vs_ai": self.vs_ai
        })

    def on_exit(self) -> None:
        """Clean up when leaving gameplay."""
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.paused:
                    self.paused = False
                else:
                    self.paused = True
            elif self.paused:
                if event.key == pygame.K_q:
                    self.state_machine.change_state(GameState.MAIN_MENU)
                elif event.key == pygame.K_RETURN:
                    self.paused = False
            else:
                self._handle_key_down(event.key)

        elif event.type == pygame.KEYUP:
            self._handle_key_up(event.key)

    def _handle_key_down(self, key: int) -> None:
        """Handle key press."""
        # Player 1 controls (WASD)
        if key == pygame.K_w:
            self.p1_keys["up"] = True
        elif key == pygame.K_s:
            self.p1_keys["down"] = True
        elif key == pygame.K_a:
            self.p1_keys["left"] = True
        elif key == pygame.K_d:
            self.p1_keys["right"] = True

        # Player 2 controls (Arrow keys) - only for 2P mode
        if not self.vs_ai:
            if key == pygame.K_UP:
                self.p2_keys["up"] = True
            elif key == pygame.K_DOWN:
                self.p2_keys["down"] = True
            elif key == pygame.K_LEFT:
                self.p2_keys["left"] = True
            elif key == pygame.K_RIGHT:
                self.p2_keys["right"] = True

    def _handle_key_up(self, key: int) -> None:
        """Handle key release."""
        # Player 1 controls
        if key == pygame.K_w:
            self.p1_keys["up"] = False
        elif key == pygame.K_s:
            self.p1_keys["down"] = False
        elif key == pygame.K_a:
            self.p1_keys["left"] = False
        elif key == pygame.K_d:
            self.p1_keys["right"] = False

        # Player 2 controls
        if key == pygame.K_UP:
            self.p2_keys["up"] = False
        elif key == pygame.K_DOWN:
            self.p2_keys["down"] = False
        elif key == pygame.K_LEFT:
            self.p2_keys["left"] = False
        elif key == pygame.K_RIGHT:
            self.p2_keys["right"] = False

    def update(self, dt: float) -> None:
        """Update gameplay state."""
        if self.paused:
            return

        # Update countdown
        if self.countdown > 0:
            self.countdown_timer -= dt
            if self.countdown_timer <= 0:
                self.countdown -= 1
                self.countdown_timer = 1.0
                if self.countdown == 0:
                    self._start_round()
            return

        if not self.round_active:
            return

        # Update round timer
        self.round_timer -= dt
        if self.round_timer <= 0:
            self._end_round()
            return

        # Update screen shake
        if self.shake_duration > 0:
            self.shake_duration -= dt
            if self.shake_duration <= 0:
                self.shake_intensity = 0

        # Update players
        self.player1.handle_input(self.p1_keys)
        self.player1.update(dt)

        if isinstance(self.player2, AIPlayer):
            self.player2.update(dt, self.arena2.snacks)
        else:
            self.player2.handle_input(self.p2_keys)
            self.player2.update(dt)

        # Update arenas (spawns snacks)
        self.arena1.update(dt, self.snack_configs)
        self.arena2.update(dt, self.snack_configs)

        # Check collisions
        self._check_collisions()

    def _check_collisions(self) -> None:
        """Check for player-snack collisions."""
        # Player 1 collisions
        for snack in self.arena1.snacks[:]:
            if not snack.active:
                continue
            if self.player1.rect.colliderect(snack.rect):
                self._collect_snack(self.player1, snack)

        # Player 2 collisions
        for snack in self.arena2.snacks[:]:
            if not snack.active:
                continue
            if self.player2.rect.colliderect(snack.rect):
                self._collect_snack(self.player2, snack)

    def _collect_snack(self, player: Player, snack: Snack) -> None:
        """Handle snack collection."""
        result = snack.collect()

        # Add score
        player.add_score(result["point_value"])

        # Apply effect if any
        effect = result.get("effect")
        if effect:
            player.apply_effect(
                effect["type"],
                effect["magnitude"],
                effect["duration_seconds"]
            )

            # Trigger chaos screen shake
            if effect["type"] == "chaos":
                self.shake_intensity = 5
                self.shake_duration = effect["duration_seconds"]

    def render(self, surface: pygame.Surface) -> None:
        """Render the gameplay screen to 960x720 display."""
        surface.fill(self.bg_color)

        # Apply screen shake offset
        shake_x = 0
        shake_y = 0
        if self.shake_intensity > 0:
            import random
            shake_x = random.randint(-int(self.shake_intensity), int(self.shake_intensity))
            shake_y = random.randint(-int(self.shake_intensity), int(self.shake_intensity))

        # Draw header
        self._render_header(surface)

        # Draw arenas
        if self.arena1 and self.arena2:
            arena1_surface = self.arena1.render()
            arena2_surface = self.arena2.render()

            surface.blit(arena1_surface,
                         (self.arena1.bounds.x + shake_x, self.arena1.bounds.y + shake_y))
            surface.blit(arena2_surface,
                         (self.arena2.bounds.x + shake_x, self.arena2.bounds.y + shake_y))

        # Draw player HUDs below arenas
        if self.player1 and self.player2:
            self._render_player_hud(surface, self.player1, self.arena1.bounds, "P1")
            p2_label = "AI" if self.vs_ai else "P2"
            self._render_player_hud(surface, self.player2, self.arena2.bounds, p2_label)

        # Draw countdown
        if self.countdown > 0:
            self._render_countdown(surface)

        # Draw pause overlay
        if self.paused:
            self._render_pause(surface)

    def _render_header(self, surface: pygame.Surface) -> None:
        """Render the game header for 960x720 display."""
        # Header bar
        header_height = 60
        pygame.draw.rect(surface, (40, 80, 40), (0, 0, self.screen_width, header_height))
        pygame.draw.rect(surface, (60, 120, 60), (0, 0, self.screen_width, header_height), 2)

        # Title centered
        self.draw_text(surface, "JAZZY'S SNACK ATTACK", self.title_font,
                       (255, 220, 80), (self.screen_width // 2, 30))

        # Timer on right
        if self.round_active:
            timer_text = f"{int(self.round_timer)}s"
            timer_color = (255, 100, 100) if self.round_timer < 10 else (255, 255, 200)
            self.draw_text(surface, timer_text, self.menu_font, timer_color,
                           (self.screen_width - 60, 30))

        # Round info on left
        round_text = f"Round {self.current_round}"
        self.draw_text(surface, round_text, self.menu_font,
                       (200, 200, 150), (100, 22))

        # Wins indicator
        wins_text = f"Wins: {self.p1_round_wins} - {self.p2_round_wins}"
        self.draw_text(surface, wins_text, self.small_font,
                       (255, 255, 200), (100, 45))

    def _render_player_hud(self, surface: pygame.Surface, player: Player,
                           arena_bounds: pygame.Rect, label: str) -> None:
        """Render a player HUD below arena for 960x720."""
        hud_y = arena_bounds.bottom + 8
        hud_height = 50
        hud_width = arena_bounds.width

        # HUD background box
        color = self.p1_color if player.player_num == 1 else self.p2_color
        dark_color = (color[0] // 3, color[1] // 3, color[2] // 3)

        hud_rect = pygame.Rect(arena_bounds.x, hud_y, hud_width, hud_height)
        pygame.draw.rect(surface, dark_color, hud_rect, border_radius=8)
        pygame.draw.rect(surface, color, hud_rect, 3, border_radius=8)

        # Player label and name on left
        self.draw_text(surface, f"{label}: {player.name}", self.menu_font, (255, 255, 255),
                       (arena_bounds.x + 20, hud_y + 25), center=False)

        # Score on right
        score_text = f"Score: {player.score}"
        self.draw_text(surface, score_text, self.menu_font, (255, 220, 100),
                       (arena_bounds.right - 150, hud_y + 25), center=False)

    def _render_countdown(self, surface: pygame.Surface) -> None:
        """Render the countdown overlay for 960x720."""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(150)
        surface.blit(overlay, (0, 0))

        # Countdown number (larger font for full screen)
        if self.countdown > 0:
            text = str(self.countdown)
        else:
            text = "GO!"

        # Draw large countdown text
        large_font = pygame.font.Font(None, 200)
        text_surface = large_font.render(text, True, (255, 200, 0))
        text_rect = text_surface.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
        surface.blit(text_surface, text_rect)

    def _render_pause(self, surface: pygame.Surface) -> None:
        """Render the pause overlay for 960x720."""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(200)
        surface.blit(overlay, (0, 0))

        self.draw_text(surface, "PAUSED", self.title_font, (255, 200, 0),
                       (self.screen_width // 2, self.screen_height // 2 - 40))

        self.draw_text(surface, "Press ENTER to Resume", self.menu_font,
                       self.hud_color, (self.screen_width // 2, self.screen_height // 2 + 20))
        self.draw_text(surface, "Press Q to Quit to Menu", self.menu_font,
                       self.hud_color, (self.screen_width // 2, self.screen_height // 2 + 60))
