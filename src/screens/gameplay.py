"""Main gameplay screen with split-screen support and falling treats."""

import pygame
import random
from typing import Dict, Any, List, Optional
from .base_screen import BaseScreen, GAME_AREA_WIDTH
from ..core.state_machine import GameState
from ..core.event_bus import GameEvent
from ..entities.player import Player
from ..entities.ai_player import AIPlayer
from ..entities.snack import Snack


class FallingSnack:
    """A snack that falls from the top of the arena."""

    def __init__(self, snack_config: Dict[str, Any], x: float, arena_bounds: pygame.Rect,
                 fall_speed: float = 120, ground_y: float = None):
        self.snack_id = snack_config.get("id", "pizza")
        self.name = snack_config.get("name", "Snack")
        self.point_value = snack_config.get("point_value", 100)
        self.effect = snack_config.get("effect")
        self.color = tuple(snack_config.get("color", [255, 255, 255]))

        # Use larger size from sprite loader
        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        self.width = SpriteSheetLoader.FOOD_SIZE[0]
        self.height = SpriteSheetLoader.FOOD_SIZE[1]

        self.arena_bounds = arena_bounds
        self.x = x
        self.y = arena_bounds.top - self.height  # Start just above arena
        self.fall_speed = fall_speed

        # Ground level where snacks disappear (at player's feet level)
        self.ground_y = ground_y if ground_y else arena_bounds.bottom - 20

        self.active = True
        self.collected = False

    @property
    def rect(self) -> pygame.Rect:
        """Get the snack's collision rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def update(self, dt: float) -> bool:
        """Update snack position. Returns False if should be removed."""
        if not self.active:
            return False

        self.y += self.fall_speed * dt

        # Remove if fallen past ground level (where player stands)
        if self.y > self.ground_y:
            self.active = False
            return False

        return True

    def collect(self) -> Dict[str, Any]:
        """Mark as collected and return value."""
        self.active = False
        self.collected = True
        return {
            "snack_id": self.snack_id,
            "point_value": self.point_value,
            "effect": self.effect
        }

    def render(self, surface: pygame.Surface) -> None:
        """Render the falling snack."""
        if not self.active:
            return

        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        from ..sprites.pixel_art import SpriteCache

        # Position relative to arena
        render_x = int(self.x - self.arena_bounds.left)
        render_y = int(self.y - self.arena_bounds.top)

        # Try to get PNG food sprite first
        loader = SpriteSheetLoader()
        sprite = loader.get_food_sprite(self.snack_id)

        # Fall back to procedural sprite if PNG not available
        if sprite is None:
            cache = SpriteCache()
            sprite = cache.get_snack_sprite(self.snack_id)

        surface.blit(sprite, (render_x, render_y))


class Arena:
    """A single player's game arena for 800x800 display with falling treats."""

    def __init__(self, bounds: pygame.Rect, player: Player, level_config: Dict[str, Any]):
        self.bounds = bounds
        self.player = player
        self.level_config = level_config
        self.snacks: List[FallingSnack] = []
        self.background_color = tuple(level_config.get("background_color", [200, 200, 200]))

        # Spawn settings for falling treats
        self.spawn_timer = 0.0
        self.base_spawn_interval = 1.0
        self.spawn_rate_multiplier = level_config.get("spawn_rate_multiplier", 1.0)
        self.snack_pool = level_config.get("snack_pool", ["pizza"])
        self.max_snacks = 15
        self.fall_speed = 180  # Faster for larger screen

        # Ground level where snacks disappear (at player's feet)
        # Player top is at bounds.bottom - 160, player is 144 tall
        # So player bottom (feet) is at bounds.bottom - 160 + 144 = bounds.bottom - 16
        self.ground_y = bounds.bottom - 16

        # Create surface for this arena
        self.surface = pygame.Surface((bounds.width, bounds.height))

    def spawn_snack(self, snack_configs: List[Dict[str, Any]]) -> Optional[FallingSnack]:
        """Spawn a new falling snack at the top of the arena."""
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

        # Random X position within arena
        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        snack_size = SpriteSheetLoader.FOOD_SIZE[0]
        padding = 20
        x = random.randint(self.bounds.left + padding,
                          self.bounds.right - padding - snack_size)

        snack = FallingSnack(selected, x, self.bounds, self.fall_speed, self.ground_y)
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
        """Render the arena with wooden floor and fence border."""
        from ..sprites.pixel_art import draw_wooden_floor, draw_fence_border

        # Draw wooden plank floor
        floor_rect = pygame.Rect(0, 0, self.bounds.width, self.bounds.height)
        draw_wooden_floor(self.surface, floor_rect)

        # Draw blue wooden fence border
        border_rect = pygame.Rect(0, 0, self.bounds.width, self.bounds.height)
        draw_fence_border(self.surface, border_rect, thickness=12)

        # Draw the leash
        self._draw_leash()

        # Draw snacks
        for snack in self.snacks:
            snack.render(self.surface)

        # Draw player
        self.player.render(self.surface)

        return self.surface

    def _draw_leash(self) -> None:
        """Draw a visible leash from the left wall to the dog's collar."""
        import math

        # Leash anchor point on left wall (where it's tied)
        anchor_x = 15
        anchor_y = self.bounds.height - 100  # Near ground level

        # Dog's collar position (center-left of dog sprite, relative to arena)
        dog_x = self.player.x - self.bounds.left + 20  # Left side of dog
        dog_y = self.player.y - self.bounds.top + 40  # Near neck/collar

        # Determine leash color based on state
        leash_state = self.player.get_leash_state()
        if leash_state == "yanked":
            leash_color = (200, 80, 80)  # Red when yanked
            rope_color = (180, 60, 60)
        elif leash_state == "extended":
            leash_color = (80, 200, 80)  # Green when extended
            rope_color = (60, 180, 60)
        else:
            leash_color = (139, 90, 43)  # Brown rope normally
            rope_color = (101, 67, 33)

        # Calculate leash length and sag
        dx = dog_x - anchor_x
        dy = dog_y - anchor_y
        distance = math.sqrt(dx * dx + dy * dy)

        # Draw rope with sag (catenary-like curve)
        num_segments = 12
        sag_amount = min(30, distance * 0.15)  # More sag for longer leash

        points = []
        for i in range(num_segments + 1):
            t = i / num_segments
            # Linear interpolation
            x = anchor_x + dx * t
            y = anchor_y + dy * t
            # Add sag (parabolic curve, maximum at middle)
            sag = sag_amount * 4 * t * (1 - t)
            y += sag
            points.append((int(x), int(y)))

        # Draw thick rope shadow
        if len(points) > 1:
            pygame.draw.lines(self.surface, (50, 30, 20), False, points, 6)
            # Draw main rope
            pygame.draw.lines(self.surface, leash_color, False, points, 4)
            # Draw highlight
            highlight_points = [(p[0], p[1] - 1) for p in points]
            pygame.draw.lines(self.surface, rope_color, False, highlight_points, 2)

        # Draw anchor ring on wall
        pygame.draw.circle(self.surface, (100, 100, 100), (anchor_x, anchor_y), 8)
        pygame.draw.circle(self.surface, (150, 150, 150), (anchor_x, anchor_y), 6)
        pygame.draw.circle(self.surface, (80, 80, 80), (anchor_x, anchor_y), 4)

        # Draw collar on dog
        collar_x = int(dog_x)
        collar_y = int(dog_y)
        pygame.draw.circle(self.surface, leash_color, (collar_x, collar_y), 6)
        pygame.draw.circle(self.surface, (200, 200, 200), (collar_x, collar_y), 4)


