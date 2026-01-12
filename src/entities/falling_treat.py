"""Falling treat entity for Treat Attack game."""

import pygame
import random
from typing import Dict, Any, Tuple, Optional


class FallingTreat:
    """A treat that falls from the top of the screen."""

    def __init__(self, treat_config: Dict[str, Any], x: float, screen_height: int,
                 fall_speed: float = 150):
        """
        Initialize a falling treat.

        Args:
            treat_config: Treat configuration from settings
            x: Horizontal spawn position
            screen_height: Height of game screen (for bounds checking)
            fall_speed: Falling speed in pixels per second
        """
        self.treat_id = treat_config.get("id", "normal")
        self.name = treat_config.get("name", "Treat")
        self.point_value = treat_config.get("point_value", 100)
        self.color = tuple(treat_config.get("color", [255, 210, 80]))
        self.spawn_bias_right = treat_config.get("spawn_bias_right", False)

        # Position and size
        self.x = x
        self.y = -50  # Start above screen
        self.width = 48
        self.height = 48

        # Physics
        self.fall_speed = fall_speed
        self.screen_height = screen_height

        # State
        self.active = True
        self.collected = False

    @property
    def rect(self) -> pygame.Rect:
        """Get the treat's collision rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    @property
    def center(self) -> Tuple[float, float]:
        """Get the treat's center position."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    def update(self, dt: float) -> bool:
        """
        Update treat position.

        Args:
            dt: Delta time in seconds

        Returns:
            True if treat is still active, False if it should be removed
        """
        if not self.active:
            return False

        # Fall down
        self.y += self.fall_speed * dt

        # Check if fell off screen
        if self.y > self.screen_height:
            self.active = False
            return False

        return True

    def collect(self) -> Dict[str, Any]:
        """
        Mark treat as collected and return its value.

        Returns:
            Dictionary with treat info and point value
        """
        self.active = False
        self.collected = True
        return {
            "treat_id": self.treat_id,
            "point_value": self.point_value,
            "name": self.name
        }

    def render(self, surface: pygame.Surface) -> None:
        """
        Render the treat.

        Args:
            surface: Surface to render to
        """
        if not self.active:
            return

        # Try to get PNG sprite first
        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        loader = SpriteSheetLoader()

        # Map treat types to food sprites
        sprite_map = {
            "normal": "pizza",
            "power": "steak",
            "bad": "broccoli"
        }

        snack_id = sprite_map.get(self.treat_id, "pizza")
        sprite = loader.get_food_sprite(snack_id)

        if sprite:
            surface.blit(sprite, (int(self.x), int(self.y)))
        else:
            # Fallback to colored rectangle
            pygame.draw.rect(surface, self.color,
                           (int(self.x), int(self.y), self.width, self.height),
                           border_radius=8)

        # Draw indicator for power/bad treats
        if self.treat_id == "power":
            # Gold sparkle effect
            pygame.draw.circle(surface, (255, 255, 200),
                             (int(self.x + self.width // 2), int(self.y - 5)), 5)
        elif self.treat_id == "bad":
            # Warning indicator
            pygame.draw.circle(surface, (255, 100, 100),
                             (int(self.x + self.width // 2), int(self.y - 5)), 5)


class TreatSpawner:
    """Manages spawning of falling treats."""

    def __init__(self, screen_width: int, screen_height: int,
                 treat_configs: list, spawn_interval: float = 1.5):
        """
        Initialize the treat spawner.

        Args:
            screen_width: Width of game screen
            screen_height: Height of game screen
            treat_configs: List of treat type configurations
            spawn_interval: Base time between spawns in seconds
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.treat_configs = treat_configs
        self.spawn_interval = spawn_interval

        self.spawn_timer = 0.0
        self.fall_speed = 150
        self.margin = 50  # Margin from screen edges

    def update(self, dt: float) -> Optional[FallingTreat]:
        """
        Update spawner and potentially spawn a new treat.

        Args:
            dt: Delta time in seconds

        Returns:
            New FallingTreat if spawned, None otherwise
        """
        self.spawn_timer += dt

        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer = 0.0
            return self._spawn_treat()

        return None

    def _spawn_treat(self) -> FallingTreat:
        """Spawn a new treat based on weighted random selection."""
        # Calculate total weight
        total_weight = sum(t.get("spawn_weight", 1) for t in self.treat_configs)

        # Random selection
        roll = random.uniform(0, total_weight)
        cumulative = 0

        selected_config = self.treat_configs[0]
        for config in self.treat_configs:
            cumulative += config.get("spawn_weight", 1)
            if roll <= cumulative:
                selected_config = config
                break

        # Determine spawn X position
        if selected_config.get("spawn_bias_right", False):
            # Bias toward right side (where leash can't reach easily)
            x = random.uniform(self.screen_width * 0.6, self.screen_width - self.margin - 48)
        else:
            # Random position
            x = random.uniform(self.margin, self.screen_width - self.margin - 48)

        return FallingTreat(
            treat_config=selected_config,
            x=x,
            screen_height=self.screen_height,
            fall_speed=self.fall_speed
        )

    def set_fall_speed(self, speed: float) -> None:
        """Set the fall speed for new treats."""
        self.fall_speed = speed

    def set_spawn_interval(self, interval: float) -> None:
        """Set the spawn interval."""
        self.spawn_interval = max(0.3, interval)  # Minimum 0.3s
