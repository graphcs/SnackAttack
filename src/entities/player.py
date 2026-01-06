"""Player entity - controlled by keyboard input."""

import pygame
from typing import Dict, Any, Tuple, Optional, List


class Player:
    """A player-controlled dog character."""

    def __init__(self, character_config: Dict[str, Any], arena_bounds: pygame.Rect,
                 player_num: int = 1):
        """
        Initialize a player.

        Args:
            character_config: Character configuration from characters.json
            arena_bounds: The playable area boundaries
            player_num: Player number (1 or 2)
        """
        self.character_id = character_config.get("id", "unknown")
        self.name = character_config.get("name", "Unknown")
        self.base_speed = character_config.get("base_speed", 1.0)
        self.color = tuple(character_config.get("color", [255, 255, 255]))
        hitbox = character_config.get("hitbox", [32, 32])
        self.width = hitbox[0]
        self.height = hitbox[1]

        self.arena_bounds = arena_bounds
        self.player_num = player_num

        # Position (center of arena)
        self.x = arena_bounds.centerx - self.width // 2
        self.y = arena_bounds.centery - self.height // 2

        # Movement (scaled for 960x720 display)
        self.base_move_speed = 240  # pixels per second (for full resolution)
        self.velocity_x = 0
        self.velocity_y = 0

        # State
        self.score = 0
        self.active_effects: List[Dict[str, Any]] = []
        self.is_invincible = False
        self.controls_flipped = False

        # Animation state
        self.facing_right = True
        self.is_moving = False

    @property
    def rect(self) -> pygame.Rect:
        """Get the player's collision rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    @property
    def center(self) -> Tuple[float, float]:
        """Get the player's center position."""
        return (self.x + self.width / 2, self.y + self.height / 2)

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

        # Normalize diagonal movement
        if dx != 0 and dy != 0:
            dx *= 0.707  # 1/sqrt(2)
            dy *= 0.707

        speed = self.base_move_speed * self.base_speed * self.get_speed_multiplier()
        self.velocity_x = dx * speed
        self.velocity_y = dy * speed

        # Update facing direction
        if dx > 0:
            self.facing_right = True
        elif dx < 0:
            self.facing_right = False

        self.is_moving = dx != 0 or dy != 0

    def update(self, dt: float) -> None:
        """Update player position and state."""
        # Update position
        new_x = self.x + self.velocity_x * dt
        new_y = self.y + self.velocity_y * dt

        # Clamp to arena bounds
        new_x = max(self.arena_bounds.left, min(new_x, self.arena_bounds.right - self.width))
        new_y = max(self.arena_bounds.top, min(new_y, self.arena_bounds.bottom - self.height))

        self.x = new_x
        self.y = new_y

        # Update effects
        self.update_effects(dt)

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

    def render(self, surface: pygame.Surface, offset: Tuple[int, int] = (0, 0)) -> None:
        """
        Render the player using pixel art sprites.

        Args:
            surface: Surface to render to
            offset: Offset for rendering within arena
        """
        from ..sprites.pixel_art import SpriteCache

        render_x = int(self.x - self.arena_bounds.left + offset[0])
        render_y = int(self.y - self.arena_bounds.top + offset[1])

        # Get the pixel art sprite (64x64 for 960x720 display)
        cache = SpriteCache()
        sprite = cache.get_dog_sprite(self.character_id, self.facing_right)

        # Handle invincibility flashing
        if self.is_invincible:
            import time
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