class VotingSystem:
    """Manages voting for extend/yank leash effects."""

    def __init__(self):
        self.votes: Dict[str, List[str]] = {"extend": [], "yank": []}
        self.voting_active = True
        self.voting_duration = 10.0  # seconds
        self.cooldown_duration = 5.0  # seconds after effects are applied
        self.voting_timer = self.voting_duration
        self.cooldown_timer = 0.0
        self.last_winner: Optional[str] = None

    def add_vote(self, vote_type: str, voter_id: str) -> bool:
        """Add a vote. Returns True if successful."""
        if not self.voting_active:
            return False
        if vote_type not in self.votes:
            return False
        # One vote per user
        for v_type, voters in self.votes.items():
            if voter_id in voters:
                voters.remove(voter_id)
        self.votes[vote_type].append(voter_id)
        return True

    def get_vote_counts(self) -> Dict[str, int]:
        """Get current vote counts."""
        return {k: len(v) for k, v in self.votes.items()}

    def get_winner(self) -> Optional[str]:
        """Get the winning vote type, or None if tied."""
        counts = self.get_vote_counts()
        extend_votes = counts.get("extend", 0)
        yank_votes = counts.get("yank", 0)

        if extend_votes > yank_votes:
            return "extend"
        elif yank_votes > extend_votes:
            return "yank"
        return None  # Tied

    def update(self, dt: float) -> Optional[str]:
        """Update voting state. Returns winner if voting just ended."""
        if self.cooldown_timer > 0:
            self.cooldown_timer -= dt
            if self.cooldown_timer <= 0:
                self.reset_votes()
                self.voting_active = True
                self.voting_timer = self.voting_duration
            return None

        if self.voting_active:
            self.voting_timer -= dt
            if self.voting_timer <= 0:
                winner = self.get_winner()
                self.last_winner = winner
                self.voting_active = False
                self.cooldown_timer = self.cooldown_duration
                return winner
        return None

    def reset_votes(self) -> None:
        """Reset all votes."""
        self.votes = {"extend": [], "yank": []}
        self.last_winner = None


