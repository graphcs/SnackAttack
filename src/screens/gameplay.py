"""Main gameplay screen with split-screen support and falling treats."""

import os
import pygame
import random
from typing import Dict, Any, List, Optional, Tuple
from .base_screen import BaseScreen, GAME_AREA_WIDTH
from ..core.state_machine import GameState
from ..core.event_bus import GameEvent
from ..core.env_loader import load_env, get_twitch_token
from ..entities.player import Player
from ..entities.ai_player import AIPlayer
from ..entities.snack import Snack
from ..interaction.twitch_chat import TwitchChatManager, TWITCH_VOTE_EVENT
from ..sprites.sprite_sheet_loader import AnimationState
from ..effects.round_start_intro import RoundStartIntro
from ..effects.powerup_vfx import SnackGlow

from enum import Enum, auto

class VotingMode(Enum):
    """Voting modes for different rounds."""
    ACTION = auto()  # Yank/Extend
    TREAT = auto()   # Vote for a treat
    TRIVIA = auto()  # Trivia question



class FallingSnack:
    """A snack that falls from the top of the arena."""

    def __init__(self, snack_config: Dict[str, Any], x: float, arena_bounds: pygame.Rect,
                 fall_speed: float = 120, ground_y: float = None, scale: float = 1.0):
        self.snack_id = snack_config.get("id", "pizza")
        self.name = snack_config.get("name", "Snack")
        self.point_value = snack_config.get("point_value", 100)
        self.effect = snack_config.get("effect")
        self.color = tuple(snack_config.get("color", [255, 255, 255]))
        self.scale = scale  # Scale multiplier for size

        # Use larger size from sprite loader, scaled
        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        self.width = int(SpriteSheetLoader.FOOD_SIZE[0] * scale)
        self.height = int(SpriteSheetLoader.FOOD_SIZE[1] * scale)

        self.arena_bounds = arena_bounds
        self.x = x
        self.y = arena_bounds.top + 60  # Start lower, below menu bar
        self.fall_speed = fall_speed

        # Ground level where snacks disappear (at player's feet level)
        self.ground_y = ground_y if ground_y else arena_bounds.bottom - 20

        self.active = True
        self.collected = False

        # Rotation for natural falling effect
        import random
        self.rotation_angle = random.uniform(0, 360)  # Random start angle
        # Slow rotation, random direction (positive = counter-clockwise, negative = clockwise)
        self.rotation_speed = random.uniform(30, 60) * random.choice([-1, 1])

    @property
    def rect(self) -> pygame.Rect:
        """Get the snack's collision rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def update(self, dt: float) -> bool:
        """Update snack position. Returns False if should be removed."""
        if not self.active:
            return False

        self.y += self.fall_speed * dt
        self.rotation_angle += self.rotation_speed * dt

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

        # Scale sprite if scale factor is not 1.0
        if self.scale != 1.0:
            scaled_size = (self.width, self.height)
            sprite = pygame.transform.scale(sprite, scaled_size)

        # Rotate the sprite
        rotated_sprite = pygame.transform.rotate(sprite, self.rotation_angle)
        # Center the rotated sprite at the original position
        rotated_rect = rotated_sprite.get_rect(center=(render_x + self.width // 2, render_y + self.height // 2))
        surface.blit(rotated_sprite, rotated_rect)


class Arena:
    """A single player's game arena for 800x800 display with falling treats."""

    def __init__(self, bounds: pygame.Rect, player: Player, level_config: Dict[str, Any],
                 background_image: Optional[pygame.Surface] = None):
        self.bounds = bounds
        self.player = player
        self.level_config = level_config
        self.snacks: List[FallingSnack] = []
        self.background_color = tuple(level_config.get("background_color", [200, 200, 200]))
        self.background_image = background_image

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

        # Cloud spawn position (center x of cloud where snacks drop from)
        self.cloud_spawn_x: Optional[float] = None

        # Lightning effect for when food drops
        self.lightning_active = False
        self.lightning_timer = 0.0
        self.lightning_duration = 0.08  # Duration of lightning effect (quick flash)
        self.lightning_segments: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
        self.lightning_color = (255, 255, 100)  # Current lightning color
        self.lightning_colors = [
            (255, 255, 100),  # Yellow
            (100, 200, 255),  # Cyan
            (255, 100, 255),  # Magenta
            (255, 150, 50),   # Orange
            (150, 255, 150),  # Light green
            (255, 100, 100),  # Light red
        ]
        self.pending_snack: Optional[Dict[str, Any]] = None
        self.pending_snack_x: float = 0
        self.pending_snack_scale: float = 1.0  # Scale for voted snacks
        
        # Voted food spawning phase (pause regular spawning, spawn voted food only)
        self.voted_food_active = False
        self.voted_food_timer = 0.0
        self.voted_food_duration = 5.0  # Duration to spawn voted food
        self.voted_food_config: Optional[Dict[str, Any]] = None
        self.voted_food_spawn_interval = 0.3  # Spawn voted food frequently

        # Load thunder sound effect
        self.thunder_sound: Optional[pygame.mixer.Sound] = None
        self.thunder_played_this_round = False  # Only play once per round
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            thunder_path = os.path.join(base_dir, "Sound effect", "Thunder.mp3")
            if os.path.exists(thunder_path):
                self.thunder_sound = pygame.mixer.Sound(thunder_path)
                self.thunder_sound.set_volume(0.8)
        except Exception as e:
            print(f"Could not load thunder sound: {e}")

        # Create surface for this arena (with alpha for transparency)
        self.surface = pygame.Surface((bounds.width, bounds.height), pygame.SRCALPHA)

        # Power-up snack glow effect
        from ..core.config_manager import ConfigManager
        glow_cfg = ConfigManager().get("powerup_visuals.snack_glow", {})
        self.snack_glow = SnackGlow(glow_cfg)

    def spawn_snack(self, snack_configs: List[Dict[str, Any]]) -> Optional[FallingSnack]:
        """Trigger lightning and queue snack spawn."""
        if len(self.snacks) >= self.max_snacks:
            return None

        # Don't spawn if lightning is already active
        if self.lightning_active:
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

        # X position - spawn from cloud if available, otherwise random
        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        snack_size = SpriteSheetLoader.FOOD_SIZE[0]
        padding = 20

        if self.cloud_spawn_x is not None:
            # Spawn from cloud position with some variance
            variance = 120  # Random spread around cloud center (wider range)
            x = int(self.cloud_spawn_x + random.uniform(-variance, variance))
            # Clamp to arena bounds
            x = max(self.bounds.left + padding, min(x, self.bounds.right - padding - snack_size))
        else:
            # Fallback to random position
            x = random.randint(self.bounds.left + padding,
                              self.bounds.right - padding - snack_size)

        # Trigger lightning effect before spawning
        self._trigger_lightning(x)
        self.pending_snack = selected
        self.pending_snack_x = x
        return None

    def _trigger_lightning(self, target_x: float) -> None:
        """Trigger a lightning bolt animation from cloud to target position."""
        self.lightning_active = True
        self.lightning_timer = self.lightning_duration
        self.lightning_color = random.choice(self.lightning_colors)

        # Play thunder sound (only once per round)
        if self.thunder_sound and not self.thunder_played_this_round:
            self.thunder_sound.play()
            self.thunder_played_this_round = True

        # Generate lightning bolt segments (jagged line from cloud to target)
        self.lightning_segments = []
        if self.cloud_spawn_x is not None:
            start_x = self.cloud_spawn_x - self.bounds.left
            start_y = 50  # Start lower (below cloud)
        else:
            start_x = target_x - self.bounds.left
            start_y = 50

        end_x = target_x - self.bounds.left
        end_y = 130  # Where food starts (lower position)

        # Create jagged lightning path
        num_segments = 6
        points = [(start_x, start_y)]
        for i in range(1, num_segments):
            progress = i / num_segments
            mid_x = start_x + (end_x - start_x) * progress + random.uniform(-30, 30)
            mid_y = start_y + (end_y - start_y) * progress
            points.append((mid_x, mid_y))
        points.append((end_x, end_y))

        # Convert to line segments
        for i in range(len(points) - 1):
            self.lightning_segments.append((points[i], points[i + 1]))

    def _spawn_pending_snack(self) -> Optional[FallingSnack]:
        """Actually spawn the pending snack after lightning."""
        if self.pending_snack is None:
            return None

        snack = FallingSnack(self.pending_snack, self.pending_snack_x, self.bounds,
                            self.fall_speed, self.ground_y, scale=self.pending_snack_scale)
        self.snacks.append(snack)
        self.pending_snack = None
        self.pending_snack_scale = 1.0  # Reset scale for next snack
        return snack

    def update(self, dt: float, snack_configs: List[Dict[str, Any]]) -> None:
        """Update arena state."""
        # Update lightning animation
        if self.lightning_active:
            self.lightning_timer -= dt
            # Randomly change lightning color during animation for colorful effect
            if random.random() < 0.3:  # 30% chance each frame to change color
                self.lightning_color = random.choice(self.lightning_colors)
            if self.lightning_timer <= 0:
                self.lightning_active = False
                self.lightning_segments = []
                # Spawn the pending snack
                self._spawn_pending_snack()

        # Update spawn timer
        self.spawn_timer -= dt
        
        # Handle voted food spawning phase
        if self.voted_food_active:
            self.voted_food_timer -= dt
            if self.voted_food_timer <= 0:
                # Voted food phase ended, return to normal spawning
                self.voted_food_active = False
                self.voted_food_config = None
                self.spawn_timer = 0  # Trigger immediate spawn
            else:
                # Spawn voted food frequently during this phase
                self.spawn_timer -= dt
                if self.spawn_timer <= 0 and self.voted_food_config:
                    snack = FallingSnack(self.voted_food_config, 
                                       random.uniform(self.bounds.left + 50, self.bounds.right - 50),
                                       self.bounds, self.fall_speed, self.ground_y, 
                                       scale=self.pending_snack_scale)
                    self.snacks.append(snack)
                    self.spawn_timer = self.voted_food_spawn_interval + random.uniform(-0.1, 0.1)
        elif self.spawn_timer <= 0:
            # Regular spawning
            self.spawn_snack(snack_configs)
            interval = self.base_spawn_interval / self.spawn_rate_multiplier
            self.spawn_timer = interval + random.uniform(-0.3, 0.3)

        # Update snacks (remove inactive ones)
        self.snacks = [s for s in self.snacks if s.update(dt)]

        # Update snack glow timer
        self.snack_glow.update(dt)

    def render(self) -> pygame.Surface:
        """Render the arena with background image or wooden floor."""
        # Clear the surface
        self.surface.fill((0, 0, 0, 0))

        if self.background_image:
            # Use the background image - preserve aspect ratio
            img_width = self.background_image.get_width()
            img_height = self.background_image.get_height()
            aspect_ratio = img_width / img_height

            # Scale to fit arena width while preserving aspect ratio
            scaled_width = self.bounds.width
            scaled_height = int(scaled_width / aspect_ratio)

            # If too tall, scale to height instead
            max_height = int(self.bounds.height * 0.75)
            if scaled_height > max_height:
                scaled_height = max_height
                scaled_width = int(scaled_height * aspect_ratio)

            # Apply 1.1x scale
            scaled_width = int(scaled_width * 1.1)
            scaled_height = int(scaled_height * 1.1)

            scaled_bg = pygame.transform.scale(self.background_image,
                (scaled_width, scaled_height))
            # Center horizontally, position at bottom of arena
            bg_x = (self.bounds.width - scaled_width) // 2
            bg_y = self.bounds.height - scaled_height
            self.surface.blit(scaled_bg, (bg_x, bg_y))
        else:
            # Fallback to wooden floor
            from ..sprites.pixel_art import draw_wooden_floor, draw_fence_border
            floor_rect = pygame.Rect(0, 0, self.bounds.width, self.bounds.height)
            draw_wooden_floor(self.surface, floor_rect)
            border_rect = pygame.Rect(0, 0, self.bounds.width, self.bounds.height)
            draw_fence_border(self.surface, border_rect, thickness=12)

        # Draw the leash
        self._draw_leash()

        # Draw lightning effect
        if self.lightning_active and self.lightning_segments:
            self._draw_lightning()

        # Draw snacks (with glow for power-up items)
        for snack in self.snacks:
            if self.snack_glow.should_glow(snack.snack_id):
                # Render pulsing glow + sparkles behind the snack sprite
                cx = int(snack.x - self.bounds.left + snack.width // 2)
                cy = int(snack.y - self.bounds.top + snack.height // 2)
                self.snack_glow.render(self.surface, cx, cy,
                                       snack.snack_id, snack.color)
            snack.render(self.surface)

        # Draw player
        self.player.render(self.surface)

        return self.surface

    def _draw_lightning(self) -> None:
        """Draw colorful lightning bolt effect."""
        if not self.lightning_segments:
            return

        # Draw multiple layers for glow effect
        for thickness, alpha_mult in [(8, 0.3), (5, 0.5), (3, 0.8), (2, 1.0)]:
            color = (
                min(255, int(self.lightning_color[0] * alpha_mult + 255 * (1 - alpha_mult))),
                min(255, int(self.lightning_color[1] * alpha_mult + 255 * (1 - alpha_mult))),
                min(255, int(self.lightning_color[2] * alpha_mult + 255 * (1 - alpha_mult)))
            )
            for start, end in self.lightning_segments:
                pygame.draw.line(self.surface, color,
                               (int(start[0]), int(start[1])),
                               (int(end[0]), int(end[1])), thickness)

        # Add small branches for more detail
        for start, end in self.lightning_segments:
            if random.random() < 0.5:  # 50% chance for branch
                mid_x = (start[0] + end[0]) / 2
                mid_y = (start[1] + end[1]) / 2
                branch_end_x = mid_x + random.uniform(-25, 25)
                branch_end_y = mid_y + random.uniform(10, 25)
                pygame.draw.line(self.surface, self.lightning_color,
                               (int(mid_x), int(mid_y)),
                               (int(branch_end_x), int(branch_end_y)), 2)

    def _draw_leash(self) -> None:
        """Draw a visible leash from the wall to the dog's collar."""
        import math

        # Leash anchor point - left wall for player 1, right wall for player 2
        if self.player.player_num == 2:
            anchor_x = self.bounds.width - 15  # Right side for player 2
        else:
            anchor_x = 15  # Left side for player 1
        anchor_y = self.bounds.height - 100  # Near ground level

        # Dog's collar position (closer to dog's body, relative to arena)
        dog_x = self.player.x - self.bounds.left + 70  # Closer to dog's body
        dog_y = self.player.y - self.bounds.top + 100  # Lower on dog's body

        # Check if dog is visible in arena (for player 2, dog walks in from right)
        dog_visible = 0 <= dog_x <= self.bounds.width

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

        # Draw anchor ring on wall (always visible)
        pygame.draw.circle(self.surface, (100, 100, 100), (anchor_x, anchor_y), 8)
        pygame.draw.circle(self.surface, (150, 150, 150), (anchor_x, anchor_y), 6)
        pygame.draw.circle(self.surface, (80, 80, 80), (anchor_x, anchor_y), 4)

        # Only draw rope and collar when dog is visible
        if not dog_visible:
            return

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

        # Draw collar on dog
        collar_x = int(dog_x)
        collar_y = int(dog_y)
        pygame.draw.circle(self.surface, leash_color, (collar_x, collar_y), 6)
        pygame.draw.circle(self.surface, (200, 200, 200), (collar_x, collar_y), 4)


class VotingSystem:
    """Manages voting for different game rounds."""

    def __init__(self):
        self.mode = VotingMode.ACTION
        self.options: List[str] = ["extend", "yank"]
        self.votes: Dict[str, List[str]] = {opt: [] for opt in self.options}
        self.voting_active = True
        self.voting_duration = 10.0  # seconds
        self.cooldown_duration = 10.0  # seconds after effects are applied
        self.voting_timer = self.voting_duration
        self.cooldown_timer = 0.0
        self.last_winner: Optional[str] = None
        self.correct_trivia_answer: Optional[str] = None  # For TRIVIA mode
        self.single_vote_mode = False
        self.single_vote_completed = False

    def set_mode(
        self,
        mode: VotingMode,
        options: List[str],
        correct_answer: str = None,
        activate: bool = True,
        single_vote_mode: bool = False,
    ) -> None:
        """Set the voting mode and options."""
        self.mode = mode
        self.options = options
        self.correct_trivia_answer = correct_answer
        self.single_vote_mode = single_vote_mode
        self.single_vote_completed = False
        self.reset_votes()
        self.voting_active = False
        self.voting_timer = self.voting_duration
        self.cooldown_timer = 0.0
        if activate:
            self.start_voting_window()

    def start_voting_window(self) -> None:
        """Start a fresh voting window for the currently configured mode."""
        self.reset_votes()
        self.voting_active = True
        self.voting_timer = self.voting_duration
        self.cooldown_timer = 0.0
        self.single_vote_completed = False

    def add_vote(self, vote_type: str, voter_id: str) -> bool:
        """Add a vote. Returns True if successful."""
        if not self.voting_active:
            return False
        
        # Check if vote_type is valid (case-insensitive)
        valid_opt = None
        for opt in self.options:
            if opt.lower() == vote_type.lower():
                valid_opt = opt
                break
        
        if not valid_opt:
            return False

        # Remove previous vote from this user in any option
        for opt in self.options:
            if opt in self.votes:
                if voter_id in self.votes[opt]:
                    self.votes[opt].remove(voter_id)

        # Add new vote
        if valid_opt not in self.votes:
            self.votes[valid_opt] = []
        self.votes[valid_opt].append(voter_id)
        return True

    def get_vote_counts(self) -> Dict[str, int]:
        """Get current vote counts."""
        return {opt: len(self.votes.get(opt, [])) for opt in self.options}

    def get_winner(self) -> Optional[str]:
        """Get the winning vote option. Breaks ties by picking first option in list."""
        counts = self.get_vote_counts()
        if not counts:
            return None if self.options else None
            
        # Sort by count desc, then by option order for tiebreaker
        sorted_votes = sorted(
            counts.items(),
            key=lambda x: (-x[1], self.options.index(x[0]))
        )
        
        # Always return a winner (no ties)
        return sorted_votes[0][0] if sorted_votes else None

    def update(self, dt: float) -> Optional[str]:
        """Update voting state. Returns winner if voting just ended."""
        if self.cooldown_timer > 0:
            self.cooldown_timer -= dt
            if self.cooldown_timer <= 0:
                if self.single_vote_mode:
                    self.voting_active = False
                    self.single_vote_completed = True
                else:
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
        """Reset all votes but keep configuration."""
        self.votes = {opt: [] for opt in self.options}
        self.last_winner = None


class VotingMeter:
    """Visual display for voting status."""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.rect = pygame.Rect(x, y, width, height)
        # Colors for up to 4 options
        self.colors = [
            ((81, 180, 71), (185, 231, 199)),   # Green (Extend / Option A)
            ((221, 68, 61), (186, 143, 145)),   # Red (Yank / Option B)
            ((80, 160, 220), (180, 210, 240)),  # Blue (Option C)
            ((220, 180, 60), (240, 220, 160))   # Yellow (Option D)
        ]
        self.stroke_color = (77, 43, 31)  # #4D2B1F

    def render(self, surface: pygame.Surface, voting_system: 'VotingSystem',
               font: pygame.font.Font, small_font: pygame.font.Font,
               label_font: pygame.font.Font = None) -> None:
        """Render the voting meter."""
        if label_font is None:
            label_font = small_font

        options = voting_system.options
        counts = voting_system.get_vote_counts()
        total_votes = sum(counts.values())

        # Timer or status at top
        status_y = self.rect.y + 15
        
        status_text = ""
        status_color = self.stroke_color
        
        if voting_system.voting_active:
            # Special header for Trivia
            if voting_system.mode == VotingMode.TRIVIA:
                status_text = f"TRIVIA: {int(voting_system.voting_timer)}s"
            else:
                status_text = f"Voting: {int(voting_system.voting_timer)}s"
        elif voting_system.cooldown_timer > 0:
            winner = voting_system.last_winner
            if winner:
                # Truncate winner name if long
                disp_winner = winner if len(winner) < 10 else winner[:8] + ".."
                status_text = f"{disp_winner.upper()}! ({int(voting_system.cooldown_timer)}s)"
            else:
                status_text = f"TIE! ({int(voting_system.cooldown_timer)}s)"
        else:
            status_text = "Crowd Chaos soon"

        text_surf = small_font.render(status_text, True, status_color)
        
        # Right align status (match existing style)
        bar_margin = 20
        status_x = self.rect.right - bar_margin - text_surf.get_width()
        surface.blit(text_surf, (status_x, status_y))

        # Dynamically render bars based on number of options
        num_options = len(options)
        if num_options == 0:
            return

        bar_height = 20
        bar_y = self.rect.y + 45
        available_width = self.rect.width - (bar_margin * 2)
        
        # Calculate width per bar including gaps
        gap = 10
        total_gaps = (num_options - 1) * gap
        # Ensure bar_width is at least 1
        bar_width = max(1, (available_width - total_gaps) // num_options)
        
        for i, opt in enumerate(options):
            color_idx = i % len(self.colors)
            fill_color, bg_color = self.colors[color_idx]
            
            bar_x = self.rect.x + bar_margin + i * (bar_width + gap)
            bar_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
            
            # Background
            pygame.draw.rect(surface, bg_color, bar_rect, border_radius=4)
            
            # Fill
            votes = counts.get(opt, 0)
            if total_votes > 0 and votes > 0:
                ratio = votes / total_votes
                fill_width = int(bar_width * ratio)
                if fill_width > 0:
                    fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, fill_width, bar_height)
                    pygame.draw.rect(surface, fill_color, fill_rect, border_radius=4)
            
            # Stroke
            pygame.draw.rect(surface, self.stroke_color, bar_rect, 2, border_radius=4)
            
            # Label
            label_text = opt
            # Truncate if too long (e.g. Treat names)
            if len(label_text) > 8:
                label_text = label_text[:6] + ".."
                
            label_surf = label_font.render(label_text, True, fill_color)
            
            # Center label below bar
            label_x = bar_rect.centerx - label_surf.get_width() // 2
            label_y = bar_rect.bottom + 5
            surface.blit(label_surf, (label_x, label_y))


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

        # Button rects (dynamic)
        self.buttons: List[Tuple[pygame.Rect, str]] = []
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
        # Check if valid option
        # Note: vote_type might be case sensitive, ensuring match
        found_opt = None
        for opt in voting_system.options:
             if opt.lower() == vote_type.lower():
                 found_opt = opt
                 break
        if not found_opt:
             return

        bot_name = f"Bot{self.next_bot_id}"
        self.next_bot_id = (self.next_bot_id % 99) + 1

        cmd = f"!{found_opt}"
        
        # Pick color based on option index
        try:
             idx = voting_system.options.index(found_opt)
             colors = [
                (81, 180, 71),   # Green
                (221, 68, 61),   # Red
                (80, 160, 220),  # Blue
                (220, 180, 60)   # Yellow
             ]
             color = colors[idx % len(colors)]
        except ValueError:
             color = (200, 200, 200)

        self.add_message(bot_name, cmd, color)
        voting_system.add_vote(found_opt, bot_name)

    def update(self, dt: float, voting_system: 'VotingSystem') -> None:
        """Update auto-voting if enabled."""
        if self.auto_vote and voting_system.voting_active and voting_system.options:
            self.auto_vote_timer -= dt
            if self.auto_vote_timer <= 0:
                # Smart voting: vote for option with fewest votes to avoid ties
                counts = voting_system.get_vote_counts()
                if counts:
                    # Find option with minimum votes
                    min_votes = min(counts.values())
                    candidates = [opt for opt in voting_system.options if counts.get(opt, 0) == min_votes]
                    # Randomly pick from tied minimum options
                    vote_type = random.choice(candidates)
                else:
                    # No votes yet, pick randomly from options
                    vote_type = random.choice(voting_system.options)
                
                self.inject_vote(vote_type, voting_system)
                self.auto_vote_timer = self.auto_vote_interval + random.uniform(-0.5, 0.5)

    def handle_click(self, pos: tuple, voting_system: 'VotingSystem') -> bool:
        """Handle mouse click. Returns True if handled."""
        for rect, opt in self.buttons:
            if rect.collidepoint(pos):
                self.inject_vote(opt, voting_system)
                return True
        
        if self.auto_btn.collidepoint(pos):
            self.auto_vote = not self.auto_vote
            if self.auto_vote:
                self.add_message("System", "Auto-vote ON", (200, 200, 100))
            else:
                self.add_message("System", "Auto-vote OFF", (150, 150, 150))
            return True
        return False

    def render(self, surface: pygame.Surface, font: pygame.font.Font,
               small_font: pygame.font.Font, voting_system: 'VotingSystem') -> None:
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
        
        # Auto Vote Button
        auto_text = "AUTO"
        if self.auto_vote:
            auto_color = (100, 255, 100)
            auto_bg = (30, 80, 30)
        else:
            auto_color = (150, 150, 150)
            auto_bg = (50, 50, 60)
            
        auto_surf = small_font.render(auto_text, True, auto_color)
        self.auto_btn = pygame.Rect(self.rect.right - 50, self.rect.y + 5, 40, 25)
        pygame.draw.rect(surface, auto_bg, self.auto_btn, border_radius=4)
        pygame.draw.rect(surface, auto_color, self.auto_btn, 1, border_radius=4)
        surface.blit(auto_surf, (self.auto_btn.centerx - auto_surf.get_width()//2, self.auto_btn.centery - auto_surf.get_height()//2))

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

        # Dynamic Vote Buttons
        self.buttons = []
        options = voting_system.options
        if not options:
            return

        btn_area_y = self.rect.bottom - 130
        btn_height = 25
        btn_gap = 5
        
        for i, opt in enumerate(options):
            if i >= 4: break # Limit 4
            
            row_y = btn_area_y + i * (btn_height + btn_gap)
            btn_rect = pygame.Rect(self.rect.x + 10, row_y, self.rect.width - 20, btn_height)
            
            # Colors
            colors = [
                (50, 200, 50),   # Green
                (200, 50, 50),   # Red
                (50, 150, 220),  # Blue
                (220, 200, 50)   # Yellow
            ]
            color = colors[i % len(colors)]
            
            pygame.draw.rect(surface, (color[0]//3, color[1]//3, color[2]//3), btn_rect, border_radius=5)
            pygame.draw.rect(surface, color, btn_rect, 2, border_radius=5)
            
            text = small_font.render(f"!{opt}", True, color)
            surface.blit(text, (btn_rect.centerx - text.get_width() // 2,
                               btn_rect.centery - text.get_height() // 2))
            
            self.buttons.append((btn_rect, opt))

        # Instructions
        instr_y = self.rect.bottom - 20
        instr = small_font.render("Click or Toggle Auto", True, (120, 120, 140))
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
        self.single_dog_mode = False

        self.current_level = 1
        self.current_round = 1
        self.max_rounds = 3

        self.round_timer = 0.0
        self.round_duration = 60.0
        self.round_active = False
        self.countdown = 0
        self.countdown_timer = 0.0

        # Crowd Chaos timing (one event per round)
        self.crowd_chaos_trigger_elapsed = 35.0
        self.crowd_chaos_countdown_duration = 5.0
        self.crowd_chaos_countdown_active = False
        self.crowd_chaos_countdown_timer = 0.0
        self.crowd_chaos_countdown_value = 0
        self.crowd_chaos_triggered = False
        self.crowd_chaos_active = False
        self.crowd_chaos_mode: Optional[VotingMode] = None
        self.crowd_chaos_options: List[str] = []
        self.crowd_chaos_correct_answer: Optional[str] = None
        self.current_trivia_question = ""

        # Crowd Chaos screen tint
        self.crowd_chaos_tint_alpha = 0.0
        self.crowd_chaos_tint_max_alpha = 75

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

        # Control key states (up/down used during Red Bull flight)
        self.p1_keys = {"left": False, "right": False, "up": False, "down": False}
        self.p2_keys = {"left": False, "right": False, "up": False, "down": False}

        # Voting system for audience interaction
        self.voting_system: Optional[VotingSystem] = None
        self.voting_meter: Optional[VotingMeter] = None
        self.chat_simulator: Optional[ChatSimulator] = None
        self.twitch_manager: Optional[TwitchChatManager] = None

        # Game area width (1000px, rest is chat panel)
        self.game_area_width = GAME_AREA_WIDTH

        # Background image
        self.background_image: Optional[pygame.Surface] = None
        self.logo_image: Optional[pygame.Surface] = None
        self.battlefield_image: Optional[pygame.Surface] = None
        self.battlefield1_image: Optional[pygame.Surface] = None
        self.battlefield2_image: Optional[pygame.Surface] = None
        self.menu_bar_image: Optional[pygame.Surface] = None
        self.cloud1_image: Optional[pygame.Surface] = None
        self.cloud2_image: Optional[pygame.Surface] = None
        self.cloud1_x: float = 0.0  # Cloud 1 position (starts off-screen left)
        self.cloud2_x: float = 0.0  # Cloud 2 position (starts off-screen right)
        self.cloud_animation_done: bool = False

        # Custom font for score/timer
        self.daydream_font: Optional[pygame.font.Font] = None
        self.daydream_font_small: Optional[pygame.font.Font] = None
        self.daydream_font_smaller: Optional[pygame.font.Font] = None
        self.daydream_font_smallest: Optional[pygame.font.Font] = None
        self.daydream_font_tiny: Optional[pygame.font.Font] = None
        self.daydream_font_countdown: Optional[pygame.font.Font] = None
        self.daydream_font_chaos_title: Optional[pygame.font.Font] = None
        self.daydream_font_chaos_number: Optional[pygame.font.Font] = None

        # Announcement system for dramatic effect reveals
        self.announcement_text = ""
        self.announcement_color = (255, 255, 255)
        self.announcement_timer = 0.0
        self.announcement_duration = 2.0  # seconds

        # Screen flash effect
        self.flash_color = (0, 0, 0)
        self.flash_alpha = 0
        self.flash_timer = 0.0
        self.flash_duration = 0.3  # seconds — updated whenever flash is triggered

        # Jazzy's Chili Effect State
        self.chili_sequence_active = False
        self.chili_timer = 0.0
        self.chili_stage = 0  # 0: slow, 1: red face, 2: steam
        self.chili_target_player: Optional[Player] = None

        # Point popup system
        self.point_popups = []  # List of {x, y, points, timer, stolen}
        self.popup_duration = 1.0  # seconds
        self.daydream_font_popup: Optional[pygame.font.Font] = None

        # Walk-in animation state
        self.walk_in_active = False
        self.walk_in_duration = 3.5  # seconds for walk-in animation (slower)
        self.walk_in_timer = 0.0
        self.walk_in_frames: List[pygame.Surface] = []
        self.walk_in_frame_index = 0
        self.walk_in_frame_timer = 0.0
        self.walk_in_frame_duration = 0.15  # Slower frame rate for walking
        self.walk_in_jazzy_frame_duration = 0.125  # Jazzy is 1.2x faster
        self.walk_in_prissy_frame_duration = 0.125  # Prissy is 1.2x faster
        self.walk_in_p1_x = 0.0  # Player 1 walk-in x position
        self.walk_in_p2_x = 0.0  # Player 2 walk-in x position
        self.walk_in_p1_start_x = 0.0
        self.walk_in_p1_end_x = 0.0
        self.walk_in_p2_start_x = 0.0
        self.walk_in_p2_end_x = 0.0
        self.walk_in_p1_is_jazzy = False  # Track if player 1 is Jazzy
        self.walk_in_p2_is_jazzy = False  # Track if player 2 is Jazzy
        self.walk_in_p1_is_biggie = False  # Track if player 1 is Biggie
        self.walk_in_p2_is_biggie = False  # Track if player 2 is Biggie
        self.walk_in_biggie_frames: List[pygame.Surface] = []
        self.walk_in_biggie_frame_index = 0
        self.walk_in_biggie_frame_timer = 0.0
        self.walk_in_p1_is_prissy = False  # Track if player 1 is Prissy
        self.walk_in_p2_is_prissy = False  # Track if player 2 is Prissy
        self.walk_in_prissy_frames: List[pygame.Surface] = []
        self.walk_in_prissy_frame_index = 0
        self.walk_in_prissy_frame_timer = 0.0
        self.walk_in_p1_is_rex = False  # Track if player 1 is Rex
        self.walk_in_p2_is_rex = False  # Track if player 2 is Rex
        self.walk_in_rex_frames: List[pygame.Surface] = []
        self.walk_in_rex_frame_index = 0
        self.walk_in_rex_frame_timer = 0.0
        self.walk_in_p1_is_dash = False  # Track if player 1 is Dash
        self.walk_in_p2_is_dash = False  # Track if player 2 is Dash
        self.walk_in_dash_frames: List[pygame.Surface] = []
        self.walk_in_dash_frame_index = 0
        self.walk_in_dash_frame_timer = 0.0
        self.walk_in_p1_is_snowy = False  # Track if player 1 is Snowy
        self.walk_in_p2_is_snowy = False  # Track if player 2 is Snowy
        self.walk_in_snowy_frames: List[pygame.Surface] = []
        self.walk_in_snowy_frame_index = 0
        self.walk_in_snowy_frame_timer = 0.0
        # Left-facing frames for player 2 (walks from right side)
        self.walk_in_frames_left: List[pygame.Surface] = []
        self.walk_in_biggie_frames_left: List[pygame.Surface] = []
        self.walk_in_prissy_frames_left: List[pygame.Surface] = []
        self.walk_in_rex_frames_left: List[pygame.Surface] = []
        self.walk_in_dash_frames_left: List[pygame.Surface] = []
        self.walk_in_snowy_frames_left: List[pygame.Surface] = []
        # Custom character walk-in support
        self.walk_in_p1_is_custom = False
        self.walk_in_p2_is_custom = False
        self.walk_in_custom_frames: List[pygame.Surface] = []
        self.walk_in_custom_frames_left: List[pygame.Surface] = []
        self.walk_in_custom_frame_index = 0
        self.walk_in_custom_frame_timer = 0.0

        # Storm intro sequence (plays before countdown)
        self.storm_intro: Optional[RoundStartIntro] = None
        self.storm_intro_active = False
        self.skip_walk_in_after_intro = False

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize gameplay."""
        self.initialize_fonts()
        self._load_custom_font()
        self._load_background()

        data = data or {}
        self.game_mode = data.get("mode", "1p")
        self.vs_ai = data.get("vs_ai", True)
        self.single_dog_mode = self.game_mode == "single_dog"
        self.difficulty = data.get("difficulty", "medium")
        characters = self.config.get_all_characters()
        p1_char = data.get("p1_character", characters[0])
        default_p2 = characters[1] if len(characters) > 1 else characters[0]
        p2_char = data.get("p2_character", default_p2)

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

        # Restart background music
        self._restart_background_music()

        # Start storm intro sequence before countdown
        self._start_storm_intro()

    def _has_opponent(self) -> bool:
        """Return whether this match has a second active dog."""
        return self.player2 is not None and self.arena2 is not None

    def _uses_arrow_keys_for_player_one(self) -> bool:
        """Return whether arrow keys should control player one."""
        return self.vs_ai or self.single_dog_mode

    def _load_custom_font(self) -> None:
        """Load custom Daydream font for score and timer."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(base_dir, "ui")
        font_path = os.path.join(ui_dir, "Daydream.ttf")

        if os.path.exists(font_path):
            self.daydream_font = pygame.font.Font(font_path, 28)
            self.daydream_font_small = pygame.font.Font(font_path, 20)  # For player name
            self.daydream_font_smaller = pygame.font.Font(font_path, 16)  # For "score"
            self.daydream_font_smallest = pygame.font.Font(font_path, 14)  # For score number
            self.daydream_font_tiny = pygame.font.Font(font_path, 11)  # For voting labels
            self.daydream_font_countdown = pygame.font.Font(font_path, 120)  # For countdown
            self.daydream_font_popup = pygame.font.Font(font_path, 24)  # For point popups
            self.daydream_font_chaos_title = pygame.font.Font(font_path, 48)  # For Crowd Chaos title
            self.daydream_font_chaos_number = pygame.font.Font(font_path, 140)  # For Crowd Chaos countdown number

    def _load_background(self) -> None:
        """Load the battle screen background image and logo."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(base_dir, "ui")

        bg_path = os.path.join(ui_dir, "Battle screen background.png")
        if os.path.exists(bg_path):
            self.background_image = pygame.image.load(bg_path).convert()
            self.background_image = pygame.transform.scale(
                self.background_image, (self.screen_width, self.screen_height)
            )

        # Load logo image
        logo_path = os.path.join(ui_dir, "jazzy logo sml.png")
        if os.path.exists(logo_path):
            self.logo_image = pygame.image.load(logo_path).convert_alpha()
            # Scale to 52.8% of original size (0.44 * 1.2)
            new_width = int(self.logo_image.get_width() * 0.328)
            new_height = int(self.logo_image.get_height() * 0.328)
            self.logo_image = pygame.transform.scale(self.logo_image, (new_width, new_height))

        # Load battlefield images for each player
        battlefield1_path = os.path.join(ui_dir, "Battle field 1.png")
        battlefield2_path = os.path.join(ui_dir, "Battle field 2.png")
        if os.path.exists(battlefield1_path):
            self.battlefield1_image = pygame.image.load(battlefield1_path).convert_alpha()
        if os.path.exists(battlefield2_path):
            self.battlefield2_image = pygame.image.load(battlefield2_path).convert_alpha()
        # Fallback to old single battlefield image
        battlefield_path = os.path.join(ui_dir, "battle field.png")
        if os.path.exists(battlefield_path):
            self.battlefield_image = pygame.image.load(battlefield_path).convert_alpha()

        # Load menu bar image (yellow version for gameplay screen)
        menu_bar_path = os.path.join(ui_dir, "Menu bar yellow.png")
        if os.path.exists(menu_bar_path):
            self.menu_bar_image = pygame.image.load(menu_bar_path).convert_alpha()
            # Scale to 65.3% of original size (0.6875 * 0.95)
            new_width = int(self.menu_bar_image.get_width() * 0.653)
            new_height = int(self.menu_bar_image.get_height() * 0.653)
            self.menu_bar_image = pygame.transform.scale(self.menu_bar_image, (new_width, new_height))

        # Load cloud images
        cloud1_path = os.path.join(ui_dir, "Cloud 1.png")
        cloud2_path = os.path.join(ui_dir, "Cloud 2.png")
        if os.path.exists(cloud1_path):
            self.cloud1_image = pygame.image.load(cloud1_path).convert_alpha()
            # Scale to 50% of original size
            new_width = int(self.cloud1_image.get_width() * 0.5)
            new_height = int(self.cloud1_image.get_height() * 0.5)
            self.cloud1_image = pygame.transform.scale(self.cloud1_image, (new_width, new_height))
        if os.path.exists(cloud2_path):
            self.cloud2_image = pygame.image.load(cloud2_path).convert_alpha()
            # Scale to 50% of original size
            new_width = int(self.cloud2_image.get_width() * 0.5)
            new_height = int(self.cloud2_image.get_height() * 0.5)
            self.cloud2_image = pygame.transform.scale(self.cloud2_image, (new_width, new_height))

    def _setup_arenas(self, p1_char: Dict, p2_char: Optional[Dict]) -> None:
        """Set up the game arenas and players."""
        has_opponent = not self.single_dog_mode and p2_char is not None

        # Arena dimensions for game area (split-screen, not including chat panel)
        gap = -30  # Negative gap to overlap and bring battlefields closer
        shared_arena_width = (self.game_area_width - gap) // 2
        arena_width = shared_arena_width
        arena_height = self.screen_height - 140  # Leave room for header and HUD

        # Calculate positions
        arena_y = 130  # Below header

        # Create arena bounds
        arena1_x = 0 if has_opponent else (self.game_area_width - arena_width) // 2
        arena1_bounds = pygame.Rect(arena1_x, arena_y, arena_width, arena_height)
        arena2_bounds = None
        if has_opponent:
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
        self.player2 = None
        if has_opponent and self.vs_ai:
            difficulty_config = self.config.get_difficulty(self.difficulty)
            self.player2 = AIPlayer(p2_char, arena2_bounds, difficulty_config, horizontal_only=True)
        elif has_opponent:
            self.player2 = Player(p2_char, arena2_bounds, player_num=2, horizontal_only=True)

        # Create arenas with battlefield images (use player-specific or fallback to shared)
        arena1_bg = self.battlefield1_image if self.battlefield1_image else self.battlefield_image
        self.arena1 = Arena(arena1_bounds, self.player1, level_config, arena1_bg)
        self.arena2 = None
        if has_opponent and arena2_bounds and self.player2:
            arena2_bg = self.battlefield2_image if self.battlefield2_image else self.battlefield_image
            self.arena2 = Arena(arena2_bounds, self.player2, level_config, arena2_bg)

        # Position players at ground level (offset for larger sprites - 216px now)
        ground_offset = 230
        self.player1.y = arena1_bounds.bottom - ground_offset
        self.player1._resting_y = self.player1.y
        if self.player2 and arena2_bounds:
            self.player2.y = arena2_bounds.bottom - ground_offset
            self.player2._resting_y = self.player2.y

    def _setup_voting_ui(self) -> None:
        """Set up the voting system and UI components."""
        # Initialize voting system
        self.voting_system = VotingSystem()

        # Voting meter on right side, above menu bar
        meter_width = 300
        meter_height = 85
        meter_x = self.game_area_width - meter_width - 30  # Right side with margin
        meter_y = 105  # Above menu bar (menu bar is at y=200)
        self.voting_meter = VotingMeter(meter_x, meter_y, meter_width, meter_height)

        # Chat simulator panel on right side of screen
        panel_width = self.screen_width - self.game_area_width
        self.chat_simulator = ChatSimulator(
            self.game_area_width, 0, panel_width, self.screen_height
        )
        self.chat_simulator.add_message("System", "Welcome!", (200, 200, 100))

        # Try to connect to Twitch if configured
        env_loaded = load_env()  # Load .env file if present
        twitch_config = self.config.get_twitch_config()

        if twitch_config.get("enabled", False):
            token = get_twitch_token()
            channel = twitch_config.get("channel")

            if token and channel:
                self.chat_simulator.add_message("System", "Connecting to", (150, 150, 200))
                self.chat_simulator.add_message("System", "Twitch...", (150, 150, 200))

                self.twitch_manager = TwitchChatManager(channel, token)
                if self.twitch_manager.start():
                    self.chat_simulator.add_message("System", "TWITCH LIVE!", (100, 255, 100))
                    self.chat_simulator.add_message("System", f"#{channel}", (100, 200, 255))
                else:
                    error = self.twitch_manager.get_error() or "Unknown error"
                    self.chat_simulator.add_message("System", "Twitch failed:", (255, 100, 100))
                    self.chat_simulator.add_message("System", error[:15], (255, 150, 150))
                    self.twitch_manager = None
            else:
                if not env_loaded:
                    self.chat_simulator.add_message("System", ".env missing", (255, 200, 100))
                    self.chat_simulator.add_message("System", "create from", (255, 200, 100))
                    self.chat_simulator.add_message("System", ".env.example", (255, 200, 100))
                if not token:
                    self.chat_simulator.add_message("System", "No token in", (255, 200, 100))
                    self.chat_simulator.add_message("System", ".env file", (255, 200, 100))
                if not channel:
                    self.chat_simulator.add_message("System", "No channel", (255, 200, 100))
                    self.chat_simulator.add_message("System", "configured", (255, 200, 100))
        else:
            self.chat_simulator.add_message("System", "Click !extend or", (150, 150, 150))
            self.chat_simulator.add_message("System", "!yank to vote!", (150, 150, 150))

    def _restart_background_music(self) -> None:
        """Start gameplay music from the beginning."""
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
        music_path = os.path.join(base_dir, "Sound effect", "Gameplay.mp3")
        if os.path.exists(music_path):
            try:
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.set_volume(effective_volume)
                pygame.mixer.music.play(-1)  # Loop indefinitely
            except pygame.error as e:
                print(f"Could not play gameplay music: {e}")

    def _start_countdown(self) -> None:
        """Start the pre-round countdown."""
        self.countdown = 3
        self.countdown_timer = 1.0
        self.round_active = False
        self.walk_in_active = False
        self.cloud_animation_done = False

        # Initialize cloud positions (off-screen)
        if self.cloud1_image:
            self.cloud1_x = -self.cloud1_image.get_width()  # Start off-screen left
        if self.cloud2_image and self.arena2:
            self.cloud2_x = self.game_area_width  # Start off-screen right
        self.cloud_animation_done = False

        # Check if players are Jazzy, Biggie, Prissy, Rex, or Dash (for walk-in animation)
        p1_is_jazzy = self.player1 and self.player1.character_id == 'jazzy'
        p2_is_jazzy = self.player2 and self.player2.character_id == 'jazzy'
        p1_is_biggie = self.player1 and self.player1.character_id == 'biggie'
        p2_is_biggie = self.player2 and self.player2.character_id == 'biggie'
        p1_is_prissy = self.player1 and self.player1.character_id == 'prissy'
        p2_is_prissy = self.player2 and self.player2.character_id == 'prissy'
        p1_is_rex = self.player1 and self.player1.character_id == 'rex'
        p2_is_rex = self.player2 and self.player2.character_id == 'rex'
        p1_is_dash = self.player1 and self.player1.character_id == 'dash'
        p2_is_dash = self.player2 and self.player2.character_id == 'dash'
        p1_is_snowy = self.player1 and self.player1.character_id == 'snowy'
        p2_is_snowy = self.player2 and self.player2.character_id == 'snowy'

        # Check for custom characters (any character not in the built-in set)
        builtin_ids = {'jazzy', 'biggie', 'prissy', 'rex', 'dash', 'snowy'}
        p1_is_custom = self.player1 and self.player1.character_id not in builtin_ids
        p2_is_custom = self.player2 and self.player2.character_id not in builtin_ids

        # Position dogs with walk-in animations off-screen during countdown (they'll walk in after)
        # Other players stay at their normal center positions
        p1_has_walkin = p1_is_jazzy or p1_is_biggie or p1_is_prissy or p1_is_rex or p1_is_dash or p1_is_snowy or p1_is_custom
        p2_has_walkin = p2_is_jazzy or p2_is_biggie or p2_is_prissy or p2_is_rex or p2_is_dash or p2_is_snowy or p2_is_custom
        if self.player1:
            if self.skip_walk_in_after_intro:
                self.player1.x = self.arena1.bounds.centerx - self.player1.width // 2
            elif p1_has_walkin:
                self.player1.x = -1000
            else:
                self.player1.x = self.arena1.bounds.centerx - self.player1.width // 2
        if self.player2:
            if self.skip_walk_in_after_intro:
                self.player2.x = self.arena2.bounds.centerx - self.player2.width // 2
            elif p2_has_walkin:
                self.player2.x = -1000
            else:
                self.player2.x = self.arena2.bounds.centerx - self.player2.width // 2

        # Play countdown sound for "3" (uses 2&3 sound)
        self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "countdown_2_3"})

    def _start_walk_in(self) -> None:
        """Start the walk-in animation after countdown (for Jazzy and Biggie)."""
        from ..sprites.sprite_sheet_loader import SpriteSheetLoader

        self.walk_in_active = True
        self.walk_in_timer = self.walk_in_duration
        self.walk_in_frame_index = 0
        self.walk_in_frame_timer = 0.0
        self.walk_in_biggie_frame_index = 0
        self.walk_in_biggie_frame_timer = 0.0
        self.walk_in_prissy_frame_index = 0
        self.walk_in_prissy_frame_timer = 0.0

        # Check if either player is Jazzy, Biggie, Prissy, Rex, or Dash
        self.walk_in_p1_is_jazzy = self.player1 and self.player1.character_id == 'jazzy'
        self.walk_in_p2_is_jazzy = self.player2 and self.player2.character_id == 'jazzy'
        self.walk_in_p1_is_biggie = self.player1 and self.player1.character_id == 'biggie'
        self.walk_in_p2_is_biggie = self.player2 and self.player2.character_id == 'biggie'
        self.walk_in_p1_is_prissy = self.player1 and self.player1.character_id == 'prissy'
        self.walk_in_p2_is_prissy = self.player2 and self.player2.character_id == 'prissy'
        self.walk_in_p1_is_rex = self.player1 and self.player1.character_id == 'rex'
        self.walk_in_p2_is_rex = self.player2 and self.player2.character_id == 'rex'
        self.walk_in_p1_is_dash = self.player1 and self.player1.character_id == 'dash'
        self.walk_in_p2_is_dash = self.player2 and self.player2.character_id == 'dash'
        self.walk_in_p1_is_snowy = self.player1 and self.player1.character_id == 'snowy'
        self.walk_in_p2_is_snowy = self.player2 and self.player2.character_id == 'snowy'

        # Check for custom characters
        builtin_ids = {'jazzy', 'biggie', 'prissy', 'rex', 'dash', 'snowy'}
        self.walk_in_p1_is_custom = self.player1 and self.player1.character_id not in builtin_ids
        self.walk_in_p2_is_custom = self.player2 and self.player2.character_id not in builtin_ids

        loader = SpriteSheetLoader()

        # Load Jazzy walking frames if at least one player is Jazzy
        # Size: 121x113 * 0.95 = 115x107
        if self.walk_in_p1_is_jazzy:
            self.walk_in_frames = loader.get_walking_frames('jazzy', facing_right=True, target_size=(115, 107))
        else:
            self.walk_in_frames = []
        if self.walk_in_p2_is_jazzy:
            self.walk_in_frames_left = loader.get_walking_frames('jazzy', facing_right=False, target_size=(115, 107))
        else:
            self.walk_in_frames_left = []

        # Load Biggie walking frames if at least one player is Biggie
        # Size: 156x113 * 0.95 = 148x107
        if self.walk_in_p1_is_biggie:
            self.walk_in_biggie_frames = loader.get_walking_frames('biggie', facing_right=True, target_size=(145, 105))
        else:
            self.walk_in_biggie_frames = []
        if self.walk_in_p2_is_biggie:
            self.walk_in_biggie_frames_left = loader.get_walking_frames('biggie', facing_right=False, target_size=(145, 105))
        else:
            self.walk_in_biggie_frames_left = []

        # Load Prissy walking frames if at least one player is Prissy
        # Prissy frame size is 200x250 (3x2 grid), at height 107 = 85x107, then 1.1x = 94x118
        if self.walk_in_p1_is_prissy:
            self.walk_in_prissy_frames = loader.get_walking_frames('prissy', facing_right=True, target_size=(94, 118))
        else:
            self.walk_in_prissy_frames = []
        if self.walk_in_p2_is_prissy:
            self.walk_in_prissy_frames_left = loader.get_walking_frames('prissy', facing_right=False, target_size=(94, 118))
        else:
            self.walk_in_prissy_frames_left = []

        # Load Rex walking frames if at least one player is Rex
        # Rex frame size is 274x211 (6x6 grid), at height 107 = 139x107, then 0.95x = 131x101
        self.walk_in_rex_frame_index = 0
        self.walk_in_rex_frame_timer = 0.0
        if self.walk_in_p1_is_rex:
            self.walk_in_rex_frames = loader.get_walking_frames('rex', facing_right=True, target_size=(131, 101))
        else:
            self.walk_in_rex_frames = []
        if self.walk_in_p2_is_rex:
            self.walk_in_rex_frames_left = loader.get_walking_frames('rex', facing_right=False, target_size=(131, 101))
        else:
            self.walk_in_rex_frames_left = []

        # Load Dash walking frames if at least one player is Dash
        # Dash frame size is 286x168 (5 horizontal frames), at height 107 = 182x107, then 0.95x * 0.81 = 140x82
        self.walk_in_dash_frame_index = 0
        self.walk_in_dash_frame_timer = 0.0
        if self.walk_in_p1_is_dash:
            self.walk_in_dash_frames = loader.get_walking_frames('dash', facing_right=True, target_size=(140, 82))
        else:
            self.walk_in_dash_frames = []
        if self.walk_in_p2_is_dash:
            self.walk_in_dash_frames_left = loader.get_walking_frames('dash', facing_right=False, target_size=(140, 82))
        else:
            self.walk_in_dash_frames_left = []

        # Load Snowy walking frames if at least one player is Snowy
        # Snowy frame size is 270x244 (6x6 grid), at height 107 = 118x107, then 0.95x = 112x101
        self.walk_in_snowy_frame_index = 0
        self.walk_in_snowy_frame_timer = 0.0
        if self.walk_in_p1_is_snowy:
            self.walk_in_snowy_frames = loader.get_walking_frames('snowy', facing_right=True, target_size=(112, 101))
        else:
            self.walk_in_snowy_frames = []
        if self.walk_in_p2_is_snowy:
            self.walk_in_snowy_frames_left = loader.get_walking_frames('snowy', facing_right=False, target_size=(112, 101))
        else:
            self.walk_in_snowy_frames_left = []

        # Load custom character walking frames (use default size similar to Jazzy)
        self.walk_in_custom_frame_index = 0
        self.walk_in_custom_frame_timer = 0.0
        if self.walk_in_p1_is_custom:
            self.walk_in_custom_frames = loader.get_walking_frames(
                self.player1.character_id, facing_right=True, target_size=(115, 107))
        else:
            self.walk_in_custom_frames = []
        if self.walk_in_p2_is_custom:
            self.walk_in_custom_frames_left = loader.get_walking_frames(
                self.player2.character_id, facing_right=False, target_size=(115, 107))
        else:
            self.walk_in_custom_frames_left = []

        # Set up walk-in positions for player 1 (walks from left to center)
        if self.arena1:
            self.walk_in_p1_start_x = self.arena1.bounds.left - self.player1.width
            self.walk_in_p1_end_x = self.arena1.bounds.centerx - self.player1.width // 2
            self.walk_in_p1_x = self.walk_in_p1_start_x

        # Set up walk-in positions for player 2 (walks from right to center of their arena)
        if self.arena2:
            self.walk_in_p2_start_x = self.arena2.bounds.right
            self.walk_in_p2_end_x = self.arena2.bounds.centerx - self.player2.width // 2
            self.walk_in_p2_x = self.walk_in_p2_start_x

        # Position players at the ground level but off-screen to the left
        ground_offset = 230
        if self.arena1:
            self.player1.y = self.arena1.bounds.bottom - ground_offset
            self.player1._resting_y = self.player1.y
        if self.arena2:
            self.player2.y = self.arena2.bounds.bottom - ground_offset
            self.player2._resting_y = self.player2.y

    def _update_walk_in(self, dt: float) -> None:
        """Update the walk-in animation."""
        self.walk_in_timer -= dt

        # Update Jazzy animation frame (use either right or left frames for count)
        self.walk_in_frame_timer += dt
        if self.walk_in_frame_timer >= self.walk_in_jazzy_frame_duration:
            self.walk_in_frame_timer -= self.walk_in_jazzy_frame_duration
            jazzy_frames = self.walk_in_frames if self.walk_in_frames else self.walk_in_frames_left
            if jazzy_frames:
                self.walk_in_frame_index = (self.walk_in_frame_index + 1) % len(jazzy_frames)

        # Update Biggie animation frame (use either right or left frames for count)
        self.walk_in_biggie_frame_timer += dt
        if self.walk_in_biggie_frame_timer >= self.walk_in_frame_duration:
            self.walk_in_biggie_frame_timer -= self.walk_in_frame_duration
            biggie_frames = self.walk_in_biggie_frames if self.walk_in_biggie_frames else self.walk_in_biggie_frames_left
            if biggie_frames:
                self.walk_in_biggie_frame_index = (self.walk_in_biggie_frame_index + 1) % len(biggie_frames)

        # Update Prissy animation frame (use either right or left frames for count)
        self.walk_in_prissy_frame_timer += dt
        if self.walk_in_prissy_frame_timer >= self.walk_in_prissy_frame_duration:
            self.walk_in_prissy_frame_timer -= self.walk_in_prissy_frame_duration
            prissy_frames = self.walk_in_prissy_frames if self.walk_in_prissy_frames else self.walk_in_prissy_frames_left
            if prissy_frames:
                self.walk_in_prissy_frame_index = (self.walk_in_prissy_frame_index + 1) % len(prissy_frames)

        # Update Rex animation frame (use either right or left frames for count)
        self.walk_in_rex_frame_timer += dt
        if self.walk_in_rex_frame_timer >= self.walk_in_frame_duration:
            self.walk_in_rex_frame_timer -= self.walk_in_frame_duration
            rex_frames = self.walk_in_rex_frames if self.walk_in_rex_frames else self.walk_in_rex_frames_left
            if rex_frames:
                self.walk_in_rex_frame_index = (self.walk_in_rex_frame_index + 1) % len(rex_frames)

        # Update Dash animation frame (use either right or left frames for count)
        self.walk_in_dash_frame_timer += dt
        if self.walk_in_dash_frame_timer >= self.walk_in_frame_duration:
            self.walk_in_dash_frame_timer -= self.walk_in_frame_duration
            dash_frames = self.walk_in_dash_frames if self.walk_in_dash_frames else self.walk_in_dash_frames_left
            if dash_frames:
                self.walk_in_dash_frame_index = (self.walk_in_dash_frame_index + 1) % len(dash_frames)

        # Update Snowy animation frame (use either right or left frames for count)
        self.walk_in_snowy_frame_timer += dt
        if self.walk_in_snowy_frame_timer >= self.walk_in_frame_duration:
            self.walk_in_snowy_frame_timer -= self.walk_in_frame_duration
            snowy_frames = self.walk_in_snowy_frames if self.walk_in_snowy_frames else self.walk_in_snowy_frames_left
            if snowy_frames:
                self.walk_in_snowy_frame_index = (self.walk_in_snowy_frame_index + 1) % len(snowy_frames)

        # Update custom character animation frame
        self.walk_in_custom_frame_timer += dt
        if self.walk_in_custom_frame_timer >= self.walk_in_frame_duration:
            self.walk_in_custom_frame_timer -= self.walk_in_frame_duration
            custom_frames = self.walk_in_custom_frames if self.walk_in_custom_frames else self.walk_in_custom_frames_left
            if custom_frames:
                self.walk_in_custom_frame_index = (self.walk_in_custom_frame_index + 1) % len(custom_frames)

        # Calculate progress (0 to 1)
        progress = 1.0 - (self.walk_in_timer / self.walk_in_duration)
        progress = min(1.0, max(0.0, progress))

        # Use easing for smoother animation (ease-out)
        eased_progress = 1.0 - (1.0 - progress) ** 2

        # Update walk-in positions (for rendering)
        self.walk_in_p1_x = self.walk_in_p1_start_x + (self.walk_in_p1_end_x - self.walk_in_p1_start_x) * eased_progress
        if self.player2 and self.arena2:
            self.walk_in_p2_x = self.walk_in_p2_start_x + (self.walk_in_p2_end_x - self.walk_in_p2_start_x) * eased_progress

        # Hide players that have walk-in animations
        # They're rendered via walk-in animation sprite instead
        if self.player1:
            if self.walk_in_p1_is_jazzy or self.walk_in_p1_is_biggie or self.walk_in_p1_is_prissy or self.walk_in_p1_is_rex or self.walk_in_p1_is_dash or self.walk_in_p1_is_snowy or self.walk_in_p1_is_custom:
                self.player1.x = -1000  # Hide, we render walk-in sprite instead
            else:
                self.player1.x = self.walk_in_p1_end_x  # Show at final position

        if self.player2:
            if self.walk_in_p2_is_jazzy or self.walk_in_p2_is_biggie or self.walk_in_p2_is_prissy or self.walk_in_p2_is_rex or self.walk_in_p2_is_dash or self.walk_in_p2_is_snowy or self.walk_in_p2_is_custom:
                self.player2.x = -1000  # Hide, we render walk-in sprite instead
            else:
                self.player2.x = self.walk_in_p2_end_x  # Show at final position

        # Check if walk-in is complete
        if self.walk_in_timer <= 0:
            self.walk_in_active = False
            # Position all players at their final positions
            if self.player1:
                self.player1.x = self.walk_in_p1_end_x
            if self.player2:
                self.player2.x = self.walk_in_p2_end_x
            self._start_round()

    def _update_clouds(self, dt: float) -> None:
        """Update cloud animation - clouds move in from sides."""
        cloud_speed = 150  # pixels per second

        # Calculate target positions (above menu bar, on each player's side)
        menu_bar_y = 200
        cloud_y = menu_bar_y - 60  # Above menu bar

        # Cloud 1 target: left side of player 1's area, or center in solo mode
        if self.cloud1_image:
            target_fraction = 0.5 if self.single_dog_mode else 0.25
            cloud1_target_x = int(self.game_area_width * target_fraction) - self.cloud1_image.get_width() // 2
            if self.cloud1_x < cloud1_target_x:
                self.cloud1_x += cloud_speed * dt
                if self.cloud1_x >= cloud1_target_x:
                    self.cloud1_x = cloud1_target_x

        # Cloud 2 target: right side of player 2's area
        if self.cloud2_image and self.arena2:
            cloud2_target_x = (self.game_area_width * 3) // 4 - self.cloud2_image.get_width() // 2
            if self.cloud2_x > cloud2_target_x:
                self.cloud2_x -= cloud_speed * dt
                if self.cloud2_x <= cloud2_target_x:
                    self.cloud2_x = cloud2_target_x

        # Update arena cloud spawn positions (center of each cloud)
        if self.cloud1_image and self.arena1:
            self.arena1.cloud_spawn_x = self.cloud1_x + self.cloud1_image.get_width() // 2
        if self.cloud2_image and self.arena2:
            self.arena2.cloud_spawn_x = self.cloud2_x + self.cloud2_image.get_width() // 2

        # Check if both clouds have reached their targets
        if self.single_dog_mode:
            if self.cloud1_image:
                cloud1_target_x = self.game_area_width // 2 - self.cloud1_image.get_width() // 2
                if self.cloud1_x >= cloud1_target_x:
                    self.cloud_animation_done = True
        elif self.cloud1_image and self.cloud2_image:
            cloud1_target_x = self.game_area_width // 4 - self.cloud1_image.get_width() // 2
            cloud2_target_x = (self.game_area_width * 3) // 4 - self.cloud2_image.get_width() // 2
            if self.cloud1_x >= cloud1_target_x and self.cloud2_x <= cloud2_target_x:
                self.cloud_animation_done = True

    def _start_round(self) -> None:
        """Start the actual round."""
        self.round_timer = self.round_duration
        self.round_active = True
        self.skip_walk_in_after_intro = False
        self.crowd_chaos_triggered = False
        self.crowd_chaos_active = False
        self.crowd_chaos_countdown_active = False
        self.crowd_chaos_countdown_timer = 0.0
        self.crowd_chaos_countdown_value = 0
        self.player1.reset()
        self.arena1.snacks.clear()
        # Reset thunder sound flag for new round
        self.arena1.thunder_played_this_round = False
        if self.player2:
            self.player2.reset()
        if self.arena2:
            self.arena2.snacks.clear()
            self.arena2.thunder_played_this_round = False

        # Reset player positions to ground
        ground_offset = 230
        self.player1.y = self.arena1.bounds.bottom - ground_offset
        self.player1._resting_y = self.player1.y
        if self.player2 and self.arena2:
            self.player2.y = self.arena2.bounds.bottom - ground_offset
            self.player2._resting_y = self.player2.y

        # Configure the single Crowd Chaos voting type for this round
        if self.voting_system:
            if self.current_round == 1:
                # Round 1: Vote for a treat drop
                possible_snacks = [s for s in self.snack_configs]
                if len(possible_snacks) > 3:
                    choices = random.sample(possible_snacks, 3)
                else:
                    choices = possible_snacks

                self.crowd_chaos_mode = VotingMode.TREAT
                self.crowd_chaos_options = [s.get("id", "snack") for s in choices]
                self.crowd_chaos_correct_answer = None

                if self.chat_simulator:
                    self.chat_simulator.add_message("System", "R1 CHAOS: TREAT VOTE", (255, 255, 100))

            elif self.current_round == 2:
                # Round 2: Action vote - Yank vs Extend
                self.crowd_chaos_mode = VotingMode.ACTION
                self.crowd_chaos_options = ["extend", "yank"]
                self.crowd_chaos_correct_answer = None

                if self.chat_simulator:
                    self.chat_simulator.add_message("System", "R2 CHAOS: YANK/EXTEND", (255, 255, 100))

            else:
                # Round 3: Trivia
                trivias = [
                    {"q": "Who loves lasagna?", "a": "Jazzy", "opts": ["Jazzy", "Biggie", "Prissy", "Snowy"]},
                    {"q": "What falls from sky?", "a": "Snacks", "opts": ["Snacks", "Rain", "Cats", "Rocks"]},
                    {"q": "Best pizza topping?", "a": "Cheese", "opts": ["Cheese", "Pineapple", "Anchovy", "Olives"]},
                    {"q": "Game Name?", "a": "SnackAttack", "opts": ["SnackAttack", "DogRun", "EatFast", "Fetch Master"]}
                ]
                trivia = random.choice(trivias)
                self.current_trivia_question = trivia["q"]
                self.crowd_chaos_mode = VotingMode.TRIVIA
                self.crowd_chaos_options = trivia["opts"]
                self.crowd_chaos_correct_answer = trivia["a"]

                if self.chat_simulator:
                    self.chat_simulator.add_message("System", "R3 CHAOS: TRIVIA", (255, 200, 255))

            self.voting_system.set_mode(
                self.crowd_chaos_mode,
                self.crowd_chaos_options,
                correct_answer=self.crowd_chaos_correct_answer,
                activate=False,
                single_vote_mode=True,
            )

    def _start_crowd_chaos_countdown(self) -> None:
        """Start the on-screen Crowd Chaos countdown."""
        if self.crowd_chaos_triggered or self.crowd_chaos_countdown_active:
            return

        self.crowd_chaos_countdown_active = True
        self.crowd_chaos_countdown_timer = self.crowd_chaos_countdown_duration
        self.crowd_chaos_countdown_value = int(self.crowd_chaos_countdown_duration)

        if self.chat_simulator:
            self.chat_simulator.add_message("System", "CROWD CHAOS INCOMING!", (255, 120, 120))

    def _activate_crowd_chaos(self) -> None:
        """Activate the Crowd Chaos voting event for the round."""
        if self.crowd_chaos_triggered:
            return

        self.crowd_chaos_triggered = True
        self.crowd_chaos_countdown_active = False
        self.crowd_chaos_active = True

        if self.voting_system:
            self.voting_system.start_voting_window()

        if self.chat_simulator:
            if self.crowd_chaos_mode == VotingMode.TRIVIA and self.current_trivia_question:
                self.chat_simulator.add_message("System", f"TRIVIA: {self.current_trivia_question}", (255, 200, 255))
            self.chat_simulator.add_message("System", "CROWD CHAOS LIVE! VOTE NOW", (255, 120, 120))

        self.announcement_text = "CROWD CHAOS!"
        self.announcement_color = (255, 100, 100)
        self.announcement_timer = min(1.5, self.announcement_duration)

    def _end_round(self) -> None:
        """End the current round."""
        self.round_active = False

        # Determine winner
        if self.single_dog_mode:
            self.p1_round_wins += 1
        elif self.player1.score > self.player2.score:
            self.p1_round_wins += 1
        elif self.player2.score > self.player1.score:
            self.p2_round_wins += 1

        # Check for game over
        wins_needed = (self.max_rounds // 2) + 1
        if self.single_dog_mode:
            if self.current_round >= self.max_rounds:
                self._end_game()
            else:
                self.current_round += 1
                # Progress level every round
                if self.current_round <= 3:
                    self.current_level = self.current_round
                    level_config = self.config.get_level(self.current_level) or {}
                    self.arena1.level_config = level_config
                    self.arena1.snack_pool = level_config.get("snack_pool", ["pizza"])
                    self.arena1.background_color = tuple(level_config.get("background_color", [200, 200, 200]))
                    self.round_duration = level_config.get("round_duration_seconds", 60)
                    self.arena1.fall_speed = 180 + (self.current_level - 1) * 30
                    self.arena1.base_spawn_interval = max(0.5, 1.0 - (self.current_level - 1) * 0.15)
                self._start_countdown()
        elif self.p1_round_wins >= wins_needed or self.p2_round_wins >= wins_needed:
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
        if self.single_dog_mode or self.p1_round_wins > self.p2_round_wins:
            winner = self.player1.name
        elif self.p2_round_wins > self.p1_round_wins:
            winner = self.player2.name

        self.state_machine.change_state(GameState.GAME_OVER, {
            "mode": self.game_mode,
            "winner": winner,
            "p1_score": self.player1.score,
            "p2_score": self.player2.score if self.player2 else 0,
            "p1_rounds": self.p1_round_wins,
            "p2_rounds": self.p2_round_wins,
            "vs_ai": self.vs_ai,
            "p1_name": self.player1.name,
            "p2_name": self.player2.name if self.player2 else ""
        })

    def _start_storm_intro(self) -> None:
        """Launch the lightning + treat storm intro before the countdown."""
        self.storm_intro = RoundStartIntro(
            self.game_area_width, self.screen_height
        )
        # Use the first arena's ground level as reference
        ground_y = self.screen_height * 0.7
        if self.arena1:
            ground_y = self.arena1.bounds.bottom - 80

        from ..sprites.sprite_sheet_loader import SpriteSheetLoader

        loader = SpriteSheetLoader()
        dog1_frames = []
        dog2_frames = []
        dog1_sprite = None
        dog2_sprite = None
        if self.player1:
            dog1_frames = loader.get_animation_frames(self.player1.character_id, "run", True)[:3]
            dog1_sprite = self.player1.animation_controller.get_current_sprite()
        if self.player2:
            dog2_frames = loader.get_animation_frames(self.player2.character_id, "run", False)[:3]
            dog2_sprite = self.player2.animation_controller.get_current_sprite()

        self.storm_intro.start(
            dog1_frames=dog1_frames,
            dog2_frames=dog2_frames,
            dog1_sprite=dog1_sprite,
            dog2_sprite=dog2_sprite,
            dog_ground_y=ground_y,
        )
        self.storm_intro_active = True
        self.skip_walk_in_after_intro = True

    def on_exit(self) -> None:
        """Clean up when leaving gameplay."""
        # Stop Twitch connection if active
        if self.twitch_manager:
            self.twitch_manager.stop()
            self.twitch_manager = None
        self.storm_intro = None
        self.storm_intro_active = False
        self.skip_walk_in_after_intro = False

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        # Block gameplay input while storm intro is playing
        if self.storm_intro_active:
            return

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

        elif event.type == TWITCH_VOTE_EVENT:
            # Process Twitch vote
            vote_type = event.vote_type
            voter_id = event.voter_id
            if self.voting_system and self.voting_system.add_vote(vote_type, voter_id):
                # Show in chat simulator
                palette = [
                    (81, 180, 71),
                    (221, 68, 61),
                    (80, 160, 220),
                    (220, 180, 60),
                ]
                color = (200, 200, 200)
                for idx, opt in enumerate(self.voting_system.options):
                    if opt.lower() == vote_type.lower():
                        color = palette[idx % len(palette)]
                        break
                if self.chat_simulator:
                    self.chat_simulator.add_message(voter_id[:10], f"!{vote_type}", color)

    def _handle_key_down(self, key: int) -> None:
        """Handle key press."""
        # Player 1 controls (WASD)
        if key == pygame.K_a:
            self.p1_keys["left"] = True
        elif key == pygame.K_d:
            self.p1_keys["right"] = True
        elif key == pygame.K_w:
            self.p1_keys["up"] = True
        elif key == pygame.K_s:
            self.p1_keys["down"] = True

        # In 1P mode, arrow keys also control player 1
        if self._uses_arrow_keys_for_player_one():
            if key == pygame.K_LEFT:
                self.p1_keys["left"] = True
            elif key == pygame.K_RIGHT:
                self.p1_keys["right"] = True
            elif key == pygame.K_UP:
                self.p1_keys["up"] = True
            elif key == pygame.K_DOWN:
                self.p1_keys["down"] = True
        else:
            # Player 2 controls (Arrow keys) - only for 2P mode
            if key == pygame.K_LEFT:
                self.p2_keys["left"] = True
            elif key == pygame.K_RIGHT:
                self.p2_keys["right"] = True
            elif key == pygame.K_UP:
                self.p2_keys["up"] = True
            elif key == pygame.K_DOWN:
                self.p2_keys["down"] = True

    def _handle_key_up(self, key: int) -> None:
        """Handle key release."""
        # Player 1 controls
        if key == pygame.K_a:
            self.p1_keys["left"] = False
        elif key == pygame.K_d:
            self.p1_keys["right"] = False
        elif key == pygame.K_w:
            self.p1_keys["up"] = False
        elif key == pygame.K_s:
            self.p1_keys["down"] = False

        # In 1P mode, arrow keys also control player 1
        if self._uses_arrow_keys_for_player_one():
            if key == pygame.K_LEFT:
                self.p1_keys["left"] = False
            elif key == pygame.K_RIGHT:
                self.p1_keys["right"] = False
            elif key == pygame.K_UP:
                self.p1_keys["up"] = False
            elif key == pygame.K_DOWN:
                self.p1_keys["down"] = False
        else:
            # Player 2 controls
            if key == pygame.K_LEFT:
                self.p2_keys["left"] = False
            elif key == pygame.K_RIGHT:
                self.p2_keys["right"] = False
            elif key == pygame.K_UP:
                self.p2_keys["up"] = False
            elif key == pygame.K_DOWN:
                self.p2_keys["down"] = False

    def update(self, dt: float) -> None:
        """Update gameplay state."""
        if self.paused:
            return

        # Update storm intro if active
        if self.storm_intro_active and self.storm_intro:
            self.storm_intro.update(dt)
            if self.storm_intro.is_complete:
                self.storm_intro_active = False
                self.storm_intro = None
                self._start_countdown()
            return

        # --- Jazzy's Chili Sequence Logic ---
        gameplay_dt = dt
        if self.chili_sequence_active and self.chili_target_player:
            player = self.chili_target_player
            self.chili_timer += dt
            
            # Slow down time for everything else
            if self.chili_stage == 0:
                gameplay_dt = dt * 0.1  # Dramatic Slowdown
                # Trigger animation once (duration 3.5s)
                # Note: valid duration must be scaled by the slow-mo factor (0.1)
                # because the update loop will pass the slowed-down dt to the animation controller.
                player.animation_controller.trigger_chili_animation(duration=3.5 * 0.1)
                self.chili_stage = 1
                self.chili_timer = 0
            
            elif self.chili_stage == 1: # Playing Animation
                gameplay_dt = dt * 0.1
                
                # Emit steam particles in latter half (frames 3-4 approx)
                if self.chili_timer > 1.5 and random.random() < 0.2:
                     # Add steam particle logic here if visuals needed
                     pass
                     
                if self.chili_timer > 3.5:
                    # End sequence
                    self.chili_sequence_active = False
                    player.animation_controller.set_manual_state(None)
                    # Trigger the chaos shake NOW
                    self.shake_intensity = 5
                    self.shake_duration = 4.0 # Match effect duration
        
        # Use gameplay_dt for game updates to apply slow-mo
        dt = gameplay_dt
        
        # Update cloud animation (clouds move in during countdown/walk-in)
        if not self.cloud_animation_done:
            self._update_clouds(dt)

        # Update countdown
        if self.countdown > 0:
            self.countdown_timer -= dt
            if self.countdown_timer <= 0:
                self.countdown -= 1
                self.countdown_timer = 1.0
                if self.countdown == 0:
                    if self.skip_walk_in_after_intro:
                        self._start_round()
                    else:
                        self._start_walk_in()
                elif self.countdown == 2:
                    # Play countdown sound for "2" (uses 2&3 sound)
                    self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "countdown_2_3"})
                elif self.countdown == 1:
                    # Play countdown sound for "1"
                    self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "countdown_1"})
            return

        # Update walk-in animation
        if self.walk_in_active:
            self._update_walk_in(dt)
            return

        if not self.round_active:
            return

        # Update round timer
        self.round_timer -= dt
        if self.round_timer <= 0:
            self._end_round()
            return

        # Trigger one Crowd Chaos event at 40s elapsed in each round
        elapsed_in_round = self.round_duration - self.round_timer
        if (not self.crowd_chaos_triggered
                and not self.crowd_chaos_countdown_active
                and elapsed_in_round >= self.crowd_chaos_trigger_elapsed):
            self._start_crowd_chaos_countdown()

        # Update Crowd Chaos countdown overlay
        if self.crowd_chaos_countdown_active:
            self.crowd_chaos_countdown_timer -= dt
            if self.crowd_chaos_countdown_timer <= 0:
                self._activate_crowd_chaos()
            else:
                self.crowd_chaos_countdown_value = max(1, int(self.crowd_chaos_countdown_timer) + 1)

        # Smoothly animate chaos tint strength
        chaos_visual_active = self.crowd_chaos_countdown_active or self.crowd_chaos_active
        target_alpha = float(self.crowd_chaos_tint_max_alpha if chaos_visual_active else 0)
        self.crowd_chaos_tint_alpha += (target_alpha - self.crowd_chaos_tint_alpha) * min(1.0, dt * 6.0)

        # Update screen shake
        if self.shake_duration > 0:
            self.shake_duration -= dt
            if self.shake_duration <= 0:
                self.shake_intensity = 0

        # Update announcement timer
        if self.announcement_timer > 0:
            self.announcement_timer -= dt

        # Update flash timer - fade out smoothly
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.flash_alpha = 0
            else:
                # Linearly fade flash_alpha to 0 as timer counts down
                self.flash_alpha = int(150 * (self.flash_timer / max(0.001, self.flash_duration)))

        # Update point popups
        for popup in self.point_popups:
            popup["timer"] -= dt
            popup["y"] -= 50 * dt  # Float upward
        self.point_popups = [p for p in self.point_popups if p["timer"] > 0]

        # Update voting system
        if self.voting_system:
            # Track if cooldown was active before update
            was_in_cooldown = self.voting_system.cooldown_timer > 0
            
            vote_winner = self.voting_system.update(dt)
            if vote_winner:
                self._apply_vote_effect(vote_winner)

            # Clear chaos effect after voting cycle completes
            if self.crowd_chaos_active:
                # Check if cooldown just finished (was > 0, now <= 0)
                if was_in_cooldown and self.voting_system.cooldown_timer <= 0:
                    self.crowd_chaos_active = False
                    self.crowd_chaos_triggered = False
                # Or if single vote mode completed
                elif self.voting_system.single_vote_completed:
                    self.crowd_chaos_active = False

        # Update chat simulator (auto-voting)
        if self.chat_simulator and self.voting_system:
            self.chat_simulator.update(dt, self.voting_system)

        # Update players - horizontal only keys
        self.player1.handle_input(self.p1_keys)
        self.player1.update(dt)

        if isinstance(self.player2, AIPlayer) and self.arena2:
            self.player2.update(dt, self.arena2.snacks)
        elif self.player2:
            self.player2.handle_input(self.p2_keys)
            self.player2.update(dt)

        # Update arenas (spawns falling snacks)
        self.arena1.update(dt, self.snack_configs)
        if self.arena2:
            self.arena2.update(dt, self.snack_configs)

        # Check collisions
        self._check_collisions()

    def _check_collisions(self) -> None:
        """Check for player-snack collisions."""
        # Use smaller hitboxes for tighter collision (shrink by 40px on each side)
        p1_hitbox = self.player1.rect.inflate(-80, -80)
        p2_hitbox = self.player2.rect.inflate(-80, -80) if self.player2 else None

        # Player 1 collisions with their own arena
        for snack in self.arena1.snacks[:]:
            if not snack.active:
                continue
            snack_hitbox = snack.rect.inflate(-20, -20)
            if p1_hitbox.colliderect(snack_hitbox):
                self._collect_snack(self.player1, snack)

        # Player 2 collisions with their own arena
        if self.player2 and self.arena2 and p2_hitbox:
            for snack in self.arena2.snacks[:]:
                if not snack.active:
                    continue
                snack_hitbox = snack.rect.inflate(-20, -20)
                if p2_hitbox.colliderect(snack_hitbox):
                    self._collect_snack(self.player2, snack)

        # Cross-arena collisions when unleashed!
        # Player 1 can steal from arena 2 if they've crossed over
        if self.player1.get_leash_state() == "extended" and self.arena2:
            for snack in self.arena2.snacks[:]:
                if not snack.active:
                    continue
                snack_hitbox = snack.rect.inflate(-20, -20)
                if p1_hitbox.colliderect(snack_hitbox):
                    self._collect_snack(self.player1, snack, stolen=True)

        # Player 2 can steal from arena 1 if they've crossed over
        if self.player2 and self.arena2 and p2_hitbox and self.player2.get_leash_state() == "extended":
            for snack in self.arena1.snacks[:]:
                if not snack.active:
                    continue
                snack_hitbox = snack.rect.inflate(-20, -20)
                if p2_hitbox.colliderect(snack_hitbox):
                    self._collect_snack(self.player2, snack, stolen=True)

    def _collect_snack(self, player: Player, snack: FallingSnack, stolen: bool = False) -> None:
        """Handle snack collection."""
        result = snack.collect()

        # Emit snack collected event for sound effects
        self.event_bus.emit(GameEvent.SNACK_COLLECTED, {"snack_id": result["snack_id"]})

        # Trigger eat animation
        player.trigger_eat_animation()

        # Add score (bonus for stolen snacks!)
        points = result["point_value"]
        if stolen:
            points = int(points * 1.5)  # 50% bonus for stealing!
            if self.chat_simulator:
                self.chat_simulator.add_message("System", "STOLEN! +50%", (255, 200, 50))

        # Apply boost score multiplier (2x during Red Bull boost)
        score_multiplier = player.get_score_multiplier()
        points = int(points * score_multiplier)

        player.add_score(points)

        # Add point popup at snack position
        self.point_popups.append({
            "x": snack.x + snack.width // 2,
            "y": snack.y,
            "points": points,
            "timer": self.popup_duration,
            "stolen": stolen
        })

        # Apply effect if any
        effect = result.get("effect")
        if effect:
            # Special handling for Chili/Chaos effect
            if effect["type"] == "chaos" and player.character_id == "jazzy":
                # Trigger special Jazzy cutscene sequence
                self.chili_sequence_active = True
                self.chili_timer = 0.0
                self.chili_stage = 0
                self.chili_target_player = player
                
                # Apply the effect logic (reverse controls) but delay the chaos shake slightly
                player.apply_effect(
                    effect["type"],
                    effect["magnitude"],
                    effect["duration_seconds"]
                )
            # Check if this is a negative effect and player is invincible
            elif player.is_invincible and effect["type"] in ["slow", "chaos"]:
                # Player is invincible - skip negative effect
                pass
            else:
                player.apply_effect(
                    effect["type"],
                    effect["magnitude"],
                    effect["duration_seconds"]
                )

                # Trigger chaos screen shake
                if effect["type"] == "chaos":
                    self.shake_intensity = 5
                    self.shake_duration = effect["duration_seconds"]

    def _apply_vote_effect(self, vote_winner: str) -> None:
        """Apply the winning vote effect to both players."""
        if not self.voting_system:
            return

        mode = self.voting_system.mode
        
        if mode == VotingMode.ACTION:
            if vote_winner == "extend":
                if self.arena2 and self.player2:
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
                    self.announcement_text = "UNLEASHED!"
                else:
                    self.player1.extend_leash()
                    if self.chat_simulator:
                        self.chat_simulator.add_message("System", "LEASH EXTENDED!", (50, 200, 50))
                        self.chat_simulator.add_message("System", "More room to roam!", (100, 255, 100))
                    self.announcement_text = "LEASH EXTENDED!"
                self.announcement_color = (50, 255, 50)
                self.flash_color = (50, 200, 50)
                
            elif vote_winner == "yank":
                self.player1.yank_leash()
                if self.player2:
                    self.player2.yank_leash()
                if self.chat_simulator:
                    self.chat_simulator.add_message("System", "LEASH YANKED!", (200, 50, 50))
                # Trigger dramatic announcement
                self.announcement_text = "LEASH YANKED!"
                self.announcement_color = (255, 50, 50)
                self.flash_color = (200, 50, 50)
            
            self.announcement_timer = self.announcement_duration
            self.flash_alpha = 150
            self.flash_timer = 0.3
            self.flash_duration = 0.3
            
        elif mode == VotingMode.TREAT:
            selected_snack = None
            for s in self.snack_configs:
                if s.get("id", "").lower() == vote_winner.lower() or s.get("name", "").replace(" ", "_").lower() == vote_winner.lower():
                    selected_snack = s
                    break
            
            if selected_snack:
                self.arena1.pending_snack = selected_snack
                self.arena1.pending_snack_x = self.arena1.bounds.centerx
                self.arena1.pending_snack_scale = 1.5  # Make voted snacks 1.5x larger
                self.arena1._trigger_lightning(self.arena1.pending_snack_x)
                # Activate voted food spawning phase (spawn voted food for 5 seconds)
                self.arena1.voted_food_active = True
                self.arena1.voted_food_timer = self.arena1.voted_food_duration
                self.arena1.voted_food_config = selected_snack
                
                if self.arena2:
                    self.arena2.pending_snack = selected_snack
                    self.arena2.pending_snack_x = self.arena2.bounds.centerx
                    self.arena2.pending_snack_scale = 1.5  # Make voted snacks 1.5x larger
                    self.arena2._trigger_lightning(self.arena2.pending_snack_x)
                    # Activate voted food spawning phase (spawn voted food for 5 seconds)
                    self.arena2.voted_food_active = True
                    self.arena2.voted_food_timer = self.arena2.voted_food_duration
                    self.arena2.voted_food_config = selected_snack
                
                self.announcement_text = f"{vote_winner.upper()} DROP!"
                self.announcement_color = (100, 200, 255)
            
            self.announcement_timer = self.announcement_duration
            
        elif mode == VotingMode.TRIVIA:
            correct = self.voting_system.correct_trivia_answer
            if vote_winner == correct:
                self.announcement_text = "CORRECT! SPEED UP!"
                self.announcement_color = (100, 255, 100)
                self.player1.apply_effect("speed", 2.0, 5.0)
                if self.player2:
                    self.player2.apply_effect("speed", 2.0, 5.0)
                if self.chat_simulator:
                    self.chat_simulator.add_message("System", "CORRECT ANSWER!", (100, 255, 100))
            else:
                self.announcement_text = "WRONG ANSWER!"
                self.announcement_color = (255, 100, 100)
                if self.chat_simulator:
                    self.chat_simulator.add_message("System", f"Ans: {correct}", (200, 100, 100))
            
            self.announcement_timer = self.announcement_duration

    def render(self, surface: pygame.Surface) -> None:
        """Render the gameplay screen to 800x800 display."""
        # Render storm intro fullscreen if active
        if self.storm_intro_active and self.storm_intro:
            self.storm_intro.render(surface)
            return

        if self.background_image:
            surface.blit(self.background_image, (0, 0))
        else:
            surface.fill(self.bg_color)

        # Draw logo at top center of game area
        if self.logo_image:
            logo_rect = self.logo_image.get_rect()
            logo_x = (self.game_area_width - logo_rect.width) // 2
            logo_y = -15  # Moved upward
            surface.blit(self.logo_image, (logo_x, logo_y))

        # Apply screen shake offset
        shake_x = 0
        shake_y = 0
        if self.shake_intensity > 0:
            shake_x = random.randint(-int(self.shake_intensity), int(self.shake_intensity))
            shake_y = random.randint(-int(self.shake_intensity), int(self.shake_intensity))

        # Draw clouds above menu bar
        cloud_y = 140  # Above menu bar
        if self.cloud1_image:
            surface.blit(self.cloud1_image, (int(self.cloud1_x), cloud_y))

        # Jazzy's Chili Effect Red Border (Render BEHIND HUD but ON TOP of background/clouds if we wanted, 
        # but requirements say "border of gameplay screen should turn red". 
        # Doing it early to be under HUD or late to be over everything? 
        # Usually overlay effects are top level. Let's put it at the end of the method before Pause overlay.)

        if self.cloud2_image and self.arena2:
            surface.blit(self.cloud2_image, (int(self.cloud2_x), cloud_y))

        # Draw arenas (food layer)
        if self.arena1:
            arena1_surface = self.arena1.render()
            surface.blit(arena1_surface,
                         (self.arena1.bounds.x + shake_x, self.arena1.bounds.y + shake_y))
        if self.arena2:
            arena2_surface = self.arena2.render()
            surface.blit(arena2_surface,
                         (self.arena2.bounds.x + shake_x, self.arena2.bounds.y + shake_y))

        # Draw menu bar above food layer
        if self.menu_bar_image and self.arena1:
            menu_bar_rect = self.menu_bar_image.get_rect()
            # Position above the battlefield
            menu_bar_x = (self.game_area_width - menu_bar_rect.width) // 2
            menu_bar_y = 200  # Position above battlefield
            surface.blit(self.menu_bar_image, (menu_bar_x, menu_bar_y))

        # Draw header (scores and round info) on top of menu bar
        self._render_header(surface)

        # Render players who have crossed into the other arena (on top of everything)
        if self.arena1 and self.arena2:
            self._render_crossed_players(surface, shake_x, shake_y)

        # Draw point popups
        self._render_point_popups(surface, shake_x, shake_y)

        # Player HUDs below arenas removed per user request

        # Draw voting meter (overlays top of arenas)
        if self.voting_meter and self.voting_system:
            voting_font = self.daydream_font if self.daydream_font else self.menu_font
            voting_small_font = self.daydream_font_small if self.daydream_font_small else self.small_font
            voting_label_font = self.daydream_font_tiny if self.daydream_font_tiny else self.small_font
            self.voting_meter.render(surface, self.voting_system, voting_font, voting_small_font, voting_label_font)

        # Draw chat simulator panel on right
        if self.chat_simulator:
            self.chat_simulator.render(surface, self.menu_font, self.small_font, self.voting_system)

        # Draw leash indicators on arenas
        self._render_leash_indicators(surface)

        # Draw screen flash effect
        # Use SRCALPHA surface for reliable per-pixel alpha on macOS SDL2 Metal backend
        if self.flash_alpha > 0:
            r, g, b = self.flash_color[0], self.flash_color[1], self.flash_color[2]
            flash_surface = pygame.Surface((self.game_area_width, self.screen_height), pygame.SRCALPHA)
            flash_surface.fill((r, g, b, max(0, min(255, self.flash_alpha))))
            surface.blit(flash_surface, (0, 0))

        # Draw announcement text
        if self.announcement_timer > 0:
            self._render_announcement(surface)

        # Draw crowd chaos overlays
        self._render_crowd_chaos_tint(surface)
        self._render_crowd_chaos_overlay(surface)

        # Draw countdown
        if self.countdown > 0:
            self._render_countdown(surface)

        # Draw walk-in animation
        if self.walk_in_active:
            self._render_walk_in(surface)

        # Draw pause overlay
        if self.paused:
            self._render_pause(surface)

        # --- Jazzy's Chili Effect Red Border Overlay ---
        # Show red border when face turns red (approx after 1.5s in animation)
        if self.chili_sequence_active and self.chili_stage == 1 and self.chili_timer > 1.5:
            # Draw a thick red border pulsing
            border_thickness = 20
            red_val = 200 + int(50 * abs(pygame.time.get_ticks() % 500 - 250) / 250)
            pygame.draw.rect(surface, (red_val, 0, 0), (0, 0, self.game_area_width, self.screen_height), border_thickness)

            # Additional screen tinted overlay
            # Use SRCALPHA with alpha in fill color — set_alpha() is unreliable on macOS SDL2 Metal
            overlay = pygame.Surface((self.game_area_width, self.screen_height), pygame.SRCALPHA)
            overlay.fill((255, 0, 0, 30))  # Slight red tint
            surface.blit(overlay, (0, 0))

    def _render_crowd_chaos_tint(self, surface: pygame.Surface) -> None:
        """Render a subtle red color shift during Crowd Chaos countdown/event."""
        if self.crowd_chaos_tint_alpha <= 1:
            return

        pulse = 0.85 + 0.15 * abs(pygame.time.get_ticks() % 500 - 250) / 250
        alpha = int(self.crowd_chaos_tint_alpha * pulse)
        alpha = max(0, min(140, alpha))

        if alpha <= 0:
            return

        # Use SRCALPHA surface for reliable per-pixel alpha compositing on macOS
        tint_surface = pygame.Surface((self.game_area_width, self.screen_height), pygame.SRCALPHA)
        tint_surface.fill((220, 40, 40, alpha))
        surface.blit(tint_surface, (0, 0))

    def _render_crowd_chaos_overlay(self, surface: pygame.Surface) -> None:
        """Render countdown and live-chaos labels to clearly communicate the event."""
        center_x = self.game_area_width // 2

        title_font = self.daydream_font_chaos_title if self.daydream_font_chaos_title else self.daydream_font_small if self.daydream_font_small else self.menu_font
        value_font = self.daydream_font_chaos_number if self.daydream_font_chaos_number else self.daydream_font if self.daydream_font else self.title_font
        helper_font = self.daydream_font_tiny if self.daydream_font_tiny else self.small_font

        if self.crowd_chaos_countdown_active:
            title = "CROWD CHAOS IN"
            title_surf = title_font.render(title, True, (255, 235, 235))
            title_rect = title_surf.get_rect(center=(center_x, 280))
            surface.blit(title_surf, title_rect)

            pulse_scale = 1.0 + 0.08 * abs(pygame.time.get_ticks() % 400 - 200) / 200
            number = str(max(1, self.crowd_chaos_countdown_value))
            number_surf = value_font.render(number, True, (255, 110, 110))
            if pulse_scale != 1.0:
                number_surf = pygame.transform.smoothscale(
                    number_surf,
                    (
                        max(1, int(number_surf.get_width() * pulse_scale)),
                        max(1, int(number_surf.get_height() * pulse_scale)),
                    ),
                )
            number_rect = number_surf.get_rect(center=(center_x, 380))
            surface.blit(number_surf, number_rect)

        elif self.crowd_chaos_active and self.voting_system:
            status = "CROWD CHAOS LIVE"
            status_surf = title_font.render(status, True, (255, 180, 180))
            status_rect = status_surf.get_rect(center=(center_x, 300))
            surface.blit(status_surf, status_rect)

            options = "   ".join([f"!{opt}" for opt in self.voting_system.options[:4]])
            if options:
                options_surf = helper_font.render(options, True, (255, 230, 200))
                options_rect = options_surf.get_rect(center=(center_x, 330))
                surface.blit(options_surf, options_rect)

    def _render_header(self, surface: pygame.Surface) -> None:
        """Render the game header (score and round info on menu bar)."""
        # Calculate position on menu bar (above battlefield)
        menu_bar_y = 200  # Position above battlefield
        if self.menu_bar_image:
            # Position text centered vertically on menu bar
            info_y = menu_bar_y + self.menu_bar_image.get_height() // 2
        else:
            info_y = 80

        # Colors
        score_color = (147, 76, 48)  # #934C30 for player scores
        vs_color = (77, 43, 31)  # #4D2B1F for round wins
        timer_color = (77, 43, 31)  # #4D2B1F for timer and round
        font = self.daydream_font if self.daydream_font else self.menu_font

        # Calculate position above menu bar for timer and round
        above_menu_y = menu_bar_y - 10

        # Smaller font for timer and round
        small_font = self.daydream_font_small if self.daydream_font_small else font

        # Round number on left side (above menu bar)
        round_text = f"round {self.current_round}"
        left_x = 70  # Left aligned position
        round_y = above_menu_y - 60  # Moved upward more
        self.draw_text(surface, round_text, small_font, timer_color,
                       (left_x, round_y), center=False)

        # Timer on left side, below round number (left aligned to match round)
        if self.round_active:
            timer_text = f"{int(self.round_timer)}s"
            self.draw_text(surface, timer_text, small_font, timer_color,
                           (left_x, round_y + 35), center=False)

        if self.single_dog_mode:
            rounds_cleared_text = f"round wins {self.p1_round_wins}"
            rounds_surface = small_font.render(rounds_cleared_text, True, vs_color)
            rounds_rect = rounds_surface.get_rect(center=(self.game_area_width // 2, info_y))
            surface.blit(rounds_surface, rounds_rect)
        else:
            # Round wins display centered "# vs #" with smaller "vs"
            vs_font = self.daydream_font_smallest if self.daydream_font_smallest else font
            p1_wins_surface = font.render(str(self.p1_round_wins), True, vs_color)
            vs_surface = vs_font.render("vs", True, vs_color)
            p2_wins_surface = font.render(str(self.p2_round_wins), True, vs_color)

            total_width = p1_wins_surface.get_width() + 8 + vs_surface.get_width() + 8 + p2_wins_surface.get_width()
            start_x = (self.game_area_width - total_width) // 2

            surface.blit(p1_wins_surface, (start_x, info_y - p1_wins_surface.get_height() // 2))
            start_x += p1_wins_surface.get_width() + 8
            surface.blit(vs_surface, (start_x, info_y - vs_surface.get_height() // 2))
            start_x += vs_surface.get_width() + 8
            surface.blit(p2_wins_surface, (start_x, info_y - p2_wins_surface.get_height() // 2))

        # Get fonts for different sizes
        name_font = self.daydream_font_small if self.daydream_font_small else font  # 20px
        score_label_font = self.daydream_font_smallest if self.daydream_font_smallest else font  # 14px (smallest)
        score_num_font = self.daydream_font_smaller if self.daydream_font_smaller else font  # 16px

        # Player 1 score on left: "player name" "score" "#"
        if self.player1:
            x_pos = 80
            # Render player name
            name_surface = name_font.render(self.player1.name, True, score_color)
            name_height = name_surface.get_height()
            surface.blit(name_surface, (x_pos, info_y - name_height // 2))
            x_pos += name_surface.get_width() + 15  # More space after name

            # Render "score"
            score_label_surface = score_label_font.render("score", True, score_color)
            surface.blit(score_label_surface, (x_pos, info_y - score_label_surface.get_height() // 2))
            x_pos += score_label_surface.get_width() + 5

            # Render score number
            score_num_surface = score_num_font.render(str(self.player1.score), True, score_color)
            surface.blit(score_num_surface, (x_pos, info_y - score_num_surface.get_height() // 2))

        # Player 2 score on right: "player name" "score" "#"
        if self.player2:
            # Calculate total width first for right alignment
            name_surface = name_font.render(self.player2.name, True, score_color)
            score_label_surface = score_label_font.render("score", True, score_color)
            score_num_surface = score_num_font.render(str(self.player2.score), True, score_color)
            total_width = name_surface.get_width() + 15 + score_label_surface.get_width() + 5 + score_num_surface.get_width()

            x_pos = self.game_area_width - 80 - total_width
            # Render player name
            surface.blit(name_surface, (x_pos, info_y - name_surface.get_height() // 2))
            x_pos += name_surface.get_width() + 15  # More space after name

            # Render "score"
            surface.blit(score_label_surface, (x_pos, info_y - score_label_surface.get_height() // 2))
            x_pos += score_label_surface.get_width() + 5

            # Render score number
            surface.blit(score_num_surface, (x_pos, info_y - score_num_surface.get_height() // 2))

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

        # Score on right with Daydream font and orange color
        score_text = f"{player.score}"
        score_font = self.daydream_font if self.daydream_font else self.menu_font
        orange_color = (232, 136, 55)  # #E88837
        self.draw_text(surface, score_text, score_font, orange_color,
                       (arena_bounds.right - 60, hud_y + 22), center=False)

    def _render_crossed_players(self, surface: pygame.Surface, shake_x: int, shake_y: int) -> None:
        """Render players who have crossed into the gap or other arena."""
        if not self.player2 or not self.arena2:
            return

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

    def _render_point_popups(self, surface: pygame.Surface, shake_x: int, shake_y: int) -> None:
        """Render floating point popups when treats are collected."""
        popup_font = self.daydream_font_popup if self.daydream_font_popup else pygame.font.Font(None, 32)
        popup_color = (81, 180, 71)  # #51B447
        outline_color = (255, 255, 255)  # White outline

        for popup in self.point_popups:
            points = popup['points']
            text = f"+{points}" if points >= 0 else f"{points}"
            x = int(popup["x"]) + shake_x
            y = int(popup["y"]) + shake_y

            # Use red for negative points, green for positive
            color = popup_color if points >= 0 else (222, 97, 91)  # #DE615B for negative

            # Draw white outline by rendering text offset in multiple directions (thicker)
            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2),
                           (-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
                outline_surface = popup_font.render(text, True, outline_color)
                outline_rect = outline_surface.get_rect(center=(x + dx, y + dy))
                surface.blit(outline_surface, outline_rect)

            # Draw main text on top
            text_surface = popup_font.render(text, True, color)
            text_rect = text_surface.get_rect(center=(x, y))
            surface.blit(text_surface, text_rect)

    def _render_countdown(self, surface: pygame.Surface) -> None:
        """Render the countdown overlay."""
        # Countdown number
        if self.countdown > 0:
            text = str(self.countdown)
        else:
            text = "GO!"

        # Draw large countdown text (centered in game area) with Daydream font and #FBCD64 color
        countdown_font = self.daydream_font_countdown if self.daydream_font_countdown else pygame.font.Font(None, 180)
        countdown_color = (251, 205, 100)  # #FBCD64
        text_surface = countdown_font.render(text, True, countdown_color)
        text_rect = text_surface.get_rect(center=(self.game_area_width // 2, self.screen_height // 2))
        surface.blit(text_surface, text_rect)

    def _render_pause(self, surface: pygame.Surface) -> None:
        """Render the pause overlay."""
        # Semi-transparent overlay (only over game area)
        # Use SRCALPHA + alpha in fill — set_alpha() on plain Surface is broken on macOS SDL2 Metal
        overlay = pygame.Surface((self.game_area_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))

        center_x = self.game_area_width // 2

        # Use Daydream font for pause text
        pause_title_font = self.daydream_font if self.daydream_font else self.title_font
        pause_menu_font = self.daydream_font_small if self.daydream_font_small else self.menu_font

        self.draw_text(surface, "PAUSED", pause_title_font, (255, 200, 0),
                       (center_x, self.screen_height // 2 - 40))

        self.draw_text(surface, "Press ENTER to Resume", pause_menu_font,
                       self.hud_color, (center_x, self.screen_height // 2 + 20))
        self.draw_text(surface, "Press Q to Quit to Menu", pause_menu_font,
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
                    # Use SRCALPHA + alpha in fill — set_alpha() on plain Surface is broken on macOS SDL2 Metal
                    restricted_surface = pygame.Surface((restricted_width, arena.bounds.height - 80), pygame.SRCALPHA)
                    restricted_surface.fill((200, 50, 50, 80))
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
        # Use Daydream font for announcement
        large_font = self.daydream_font if self.daydream_font else pygame.font.Font(None, 100)
        subtitle_font = self.daydream_font_small if self.daydream_font_small else self.small_font

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
        elif "EXTENDED" in self.announcement_text:
            subtitle = "More room to roam!"
            subtitle2 = None
        else:
            subtitle = "Dog movement is restricted!" if self.single_dog_mode else "Dogs movement is restricted!"
            subtitle2 = None

        subtitle_surf = subtitle_font.render(subtitle, True, (255, 255, 255))
        subtitle_rect = subtitle_surf.get_rect(center=(center_x, center_y + 60))
        surface.blit(subtitle_surf, subtitle_rect)

        if subtitle2:
            subtitle2_surf = subtitle_font.render(subtitle2, True, (255, 220, 100))
            subtitle2_rect = subtitle2_surf.get_rect(center=(center_x, center_y + 85))
            surface.blit(subtitle2_surf, subtitle2_rect)

    def _render_walk_in(self, surface: pygame.Surface) -> None:
        """Render the walk-in animation for Jazzy, Biggie, and Prissy."""
        # Player ground offset is 230, player height/width is 216
        player_ground_offset = 230
        player_height = 216
        player_width = 216

        # Vertical adjustment to move animation up (same for all characters)
        y_offset = -55

        # Render Jazzy walk-in
        # Player 1 side (facing right)
        if self.walk_in_p1_is_jazzy and self.walk_in_frames and self.arena1:
            frame_index = self.walk_in_frame_index % len(self.walk_in_frames)
            walk_sprite = self.walk_in_frames[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena1.bounds.bottom - player_ground_offset + player_height
            p1_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p1_render_x = int(self.walk_in_p1_x) + x_center_offset
            surface.blit(walk_sprite, (p1_render_x, p1_render_y))

        # Player 2 side (facing left, walking from right)
        if self.walk_in_p2_is_jazzy and self.walk_in_frames_left and self.arena2:
            frame_index = self.walk_in_frame_index % len(self.walk_in_frames_left)
            walk_sprite = self.walk_in_frames_left[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena2.bounds.bottom - player_ground_offset + player_height
            p2_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p2_render_x = int(self.walk_in_p2_x) + x_center_offset
            surface.blit(walk_sprite, (p2_render_x, p2_render_y))

        # Render Biggie walk-in
        # Player 1 side (facing right)
        if self.walk_in_p1_is_biggie and self.walk_in_biggie_frames and self.arena1:
            frame_index = self.walk_in_biggie_frame_index % len(self.walk_in_biggie_frames)
            walk_sprite = self.walk_in_biggie_frames[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena1.bounds.bottom - player_ground_offset + player_height
            p1_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p1_render_x = int(self.walk_in_p1_x) + x_center_offset
            surface.blit(walk_sprite, (p1_render_x, p1_render_y))

        # Player 2 side (facing left, walking from right)
        if self.walk_in_p2_is_biggie and self.walk_in_biggie_frames_left and self.arena2:
            frame_index = self.walk_in_biggie_frame_index % len(self.walk_in_biggie_frames_left)
            walk_sprite = self.walk_in_biggie_frames_left[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena2.bounds.bottom - player_ground_offset + player_height
            p2_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p2_render_x = int(self.walk_in_p2_x) + x_center_offset
            surface.blit(walk_sprite, (p2_render_x, p2_render_y))

        # Render Prissy walk-in
        # Player 1 side (facing right)
        if self.walk_in_p1_is_prissy and self.walk_in_prissy_frames and self.arena1:
            frame_index = self.walk_in_prissy_frame_index % len(self.walk_in_prissy_frames)
            walk_sprite = self.walk_in_prissy_frames[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena1.bounds.bottom - player_ground_offset + player_height
            p1_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p1_render_x = int(self.walk_in_p1_x) + x_center_offset
            surface.blit(walk_sprite, (p1_render_x, p1_render_y))

        # Player 2 side (facing left, walking from right)
        if self.walk_in_p2_is_prissy and self.walk_in_prissy_frames_left and self.arena2:
            frame_index = self.walk_in_prissy_frame_index % len(self.walk_in_prissy_frames_left)
            walk_sprite = self.walk_in_prissy_frames_left[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena2.bounds.bottom - player_ground_offset + player_height
            p2_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p2_render_x = int(self.walk_in_p2_x) + x_center_offset
            surface.blit(walk_sprite, (p2_render_x, p2_render_y))

        # Render Rex walk-in
        # Player 1 side (facing right)
        if self.walk_in_p1_is_rex and self.walk_in_rex_frames and self.arena1:
            frame_index = self.walk_in_rex_frame_index % len(self.walk_in_rex_frames)
            walk_sprite = self.walk_in_rex_frames[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena1.bounds.bottom - player_ground_offset + player_height
            p1_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p1_render_x = int(self.walk_in_p1_x) + x_center_offset
            surface.blit(walk_sprite, (p1_render_x, p1_render_y))

        # Player 2 side (facing left, walking from right)
        if self.walk_in_p2_is_rex and self.walk_in_rex_frames_left and self.arena2:
            frame_index = self.walk_in_rex_frame_index % len(self.walk_in_rex_frames_left)
            walk_sprite = self.walk_in_rex_frames_left[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena2.bounds.bottom - player_ground_offset + player_height
            p2_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p2_render_x = int(self.walk_in_p2_x) + x_center_offset
            surface.blit(walk_sprite, (p2_render_x, p2_render_y))

        # Render Dash walk-in
        # Player 1 side (facing right)
        if self.walk_in_p1_is_dash and self.walk_in_dash_frames and self.arena1:
            frame_index = self.walk_in_dash_frame_index % len(self.walk_in_dash_frames)
            walk_sprite = self.walk_in_dash_frames[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena1.bounds.bottom - player_ground_offset + player_height
            p1_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p1_render_x = int(self.walk_in_p1_x) + x_center_offset
            surface.blit(walk_sprite, (p1_render_x, p1_render_y))

        # Player 2 side (facing left, walking from right)
        if self.walk_in_p2_is_dash and self.walk_in_dash_frames_left and self.arena2:
            frame_index = self.walk_in_dash_frame_index % len(self.walk_in_dash_frames_left)
            walk_sprite = self.walk_in_dash_frames_left[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena2.bounds.bottom - player_ground_offset + player_height
            p2_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p2_render_x = int(self.walk_in_p2_x) + x_center_offset
            surface.blit(walk_sprite, (p2_render_x, p2_render_y))

        # Render Snowy walk-in
        # Player 1 side (facing right)
        if self.walk_in_p1_is_snowy and self.walk_in_snowy_frames and self.arena1:
            frame_index = self.walk_in_snowy_frame_index % len(self.walk_in_snowy_frames)
            walk_sprite = self.walk_in_snowy_frames[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena1.bounds.bottom - player_ground_offset + player_height
            p1_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p1_render_x = int(self.walk_in_p1_x) + x_center_offset
            surface.blit(walk_sprite, (p1_render_x, p1_render_y))

        # Player 2 side (facing left, walking from right)
        if self.walk_in_p2_is_snowy and self.walk_in_snowy_frames_left and self.arena2:
            frame_index = self.walk_in_snowy_frame_index % len(self.walk_in_snowy_frames_left)
            walk_sprite = self.walk_in_snowy_frames_left[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena2.bounds.bottom - player_ground_offset + player_height
            p2_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p2_render_x = int(self.walk_in_p2_x) + x_center_offset
            surface.blit(walk_sprite, (p2_render_x, p2_render_y))

        # Render custom character walk-in
        # Player 1 side (facing right)
        if self.walk_in_p1_is_custom and self.walk_in_custom_frames and self.arena1:
            frame_index = self.walk_in_custom_frame_index % len(self.walk_in_custom_frames)
            walk_sprite = self.walk_in_custom_frames[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena1.bounds.bottom - player_ground_offset + player_height
            p1_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p1_render_x = int(self.walk_in_p1_x) + x_center_offset
            surface.blit(walk_sprite, (p1_render_x, p1_render_y))

        # Player 2 side (facing left, walking from right)
        if self.walk_in_p2_is_custom and self.walk_in_custom_frames_left and self.arena2:
            frame_index = self.walk_in_custom_frame_index % len(self.walk_in_custom_frames_left)
            walk_sprite = self.walk_in_custom_frames_left[frame_index]
            walk_sprite_height = walk_sprite.get_height()
            walk_sprite_width = walk_sprite.get_width()
            x_center_offset = (player_width - walk_sprite_width) // 2
            player_feet_y = self.arena2.bounds.bottom - player_ground_offset + player_height
            p2_render_y = int(player_feet_y - walk_sprite_height) + y_offset
            p2_render_x = int(self.walk_in_p2_x) + x_center_offset
            surface.blit(walk_sprite, (p2_render_x, p2_render_y))

        # Draw "GO!" text centered (same position as countdown)
        center_x = self.game_area_width // 2
        center_y = self.screen_height // 2

        countdown_font = self.daydream_font_countdown if self.daydream_font_countdown else pygame.font.Font(None, 80)
        countdown_color = (251, 205, 100)  # #FBCD64

        text_surface = countdown_font.render("GO!", True, countdown_color)
        text_rect = text_surface.get_rect(center=(center_x, center_y))
        surface.blit(text_surface, text_rect)
