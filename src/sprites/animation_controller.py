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

        # Special manual animation tracking for cutscenes
        self.manual_override_state: Optional[AnimationState] = None

        # Frame durations per state
        self.frame_durations = {
            AnimationState.IDLE: 0.0,  # No animation for idle
            AnimationState.RUN: SpriteSheetLoader.RUN_FRAME_DURATION,
            AnimationState.EAT: SpriteSheetLoader.EAT_FRAME_DURATION,
            AnimationState.FACE_CAMERA: 0.1,
            AnimationState.FACE_CAMERA_RED: 0.1,
            AnimationState.CHILI_REACTION: 0.5  # Slower animation for emphasis (0.5s per frame * 4 = 2s total)
        }


        # Preload animations for this character
        self.loader.preload_character(character_id)

    def trigger_eat_animation(self) -> None:
        """Trigger the eat/attack animation."""
        # Only trigger eat if not in manual override
        if self.manual_override_state:
            return

        self.state = AnimationState.EAT
        self.eat_timer = self.eat_duration
        self.current_frame = 0
        self.frame_timer = 0.0

    def trigger_chili_animation(self, duration: float) -> None:
        """Trigger the special chili reaction animation."""
        # Set as manual override to lock controls/movement
        self.manual_override_state = AnimationState.CHILI_REACTION
        self.state = AnimationState.CHILI_REACTION
        self.current_frame = 0
        self.frame_timer = 0.0
        
        # Determine frame duration based on total duration and frame count
        frame_count = SpriteSheetLoader.CHILI_ANIMATION_FRAME_COUNT
        self.frame_durations[AnimationState.CHILI_REACTION] = duration / frame_count

    def set_manual_state(self, state: Optional[AnimationState]) -> None:
        """Set a manual animation state that overrides normal updates."""
        self.manual_override_state = state
        if state:
            self.state = state
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

        # Handle manual override (takes priority over everything)
        if self.manual_override_state:
            if self.manual_override_state in [AnimationState.FACE_CAMERA, AnimationState.FACE_CAMERA_RED, AnimationState.CHILI_REACTION]:
                 self._advance_frame(dt)
            return

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
        animation_type = 'run'
        if self.state == AnimationState.EAT:
            animation_type = 'eat'
        elif self.state == AnimationState.FACE_CAMERA:
            animation_type = 'face_camera'
        elif self.state == AnimationState.FACE_CAMERA_RED:
            animation_type = 'face_camera_red'
        elif self.state == AnimationState.CHILI_REACTION:
            animation_type = 'chili_reaction'
            
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
