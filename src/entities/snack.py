"""Snack entity - collectible items in the game."""

import pygame
from typing import Dict, Any, Tuple, Optional


class Snack:
    """A collectible snack item."""

    def __init__(self, snack_config: Dict[str, Any], position: Tuple[float, float],
                 arena_bounds: pygame.Rect):
        """
        Initialize a snack.

        Args:
            snack_config: Snack configuration from snacks.json
            position: Initial (x, y) position
            arena_bounds: Arena boundaries for reference
        """
        self.snack_id = snack_config.get("id", "unknown")
        self.name = snack_config.get("name", "Unknown")
        self.point_value = snack_config.get("point_value", 0)
        self.effect = snack_config.get("effect")
        self.despawn_time = snack_config.get("despawn_seconds", 8.0)
        self.color = tuple(snack_config.get("color", [255, 255, 255]))
        size = snack_config.get("size", [16, 16])
        self.width = size[0]
        self.height = size[1]

        self.arena_bounds = arena_bounds
        self.x, self.y = position
        self.active = True
        self.time_alive = 0.0

        # Visual effects
        self.bob_offset = 0.0
        self.bob_speed = 3.0

    @property
    def rect(self) -> pygame.Rect:
        """Get the snack's collision rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    @property
    def center(self) -> Tuple[float, float]:
        """Get the snack's center position."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    def update(self, dt: float) -> bool:
        """
        Update snack state.

        Args:
            dt: Delta time in seconds

        Returns:
            True if snack is still active, False if it should despawn
        """
        if not self.active:
            return False

        self.time_alive += dt

        # Check for despawn
        if self.time_alive >= self.despawn_time:
            self.active = False
            return False

        # Update bob animation
        import math
        self.bob_offset = math.sin(self.time_alive * self.bob_speed) * 3

        return True

    def collect(self) -> Dict[str, Any]:
        """
        Mark snack as collected and return its effects.

        Returns:
            Dictionary with point_value and effect data
        """
        self.active = False
        return {
            "snack_id": self.snack_id,
            "point_value": self.point_value,
            "effect": self.effect
        }

    def get_despawn_progress(self) -> float:
        """
        Get progress toward despawning (0.0 to 1.0).

        Returns:
            Float from 0.0 (just spawned) to 1.0 (about to despawn)
        """
        return min(1.0, self.time_alive / self.despawn_time)

    def render(self, surface: pygame.Surface, offset: Tuple[int, int] = (0, 0)) -> None:
        """
        Render the snack using PNG food sprites.

        Args:
            surface: Surface to render to
            offset: Offset for rendering within arena
        """
        if not self.active:
            return

        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        from ..sprites.pixel_art import SpriteCache

        render_x = int(self.x - self.arena_bounds.left + offset[0])
        render_y = int(self.y - self.arena_bounds.top + offset[1] + self.bob_offset)

        # Try to get PNG food sprite first
        loader = SpriteSheetLoader()
        sprite = loader.get_food_sprite(self.snack_id)

        # Fall back to procedural sprite if PNG not available
        if sprite is None:
            cache = SpriteCache()
            sprite = cache.get_snack_sprite(self.snack_id)

        # Handle despawn flashing
        despawn_progress = self.get_despawn_progress()
        if despawn_progress > 0.7:
            import time
            if int(time.time() * 5) % 2 == 0:
                # Make sprite semi-transparent by creating a copy
                sprite = sprite.copy()
                sprite.set_alpha(128)

        # Draw the sprite
        surface.blit(sprite, (render_x, render_y))
