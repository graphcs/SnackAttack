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
    FACE_CAMERA = auto() # Special state: facing camera (chili effect)
    FACE_CAMERA_RED = auto() # Special state: facing camera and red (chili effect)
    CHILI_REACTION = auto() # New chili reaction animation


class SpriteSheetLoader:
    """Loads and manages sprite sheet animations."""

    _instance: Optional['SpriteSheetLoader'] = None

    # Sprite sheet configuration
    FRAME_COUNT = 3  # 3 frames per animation
    CHILI_ANIMATION_FRAME_COUNT = 3  # 3 frames for chili reaction

    # Target gameplay sprite size - large for good visibility
    GAMEPLAY_SIZE = (216, 216)  # 1.5x bigger (was 144x144)
    PORTRAIT_SIZE = (160, 160)
    FOOD_SIZE = (72, 72)  # Snack sprite size - 0.9x of original 80x80

    # Character-specific gameplay sizes (overrides GAMEPLAY_SIZE)
    CHARACTER_SIZES = {
        'prissy': (173, 173),  # 0.8x of 216
    }

    # Custom/generated characters use this size (slightly smaller to match built-ins)
    CUSTOM_CHARACTER_SIZE = (163, 163)

    # Animation timing (in seconds)
    RUN_FRAME_DURATION = 0.1      # 10 FPS for run cycle
    EAT_FRAME_DURATION = 0.12     # Slightly slower for eat
    EAT_ANIMATION_DURATION = 0.4  # Total eat animation time

    # Character ID to sprite sheet name mapping
    CHARACTER_NAMES = {
        'biggie': 'Biggie',
        'prissy': 'Prissy',
        'dash': 'Dash',
        'snowy': 'Snowy',
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
        'steak': 'Steak',
        'red_bull': 'Red Bull'
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

        # Load custom character mappings from config
        self._load_custom_characters()

    def _load_custom_characters(self):
        """Load custom character mappings from characters.json config."""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'config', 'characters.json'
            )
            if os.path.exists(config_path):
                import json
                with open(config_path, 'r') as f:
                    data = json.load(f)
                characters = data.get('characters', [])
                for char_data in characters:
                    char_id = char_data.get('id', '')
                    if char_data.get('custom', False) and char_id and char_id not in self.CHARACTER_NAMES:
                        display_name = char_data.get('display_name', char_id.capitalize())
                        self.CHARACTER_NAMES[char_id] = display_name
                        # Custom characters get a smaller size to match built-ins
                        if char_id not in self.CHARACTER_SIZES:
                            self.CHARACTER_SIZES[char_id] = self.CUSTOM_CHARACTER_SIZE
        except Exception as e:
            print(f"[SpriteSheetLoader] Warning: Could not load custom characters: {e}")

    def register_custom_character(self, character_id: str, display_name: str):
        """Register a custom character for sprite loading at runtime."""
        self.CHARACTER_NAMES[character_id] = display_name
        # Custom characters get a smaller size to match built-ins
        if character_id not in self.CHARACTER_SIZES:
            self.CHARACTER_SIZES[character_id] = self.CUSTOM_CHARACTER_SIZE
        # Clear any cached entries for this character so they reload
        keys_to_remove = [k for k in self._animation_cache if k[0] == character_id]
        for k in keys_to_remove:
            del self._animation_cache[k]
        if character_id in self._portrait_cache:
            del self._portrait_cache[character_id]

    def _get_sprite_path(self) -> str:
        """Get the path to sprite sheets folder."""
        # Navigate from src/sprites/ to Sprite sheets/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, '..', '..', 'Sprite sheets')

    def _get_profile_path(self) -> str:
        """Get the path to profile images folder."""
        # Profile images are in: snack_attack/Profile/
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
        elif animation_type == 'face_camera':
            return f"{name.lower()}_face_camera.png"
        elif animation_type == 'face_camera_red':
            return f"{name.lower()}_face_camera_red.png"
        elif animation_type == 'chili_reaction':
            return f"{name} chili reaction sprite.png"

        return f"{name} run sprite.png"  # Fallback

    def _get_boost_sheet_path(self, character_id: str, animation_type: str) -> Optional[str]:
        """Get path to generated boost-wing sprite sheet for run/eat animations."""
        if animation_type not in ('run', 'eat'):
            return None

        name = self.CHARACTER_NAMES.get(character_id, character_id.capitalize())
        boost_dir = os.path.join(self._sprite_path, 'boost_wings')

        if animation_type == 'run':
            candidates = [
                os.path.join(boost_dir, f"{name} boost run sprite.png"),
                os.path.join(boost_dir, f"{name} run boost sprite.png"),
            ]
        else:
            candidates = [
                os.path.join(boost_dir, f"{name} boost eat:attack sprite.png"),
                os.path.join(boost_dir, f"{name} boost eat:attack.png"),
            ]

        # Custom avatar fallback location
        custom_base = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '..', 'custom_avatars', character_id
        )
        if animation_type == 'run':
            candidates.extend([
                os.path.join(custom_base, 'boost_run_sprite.png'),
                os.path.join(custom_base, 'run_boost_sprite.png'),
            ])
        else:
            candidates.extend([
                os.path.join(custom_base, 'boost_eat_sprite.png'),
                os.path.join(custom_base, 'eat_boost_sprite.png'),
            ])

        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _get_boost_sprite_path(self, character_id: str) -> Optional[str]:
        """Get path to generated single boost-wing sprite image."""
        name = self.CHARACTER_NAMES.get(character_id, character_id.capitalize())
        boost_dir = os.path.join(self._sprite_path, 'boost_wings')

        candidates = [
            os.path.join(boost_dir, f"{name} boost.png"),
            os.path.join(boost_dir, f"{name} winged boost.png"),
        ]

        custom_base = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '..', 'custom_avatars', character_id
        )
        candidates.extend([
            os.path.join(custom_base, 'boost.png'),
            os.path.join(custom_base, 'boost_sprite.png'),
        ])

        for path in candidates:
            if os.path.exists(path):
                return path

        # Flexible filename matching (e.g. "Jazzy boost-Photoroom.png", "Snowy boost-Photoroom (1).png")
        if os.path.isdir(boost_dir):
            normalized_name = name.lower()
            dynamic_matches: List[str] = []
            for filename in os.listdir(boost_dir):
                lower = filename.lower()
                if not lower.endswith('.png'):
                    continue
                if normalized_name not in lower:
                    continue
                if 'boost' not in lower:
                    continue
                dynamic_matches.append(os.path.join(boost_dir, filename))

            if dynamic_matches:
                dynamic_matches.sort()
                return dynamic_matches[0]

        return None

    def _get_front_flight_sprite_path(self, character_id: str) -> Optional[str]:
        """Get path to generated front-facing flight sprite image."""
        name = self.CHARACTER_NAMES.get(character_id, character_id.capitalize())
        candidates = [
            os.path.join(self._sprite_path, f"{name.lower()}_face_camera_flight.png"),
        ]

        custom_base = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '..', 'custom_avatars', character_id
        )
        candidates.extend([
            os.path.join(custom_base, 'face_camera_flight.png'),
            os.path.join(custom_base, 'flight_front.png'),
        ])

        for path in candidates:
            if os.path.exists(path):
                return path

        return None

    def _load_sprite_sheet(self, filepath: str) -> Optional[pygame.Surface]:
        """Load a sprite sheet image."""
        try:
            if os.path.exists(filepath):
                return pygame.image.load(filepath).convert_alpha()
        except pygame.error as e:
            print(f"Error loading sprite sheet {filepath}: {e}")
        return None

    def _extract_frames(self, sheet: pygame.Surface, frame_count: int = None) -> List[pygame.Surface]:
        """Extract individual frames from a sprite sheet."""
        if frame_count is None:
            frame_count = self.FRAME_COUNT

        frames = []
        sheet_width = sheet.get_width()
        sheet_height = sheet.get_height()
        frame_width = sheet_width // frame_count

        for i in range(frame_count):
            # Create subsurface for each frame
            x = i * frame_width
            frame_rect = pygame.Rect(x, 0, frame_width, sheet_height)
            frame = sheet.subsurface(frame_rect).copy()
            frames.append(frame)
        return frames

    @staticmethod
    def _get_content_bounds(surface: pygame.Surface) -> Optional[pygame.Rect]:
        """Get the bounding box of non-transparent pixels in a surface.

        Returns:
            Rect of the content area, or None if entirely transparent.
        """
        mask = pygame.mask.from_surface(surface, threshold=10)
        bounding_rects = mask.get_bounding_rects()
        if not bounding_rects:
            return None
        # Union all bounding rects (there should typically be just one)
        combined = bounding_rects[0]
        for r in bounding_rects[1:]:
            combined.union_ip(r)
        return combined

    def _normalize_custom_frame(self, frame: pygame.Surface,
                                target_size: Tuple[int, int]) -> pygame.Surface:
        """Normalize a custom character frame so its content fill ratio
        matches that of built-in characters (60-75% of the frame).

        If the content fills less than 40% or more than 90% of the frame,
        re-scale content to ~67% fill and re-centre within the target size.

        Args:
            frame: The scaled frame to normalize.
            target_size: The desired output size (w, h).

        Returns:
            Normalized frame surface.
        """
        bounds = self._get_content_bounds(frame)
        if bounds is None:
            return frame

        frame_w, frame_h = target_size
        content_w, content_h = bounds.width, bounds.height

        # Calculate fill ratio (area-based)
        frame_area = frame_w * frame_h
        content_area = content_w * content_h
        fill_ratio = content_area / max(frame_area, 1)

        # Also check dimensional fill (max of width/height fractions)
        dim_fill = max(content_w / max(frame_w, 1), content_h / max(frame_h, 1))

        if 0.40 <= dim_fill <= 0.90:
            # Within acceptable range — just re-centre
            return self._center_content(frame, bounds, target_size)

        # Target dimensional fill of ~67%
        target_fill = 0.67
        scale_factor = target_fill / max(dim_fill, 0.01)

        # Extract the content region
        content = frame.subsurface(bounds).copy()
        new_w = max(1, int(content_w * scale_factor))
        new_h = max(1, int(content_h * scale_factor))

        # Clamp to target size
        new_w = min(new_w, frame_w)
        new_h = min(new_h, frame_h)

        scaled_content = pygame.transform.smoothscale(content, (new_w, new_h))

        # Centre within a new frame
        result = pygame.Surface(target_size, pygame.SRCALPHA)
        paste_x = (frame_w - new_w) // 2
        paste_y = (frame_h - new_h) // 2
        result.blit(scaled_content, (paste_x, paste_y))
        return result

    @staticmethod
    def _center_content(frame: pygame.Surface, bounds: pygame.Rect,
                        target_size: Tuple[int, int]) -> pygame.Surface:
        """Re-centre content within the frame without resizing."""
        frame_w, frame_h = target_size
        content = frame.subsurface(bounds).copy()

        # Check if already roughly centred (within 3px)
        expected_x = (frame_w - bounds.width) // 2
        expected_y = (frame_h - bounds.height) // 2
        if abs(bounds.x - expected_x) <= 3 and abs(bounds.y - expected_y) <= 3:
            return frame

        result = pygame.Surface(target_size, pygame.SRCALPHA)
        paste_x = (frame_w - bounds.width) // 2
        paste_y = (frame_h - bounds.height) // 2
        result.blit(content, (paste_x, paste_y))
        return result

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

        # Extract and scale frames (use character-specific size if available)
        # Check if this is a single-frame animation (face_camera)
        if animation_type in ['face_camera', 'face_camera_red']:
            # Treat entire sheet as one frame
            frames = [sheet]
        elif animation_type == 'chili_reaction':
             # Use specific frame count for chili reaction
            frames = self._extract_frames(sheet, frame_count=self.CHILI_ANIMATION_FRAME_COUNT)
        else:
            # Regular sprite sheet
            frames = self._extract_frames(sheet)
            
        target_size = self.CHARACTER_SIZES.get(character_id, self.GAMEPLAY_SIZE)
        frames = self._scale_frames(frames, target_size)

        # Normalize custom/generated character frames for consistent sizing
        is_custom = character_id not in ('biggie', 'prissy', 'dash', 'snowy', 'rex', 'jazzy')
        if is_custom:
            frames = [self._normalize_custom_frame(f, target_size) for f in frames]

        # Flip if facing left (sprites are drawn facing right)
        # Note: face_camera typically shouldn't be flipped as it faces forward,
        # but if the original art is slightly angled, we might want to. 
        # For now, let's keep flipping logic consistent or skip for face_camera if needed.
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
                if animation_type in ['face_camera', 'face_camera_red']:
                    original_frames = [sheet]
                else:
                    original_frames = self._extract_frames(sheet)
                original_frames = self._scale_frames(original_frames, target_size)
                opposite_frames = original_frames
            self._animation_cache[opposite_key] = opposite_frames

        return frames

    def get_boost_animation_frames(self, character_id: str, animation_type: str,
                                   facing_right: bool = True) -> List[pygame.Surface]:
        """Get boost-wing animation frames for run/eat. Returns [] if not available."""
        cache_key = (character_id, f'boost_{animation_type}', facing_right)
        if cache_key in self._animation_cache:
            return self._animation_cache[cache_key]

        filepath = self._get_boost_sheet_path(character_id, animation_type)
        if not filepath:
            return []

        sheet = self._load_sprite_sheet(filepath)
        if sheet is None:
            return []

        frames = self._extract_frames(sheet)
        target_size = self.CHARACTER_SIZES.get(character_id, self.GAMEPLAY_SIZE)
        frames = self._scale_frames(frames, target_size)

        # Normalize custom character frames for consistent sizing
        is_custom = character_id not in ('biggie', 'prissy', 'dash', 'snowy', 'rex', 'jazzy')
        if is_custom:
            frames = [self._normalize_custom_frame(f, target_size) for f in frames]

        if not facing_right:
            frames = self._flip_frames(frames)

        self._animation_cache[cache_key] = frames

        opposite_key = (character_id, f'boost_{animation_type}', not facing_right)
        if opposite_key not in self._animation_cache:
            self._animation_cache[opposite_key] = self._flip_frames(frames)

        return frames

    def get_boost_sprite(self, character_id: str,
                         facing_right: bool = True) -> Optional[pygame.Surface]:
        """Get single boost-wing sprite image. Returns None if not available."""
        cache_key = (character_id, 'boost_single', facing_right)
        if cache_key in self._animation_cache:
            frames = self._animation_cache[cache_key]
            return frames[0] if frames else None

        filepath = self._get_boost_sprite_path(character_id)
        if not filepath:
            return None

        sprite = self._load_sprite_sheet(filepath)
        if sprite is None:
            return None

        target_size = self.CHARACTER_SIZES.get(character_id, self.GAMEPLAY_SIZE)
        sprite = pygame.transform.smoothscale(sprite, target_size)

        if not facing_right:
            sprite = pygame.transform.flip(sprite, True, False)

        self._animation_cache[cache_key] = [sprite]
        opposite_key = (character_id, 'boost_single', not facing_right)
        if opposite_key not in self._animation_cache:
            self._animation_cache[opposite_key] = [pygame.transform.flip(sprite, True, False)]

        return sprite

    def get_front_flight_sprite(self, character_id: str) -> Optional[pygame.Surface]:
        """Get single front-facing flight sprite image. Returns None if unavailable."""
        cache_key = (character_id, 'front_flight', True)
        if cache_key in self._animation_cache:
            frames = self._animation_cache[cache_key]
            return frames[0] if frames else None

        filepath = self._get_front_flight_sprite_path(character_id)
        if not filepath:
            return None

        sprite = self._load_sprite_sheet(filepath)
        if sprite is None:
            return None

        target_size = self.CHARACTER_SIZES.get(character_id, self.GAMEPLAY_SIZE)
        sprite = pygame.transform.smoothscale(sprite, target_size)
        self._animation_cache[cache_key] = [sprite]
        return sprite

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

    def get_steam_sprite(self) -> Optional[pygame.Surface]:
        """Get the steam effect sprite."""
        # Use cache if available (reusing food cache key 'steam' which won't collide with real food ids)
        if 'steam' in self._food_cache:
            return self._food_cache['steam']
            
        # Try loading specific jazzy steam or generic steam
        filename = "jazzy_steam_ears.png"
        filepath = os.path.join(self._sprite_path, filename) # Check sprite path
        
        if not os.path.exists(filepath):
            # Try food path just in case
             filepath = os.path.join(self._food_path, filename)
        
        try:
            if os.path.exists(filepath):
                sprite = pygame.image.load(filepath).convert_alpha()
                # Scale steam to reasonable size (e.g. 64x64)
                size = (64, 64)
                sprite = pygame.transform.smoothscale(sprite, size)
                self._food_cache['steam'] = sprite
                return sprite
        except pygame.error as e:
            print(f"Error loading steam sprite: {e}")
            
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
                # Use custom sizes for certain foods
                if snack_id == 'red_bull':
                    size = (int(self.FOOD_SIZE[0] * 0.9), int(self.FOOD_SIZE[1] * 0.9))  # 0.95 * 0.95
                elif snack_id == 'pizza':
                    size = (int(self.FOOD_SIZE[0] * 0.95), int(self.FOOD_SIZE[1] * 0.95))
                else:
                    size = self.FOOD_SIZE
                sprite = pygame.transform.smoothscale(sprite, size)
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

    def get_walking_frames(self, character_id: str, facing_right: bool = True,
                           target_size: Tuple[int, int] = None) -> List[pygame.Surface]:
        """
        Get walking animation frames from a grid-based walking sprite sheet.

        The walking sprite sheet is an 8x6 grid. Row 2 (0-indexed) contains
        the side-walking frames facing right.

        Args:
            character_id: Character identifier (e.g., 'jazzy')
            facing_right: Direction character is facing
            target_size: Optional target size for scaling (None = use original frame size)

        Returns:
            List of pygame Surfaces for the walking animation frames
        """
        cache_key = (character_id, 'walking', facing_right, target_size)

        if cache_key in self._animation_cache:
            return self._animation_cache[cache_key]

        # Build the walking sprite sheet filename
        name = self.CHARACTER_NAMES.get(character_id, character_id.capitalize())
        filename = f"{name} walking.png"
        filepath = os.path.join(self._sprite_path, filename)

        sheet = self._load_sprite_sheet(filepath)
        if sheet is None:
            # Cache empty list to avoid repeated warnings
            self._animation_cache[cache_key] = []
            return []

        # Extract frames - different characters have different layouts
        sheet_width = sheet.get_width()
        sheet_height = sheet.get_height()

        # Check if this is a custom character (horizontal strip format)
        is_custom = character_id not in ('jazzy', 'biggie', 'prissy', 'snowy', 'rex', 'dash')

        if is_custom:
            # Custom characters use a simple horizontal strip (auto-detect frame count)
            # If width > 3x height, assume multiple frames side by side
            aspect = sheet_width / max(sheet_height, 1)
            cols = max(1, round(aspect))
            frame_width = sheet_width // cols
            frame_height = sheet_height

            frames = []
            for col in range(cols):
                x = col * frame_width
                frame_rect = pygame.Rect(x, 0, frame_width, frame_height)
                frame = sheet.subsurface(frame_rect).copy()
                frames.append(frame)
        elif character_id == 'prissy':
            # Prissy walking sprite is a 3x2 grid (6 frames total)
            cols = 3
            rows = 2
            frame_width = sheet_width // cols
            frame_height = sheet_height // rows

            # Extract all 6 frames (row by row, left to right)
            frames = []
            for row in range(rows):
                for col in range(cols):
                    x = col * frame_width
                    y = row * frame_height
                    frame_rect = pygame.Rect(x, y, frame_width, frame_height)
                    frame = sheet.subsurface(frame_rect).copy()
                    frames.append(frame)
        elif character_id == 'dash':
            # Dash walking sprite is a horizontal strip with 5 frames
            cols = 5
            frame_width = sheet_width // cols
            frame_height = sheet_height

            frames = []
            for col in range(cols):
                x = col * frame_width
                frame_rect = pygame.Rect(x, 0, frame_width, frame_height)
                frame = sheet.subsurface(frame_rect).copy()
                frames.append(frame)
        else:
            # Other characters use 6x6 grid, row 2 for walking
            cols = 6
            rows = 6
            frame_width = sheet_width // cols
            frame_height = sheet_height // rows
            walk_row = 2

            frames = []
            for col in range(cols):
                x = col * frame_width
                y = walk_row * frame_height
                frame_rect = pygame.Rect(x, y, frame_width, frame_height)
                frame = sheet.subsurface(frame_rect).copy()
                frames.append(frame)

        # Only scale if target_size is specified
        if target_size:
            frames = self._scale_frames(frames, target_size)

        # Flip if facing left
        if not facing_right:
            frames = self._flip_frames(frames)

        # Cache the frames
        self._animation_cache[cache_key] = frames

        # Also cache the opposite direction
        opposite_key = (character_id, 'walking', not facing_right, target_size)
        if opposite_key not in self._animation_cache:
            opposite_frames = self._flip_frames(frames) if facing_right else frames
            self._animation_cache[opposite_key] = opposite_frames

        return frames
