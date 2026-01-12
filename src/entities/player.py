"""Player entity - controlled by keyboard input."""

import pygame
import time
from typing import Dict, Any, Tuple, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..sprites.animation_controller import AnimationController


class Player:
    """A player-controlled dog character."""

    def __init__(self, character_config: Dict[str, Any], arena_bounds: pygame.Rect,
                 player_num: int = 1, horizontal_only: bool = False):
        """
        Initialize a player.

        Args:
            character_config: Character configuration from characters.json
            arena_bounds: The playable area boundaries
            player_num: Player number (1 or 2)
            horizontal_only: If True, only allow horizontal movement
        """
        self.character_id = character_config.get("id", "unknown")
        self.name = character_config.get("name", "Unknown")
        self.base_speed = character_config.get("base_speed", 1.0)
        self.color = tuple(character_config.get("color", [255, 255, 255]))

        # Use larger sprite size from SpriteSheetLoader
        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        self.width = SpriteSheetLoader.GAMEPLAY_SIZE[0]
        self.height = SpriteSheetLoader.GAMEPLAY_SIZE[1]

        self.arena_bounds = arena_bounds
        self.player_num = player_num
        self.horizontal_only = horizontal_only

        # Position (center of arena horizontally)
        self.x = arena_bounds.centerx - self.width // 2
        self.y = arena_bounds.centery - self.height // 2

        # Movement - faster for larger screen
        self.base_move_speed = 350  # pixels per second
        self.velocity_x = 0
        self.velocity_y = 0

        # State
        self.score = 0
        self.active_effects: List[Dict[str, Any]] = []
        self.is_invincible = False
        self.controls_flipped = False

        # Leash system - controls horizontal movement boundaries
        self.leash_base_min_x = arena_bounds.left
        self.leash_base_max_x = arena_bounds.right - self.width
        self.leash_min_x = self.leash_base_min_x
        self.leash_max_x = self.leash_base_max_x
        self.leash_effect_timer = 0.0
        self.leash_effect_duration = 8.0  # seconds (longer to see the effect)
        # Calculate arena width for dramatic effects
        arena_width = arena_bounds.width
        self.leash_extend_amount = int(arena_width * 0.15)  # Extend 15% more
        self.leash_yank_amount = int(arena_width * 0.35)  # Restrict by 35% (very noticeable!)

        # Animation state
        self.facing_right = True
        self.is_moving = False

        # Animation controller (lazy initialization)
        self._animation_controller: Optional['AnimationController'] = None

    @property
    def rect(self) -> pygame.Rect:
        """Get the player's collision rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    @property
    def center(self) -> Tuple[float, float]:
        """Get the player's center position."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def animation_controller(self) -> 'AnimationController':
        """Lazy initialization of animation controller."""
        if self._animation_controller is None:
            from ..sprites.animation_controller import AnimationController
            self._animation_controller = AnimationController(self.character_id)
        return self._animation_controller

    def trigger_eat_animation(self) -> None:
        """Trigger the eat/attack animation when collecting a snack."""
        self.animation_controller.trigger_eat_animation()

    def get_speed_multiplier(self) -> float:
        """Calculate current speed multiplier from active effects."""
        multiplier = 1.0
        for effect in self.active_effects:
            if effect["type"] in ("speed_boost", "slow"):
                multiplier *= effect["magnitude"]
        return multiplier

    def apply_effect(self, effect_type: str, magnitude: float, duration: float) -> None:
        """Apply a power-up or penalty effect."""
        effect = {
            "type": effect_type,
            "magnitude": magnitude,
            "duration": duration,
            "time_remaining": duration
        }
        self.active_effects.append(effect)

        if effect_type == "invincibility":
            self.is_invincible = True
        elif effect_type == "chaos":
            self.controls_flipped = True

    def update_effects(self, dt: float) -> List[Dict[str, Any]]:
        """
        Update effect timers and remove expired effects.

        Returns:
            List of expired effects
        """
        expired = []
        still_active = []

        for effect in self.active_effects:
            effect["time_remaining"] -= dt
            if effect["time_remaining"] <= 0:
                expired.append(effect)
                # Reset state flags
                if effect["type"] == "invincibility":
                    self.is_invincible = False
                elif effect["type"] == "chaos":
                    self.controls_flipped = False
            else:
                still_active.append(effect)

        self.active_effects = still_active
        return expired

    def handle_input(self, keys_pressed: Dict[str, bool]) -> None:
        """
        Handle keyboard input for movement.

        Args:
            keys_pressed: Dictionary of control keys to their pressed state
        """
        dx = 0
        dy = 0

        if not self.horizontal_only:
            if keys_pressed.get("up", False):
                dy = -1
            if keys_pressed.get("down", False):
                dy = 1

        if keys_pressed.get("left", False):
            dx = -1
        if keys_pressed.get("right", False):
            dx = 1

        # Apply chaos effect (flip controls)
        if self.controls_flipped:
            dx = -dx
            dy = -dy

        # Normalize diagonal movement (only if not horizontal_only)
        if not self.horizontal_only and dx != 0 and dy != 0:
            dx *= 0.707  # 1/sqrt(2)
            dy *= 0.707

        speed = self.base_move_speed * self.base_speed * self.get_speed_multiplier()
        self.velocity_x = dx * speed
        self.velocity_y = dy * speed if not self.horizontal_only else 0

        # Update facing direction
        if dx > 0:
            self.facing_right = True
        elif dx < 0:
            self.facing_right = False

        self.is_moving = dx != 0 or (not self.horizontal_only and dy != 0)

    def update(self, dt: float) -> None:
        """Update player position and state."""
        # Update leash effect timer
        if self.leash_effect_timer > 0:
            self.leash_effect_timer -= dt
            if self.leash_effect_timer <= 0:
                self.reset_leash()

        # Update position
        new_x = self.x + self.velocity_x * dt
        new_y = self.y + self.velocity_y * dt

        # Clamp to leash bounds (horizontal) and arena bounds (vertical)
        new_x = max(self.leash_min_x, min(new_x, self.leash_max_x))
        new_y = max(self.arena_bounds.top, min(new_y, self.arena_bounds.bottom - self.height))

        self.x = new_x
        self.y = new_y

        # Update animation controller
        self.animation_controller.update(dt, self.is_moving, self.facing_right)

        # Update effects
        self.update_effects(dt)

    def extend_leash(self, cross_arena_max_x: int = None) -> None:
        """Extend the leash, allowing more movement range.

        Args:
            cross_arena_max_x: If provided, allows dog to cross into other arena up to this x position
        """
        if cross_arena_max_x is not None:
            # Allow crossing into other arena!
            self.leash_max_x = cross_arena_max_x
        else:
            self.leash_max_x = self.leash_base_max_x + self.leash_extend_amount
        self.leash_effect_timer = self.leash_effect_duration

    def yank_leash(self) -> None:
        """Yank the leash, restricting movement range."""
        # Calculate restricted max_x (can't go below min_x + some minimum space)
        min_range = self.width * 2  # At least 2 dog widths of movement
        self.leash_max_x = max(
            self.leash_base_max_x - self.leash_yank_amount,
            self.leash_min_x + min_range
        )
        self.leash_effect_timer = self.leash_effect_duration

    def reset_leash(self) -> None:
        """Reset leash to default boundaries."""
        self.leash_min_x = self.leash_base_min_x
        self.leash_max_x = self.leash_base_max_x
        self.leash_effect_timer = 0.0

    def get_leash_state(self) -> str:
        """Get current leash state for visual feedback."""
        if self.leash_effect_timer <= 0:
            return "normal"
        elif self.leash_max_x > self.leash_base_max_x:
            return "extended"
        elif self.leash_max_x < self.leash_base_max_x:
            return "yanked"
        return "normal"

    def add_score(self, points: int) -> None:
        """Add points to the player's score."""
        self.score += points
        if self.score < 0:
            self.score = 0

    def reset_position(self) -> None:
        """Reset player to center of arena."""
        self.x = self.arena_bounds.centerx - self.width // 2
        self.y = self.arena_bounds.centery - self.height // 2
        self.velocity_x = 0
        self.velocity_y = 0

    def reset(self) -> None:
        """Reset player state for new round."""
        self.reset_position()
        self.score = 0
        self.active_effects.clear()
        self.is_invincible = False
        self.controls_flipped = False
        self.reset_leash()

        # Reset animation state
        if self._animation_controller is not None:
            self._animation_controller.reset()

    def render(self, surface: pygame.Surface, offset: Tuple[int, int] = (0, 0)) -> None:
        """
        Render the player using sprite sheet animations.

        Args:
            surface: Surface to render to
            offset: Offset for rendering within arena
        """
        render_x = int(self.x - self.arena_bounds.left + offset[0])
        render_y = int(self.y - self.arena_bounds.top + offset[1])

        # Get current animation frame from animation controller
        sprite = self.animation_controller.get_current_sprite()

        # Fallback to procedural sprite if animation not available
        if sprite is None:
            from ..sprites.pixel_art import SpriteCache
            cache = SpriteCache()
            sprite = cache.get_dog_sprite(self.character_id, self.facing_right)

        # Handle invincibility flashing
        if self.is_invincible:
            if int(time.time() * 10) % 2 == 0:
                # Create a white-tinted version
                flash_sprite = sprite.copy()
                flash_sprite.fill((255, 255, 255, 100), special_flags=pygame.BLEND_RGBA_ADD)
                sprite = flash_sprite

        # Draw the sprite
        surface.blit(sprite, (render_x, render_y))

        # Draw effect indicators above the sprite
        indicator_y = render_y - 10
        indicator_x = render_x + 32

        for effect in self.active_effects:
            if effect["type"] == "speed_boost":
                pygame.draw.circle(surface, (255, 255, 0), (indicator_x, indicator_y), 6)
            elif effect["type"] == "slow":
                pygame.draw.circle(surface, (100, 200, 100), (indicator_x, indicator_y), 6)
            elif effect["type"] == "chaos":
                pygame.draw.circle(surface, (255, 100, 100), (indicator_x, indicator_y), 6)
            elif effect["type"] == "invincibility":
                pygame.draw.circle(surface, (255, 255, 100), (indicator_x, indicator_y), 6)
