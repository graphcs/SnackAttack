"""Animation controller for managing sprite animations."""

import pygame
from typing import Optional, List
from .sprite_sheet_loader import SpriteSheetLoader, AnimationState


class AnimationController:
    """Controls animation state and frame timing for a character."""

    def __init__(self, character_id: str):
        self.character_id = character_id
        self.loader = SpriteSheetLoader()

        # Current state
        self.state = AnimationState.IDLE
        self.facing_right = True

        # Frame timing
        self.current_frame = 0
        self.frame_timer = 0.0

        # Eat animation tracking
        self.eat_timer = 0.0
        self.eat_duration = SpriteSheetLoader.EAT_ANIMATION_DURATION

        # Frame durations per state
        self.frame_durations = {
            AnimationState.IDLE: 0.0,  # No animation for idle
            AnimationState.RUN: SpriteSheetLoader.RUN_FRAME_DURATION,
            AnimationState.EAT: SpriteSheetLoader.EAT_FRAME_DURATION
        }

        # Preload animations for this character
        self.loader.preload_character(character_id)

    def trigger_eat_animation(self) -> None:
        """Trigger the eat/attack animation."""
        self.state = AnimationState.EAT
        self.eat_timer = self.eat_duration
        self.current_frame = 0
        self.frame_timer = 0.0

    def update(self, dt: float, is_moving: bool, facing_right: bool) -> None:
        """
        Update animation state.

        Args:
            dt: Delta time in seconds
            is_moving: Whether the character is moving
            facing_right: Direction character is facing
        """
        self.facing_right = facing_right

        # Handle eat animation (takes priority)
        if self.state == AnimationState.EAT:
            self.eat_timer -= dt
            if self.eat_timer <= 0:
                # Eat animation finished, return to appropriate state
                self.state = AnimationState.RUN if is_moving else AnimationState.IDLE
                self.current_frame = 0
                self.frame_timer = 0.0
            else:
                # Continue eat animation
                self._advance_frame(dt)
        else:
            # Normal state transitions
            new_state = AnimationState.RUN if is_moving else AnimationState.IDLE
            if new_state != self.state:
                self.state = new_state
                self.current_frame = 0
                self.frame_timer = 0.0

            if self.state == AnimationState.RUN:
                self._advance_frame(dt)

    def _advance_frame(self, dt: float) -> None:
        """Advance to next animation frame if timer elapsed."""
        frame_duration = self.frame_durations.get(self.state, 0.1)
        if frame_duration <= 0:
            return

        self.frame_timer += dt
        if self.frame_timer >= frame_duration:
            self.frame_timer -= frame_duration
            frames = self._get_current_frames()
            if frames:
                self.current_frame = (self.current_frame + 1) % len(frames)

    def _get_current_frames(self) -> List[pygame.Surface]:
        """Get frames for current animation state."""
        animation_type = 'eat' if self.state == AnimationState.EAT else 'run'
        return self.loader.get_animation_frames(
            self.character_id, animation_type, self.facing_right
        )

    def get_current_sprite(self) -> Optional[pygame.Surface]:
        """Get the current animation frame to render."""
        frames = self._get_current_frames()

        if not frames:
            return None

        # For IDLE state, use first frame of run animation
        if self.state == AnimationState.IDLE:
            return frames[0]

        # Ensure frame index is valid
        frame_index = min(self.current_frame, len(frames) - 1)
        return frames[frame_index]

    def reset(self) -> None:
        """Reset animation state."""
        self.state = AnimationState.IDLE
        self.current_frame = 0
        self.frame_timer = 0.0
        self.eat_timer = 0.0