class VotingMeter:
    """Visual display for voting status."""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.rect = pygame.Rect(x, y, width, height)
        self.extend_color = (50, 200, 50)  # Green
        self.yank_color = (200, 50, 50)  # Red
        self.bg_color = (40, 40, 60)
        self.border_color = (100, 100, 140)

    def render(self, surface: pygame.Surface, voting_system: 'VotingSystem',
               font: pygame.font.Font, small_font: pygame.font.Font) -> None:
        """Render the voting meter."""
        # Background
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=8)
        pygame.draw.rect(surface, self.border_color, self.rect, 2, border_radius=8)

        counts = voting_system.get_vote_counts()
        extend_votes = counts.get("extend", 0)
        yank_votes = counts.get("yank", 0)
        total_votes = extend_votes + yank_votes

        # Vote bars
        bar_height = 20
        bar_y = self.rect.y + 30
        bar_margin = 20
        bar_width = self.rect.width - bar_margin * 2

        # Extend bar (green, left side)
        extend_bar_rect = pygame.Rect(self.rect.x + bar_margin, bar_y, bar_width // 2 - 5, bar_height)
        pygame.draw.rect(surface, (30, 60, 30), extend_bar_rect, border_radius=4)

        # Yank bar (red, right side)
        yank_bar_rect = pygame.Rect(self.rect.x + bar_margin + bar_width // 2 + 5, bar_y, bar_width // 2 - 5, bar_height)
        pygame.draw.rect(surface, (60, 30, 30), yank_bar_rect, border_radius=4)

        # Fill bars proportionally
        if total_votes > 0:
            extend_fill = int((extend_votes / max(extend_votes + yank_votes, 1)) * (bar_width // 2 - 10))
            yank_fill = int((yank_votes / max(extend_votes + yank_votes, 1)) * (bar_width // 2 - 10))

            if extend_fill > 0:
                fill_rect = pygame.Rect(extend_bar_rect.x + 3, bar_y + 3, extend_fill, bar_height - 6)
                pygame.draw.rect(surface, self.extend_color, fill_rect, border_radius=2)

            if yank_fill > 0:
                fill_rect = pygame.Rect(yank_bar_rect.x + 3, bar_y + 3, yank_fill, bar_height - 6)
                pygame.draw.rect(surface, self.yank_color, fill_rect, border_radius=2)

        # Labels and counts
        label_y = self.rect.y + 12
        text_surf = small_font.render("EXTEND", True, self.extend_color)
        surface.blit(text_surf, (self.rect.x + bar_margin, label_y))

        text_surf = small_font.render("YANK", True, self.yank_color)
        text_rect = text_surf.get_rect(right=self.rect.right - bar_margin)
        text_rect.y = label_y
        surface.blit(text_surf, text_rect)

        # Vote counts
        count_y = bar_y + bar_height + 5
        text_surf = small_font.render(str(extend_votes), True, (255, 255, 255))
        surface.blit(text_surf, (extend_bar_rect.centerx - text_surf.get_width() // 2, count_y))

        text_surf = small_font.render(str(yank_votes), True, (255, 255, 255))
        surface.blit(text_surf, (yank_bar_rect.centerx - text_surf.get_width() // 2, count_y))

        # Timer or status
        status_y = self.rect.bottom - 25
        if voting_system.voting_active:
            timer_text = f"Voting: {int(voting_system.voting_timer)}s"
            text_surf = small_font.render(timer_text, True, (200, 200, 100))
        elif voting_system.cooldown_timer > 0:
            if voting_system.last_winner:
                status_text = f"{voting_system.last_winner.upper()}! ({int(voting_system.cooldown_timer)}s)"
                color = self.extend_color if voting_system.last_winner == "extend" else self.yank_color
            else:
                status_text = f"TIE! ({int(voting_system.cooldown_timer)}s)"
                color = (200, 200, 100)
            text_surf = small_font.render(status_text, True, color)
        else:
            text_surf = small_font.render("Waiting...", True, (150, 150, 150))

        surface.blit(text_surf, (self.rect.centerx - text_surf.get_width() // 2, status_y))


class ChatMessage:
    """A single chat message for the simulator."""

    def __init__(self, username: str, message: str, color: tuple = (255, 255, 255)):
        self.username = username
        self.message = message
        self.color = color
        self.timestamp = 0.0


class ChatSimulator:
    """Simulates chat messages for testing voting."""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.rect = pygame.Rect(x, y, width, height)
        self.messages: List[ChatMessage] = []
        self.max_messages = 15
        self.auto_vote = False
        self.auto_vote_timer = 0.0
        self.auto_vote_interval = 2.0  # seconds between auto votes

        # Bot names for auto-voting
        self.bot_names = ["TwitchBot1", "Viewer42", "DogLover", "ChatFan", "StreamPro",
                          "GamePlayer", "CoolUser", "NicePerson", "HelpfulHank", "FunGuy"]
        self.next_bot_id = 1

        # Button rects (will be set in render)
        self.extend_btn = pygame.Rect(0, 0, 0, 0)
        self.yank_btn = pygame.Rect(0, 0, 0, 0)
        self.auto_btn = pygame.Rect(0, 0, 0, 0)

        self.bg_color = (25, 25, 35)
        self.border_color = (80, 80, 100)

    def add_message(self, username: str, message: str, color: tuple = (255, 255, 255)) -> None:
        """Add a chat message."""
        msg = ChatMessage(username, message, color)
        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    def inject_vote(self, vote_type: str, voting_system: 'VotingSystem') -> None:
        """Inject a simulated vote."""
        bot_name = f"Bot{self.next_bot_id}"
        self.next_bot_id = (self.next_bot_id % 99) + 1

        cmd = f"!{vote_type}"
        color = (50, 200, 50) if vote_type == "extend" else (200, 50, 50)
        self.add_message(bot_name, cmd, color)
        voting_system.add_vote(vote_type, bot_name)

    def update(self, dt: float, voting_system: 'VotingSystem') -> None:
        """Update auto-voting if enabled."""
        if self.auto_vote and voting_system.voting_active:
            self.auto_vote_timer -= dt
            if self.auto_vote_timer <= 0:
                # Random vote
                vote_type = random.choice(["extend", "yank"])
                self.inject_vote(vote_type, voting_system)
                self.auto_vote_timer = self.auto_vote_interval + random.uniform(-0.5, 0.5)

    def handle_click(self, pos: tuple, voting_system: 'VotingSystem') -> bool:
        """Handle mouse click. Returns True if handled."""
        if self.extend_btn.collidepoint(pos):
            self.inject_vote("extend", voting_system)
            return True
        elif self.yank_btn.collidepoint(pos):
            self.inject_vote("yank", voting_system)
            return True
        elif self.auto_btn.collidepoint(pos):
            self.auto_vote = not self.auto_vote
            if self.auto_vote:
                self.add_message("System", "Auto-vote ON", (200, 200, 100))
            else:
                self.add_message("System", "Auto-vote OFF", (150, 150, 150))
            return True
        return False

    def render(self, surface: pygame.Surface, font: pygame.font.Font,
               small_font: pygame.font.Font) -> None:
        """Render the chat simulator panel."""
        # Background
        pygame.draw.rect(surface, self.bg_color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 2)

        # Header
        header_rect = pygame.Rect(self.rect.x, self.rect.y, self.rect.width, 35)
        pygame.draw.rect(surface, (40, 40, 55), header_rect)
        pygame.draw.line(surface, self.border_color, (self.rect.x, header_rect.bottom),
                        (self.rect.right, header_rect.bottom), 2)

        header_text = font.render("CHAT SIM", True, (200, 200, 255))
        surface.blit(header_text, (self.rect.x + 10, self.rect.y + 8))

        # Messages area
        msg_y = header_rect.bottom + 10
        msg_height = 16
        for msg in self.messages[-12:]:  # Show last 12 messages
            # Username
            user_surf = small_font.render(f"{msg.username}:", True, msg.color)
            surface.blit(user_surf, (self.rect.x + 8, msg_y))

            # Message (truncate if needed)
            msg_text = msg.message[:15] if len(msg.message) > 15 else msg.message
            msg_surf = small_font.render(msg_text, True, (220, 220, 220))
            surface.blit(msg_surf, (self.rect.x + 8 + user_surf.get_width() + 5, msg_y))

            msg_y += msg_height
            if msg_y > self.rect.bottom - 120:
                break

        # Buttons at bottom
        btn_width = 80
        btn_height = 30
        btn_y = self.rect.bottom - 100

        # Extend button
        self.extend_btn = pygame.Rect(self.rect.x + 10, btn_y, btn_width, btn_height)
        pygame.draw.rect(surface, (30, 80, 30), self.extend_btn, border_radius=5)
        pygame.draw.rect(surface, (50, 200, 50), self.extend_btn, 2, border_radius=5)
        text = small_font.render("!extend", True, (50, 200, 50))
        surface.blit(text, (self.extend_btn.centerx - text.get_width() // 2,
                           self.extend_btn.centery - text.get_height() // 2))

        # Yank button
        self.yank_btn = pygame.Rect(self.rect.x + 100, btn_y, btn_width, btn_height)
        pygame.draw.rect(surface, (80, 30, 30), self.yank_btn, border_radius=5)
        pygame.draw.rect(surface, (200, 50, 50), self.yank_btn, 2, border_radius=5)
        text = small_font.render("!yank", True, (200, 50, 50))
        surface.blit(text, (self.yank_btn.centerx - text.get_width() // 2,
                           self.yank_btn.centery - text.get_height() // 2))

        # Auto button
        self.auto_btn = pygame.Rect(self.rect.x + 10, btn_y + 40, self.rect.width - 20, btn_height)
        auto_color = (100, 200, 100) if self.auto_vote else (100, 100, 100)
        pygame.draw.rect(surface, (30, 30, 40), self.auto_btn, border_radius=5)
        pygame.draw.rect(surface, auto_color, self.auto_btn, 2, border_radius=5)
        auto_text = "AUTO: ON" if self.auto_vote else "AUTO: OFF"
        text = small_font.render(auto_text, True, auto_color)
        surface.blit(text, (self.auto_btn.centerx - text.get_width() // 2,
                           self.auto_btn.centery - text.get_height() // 2))

        # Instructions
        instr_y = self.rect.bottom - 20
        instr = small_font.render("Click buttons to vote", True, (120, 120, 140))
        surface.blit(instr, (self.rect.x + 10, instr_y))


class GameplayScreen(BaseScreen):
    """Split-screen gameplay screen with falling treats."""

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

        # Control key states - horizontal only
        self.p1_keys = {"left": False, "right": False}
        self.p2_keys = {"left": False, "right": False}

        # Voting system for audience interaction
        self.voting_system: Optional[VotingSystem] = None
        self.voting_meter: Optional[VotingMeter] = None
        self.chat_simulator: Optional[ChatSimulator] = None

        # Game area width (1000px, rest is chat panel)
        self.game_area_width = GAME_AREA_WIDTH

        # Announcement system for dramatic effect reveals
        self.announcement_text = ""
        self.announcement_color = (255, 255, 255)
        self.announcement_timer = 0.0
        self.announcement_duration = 2.0  # seconds

        # Screen flash effect
        self.flash_color = (0, 0, 0)
        self.flash_alpha = 0
        self.flash_timer = 0.0

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

        # Initialize voting system and UI
        self._setup_voting_ui()

        # Start countdown
        self._start_countdown()

    def _setup_arenas(self, p1_char: Dict, p2_char: Dict) -> None:
        """Set up the game arenas and players."""
        # Arena dimensions for game area (split-screen, not including chat panel)
        gap = 16
        arena_width = (self.game_area_width - gap) // 2
        arena_height = self.screen_height - 140  # Leave room for header and HUD

        # Calculate positions
        arena_y = 65  # Below header

        # Create arena bounds
        arena1_bounds = pygame.Rect(0, arena_y, arena_width, arena_height)
        arena2_bounds = pygame.Rect(arena_width + gap, arena_y, arena_width, arena_height)

        # Get level config
        level_config = self.config.get_level(self.current_level)
        if not level_config:
            level_config = {"background_color": [200, 200, 200], "snack_pool": ["pizza"],
                            "round_duration_seconds": 60, "spawn_rate_multiplier": 1.0}

        self.round_duration = level_config.get("round_duration_seconds", 60)

        # Create player 1 - horizontal movement only
        self.player1 = Player(p1_char, arena1_bounds, player_num=1, horizontal_only=True)

        # Create player 2 (AI or human) - horizontal movement only
        if self.vs_ai:
            difficulty_config = self.config.get_difficulty(self.difficulty)
            self.player2 = AIPlayer(p2_char, arena2_bounds, difficulty_config, horizontal_only=True)
        else:
            self.player2 = Player(p2_char, arena2_bounds, player_num=2, horizontal_only=True)

        # Create arenas
        self.arena1 = Arena(arena1_bounds, self.player1, level_config)
        self.arena2 = Arena(arena2_bounds, self.player2, level_config)

        # Position players at ground level (offset for larger sprites)
        ground_offset = 160
        self.player1.y = arena1_bounds.bottom - ground_offset
        self.player2.y = arena2_bounds.bottom - ground_offset

    def _setup_voting_ui(self) -> None:
        """Set up the voting system and UI components."""
        # Initialize voting system
        self.voting_system = VotingSystem()

        # Voting meter at top center of game area
        meter_width = 300
        meter_height = 85
        meter_x = (self.game_area_width - meter_width) // 2
        meter_y = 58  # Just below header
        self.voting_meter = VotingMeter(meter_x, meter_y, meter_width, meter_height)

        # Chat simulator panel on right side of screen
        panel_width = self.screen_width - self.game_area_width
        self.chat_simulator = ChatSimulator(
            self.game_area_width, 0, panel_width, self.screen_height
        )
        self.chat_simulator.add_message("System", "Welcome!", (200, 200, 100))
        self.chat_simulator.add_message("System", "Click !extend or", (150, 150, 150))
        self.chat_simulator.add_message("System", "!yank to vote!", (150, 150, 150))

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

        # Reset player positions to ground
        ground_offset = 160
        self.player1.y = self.arena1.bounds.bottom - ground_offset
        self.player2.y = self.arena2.bounds.bottom - ground_offset

    def _end_round(self) -> None:
        """End the current round."""
        self.round_active = False

        # Determine winner
        if self.player1.score > self.player2.score:
            self.p1_round_wins += 1
        elif self.player2.score > self.player1.score:
            self.p2_round_wins += 1

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
                # Increase difficulty
                self.arena1.fall_speed = 180 + (self.current_level - 1) * 30
                self.arena2.fall_speed = 180 + (self.current_level - 1) * 30
                self.arena1.base_spawn_interval = max(0.5, 1.0 - (self.current_level - 1) * 0.15)
                self.arena2.base_spawn_interval = max(0.5, 1.0 - (self.current_level - 1) * 0.15)
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

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                if self.chat_simulator and self.voting_system:
                    self.chat_simulator.handle_click(event.pos, self.voting_system)

    def _handle_key_down(self, key: int) -> None:
        """Handle key press - horizontal only."""
        # Player 1 controls (WASD)
        if key == pygame.K_a:
            self.p1_keys["left"] = True
        elif key == pygame.K_d:
            self.p1_keys["right"] = True

        # In 1P mode, arrow keys also control player 1
        if self.vs_ai:
            if key == pygame.K_LEFT:
                self.p1_keys["left"] = True
            elif key == pygame.K_RIGHT:
                self.p1_keys["right"] = True
        else:
            # Player 2 controls (Arrow keys) - only for 2P mode
            if key == pygame.K_LEFT:
                self.p2_keys["left"] = True
            elif key == pygame.K_RIGHT:
                self.p2_keys["right"] = True

    def _handle_key_up(self, key: int) -> None:
        """Handle key release - horizontal only."""
        # Player 1 controls
        if key == pygame.K_a:
            self.p1_keys["left"] = False
        elif key == pygame.K_d:
            self.p1_keys["right"] = False

        # In 1P mode, arrow keys also control player 1
        if self.vs_ai:
            if key == pygame.K_LEFT:
                self.p1_keys["left"] = False
            elif key == pygame.K_RIGHT:
                self.p1_keys["right"] = False
        else:
            # Player 2 controls
            if key == pygame.K_LEFT:
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

        # Update announcement timer
        if self.announcement_timer > 0:
            self.announcement_timer -= dt

        # Update flash timer
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.flash_alpha = 0

        # Update voting system
        if self.voting_system:
            vote_winner = self.voting_system.update(dt)
            if vote_winner:
                self._apply_vote_effect(vote_winner)

        # Update chat simulator (auto-voting)
        if self.chat_simulator and self.voting_system:
            self.chat_simulator.update(dt, self.voting_system)

        # Update players - horizontal only keys
        self.player1.handle_input(self.p1_keys)
        self.player1.update(dt)

        if isinstance(self.player2, AIPlayer):
            self.player2.update(dt, self.arena2.snacks)
        else:
            self.player2.handle_input(self.p2_keys)
            self.player2.update(dt)

        # Update arenas (spawns falling snacks)
        self.arena1.update(dt, self.snack_configs)
        self.arena2.update(dt, self.snack_configs)

        # Check collisions
        self._check_collisions()

    def _check_collisions(self) -> None:
        """Check for player-snack collisions."""
        # Player 1 collisions with their own arena
        for snack in self.arena1.snacks[:]:
            if not snack.active:
                continue
            if self.player1.rect.colliderect(snack.rect):
                self._collect_snack(self.player1, snack)

        # Player 2 collisions with their own arena
        for snack in self.arena2.snacks[:]:
            if not snack.active:
                continue
            if self.player2.rect.colliderect(snack.rect):
                self._collect_snack(self.player2, snack)

        # Cross-arena collisions when unleashed!
        # Player 1 can steal from arena 2 if they've crossed over
        if self.player1.get_leash_state() == "extended":
            for snack in self.arena2.snacks[:]:
                if not snack.active:
                    continue
                if self.player1.rect.colliderect(snack.rect):
                    self._collect_snack(self.player1, snack, stolen=True)

        # Player 2 can steal from arena 1 if they've crossed over
        if self.player2.get_leash_state() == "extended":
            for snack in self.arena1.snacks[:]:
                if not snack.active:
                    continue
                if self.player2.rect.colliderect(snack.rect):
                    self._collect_snack(self.player2, snack, stolen=True)

    def _collect_snack(self, player: Player, snack: FallingSnack, stolen: bool = False) -> None:
        """Handle snack collection."""
        result = snack.collect()

        # Trigger eat animation
        player.trigger_eat_animation()

        # Add score (bonus for stolen snacks!)
        points = result["point_value"]
        if stolen:
            points = int(points * 1.5)  # 50% bonus for stealing!
            if self.chat_simulator:
                self.chat_simulator.add_message("System", "STOLEN! +50%", (255, 200, 50))

        player.add_score(points)

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

    def _apply_vote_effect(self, vote_type: str) -> None:
        """Apply the winning vote effect to both players."""
        if vote_type == "extend":
            # Calculate how far into the OTHER arena each player can go
            # Player 1 can go into arena 2's left portion
            p1_cross_max = self.arena2.bounds.left + 150  # 150px into arena 2
            # Player 2 can go into arena 1's right portion
            p2_cross_max = self.arena1.bounds.right + 150  # This is arena2's extended range

            self.player1.extend_leash(cross_arena_max_x=p1_cross_max)
            self.player2.extend_leash(cross_arena_max_x=p2_cross_max)

            if self.chat_simulator:
                self.chat_simulator.add_message("System", "LEASH EXTENDED!", (50, 200, 50))
                self.chat_simulator.add_message("System", "Dogs can CROSS!", (100, 255, 100))
            # Trigger dramatic announcement
            self.announcement_text = "UNLEASHED!"
            self.announcement_color = (50, 255, 50)
            self.announcement_timer = self.announcement_duration
            self.flash_color = (50, 200, 50)
            self.flash_alpha = 150
            self.flash_timer = 0.3
        elif vote_type == "yank":
            self.player1.yank_leash()
            self.player2.yank_leash()
            if self.chat_simulator:
                self.chat_simulator.add_message("System", "LEASH YANKED!", (200, 50, 50))
            # Trigger dramatic announcement
            self.announcement_text = "LEASH YANKED!"
            self.announcement_color = (255, 50, 50)
            self.announcement_timer = self.announcement_duration
            self.flash_color = (200, 50, 50)
            self.flash_alpha = 150
            self.flash_timer = 0.3

    def render(self, surface: pygame.Surface) -> None:
        """Render the gameplay screen to 800x800 display."""
        surface.fill(self.bg_color)

        # Apply screen shake offset
        shake_x = 0
        shake_y = 0
        if self.shake_intensity > 0:
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

            # Render players who have crossed into the other arena (on top of everything)
            self._render_crossed_players(surface, shake_x, shake_y)

        # Draw player HUDs below arenas
        if self.player1 and self.player2:
            self._render_player_hud(surface, self.player1, self.arena1.bounds, "P1")
            p2_label = "AI" if self.vs_ai else "P2"
            self._render_player_hud(surface, self.player2, self.arena2.bounds, p2_label)

        # Draw voting meter (overlays top of arenas)
        if self.voting_meter and self.voting_system:
            self.voting_meter.render(surface, self.voting_system, self.menu_font, self.small_font)

        # Draw chat simulator panel on right
        if self.chat_simulator:
            self.chat_simulator.render(surface, self.menu_font, self.small_font)

        # Draw leash indicators on arenas
        self._render_leash_indicators(surface)

        # Draw screen flash effect
        if self.flash_alpha > 0:
            flash_surface = pygame.Surface((self.game_area_width, self.screen_height))
            flash_surface.fill(self.flash_color)
            flash_surface.set_alpha(self.flash_alpha)
            surface.blit(flash_surface, (0, 0))

        # Draw announcement text
        if self.announcement_timer > 0:
            self._render_announcement(surface)

        # Draw countdown
        if self.countdown > 0:
            self._render_countdown(surface)

        # Draw pause overlay
        if self.paused:
            self._render_pause(surface)

    def _render_header(self, surface: pygame.Surface) -> None:
        """Render the game header."""
        # Header bar (only over game area)
        header_height = 55
        pygame.draw.rect(surface, (40, 80, 40), (0, 0, self.game_area_width, header_height))
        pygame.draw.rect(surface, (60, 120, 60), (0, 0, self.game_area_width, header_height), 2)

        # Title centered in game area
        self.draw_text(surface, "JAZZY'S SNACK ATTACK", self.title_font,
                       (255, 220, 80), (self.game_area_width // 2, 28))

        # Timer on right side of game area
        if self.round_active:
            timer_text = f"{int(self.round_timer)}s"
            timer_color = (255, 100, 100) if self.round_timer < 10 else (255, 255, 200)
            self.draw_text(surface, timer_text, self.menu_font, timer_color,
                           (self.game_area_width - 50, 28))

        # Round info on left
        round_text = f"R{self.current_round}"
        self.draw_text(surface, round_text, self.menu_font,
                       (200, 200, 150), (40, 20))

        # Wins indicator
        wins_text = f"{self.p1_round_wins}-{self.p2_round_wins}"
        self.draw_text(surface, wins_text, self.small_font,
                       (255, 255, 200), (40, 42))

    def _render_player_hud(self, surface: pygame.Surface, player: Player,
                           arena_bounds: pygame.Rect, label: str) -> None:
        """Render a player HUD below arena for 800x800."""
        hud_y = arena_bounds.bottom + 5
        hud_height = 45
        hud_width = arena_bounds.width

        # HUD background box
        color = self.p1_color if player.player_num == 1 else self.p2_color
        dark_color = (color[0] // 3, color[1] // 3, color[2] // 3)

        hud_rect = pygame.Rect(arena_bounds.x, hud_y, hud_width, hud_height)
        pygame.draw.rect(surface, dark_color, hud_rect, border_radius=6)
        pygame.draw.rect(surface, color, hud_rect, 2, border_radius=6)

        # Player label and name on left
        self.draw_text(surface, f"{label}: {player.name}", self.small_font, (255, 255, 255),
                       (arena_bounds.x + 10, hud_y + 22), center=False)

        # Score on right
        score_text = f"{player.score}"
        self.draw_text(surface, score_text, self.menu_font, (255, 220, 100),
                       (arena_bounds.right - 60, hud_y + 22), center=False)

    def _render_crossed_players(self, surface: pygame.Surface, shake_x: int, shake_y: int) -> None:
        """Render players who have crossed into the gap or other arena."""
        # Check if player 1 has crossed into the gap or arena 2
        if self.player1.x + self.player1.width > self.arena1.bounds.right:
            # Player 1 is crossing! Render them on the main surface
            sprite = self.player1.animation_controller.get_current_sprite()
            if sprite:
                render_x = int(self.player1.x) + shake_x
                render_y = int(self.player1.y) + shake_y
                surface.blit(sprite, (render_x, render_y))

                # Draw a glowing outline to show they're "unleashed"
                glow_rect = pygame.Rect(render_x - 3, render_y - 3,
                                       self.player1.width + 6, self.player1.height + 6)
                pygame.draw.rect(surface, (50, 255, 50), glow_rect, 3, border_radius=8)

        # Check if player 2 has crossed into the gap or arena 1
        if self.player2.x < self.arena2.bounds.left:
            # Player 2 is crossing! Render them on the main surface
            sprite = self.player2.animation_controller.get_current_sprite()
            if sprite:
                render_x = int(self.player2.x) + shake_x
                render_y = int(self.player2.y) + shake_y
                surface.blit(sprite, (render_x, render_y))

                # Draw a glowing outline to show they're "unleashed"
                glow_rect = pygame.Rect(render_x - 3, render_y - 3,
                                       self.player2.width + 6, self.player2.height + 6)
                pygame.draw.rect(surface, (50, 255, 50), glow_rect, 3, border_radius=8)

    def _render_countdown(self, surface: pygame.Surface) -> None:
        """Render the countdown overlay."""
        # Semi-transparent overlay (only over game area)
        overlay = pygame.Surface((self.game_area_width, self.screen_height))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(150)
        surface.blit(overlay, (0, 0))

        # Countdown number
        if self.countdown > 0:
            text = str(self.countdown)
        else:
            text = "GO!"

        # Draw large countdown text (centered in game area)
        large_font = pygame.font.Font(None, 180)
        text_surface = large_font.render(text, True, (255, 200, 0))
        text_rect = text_surface.get_rect(center=(self.game_area_width // 2, self.screen_height // 2))
        surface.blit(text_surface, text_rect)

    def _render_pause(self, surface: pygame.Surface) -> None:
        """Render the pause overlay."""
        # Semi-transparent overlay (only over game area)
        overlay = pygame.Surface((self.game_area_width, self.screen_height))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(200)
        surface.blit(overlay, (0, 0))

        center_x = self.game_area_width // 2
        self.draw_text(surface, "PAUSED", self.title_font, (255, 200, 0),
                       (center_x, self.screen_height // 2 - 40))

        self.draw_text(surface, "Press ENTER to Resume", self.menu_font,
                       self.hud_color, (center_x, self.screen_height // 2 + 20))
        self.draw_text(surface, "Press Q to Quit to Menu", self.menu_font,
                       self.hud_color, (center_x, self.screen_height // 2 + 60))

    def _render_leash_indicators(self, surface: pygame.Surface) -> None:
        """Render visual indicators for leash state on each arena."""
        for player, arena in [(self.player1, self.arena1), (self.player2, self.arena2)]:
            if not player or not arena:
                continue

            leash_state = player.get_leash_state()
            if leash_state == "normal":
                continue

            if leash_state == "extended":
                # Draw green glow on the right edge indicating freedom
                for i in range(30):
                    alpha = 180 - i * 6
                    if alpha > 0:
                        pygame.draw.line(surface, (50, 200, 50),
                                       (arena.bounds.right - i, arena.bounds.top + 60),
                                       (arena.bounds.right - i, arena.bounds.bottom - 20), 2)

                # Draw arrow pointing to the other arena
                arrow_x = arena.bounds.right - 40
                arrow_y = arena.bounds.centery
                pygame.draw.polygon(surface, (50, 255, 50), [
                    (arrow_x, arrow_y - 20),
                    (arrow_x + 30, arrow_y),
                    (arrow_x, arrow_y + 20)
                ])

                # Draw "GO STEAL!" text
                text_surf = self.menu_font.render("GO STEAL!", True, (50, 255, 50))
                text_x = arena.bounds.centerx - text_surf.get_width() // 2
                surface.blit(text_surf, (text_x, arena.bounds.top + 10))

            elif leash_state == "yanked":
                # Calculate where the restriction line is
                restrict_x = int(player.leash_max_x)

                # Draw a thick red barrier line
                pygame.draw.line(surface, (255, 50, 50),
                               (restrict_x, arena.bounds.top + 60),
                               (restrict_x, arena.bounds.bottom - 20), 8)

                # Draw pulsing X pattern on the restricted zone
                restricted_width = arena.bounds.right - restrict_x
                if restricted_width > 10:
                    # Semi-transparent red overlay on restricted area
                    restricted_surface = pygame.Surface((restricted_width, arena.bounds.height - 80))
                    restricted_surface.fill((200, 50, 50))
                    restricted_surface.set_alpha(80)
                    surface.blit(restricted_surface, (restrict_x, arena.bounds.top + 60))

                    # Draw X marks
                    for x_offset in range(20, restricted_width - 10, 40):
                        x_pos = restrict_x + x_offset
                        y_center = arena.bounds.centery
                        pygame.draw.line(surface, (255, 100, 100),
                                       (x_pos - 10, y_center - 10),
                                       (x_pos + 10, y_center + 10), 3)
                        pygame.draw.line(surface, (255, 100, 100),
                                       (x_pos + 10, y_center - 10),
                                       (x_pos - 10, y_center + 10), 3)

                # Draw "RESTRICTED!" text
                text_surf = self.menu_font.render("RESTRICTED!", True, (255, 50, 50))
                text_x = arena.bounds.centerx - text_surf.get_width() // 2
                surface.blit(text_surf, (text_x, arena.bounds.top + 10))

    def _render_announcement(self, surface: pygame.Surface) -> None:
        """Render a big dramatic announcement in the center of the screen."""
        # Calculate pulse effect based on timer
        pulse = 1.0 + 0.1 * abs((self.announcement_timer % 0.4) - 0.2) / 0.2

        # Create large font
        font_size = int(100 * pulse)
        large_font = pygame.font.Font(None, font_size)

        # Render text with shadow
        shadow_surf = large_font.render(self.announcement_text, True, (0, 0, 0))
        text_surf = large_font.render(self.announcement_text, True, self.announcement_color)

        # Center in game area
        center_x = self.game_area_width // 2
        center_y = self.screen_height // 2

        shadow_rect = shadow_surf.get_rect(center=(center_x + 4, center_y + 4))
        text_rect = text_surf.get_rect(center=(center_x, center_y))

        surface.blit(shadow_surf, shadow_rect)
        surface.blit(text_surf, text_rect)

        # Draw subtitle explaining what happened
        if "UNLEASHED" in self.announcement_text:
            subtitle = "Dogs can cross into enemy territory!"
            subtitle2 = "Steal snacks for 50% BONUS!"
        else:
            subtitle = "Dogs movement is restricted!"
            subtitle2 = None

        subtitle_surf = self.small_font.render(subtitle, True, (255, 255, 255))
        subtitle_rect = subtitle_surf.get_rect(center=(center_x, center_y + 60))
        surface.blit(subtitle_surf, subtitle_rect)

        if subtitle2:
            subtitle2_surf = self.small_font.render(subtitle2, True, (255, 220, 100))
            subtitle2_rect = subtitle2_surf.get_rect(center=(center_x, center_y + 85))
            surface.blit(subtitle2_surf, subtitle2_rect)
