"""AI-controlled player entity."""

import pygame
import random
import math
from typing import Dict, Any, List, Optional, Tuple
from .player import Player
from .snack import Snack


class AIPlayer(Player):
    """An AI-controlled dog character."""

    def __init__(self, character_config: Dict[str, Any], arena_bounds: pygame.Rect,
                 difficulty_config: Dict[str, Any]):
        """
        Initialize an AI player.

        Args:
            character_config: Character configuration from characters.json
            arena_bounds: The playable area boundaries
            difficulty_config: AI difficulty settings
        """
        super().__init__(character_config, arena_bounds, player_num=2)

        # AI settings from config
        self.reaction_delay = difficulty_config.get("reaction_delay_ms", 250) / 1000.0
        self.decision_accuracy = difficulty_config.get("decision_accuracy", 0.8)
        self.pathfinding_efficiency = difficulty_config.get("pathfinding_efficiency", 0.85)
        self.avoids_penalties = difficulty_config.get("avoids_penalties", True)
        self.targets_powerups = difficulty_config.get("targets_powerups", True)

        # AI state
        self.decision_timer = 0.0
        self.current_target: Optional[Snack] = None
        self.target_position: Optional[Tuple[float, float]] = None

    def update(self, dt: float, snacks: List[Snack] = None) -> None:
        """
        Update AI player.

        Args:
            dt: Delta time in seconds
            snacks: List of snacks in the arena
        """
        snacks = snacks or []

        # Update decision timer
        self.decision_timer -= dt

        if self.decision_timer <= 0:
            self.make_decision(snacks)
            self.decision_timer = self.reaction_delay

        # Move toward target
        if self.target_position:
            self.move_toward_target(dt)

        # Update position with velocity
        new_x = self.x + self.velocity_x * dt
        new_y = self.y + self.velocity_y * dt

        # Clamp to arena bounds
        new_x = max(self.arena_bounds.left, min(new_x, self.arena_bounds.right - self.width))
        new_y = max(self.arena_bounds.top, min(new_y, self.arena_bounds.bottom - self.height))

        self.x = new_x
        self.y = new_y

        # Update effects
        self.update_effects(dt)

        # Check if target was collected or despawned
        if self.current_target and not self.current_target.active:
            self.current_target = None
            self.target_position = None

    def make_decision(self, snacks: List[Snack]) -> None:
        """
        Decide which snack to target.

        Args:
            snacks: List of available snacks
        """
        if not snacks:
            self.current_target = None
            self.target_position = None
            # Wander randomly (smaller padding for 320x240 world)
            self.target_position = (
                random.randint(self.arena_bounds.left + 10, self.arena_bounds.right - 10),
                random.randint(self.arena_bounds.top + 10, self.arena_bounds.bottom - 10)
            )
            return

        # Filter active snacks
        active_snacks = [s for s in snacks if s.active]
        if not active_snacks:
            self.current_target = None
            self.target_position = None
            return

        # Score each snack
        scored_snacks = []
        for snack in active_snacks:
            score = self.evaluate_snack(snack)
            scored_snacks.append((snack, score))

        # Sometimes make a suboptimal choice based on accuracy
        if random.random() > self.decision_accuracy:
            # Pick a random snack
            self.current_target = random.choice(active_snacks)
        else:
            # Pick the best snack
            scored_snacks.sort(key=lambda x: x[1], reverse=True)
            self.current_target = scored_snacks[0][0]

        if self.current_target:
            self.target_position = self.current_target.center

    def evaluate_snack(self, snack: Snack) -> float:
        """
        Score a snack's desirability.

        Args:
            snack: Snack to evaluate

        Returns:
            Desirability score (higher is better)
        """
        # Base score is point value
        score = float(snack.point_value)

        # Calculate distance
        dx = snack.x - self.x
        dy = snack.y - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        # Closer snacks are better (distance penalty)
        score -= distance * 0.5

        # Handle penalties (broccoli)
        if snack.point_value < 0 and self.avoids_penalties:
            score -= 300  # Strong penalty

        # Bonus for power-ups
        if snack.effect and self.targets_powerups:
            if snack.effect.get("type") == "speed_boost":
                score += 100
            elif snack.effect.get("type") == "invincibility":
                score += 150

        # Consider time remaining (prioritize snacks about to despawn)
        time_bonus = max(0, 5 - snack.time_alive) * 10
        score += time_bonus

        return score

    def move_toward_target(self, dt: float) -> None:
        """Move toward the current target position."""
        if not self.target_position:
            self.velocity_x = 0
            self.velocity_y = 0
            return

        target_x, target_y = self.target_position
        center_x, center_y = self.center

        dx = target_x - center_x
        dy = target_y - center_y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 5:
            # Close enough
            self.velocity_x = 0
            self.velocity_y = 0
            return

        # Normalize direction
        dx /= distance
        dy /= distance

        # Apply pathfinding inefficiency (add some randomness)
        if random.random() > self.pathfinding_efficiency:
            dx += random.uniform(-0.3, 0.3)
            dy += random.uniform(-0.3, 0.3)
            # Re-normalize
            length = math.sqrt(dx * dx + dy * dy)
            if length > 0:
                dx /= length
                dy /= length

        # Apply chaos effect (flip controls)
        if self.controls_flipped:
            dx = -dx
            dy = -dy

        # Calculate speed
        speed = self.base_move_speed * self.base_speed * self.get_speed_multiplier()

        self.velocity_x = dx * speed
        self.velocity_y = dy * speed

        # Update facing direction
        if dx > 0:
            self.facing_right = True
        elif dx < 0:
            self.facing_right = False

        self.is_moving = True

    def handle_input(self, keys_pressed: Dict[str, bool]) -> None:
        """AI doesn't use keyboard input - override to do nothing."""
        pass

    def reset(self) -> None:
        """Reset AI state for new round."""
        super().reset()
        self.current_target = None
        self.target_position = None
        self.decision_timer = 0.0
