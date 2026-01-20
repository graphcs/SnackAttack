"""Sprite sheet loader for character animations."""

import pygame
import os
from typing import Dict, List, Tuple, Optional
from enum import Enum, auto


class AnimationState(Enum):
    """Player animation states."""
    IDLE = auto()      # Standing still (use first frame of run)
    RUN = auto()       # Moving
    EAT = auto()       # Collecting snack


class SpriteSheetLoader:
    """Loads and manages sprite sheet animations."""

    _instance: Optional['SpriteSheetLoader'] = None

    # Sprite sheet configuration
    FRAME_COUNT = 3  # 3 frames per animation

    # Target gameplay sprite size - large for good visibility
    GAMEPLAY_SIZE = (144, 144)
    PORTRAIT_SIZE = (160, 160)
    FOOD_SIZE = (72, 72)  # Snack sprite size - 0.9x of original 80x80

    # Animation timing (in seconds)
    RUN_FRAME_DURATION = 0.1      # 10 FPS for run cycle
    EAT_FRAME_DURATION = 0.12     # Slightly slower for eat
    EAT_ANIMATION_DURATION = 0.4  # Total eat animation time

    # Character ID to sprite sheet name mapping
    CHARACTER_NAMES = {
        'biggie': 'Biggie',
        'prissy': 'Prissy',
        'dash': 'Dash',
        'lobo': 'Lobo',
        'rex': 'Rex',
        'jazzy': 'Jazzy'
    }

    # Snack ID to food image filename mapping
    FOOD_NAMES = {
        'pizza': 'Pizza',
        'bone': 'Bone',
        'broccoli': 'Broccoli',
        'spicy_pepper': 'Chilli',
        'bacon': 'Bacon',
        'steak': 'Steak'
    }

    def __new__(cls) -> 'SpriteSheetLoader':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Cache for loaded animations
        # Key: (character_id, animation_type, facing_right)
        # Value: List[pygame.Surface] (scaled frames)
        self._animation_cache: Dict[Tuple[str, str, bool], List[pygame.Surface]] = {}

        # Cache for portraits
        self._portrait_cache: Dict[str, pygame.Surface] = {}

        # Cache for food sprites
        self._food_cache: Dict[str, pygame.Surface] = {}

        # Base paths
        self._sprite_path = self._get_sprite_path()
        self._profile_path = self._get_profile_path()
        self._food_path = self._get_food_path()

    def _get_sprite_path(self) -> str:
        """Get the path to sprite sheets folder."""
        # Navigate from src/sprites/ to Sprite sheets/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, '..', '..', 'Sprite sheets')

    def _get_profile_path(self) -> str:
        """Get the path to profile images folder."""
        # Profile folder is at: snack_attack/Profile/
        # This file is at: snack_attack/src/sprites/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, '..', '..', 'Profile')

    def _get_food_path(self) -> str:
        """Get the path to food images folder."""
        # Food folder is at: snack_attack/Food/
        # This file is at: snack_attack/src/sprites/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, '..', '..', 'Food')

    def _get_sprite_sheet_filename(self, character_id: str, animation_type: str) -> str:
        """Get the filename for a sprite sheet."""
        name = self.CHARACTER_NAMES.get(character_id, character_id.capitalize())

        if animation_type == 'run':
            return f"{name} run sprite.png"
        elif animation_type == 'eat':
            # Handle inconsistent naming - Biggie lacks 'sprite' in filename
            if character_id == 'biggie':
                return f"{name} eat:attack.png"
            else:
                return f"{name} eat:attack sprite.png"

        return f"{name} run sprite.png"  # Fallback

    def _load_sprite_sheet(self, filepath: str) -> Optional[pygame.Surface]:
        """Load a sprite sheet image."""
        try:
            if os.path.exists(filepath):
                return pygame.image.load(filepath).convert_alpha()
        except pygame.error as e:
            print(f"Error loading sprite sheet {filepath}: {e}")
        return None

    def _extract_frames(self, sheet: pygame.Surface) -> List[pygame.Surface]:
        """Extract individual frames from a sprite sheet."""
        frames = []
        sheet_width = sheet.get_width()
        sheet_height = sheet.get_height()
        frame_width = sheet_width // self.FRAME_COUNT

        for i in range(self.FRAME_COUNT):
            # Create subsurface for each frame
            x = i * frame_width
            frame_rect = pygame.Rect(x, 0, frame_width, sheet_height)
            frame = sheet.subsurface(frame_rect).copy()
            frames.append(frame)
        return frames

    def _scale_frames(self, frames: List[pygame.Surface],
                      target_size: Tuple[int, int]) -> List[pygame.Surface]:
        """Scale frames to target size."""
        return [pygame.transform.smoothscale(f, target_size) for f in frames]

    def _flip_frames(self, frames: List[pygame.Surface]) -> List[pygame.Surface]:
        """Horizontally flip frames for left-facing direction."""
        return [pygame.transform.flip(f, True, False) for f in frames]

    def get_animation_frames(self, character_id: str, animation_type: str,
                             facing_right: bool = True) -> List[pygame.Surface]:
        """
        Get animation frames for a character.

        Args:
            character_id: Character identifier (e.g., 'biggie', 'jazzy')
            animation_type: 'run' or 'eat'
            facing_right: Direction character is facing

        Returns:
            List of pygame Surfaces for the animation frames
        """
        cache_key = (character_id, animation_type, facing_right)

        if cache_key in self._animation_cache:
            return self._animation_cache[cache_key]

        # Load the sprite sheet
        filename = self._get_sprite_sheet_filename(character_id, animation_type)
        filepath = os.path.join(self._sprite_path, filename)
        sheet = self._load_sprite_sheet(filepath)

        if sheet is None:
            # Return empty list if loading fails
            print(f"Warning: Could not load sprite sheet for {character_id} {animation_type}")
            return []

        # Extract and scale frames
        frames = self._extract_frames(sheet)
        frames = self._scale_frames(frames, self.GAMEPLAY_SIZE)

        # Flip if facing left (sprites are drawn facing right)
        if not facing_right:
            frames = self._flip_frames(frames)

        # Cache this direction
        self._animation_cache[cache_key] = frames

        # Also preload and cache the opposite direction
        opposite_key = (character_id, animation_type, not facing_right)
        if opposite_key not in self._animation_cache:
            if facing_right:
                # We have right-facing, create left by flipping
                opposite_frames = self._flip_frames(frames)
            else:
                # We have left-facing (flipped), load original for right
                original_frames = self._extract_frames(sheet)
                original_frames = self._scale_frames(original_frames, self.GAMEPLAY_SIZE)
                opposite_frames = original_frames
            self._animation_cache[opposite_key] = opposite_frames

        return frames

    def get_portrait(self, character_id: str) -> Optional[pygame.Surface]:
        """Get portrait image for character select screen."""
        if character_id in self._portrait_cache:
            return self._portrait_cache[character_id]

        name = self.CHARACTER_NAMES.get(character_id, character_id.capitalize())
        filepath = os.path.join(self._profile_path, f"{name}.png")

        try:
            if os.path.exists(filepath):
                portrait = pygame.image.load(filepath).convert_alpha()
                portrait = pygame.transform.smoothscale(portrait, self.PORTRAIT_SIZE)
                self._portrait_cache[character_id] = portrait
                return portrait
        except pygame.error as e:
            print(f"Error loading portrait for {character_id}: {e}")

        return None

    def get_food_sprite(self, snack_id: str) -> Optional[pygame.Surface]:
        """Get food sprite image for a snack."""
        if snack_id in self._food_cache:
            return self._food_cache[snack_id]

        name = self.FOOD_NAMES.get(snack_id)
        if name is None:
            return None

        filepath = os.path.join(self._food_path, f"{name}.png")

        try:
            if os.path.exists(filepath):
                sprite = pygame.image.load(filepath).convert_alpha()
                sprite = pygame.transform.smoothscale(sprite, self.FOOD_SIZE)
                self._food_cache[snack_id] = sprite
                return sprite
        except pygame.error as e:
            print(f"Error loading food sprite for {snack_id}: {e}")

        return None

    def preload_character(self, character_id: str) -> None:
        """Preload all animations for a character."""
        for animation_type in ['run', 'eat']:
            for facing_right in [True, False]:
                self.get_animation_frames(character_id, animation_type, facing_right)
        self.get_portrait(character_id)

    def preload_all(self) -> None:
        """Preload all character animations."""
        for character_id in self.CHARACTER_NAMES.keys():
            self.preload_character(character_id)

    def clear_cache(self) -> None:
        """Clear all cached sprites."""
        self._animation_cache.clear()
        self._portrait_cache.clear()
        self._food_cache.clear()
