"""Catcher dog entity for Treat Attack game."""

import pygame
from typing import Dict, Any, Tuple, Optional
from enum import Enum, auto


class LeashState(Enum):
    """Leash constraint states."""
    NORMAL = auto()
    EXTENDED = auto()
    YANKED = auto()


class CatcherDog:
    """A dog that moves horizontally to catch falling treats."""

    def __init__(self, config: Dict[str, Any], character_id: str = "jazzy"):
        """
        Initialize the catcher dog.

        Args:
            config: Game configuration from treat_attack_settings.json
            character_id: Character identifier for sprites
        """
        self.character_id = character_id

        # Get settings from config
        dog_config = config.get("dog", {})
        leash_config = config.get("leash", {})
        screen_config = config.get("screen", {})

        # Position and size
        self.width = dog_config.get("width", 64)
        self.height = dog_config.get("height", 64)
        self.ground_y = dog_config.get("ground_y", 650)
        self.screen_width = screen_config.get("width", 720)

        # Start in center of default range
        default_min = leash_config.get("default_min_x", 50)
        default_max = leash_config.get("default_max_x", 550)
        self.x = (default_min + default_max) / 2
        self.y = self.ground_y

        # Movement
        self.move_speed = dog_config.get("move_speed", 300)
        self.velocity_x = 0
        self.facing_right = True
        self.is_moving = False

        # Leash constraints
        self.leash_anchor_x = dog_config.get("leash_anchor_x", 0)
        self.default_min_x = default_min
        self.default_max_x = default_max
        self.extended_max_x = leash_config.get("extended_max_x", 670)
        self.yanked_max_x = leash_config.get("yanked_max_x", 350)
        self.effect_duration = leash_config.get("effect_duration_seconds", 5.0)

        # Current leash state
        self.leash_state = LeashState.NORMAL
        self.leash_effect_timer = 0.0

        # Animation
        self.is_eating = False
        self.eat_timer = 0.0
        self.eat_duration = 0.4

        # Animation controller (loaded lazily)
        self._animation_controller = None

    @property
    def rect(self) -> pygame.Rect:
        """Get the dog's collision rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    @property
    def center(self) -> Tuple[float, float]:
        """Get the dog's center position."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def current_min_x(self) -> float:
        """Get current minimum X based on leash state."""
        return self.default_min_x

    @property
    def current_max_x(self) -> float:
        """Get current maximum X based on leash state."""
        if self.leash_state == LeashState.EXTENDED:
            return self.extended_max_x
        elif self.leash_state == LeashState.YANKED:
            return self.yanked_max_x
        return self.default_max_x

    def _get_animation_controller(self):
        """Lazily initialize animation controller."""
        if self._animation_controller is None:
            from ..sprites.animation_controller import AnimationController
            self._animation_controller = AnimationController(self.character_id)
        return self._animation_controller

    def set_leash_state(self, state: LeashState) -> None:
        """
        Set the leash state (from voting results).

        Args:
            state: New leash state
        """
        self.leash_state = state
        if state != LeashState.NORMAL:
            self.leash_effect_timer = self.effect_duration

    def extend_leash(self) -> None:
        """Extend the leash (allows reaching further right)."""
        self.set_leash_state(LeashState.EXTENDED)

    def yank_leash(self) -> None:
        """Yank the leash (restricts movement range)."""
        self.set_leash_state(LeashState.YANKED)

    def reset_leash(self) -> None:
        """Reset leash to normal state."""
        self.leash_state = LeashState.NORMAL
        self.leash_effect_timer = 0.0

    def move_left(self) -> None:
        """Set movement direction to left."""
        self.velocity_x = -self.move_speed
        self.facing_right = False
        self.is_moving = True

    def move_right(self) -> None:
        """Set movement direction to right."""
        self.velocity_x = self.move_speed
        self.facing_right = True
        self.is_moving = True

    def stop(self) -> None:
        """Stop horizontal movement."""
        self.velocity_x = 0
        self.is_moving = False

    def trigger_eat(self) -> None:
        """Trigger the eat animation."""
        self.is_eating = True
        self.eat_timer = self.eat_duration
        controller = self._get_animation_controller()
        controller.trigger_eat_animation()

    def update(self, dt: float) -> None:
        """
        Update dog position and state.

        Args:
            dt: Delta time in seconds
        """
        # Update leash effect timer
        if self.leash_effect_timer > 0:
            self.leash_effect_timer -= dt
            if self.leash_effect_timer <= 0:
                self.reset_leash()

        # Update eat animation timer
        if self.is_eating:
            self.eat_timer -= dt
            if self.eat_timer <= 0:
                self.is_eating = False

        # Apply horizontal movement
        if self.velocity_x != 0:
            new_x = self.x + self.velocity_x * dt

            # Clamp to leash boundaries
            min_x = self.current_min_x
            max_x = self.current_max_x - self.width

            self.x = max(min_x, min(new_x, max_x))

        # Update animation
        controller = self._get_animation_controller()
        controller.update(dt, self.is_moving, self.facing_right)

    def check_collision(self, treat_rect: pygame.Rect) -> bool:
        """
        Check if dog collides with a treat.

        Args:
            treat_rect: Treat's collision rectangle

        Returns:
            True if collision detected
        """
        return self.rect.colliderect(treat_rect)

    def render(self, surface: pygame.Surface) -> None:
        """
        Render the dog.

        Args:
            surface: Surface to render to
        """
        controller = self._get_animation_controller()
        frame = controller.get_current_sprite()

        if frame:
            surface.blit(frame, (int(self.x), int(self.y)))
        else:
            # Fallback to colored rectangle
            pygame.draw.rect(surface, (139, 69, 19),
                           (int(self.x), int(self.y), self.width, self.height),
                           border_radius=8)

        # Draw leash line (visual indicator)
        self._render_leash(surface)

        # Draw leash state indicator
        self._render_leash_indicator(surface)

    def _render_leash(self, surface: pygame.Surface) -> None:
        """Render the leash line from anchor to dog."""
        anchor_pos = (self.leash_anchor_x, int(self.y + self.height / 2))
        dog_pos = (int(self.x), int(self.y + self.height / 2))

        # Leash color based on state
        if self.leash_state == LeashState.EXTENDED:
            color = (100, 200, 100)  # Green for extended
        elif self.leash_state == LeashState.YANKED:
            color = (200, 100, 100)  # Red for yanked
        else:
            color = (139, 90, 43)  # Brown for normal

        # Draw leash as a curved line (simple bezier approximation)
        # Using 3 line segments for a slight sag effect
        mid_x = (anchor_pos[0] + dog_pos[0]) / 2
        sag_y = anchor_pos[1] + 20  # Sag down a bit

        pygame.draw.line(surface, color, anchor_pos, (mid_x, sag_y), 3)
        pygame.draw.line(surface, color, (mid_x, sag_y), dog_pos, 3)

    def _render_leash_indicator(self, surface: pygame.Surface) -> None:
        """Render leash state indicator above dog."""
        if self.leash_state == LeashState.NORMAL:
            return

        # Position above dog
        indicator_x = int(self.x + self.width / 2)
        indicator_y = int(self.y - 15)

        # Draw indicator
        if self.leash_state == LeashState.EXTENDED:
            # Green up arrows
            color = (100, 255, 100)
            pygame.draw.polygon(surface, color, [
                (indicator_x, indicator_y - 5),
                (indicator_x - 8, indicator_y + 5),
                (indicator_x + 8, indicator_y + 5)
            ])
        elif self.leash_state == LeashState.YANKED:
            # Red X
            color = (255, 100, 100)
            pygame.draw.line(surface, color,
                           (indicator_x - 6, indicator_y - 6),
                           (indicator_x + 6, indicator_y + 6), 3)
            pygame.draw.line(surface, color,
                           (indicator_x + 6, indicator_y - 6),
                           (indicator_x - 6, indicator_y + 6), 3)

    def get_leash_effect_remaining(self) -> float:
        """Get remaining time on leash effect (0.0 to 1.0)."""
        if self.leash_state == LeashState.NORMAL:
            return 0.0
        return self.leash_effect_timer / self.effect_duration
