"""Pixel art sprite creation for Jazzy's Snack Attack - Detailed version."""

import pygame
from typing import Dict, Tuple, Optional


class SpriteCache:
    """Cache for created sprites to avoid recreating them each frame."""

    _instance: Optional['SpriteCache'] = None

    def __new__(cls) -> 'SpriteCache':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._dog_sprites: Dict[str, pygame.Surface] = {}
            cls._instance._dog_portraits: Dict[str, pygame.Surface] = {}
            cls._instance._snack_sprites: Dict[str, pygame.Surface] = {}
            cls._instance._snack_icons: Dict[str, pygame.Surface] = {}
            cls._instance._floor_tiles: Dict[int, pygame.Surface] = {}
            cls._instance._fence_segments: Dict[str, pygame.Surface] = {}
        return cls._instance

    def get_dog_sprite(self, dog_id: str, facing_right: bool = True) -> pygame.Surface:
        """Get or create a dog sprite."""
        key = f"{dog_id}_{'r' if facing_right else 'l'}"
        if key not in self._dog_sprites:
            sprite = create_dog_sprite(dog_id, facing_right)
            self._dog_sprites[key] = sprite
        return self._dog_sprites[key]

    def get_dog_portrait(self, dog_id: str) -> pygame.Surface:
        """Get or create a dog portrait for character select."""
        if dog_id not in self._dog_portraits:
            portrait = create_dog_portrait(dog_id)
            self._dog_portraits[dog_id] = portrait
        return self._dog_portraits[dog_id]

    def get_snack_sprite(self, snack_id: str) -> pygame.Surface:
        """Get or create a snack sprite."""
        if snack_id not in self._snack_sprites:
            sprite = create_snack_sprite(snack_id)
            self._snack_sprites[snack_id] = sprite
        return self._snack_sprites[snack_id]

    def get_snack_icon(self, snack_id: str) -> pygame.Surface:
        """Get or create a small snack icon for HUD."""
        if snack_id not in self._snack_icons:
            icon = create_snack_icon(snack_id)
            self._snack_icons[snack_id] = icon
        return self._snack_icons[snack_id]

    def get_floor_tile(self, variant: int = 0) -> pygame.Surface:
        """Get or create a wooden floor tile."""
        if variant not in self._floor_tiles:
            self._floor_tiles[variant] = create_wood_plank_tile(variant)
        return self._floor_tiles[variant]

    def get_fence_segment(self, segment_type: str) -> pygame.Surface:
        """Get a fence segment (vertical plank)."""
        if segment_type not in self._fence_segments:
            self._fence_segments[segment_type] = create_fence_segment(segment_type)
        return self._fence_segments[segment_type]


# ============== DOG PORTRAITS (80x80) - Full body sitting ==============

def create_dog_portrait(dog_id: str) -> pygame.Surface:
    """Create an 80x80 portrait for character selection showing full sitting dog."""
    surface = pygame.Surface((80, 80), pygame.SRCALPHA)

    if dog_id == "biggie":
        _draw_biggie_portrait(surface)
    elif dog_id == "prissy":
        _draw_prissy_portrait(surface)
    elif dog_id == "dash":
        _draw_dash_portrait(surface)
    elif dog_id == "lobo":
        _draw_lobo_portrait(surface)
    elif dog_id == "rex":
        _draw_rex_portrait(surface)
    elif dog_id == "buster":
        _draw_buster_portrait(surface)
    elif dog_id == "queenie":
        _draw_queenie_portrait(surface)
    else:
        pygame.draw.rect(surface, (200, 200, 200), (10, 10, 60, 60))

    return surface


def _draw_biggie_portrait(surface: pygame.Surface) -> None:
    """Draw Biggie the Bulldog - stocky brown bulldog, sitting pose."""
    # Colors - rich brown tones
    body_dark = (120, 75, 35)
    body_main = (160, 105, 55)
    body_light = (195, 145, 95)
    body_highlight = (220, 180, 130)
    nose_color = (45, 35, 35)
    eye_white = (255, 255, 255)
    eye_pupil = (35, 25, 25)
    tongue = (220, 120, 130)

    # Back body (sitting, rounded)
    pygame.draw.ellipse(surface, body_main, (15, 45, 50, 35))
    pygame.draw.ellipse(surface, body_light, (20, 48, 40, 25))

    # Front legs/paws (sitting in front)
    pygame.draw.ellipse(surface, body_main, (18, 62, 18, 18))  # Left paw
    pygame.draw.ellipse(surface, body_main, (44, 62, 18, 18))  # Right paw
    pygame.draw.ellipse(surface, body_light, (20, 64, 14, 12))  # Left highlight
    pygame.draw.ellipse(surface, body_light, (46, 64, 14, 12))  # Right highlight

    # Chest (front)
    pygame.draw.ellipse(surface, body_light, (25, 40, 30, 30))
    pygame.draw.ellipse(surface, body_highlight, (30, 45, 20, 18))

    # Head (large, square-ish bulldog head)
    pygame.draw.ellipse(surface, body_main, (18, 8, 44, 40))  # Main head
    pygame.draw.ellipse(surface, body_light, (22, 14, 36, 28))  # Face

    # Jowls/cheeks (signature bulldog)
    pygame.draw.ellipse(surface, body_light, (12, 28, 18, 16))  # Left jowl
    pygame.draw.ellipse(surface, body_light, (50, 28, 18, 16))  # Right jowl
    pygame.draw.ellipse(surface, body_highlight, (14, 30, 12, 10))
    pygame.draw.ellipse(surface, body_highlight, (52, 30, 12, 10))

    # Ears (small, folded bulldog ears)
    pygame.draw.ellipse(surface, body_dark, (16, 6, 12, 14))  # Left ear
    pygame.draw.ellipse(surface, body_dark, (52, 6, 12, 14))  # Right ear

    # Wrinkles on forehead
    pygame.draw.arc(surface, body_dark, (28, 16, 24, 8), 3.14, 6.28, 2)
    pygame.draw.arc(surface, body_dark, (30, 20, 20, 6), 3.14, 6.28, 2)

    # Eyes (wide-set bulldog eyes)
    pygame.draw.ellipse(surface, eye_white, (24, 24, 12, 10))  # Left eye white
    pygame.draw.ellipse(surface, eye_white, (44, 24, 12, 10))  # Right eye white
    pygame.draw.circle(surface, eye_pupil, (31, 28), 4)  # Left pupil
    pygame.draw.circle(surface, eye_pupil, (51, 28), 4)  # Right pupil
    pygame.draw.circle(surface, (255, 255, 255), (29, 26), 2)  # Left highlight
    pygame.draw.circle(surface, (255, 255, 255), (49, 26), 2)  # Right highlight

    # Nose (large bulldog nose)
    pygame.draw.ellipse(surface, nose_color, (32, 36, 16, 10))
    pygame.draw.ellipse(surface, (60, 50, 50), (34, 38, 5, 4))  # Nostril
    pygame.draw.ellipse(surface, (60, 50, 50), (41, 38, 5, 4))  # Nostril

    # Mouth/tongue (happy panting)
    pygame.draw.ellipse(surface, tongue, (35, 44, 10, 8))


def _draw_prissy_portrait(surface: pygame.Surface) -> None:
    """Draw Prissy the Poodle - pink fluffy poodle, sitting pose."""
    # Colors - pink poodle tones
    fur_dark = (220, 150, 170)
    fur_main = (255, 190, 210)
    fur_light = (255, 220, 235)
    fur_highlight = (255, 240, 245)
    nose_color = (60, 45, 50)
    eye_color = (50, 40, 45)
    bow_color = (255, 100, 150)

    # Back pom (sitting body)
    pygame.draw.circle(surface, fur_main, (40, 58), 20)
    pygame.draw.circle(surface, fur_light, (40, 55), 15)
    pygame.draw.circle(surface, fur_highlight, (38, 52), 8)

    # Leg poms
    pygame.draw.circle(surface, fur_main, (22, 70), 10)  # Left leg
    pygame.draw.circle(surface, fur_main, (58, 70), 10)  # Right leg
    pygame.draw.circle(surface, fur_light, (22, 68), 7)
    pygame.draw.circle(surface, fur_light, (58, 68), 7)

    # Front paws with pom-poms
    pygame.draw.circle(surface, fur_main, (28, 65), 8)
    pygame.draw.circle(surface, fur_main, (52, 65), 8)
    pygame.draw.circle(surface, fur_light, (28, 63), 5)
    pygame.draw.circle(surface, fur_light, (52, 63), 5)

    # Neck pom
    pygame.draw.circle(surface, fur_main, (40, 40), 14)
    pygame.draw.circle(surface, fur_light, (40, 38), 10)

    # Head (round poodle head with top pom)
    pygame.draw.circle(surface, fur_main, (40, 24), 16)
    pygame.draw.circle(surface, fur_light, (40, 22), 12)

    # Top pom (signature poodle puff)
    pygame.draw.circle(surface, fur_main, (40, 6), 12)
    pygame.draw.circle(surface, fur_light, (40, 4), 9)
    pygame.draw.circle(surface, fur_highlight, (38, 2), 5)

    # Ear poms
    pygame.draw.circle(surface, fur_main, (18, 22), 10)  # Left ear
    pygame.draw.circle(surface, fur_main, (62, 22), 10)  # Right ear
    pygame.draw.circle(surface, fur_light, (18, 20), 7)
    pygame.draw.circle(surface, fur_light, (62, 20), 7)

    # Pretty bow
    pygame.draw.ellipse(surface, bow_color, (32, 8, 8, 6))  # Left bow
    pygame.draw.ellipse(surface, bow_color, (40, 8, 8, 6))  # Right bow
    pygame.draw.circle(surface, (255, 50, 100), (40, 10), 3)  # Center

    # Face
    pygame.draw.ellipse(surface, fur_highlight, (32, 22, 16, 14))

    # Eyes (elegant poodle eyes)
    pygame.draw.ellipse(surface, eye_color, (32, 22, 8, 10))  # Left eye
    pygame.draw.ellipse(surface, eye_color, (40, 22, 8, 10))  # Right eye
    pygame.draw.circle(surface, (255, 255, 255), (35, 24), 2)  # Left highlight
    pygame.draw.circle(surface, (255, 255, 255), (43, 24), 2)  # Right highlight

    # Nose
    pygame.draw.ellipse(surface, nose_color, (36, 32, 8, 6))


def _draw_dash_portrait(surface: pygame.Surface) -> None:
    """Draw Dash the Chihuahua - small black/tan chihuahua with huge ears."""
    # Colors
    body_black = (45, 35, 30)
    body_tan = (210, 165, 110)
    body_tan_light = (235, 200, 150)
    ear_pink = (255, 180, 170)
    eye_white = (255, 255, 255)
    eye_pupil = (25, 20, 20)
    nose_color = (30, 25, 25)

    # Small body (sitting)
    pygame.draw.ellipse(surface, body_black, (25, 50, 30, 25))
    pygame.draw.ellipse(surface, body_tan, (28, 58, 24, 18))  # Tan belly

    # Small front paws
    pygame.draw.ellipse(surface, body_tan, (26, 68, 10, 10))  # Left paw
    pygame.draw.ellipse(surface, body_tan, (44, 68, 10, 10))  # Right paw
    pygame.draw.ellipse(surface, body_tan_light, (28, 70, 6, 6))
    pygame.draw.ellipse(surface, body_tan_light, (46, 70, 6, 6))

    # Chest
    pygame.draw.ellipse(surface, body_tan, (30, 45, 20, 20))
    pygame.draw.ellipse(surface, body_tan_light, (33, 48, 14, 14))

    # Head (apple-shaped chihuahua head)
    pygame.draw.circle(surface, body_black, (40, 32), 18)
    pygame.draw.ellipse(surface, body_tan, (30, 35, 20, 16))  # Tan muzzle area
    pygame.draw.ellipse(surface, body_tan_light, (33, 38, 14, 10))

    # HUGE ears (signature chihuahua)
    # Left ear
    pygame.draw.polygon(surface, body_black, [(22, 32), (5, 2), (35, 22)])
    pygame.draw.polygon(surface, ear_pink, [(24, 28), (12, 10), (32, 22)])
    # Right ear
    pygame.draw.polygon(surface, body_black, [(58, 32), (75, 2), (45, 22)])
    pygame.draw.polygon(surface, ear_pink, [(56, 28), (68, 10), (48, 22)])

    # Big eyes (chihuahuas have big eyes)
    pygame.draw.circle(surface, eye_white, (33, 30), 8)  # Left eye
    pygame.draw.circle(surface, eye_white, (47, 30), 8)  # Right eye
    pygame.draw.circle(surface, eye_pupil, (35, 31), 5)  # Left pupil
    pygame.draw.circle(surface, eye_pupil, (49, 31), 5)  # Right pupil
    pygame.draw.circle(surface, (255, 255, 255), (33, 28), 3)  # Left highlight
    pygame.draw.circle(surface, (255, 255, 255), (47, 28), 3)  # Right highlight

    # Small nose
    pygame.draw.ellipse(surface, nose_color, (37, 42, 6, 5))

    # Thin tail (curled up)
    pygame.draw.arc(surface, body_black, (50, 45, 20, 20), 0, 3.14, 3)


def _draw_lobo_portrait(surface: pygame.Surface) -> None:
    """Draw Lobo the Husky - gray/white husky with blue eyes."""
    # Colors
    fur_gray = (140, 150, 165)
    fur_gray_dark = (100, 110, 125)
    fur_white = (250, 252, 255)
    fur_cream = (240, 235, 225)
    eye_blue = (80, 170, 240)
    nose_color = (45, 45, 55)

    # Body (sitting)
    pygame.draw.ellipse(surface, fur_gray, (18, 45, 44, 32))
    pygame.draw.ellipse(surface, fur_white, (26, 52, 28, 22))  # White belly

    # Front paws
    pygame.draw.ellipse(surface, fur_gray, (20, 65, 16, 14))  # Left paw
    pygame.draw.ellipse(surface, fur_gray, (44, 65, 16, 14))  # Right paw
    pygame.draw.ellipse(surface, fur_white, (22, 70, 12, 8))  # White paw tips
    pygame.draw.ellipse(surface, fur_white, (46, 70, 12, 8))

    # Chest (white chest patch)
    pygame.draw.ellipse(surface, fur_white, (28, 40, 24, 24))
    pygame.draw.ellipse(surface, fur_cream, (32, 44, 16, 16))

    # Head
    pygame.draw.ellipse(surface, fur_gray, (20, 8, 40, 38))  # Main head

    # White face mask (signature husky marking)
    pygame.draw.ellipse(surface, fur_white, (28, 20, 24, 24))
    # Gray on top
    pygame.draw.ellipse(surface, fur_gray, (26, 8, 28, 20))

    # Ears (pointed husky ears)
    pygame.draw.polygon(surface, fur_gray, [(22, 18), (14, -2), (34, 12)])  # Left
    pygame.draw.polygon(surface, fur_gray, [(58, 18), (66, -2), (46, 12)])  # Right
    pygame.draw.polygon(surface, fur_gray_dark, [(24, 14), (18, 4), (30, 12)])
    pygame.draw.polygon(surface, fur_gray_dark, [(56, 14), (62, 4), (50, 12)])

    # Blue eyes (signature husky!)
    pygame.draw.circle(surface, (255, 255, 255), (32, 28), 7)
    pygame.draw.circle(surface, (255, 255, 255), (48, 28), 7)
    pygame.draw.circle(surface, eye_blue, (33, 29), 5)
    pygame.draw.circle(surface, eye_blue, (49, 29), 5)
    pygame.draw.circle(surface, (40, 100, 180), (34, 30), 3)  # Darker center
    pygame.draw.circle(surface, (40, 100, 180), (50, 30), 3)
    pygame.draw.circle(surface, (255, 255, 255), (31, 27), 2)  # Highlight
    pygame.draw.circle(surface, (255, 255, 255), (47, 27), 2)

    # Nose
    pygame.draw.ellipse(surface, nose_color, (35, 38, 10, 8))

    # Fluffy tail (curled)
    pygame.draw.ellipse(surface, fur_gray, (55, 42, 18, 14))
    pygame.draw.ellipse(surface, fur_white, (58, 44, 12, 8))


def _draw_rex_portrait(surface: pygame.Surface) -> None:
    """Draw Rex the Dachshund - brown dachshund with long body."""
    # Colors - warm brown tones
    body_main = (165, 100, 50)
    body_dark = (130, 75, 35)
    body_light = (200, 140, 85)
    body_highlight = (225, 175, 120)
    nose_color = (40, 30, 30)
    eye_color = (50, 40, 35)

    # Long body (signature dachshund - horizontal even when sitting)
    pygame.draw.ellipse(surface, body_main, (10, 48, 60, 24))
    pygame.draw.ellipse(surface, body_light, (18, 52, 44, 16))

    # Short legs (very short dachshund legs)
    pygame.draw.ellipse(surface, body_dark, (15, 66, 12, 12))  # Left front
    pygame.draw.ellipse(surface, body_dark, (53, 66, 12, 12))  # Right front
    pygame.draw.ellipse(surface, body_main, (17, 68, 8, 8))
    pygame.draw.ellipse(surface, body_main, (55, 68, 8, 8))

    # Back legs visible
    pygame.draw.ellipse(surface, body_dark, (5, 58, 14, 14))  # Left back
    pygame.draw.ellipse(surface, body_dark, (61, 58, 14, 14))  # Right back

    # Chest (front)
    pygame.draw.ellipse(surface, body_light, (52, 40, 20, 22))
    pygame.draw.ellipse(surface, body_highlight, (55, 44, 14, 14))

    # Long snout head (dachshund has long nose)
    pygame.draw.ellipse(surface, body_main, (48, 14, 28, 32))  # Main head
    pygame.draw.ellipse(surface, body_light, (52, 20, 20, 22))

    # Long snout
    pygame.draw.ellipse(surface, body_main, (62, 28, 18, 14))
    pygame.draw.ellipse(surface, body_light, (64, 30, 14, 10))

    # Floppy ears (long dachshund ears)
    pygame.draw.ellipse(surface, body_dark, (44, 18, 14, 28))  # Left ear
    pygame.draw.ellipse(surface, body_main, (46, 22, 10, 20))

    # Eye
    pygame.draw.circle(surface, (255, 255, 255), (58, 26), 6)
    pygame.draw.circle(surface, eye_color, (59, 27), 4)
    pygame.draw.circle(surface, (255, 255, 255), (57, 24), 2)

    # Nose (at end of snout)
    pygame.draw.ellipse(surface, nose_color, (72, 32, 8, 7))

    # Tail (thin, slightly raised)
    pygame.draw.arc(surface, body_main, (2, 40, 20, 25), 1.5, 4.5, 4)


def _draw_buster_portrait(surface: pygame.Surface) -> None:
    """Draw Buster the Beagle - tricolor beagle with floppy ears."""
    # Colors - tricolor (white, tan, black)
    white = (255, 252, 248)
    tan = (210, 160, 100)
    tan_light = (235, 195, 145)
    black = (45, 40, 38)
    nose_color = (35, 30, 30)
    eye_color = (55, 45, 40)

    # Body (sitting)
    pygame.draw.ellipse(surface, white, (20, 48, 40, 28))
    pygame.draw.ellipse(surface, tan, (45, 50, 18, 20))  # Tan patch on side

    # Front paws
    pygame.draw.ellipse(surface, white, (22, 66, 14, 12))  # Left paw
    pygame.draw.ellipse(surface, white, (44, 66, 14, 12))  # Right paw

    # Chest (white)
    pygame.draw.ellipse(surface, white, (28, 38, 24, 26))

    # Head
    pygame.draw.ellipse(surface, white, (24, 12, 32, 34))  # Main head
    pygame.draw.ellipse(surface, tan, (24, 12, 32, 18))  # Tan on top
    pygame.draw.ellipse(surface, black, (30, 12, 20, 10))  # Black cap

    # Long floppy ears (signature beagle)
    pygame.draw.ellipse(surface, tan, (8, 22, 20, 40))  # Left ear
    pygame.draw.ellipse(surface, tan, (52, 22, 20, 40))  # Right ear
    pygame.draw.ellipse(surface, tan_light, (12, 28, 12, 28))
    pygame.draw.ellipse(surface, tan_light, (56, 28, 12, 28))

    # White blaze down face
    pygame.draw.ellipse(surface, white, (34, 20, 12, 22))

    # Eyes (soulful beagle eyes)
    pygame.draw.circle(surface, (255, 255, 255), (32, 28), 6)
    pygame.draw.circle(surface, (255, 255, 255), (48, 28), 6)
    pygame.draw.circle(surface, eye_color, (33, 29), 4)
    pygame.draw.circle(surface, eye_color, (49, 29), 4)
    pygame.draw.circle(surface, (255, 255, 255), (31, 26), 2)
    pygame.draw.circle(surface, (255, 255, 255), (47, 26), 2)

    # Nose
    pygame.draw.ellipse(surface, nose_color, (36, 38, 8, 6))

    # White tail tip (beagle signature)
    pygame.draw.ellipse(surface, tan, (55, 48, 14, 10))
    pygame.draw.ellipse(surface, white, (62, 46, 10, 8))


def _draw_queenie_portrait(surface: pygame.Surface) -> None:
    """Draw Queenie the Corgi - orange/white corgi with big ears."""
    # Colors
    orange = (235, 170, 70)
    orange_dark = (200, 135, 45)
    orange_light = (250, 200, 120)
    white = (255, 252, 248)
    cream = (255, 245, 235)
    nose_color = (40, 35, 35)
    eye_color = (50, 42, 38)

    # Body (long corgi body, sitting)
    pygame.draw.ellipse(surface, orange, (12, 48, 56, 26))
    pygame.draw.ellipse(surface, white, (24, 56, 32, 16))  # White belly

    # Short stubby legs (signature corgi)
    pygame.draw.ellipse(surface, orange, (18, 66, 12, 14))  # Left front
    pygame.draw.ellipse(surface, orange, (50, 66, 12, 14))  # Right front
    pygame.draw.ellipse(surface, white, (19, 72, 10, 8))  # White paws
    pygame.draw.ellipse(surface, white, (51, 72, 10, 8))

    # Fluffy butt (no tail - corgis!)
    pygame.draw.circle(surface, orange, (12, 54), 12)
    pygame.draw.circle(surface, orange_light, (10, 52), 8)

    # Chest (white bib)
    pygame.draw.ellipse(surface, white, (32, 40, 24, 24))
    pygame.draw.ellipse(surface, cream, (36, 44, 16, 16))

    # Head (fox-like corgi head)
    pygame.draw.ellipse(surface, orange, (24, 10, 36, 36))
    pygame.draw.ellipse(surface, white, (32, 26, 20, 18))  # White blaze

    # Big pointed ears (signature corgi ears)
    pygame.draw.polygon(surface, orange, [(26, 20), (14, -4), (40, 14)])  # Left
    pygame.draw.polygon(surface, orange, [(58, 20), (70, -4), (44, 14)])  # Right
    pygame.draw.polygon(surface, orange_dark, [(28, 16), (20, 4), (36, 14)])
    pygame.draw.polygon(surface, orange_dark, [(56, 16), (64, 4), (48, 14)])

    # Smiling corgi face
    pygame.draw.ellipse(surface, orange_light, (34, 18, 16, 12))

    # Eyes (happy corgi eyes)
    pygame.draw.circle(surface, (255, 255, 255), (34, 26), 6)
    pygame.draw.circle(surface, (255, 255, 255), (50, 26), 6)
    pygame.draw.circle(surface, eye_color, (35, 27), 4)
    pygame.draw.circle(surface, eye_color, (51, 27), 4)
    pygame.draw.circle(surface, (255, 255, 255), (33, 24), 2)
    pygame.draw.circle(surface, (255, 255, 255), (49, 24), 2)

    # Nose
    pygame.draw.ellipse(surface, nose_color, (38, 34, 8, 6))

    # Happy smile
    pygame.draw.arc(surface, (180, 100, 110), (36, 36, 12, 8), 3.14, 6.28, 2)


# ============== DOG GAMEPLAY SPRITES (64x64 for 960x720 display) ==============

def create_dog_sprite(dog_id: str, facing_right: bool = True) -> pygame.Surface:
    """Create a 64x64 pixel art sprite for a dog character (for 960x720 display)."""
    # Create at 48x48 then scale up to 64x64 for detailed retro look
    large_surface = pygame.Surface((48, 48), pygame.SRCALPHA)

    if dog_id == "biggie":
        _draw_biggie_sprite(large_surface, facing_right)
    elif dog_id == "prissy":
        _draw_prissy_sprite(large_surface, facing_right)
    elif dog_id == "dash":
        _draw_dash_sprite(large_surface, facing_right)
    elif dog_id == "lobo":
        _draw_lobo_sprite(large_surface, facing_right)
    elif dog_id == "rex":
        _draw_rex_sprite(large_surface, facing_right)
    elif dog_id == "buster":
        _draw_buster_sprite(large_surface, facing_right)
    elif dog_id == "queenie":
        _draw_queenie_sprite(large_surface, facing_right)
    else:
        pygame.draw.rect(large_surface, (200, 200, 200), (8, 8, 32, 32))

    # Scale up to 64x64 for full resolution display
    return pygame.transform.scale(large_surface, (64, 64))


def _draw_biggie_sprite(surface: pygame.Surface, facing_right: bool) -> None:
    """Draw Biggie gameplay sprite - stocky bulldog walking."""
    body_dark = (120, 75, 35)
    body_main = (160, 105, 55)
    body_light = (195, 145, 95)
    nose = (45, 35, 35)
    eye = (35, 25, 25)

    # Flip coordinates if facing left
    def fx(x):
        return x if facing_right else 48 - x

    # Body (stocky)
    pygame.draw.ellipse(surface, body_main, (fx(8) - (0 if facing_right else 28), 20, 28, 20))
    pygame.draw.ellipse(surface, body_light, (fx(12) - (0 if facing_right else 20), 24, 20, 12))

    # Legs
    pygame.draw.rect(surface, body_dark, (fx(10) - (0 if facing_right else 6), 36, 6, 12))
    pygame.draw.rect(surface, body_dark, (fx(28) - (0 if facing_right else 6), 36, 6, 12))

    # Head
    pygame.draw.ellipse(surface, body_main, (fx(24) - (0 if facing_right else 20), 6, 20, 22))
    pygame.draw.ellipse(surface, body_light, (fx(26) - (0 if facing_right else 14), 12, 14, 12))

    # Jowls
    pygame.draw.ellipse(surface, body_light, (fx(22) - (0 if facing_right else 8), 18, 8, 10))
    pygame.draw.ellipse(surface, body_light, (fx(36) - (0 if facing_right else 8), 18, 8, 10))

    # Ears
    pygame.draw.ellipse(surface, body_dark, (fx(24) - (0 if facing_right else 6), 4, 6, 8))
    pygame.draw.ellipse(surface, body_dark, (fx(38) - (0 if facing_right else 6), 4, 6, 8))

    # Eye
    ex = fx(34) - (0 if facing_right else 6)
    pygame.draw.circle(surface, (255, 255, 255), (ex, 14), 4)
    pygame.draw.circle(surface, eye, (ex + (1 if facing_right else -1), 14), 2)

    # Nose
    pygame.draw.ellipse(surface, nose, (fx(32) - (0 if facing_right else 6), 20, 6, 4))

    # Tail
    tx = fx(6) - (0 if facing_right else 6)
    pygame.draw.ellipse(surface, body_main, (tx, 22, 6, 6))


def _draw_prissy_sprite(surface: pygame.Surface, facing_right: bool) -> None:
    """Draw Prissy gameplay sprite - fluffy pink poodle."""
    fur_main = (255, 190, 210)
    fur_light = (255, 220, 235)
    fur_dark = (220, 150, 170)
    nose = (60, 45, 50)
    eye = (50, 40, 45)

    def fx(x):
        return x if facing_right else 48 - x

    # Body pom
    pygame.draw.circle(surface, fur_main, (fx(24), 30), 12)
    pygame.draw.circle(surface, fur_light, (fx(24), 28), 8)

    # Legs
    pygame.draw.rect(surface, fur_dark, (fx(18) - (0 if facing_right else 4), 38, 4, 10))
    pygame.draw.rect(surface, fur_dark, (fx(28) - (0 if facing_right else 4), 38, 4, 10))

    # Leg poms
    pygame.draw.circle(surface, fur_main, (fx(20), 44), 4)
    pygame.draw.circle(surface, fur_main, (fx(30), 44), 4)

    # Head pom
    pygame.draw.circle(surface, fur_main, (fx(30), 16), 10)
    pygame.draw.circle(surface, fur_light, (fx(30), 14), 7)

    # Top pom
    pygame.draw.circle(surface, fur_main, (fx(30), 4), 6)
    pygame.draw.circle(surface, fur_light, (fx(30), 3), 4)

    # Ear poms
    pygame.draw.circle(surface, fur_main, (fx(22), 14), 5)
    pygame.draw.circle(surface, fur_main, (fx(40), 14), 5)

    # Eye
    ex = fx(33) - (0 if facing_right else 3)
    pygame.draw.circle(surface, eye, (ex, 16), 3)
    pygame.draw.circle(surface, (255, 255, 255), (ex - 1, 15), 1)

    # Nose
    pygame.draw.ellipse(surface, nose, (fx(30) - 2, 20, 4, 3))

    # Tail pom
    pygame.draw.circle(surface, fur_main, (fx(10), 28), 5)


def _draw_dash_sprite(surface: pygame.Surface, facing_right: bool) -> None:
    """Draw Dash gameplay sprite - small chihuahua with big ears."""
    body_black = (45, 35, 30)
    body_tan = (210, 165, 110)
    ear_pink = (255, 180, 170)
    eye = (25, 20, 20)

    def fx(x):
        return x if facing_right else 48 - x

    # Small body
    pygame.draw.ellipse(surface, body_black, (fx(14) - (0 if facing_right else 18), 26, 18, 14))
    pygame.draw.ellipse(surface, body_tan, (fx(16) - (0 if facing_right else 14), 32, 14, 8))

    # Thin legs
    pygame.draw.rect(surface, body_black, (fx(16) - (0 if facing_right else 3), 38, 3, 10))
    pygame.draw.rect(surface, body_black, (fx(28) - (0 if facing_right else 3), 38, 3, 10))

    # Head
    pygame.draw.circle(surface, body_black, (fx(30), 20), 10)
    pygame.draw.ellipse(surface, body_tan, (fx(26) - (0 if facing_right else 10), 24, 10, 8))

    # Big ears
    if facing_right:
        pygame.draw.polygon(surface, body_black, [(26, 18), (16, 0), (32, 14)])
        pygame.draw.polygon(surface, body_black, [(38, 18), (48, 0), (36, 14)])
        pygame.draw.polygon(surface, ear_pink, [(28, 16), (22, 6), (32, 14)])
        pygame.draw.polygon(surface, ear_pink, [(36, 16), (42, 6), (36, 14)])
    else:
        pygame.draw.polygon(surface, body_black, [(22, 18), (32, 0), (16, 14)])
        pygame.draw.polygon(surface, body_black, [(10, 18), (0, 0), (12, 14)])
        pygame.draw.polygon(surface, ear_pink, [(20, 16), (26, 6), (16, 14)])
        pygame.draw.polygon(surface, ear_pink, [(12, 16), (6, 6), (12, 14)])

    # Big eye
    ex = fx(33) - (0 if facing_right else 5)
    pygame.draw.circle(surface, (255, 255, 255), (ex, 18), 5)
    pygame.draw.circle(surface, eye, (ex + (1 if facing_right else -1), 19), 3)

    # Nose
    pygame.draw.ellipse(surface, (30, 25, 25), (fx(30) - 2, 26, 4, 3))

    # Thin tail
    if facing_right:
        pygame.draw.arc(surface, body_black, (6, 22, 12, 12), 0, 3.14, 2)
    else:
        pygame.draw.arc(surface, body_black, (30, 22, 12, 12), 0, 3.14, 2)


def _draw_lobo_sprite(surface: pygame.Surface, facing_right: bool) -> None:
    """Draw Lobo gameplay sprite - gray/white husky."""
    fur_gray = (140, 150, 165)
    fur_white = (250, 252, 255)
    fur_dark = (100, 110, 125)
    eye_blue = (80, 170, 240)
    nose = (45, 45, 55)

    def fx(x):
        return x if facing_right else 48 - x

    # Body
    pygame.draw.ellipse(surface, fur_gray, (fx(8) - (0 if facing_right else 26), 22, 26, 18))
    pygame.draw.ellipse(surface, fur_white, (fx(12) - (0 if facing_right else 18), 28, 18, 10))

    # Legs
    pygame.draw.rect(surface, fur_gray, (fx(12) - (0 if facing_right else 5), 36, 5, 12))
    pygame.draw.rect(surface, fur_gray, (fx(28) - (0 if facing_right else 5), 36, 5, 12))
    pygame.draw.rect(surface, fur_white, (fx(12) - (0 if facing_right else 5), 42, 5, 6))
    pygame.draw.rect(surface, fur_white, (fx(28) - (0 if facing_right else 5), 42, 5, 6))

    # Head
    pygame.draw.ellipse(surface, fur_gray, (fx(24) - (0 if facing_right else 18), 6, 18, 22))
    pygame.draw.ellipse(surface, fur_white, (fx(28) - (0 if facing_right else 12), 14, 12, 12))

    # Ears
    if facing_right:
        pygame.draw.polygon(surface, fur_gray, [(26, 12), (22, 0), (32, 8)])
        pygame.draw.polygon(surface, fur_gray, [(38, 12), (42, 0), (36, 8)])
    else:
        pygame.draw.polygon(surface, fur_gray, [(22, 12), (26, 0), (16, 8)])
        pygame.draw.polygon(surface, fur_gray, [(10, 12), (6, 0), (12, 8)])

    # Blue eye
    ex = fx(34) - (0 if facing_right else 6)
    pygame.draw.circle(surface, (255, 255, 255), (ex, 16), 4)
    pygame.draw.circle(surface, eye_blue, (ex, 17), 3)
    pygame.draw.circle(surface, (255, 255, 255), (ex - 1, 15), 1)

    # Nose
    pygame.draw.ellipse(surface, nose, (fx(32) - (0 if facing_right else 6), 22, 6, 4))

    # Fluffy tail
    pygame.draw.ellipse(surface, fur_gray, (fx(4) - (0 if facing_right else 8), 20, 8, 10))
    pygame.draw.ellipse(surface, fur_white, (fx(5) - (0 if facing_right else 5), 22, 5, 6))


def _draw_rex_sprite(surface: pygame.Surface, facing_right: bool) -> None:
    """Draw Rex gameplay sprite - dachshund with long body."""
    body_main = (165, 100, 50)
    body_dark = (130, 75, 35)
    body_light = (200, 140, 85)
    nose = (40, 30, 30)
    eye = (50, 40, 35)

    def fx(x):
        return x if facing_right else 48 - x

    # Long body (dachshund)
    pygame.draw.ellipse(surface, body_main, (fx(4) - (0 if facing_right else 36), 24, 36, 16))
    pygame.draw.ellipse(surface, body_light, (fx(10) - (0 if facing_right else 28), 28, 28, 10))

    # Short legs
    pygame.draw.rect(surface, body_dark, (fx(10) - (0 if facing_right else 4), 36, 4, 12))
    pygame.draw.rect(surface, body_dark, (fx(32) - (0 if facing_right else 4), 36, 4, 12))

    # Head with long snout
    pygame.draw.ellipse(surface, body_main, (fx(30) - (0 if facing_right else 16), 14, 16, 18))
    pygame.draw.ellipse(surface, body_main, (fx(38) - (0 if facing_right else 12), 20, 12, 10))
    pygame.draw.ellipse(surface, body_light, (fx(40) - (0 if facing_right else 8), 22, 8, 6))

    # Floppy ear
    pygame.draw.ellipse(surface, body_dark, (fx(28) - (0 if facing_right else 8), 16, 8, 18))

    # Eye
    ex = fx(36) - (0 if facing_right else 4)
    pygame.draw.circle(surface, (255, 255, 255), (ex, 18), 3)
    pygame.draw.circle(surface, eye, (ex, 19), 2)

    # Nose
    pygame.draw.ellipse(surface, nose, (fx(44) - (0 if facing_right else 5), 24, 5, 4))

    # Tail
    pygame.draw.arc(surface, body_main, (fx(2) - (0 if facing_right else 10), 20, 10, 14), 1.5, 4.5, 3)


def _draw_buster_sprite(surface: pygame.Surface, facing_right: bool) -> None:
    """Draw Buster gameplay sprite - tricolor beagle."""
    white = (255, 252, 248)
    tan = (210, 160, 100)
    black = (45, 40, 38)
    nose = (35, 30, 30)
    eye = (55, 45, 40)

    def fx(x):
        return x if facing_right else 48 - x

    # Body
    pygame.draw.ellipse(surface, white, (fx(10) - (0 if facing_right else 24), 24, 24, 16))
    pygame.draw.ellipse(surface, tan, (fx(26) - (0 if facing_right else 10), 26, 10, 12))

    # Legs
    pygame.draw.rect(surface, white, (fx(14) - (0 if facing_right else 4), 36, 4, 12))
    pygame.draw.rect(surface, white, (fx(28) - (0 if facing_right else 4), 36, 4, 12))

    # Head
    pygame.draw.ellipse(surface, white, (fx(26) - (0 if facing_right else 16), 10, 16, 20))
    pygame.draw.ellipse(surface, tan, (fx(26) - (0 if facing_right else 16), 10, 16, 10))
    pygame.draw.ellipse(surface, black, (fx(30) - (0 if facing_right else 10), 10, 10, 6))

    # Floppy ears
    pygame.draw.ellipse(surface, tan, (fx(22) - (0 if facing_right else 8), 16, 8, 20))
    pygame.draw.ellipse(surface, tan, (fx(38) - (0 if facing_right else 8), 16, 8, 20))

    # Eye
    ex = fx(34) - (0 if facing_right else 4)
    pygame.draw.circle(surface, (255, 255, 255), (ex, 18), 3)
    pygame.draw.circle(surface, eye, (ex, 19), 2)

    # Nose
    pygame.draw.ellipse(surface, nose, (fx(34) - (0 if facing_right else 5), 24, 5, 3))

    # Tail
    pygame.draw.ellipse(surface, tan, (fx(6) - (0 if facing_right else 6), 26, 6, 6))
    pygame.draw.ellipse(surface, white, (fx(4) - (0 if facing_right else 4), 24, 4, 4))


def _draw_queenie_sprite(surface: pygame.Surface, facing_right: bool) -> None:
    """Draw Queenie gameplay sprite - orange/white corgi."""
    orange = (235, 170, 70)
    orange_dark = (200, 135, 45)
    white = (255, 252, 248)
    nose = (40, 35, 35)
    eye = (50, 42, 38)

    def fx(x):
        return x if facing_right else 48 - x

    # Long body
    pygame.draw.ellipse(surface, orange, (fx(6) - (0 if facing_right else 32), 24, 32, 16))
    pygame.draw.ellipse(surface, white, (fx(14) - (0 if facing_right else 20), 32, 20, 8))

    # Short stubby legs
    pygame.draw.rect(surface, orange, (fx(12) - (0 if facing_right else 5), 36, 5, 12))
    pygame.draw.rect(surface, orange, (fx(30) - (0 if facing_right else 5), 36, 5, 12))
    pygame.draw.rect(surface, white, (fx(12) - (0 if facing_right else 5), 42, 5, 6))
    pygame.draw.rect(surface, white, (fx(30) - (0 if facing_right else 5), 42, 5, 6))

    # Head
    pygame.draw.ellipse(surface, orange, (fx(26) - (0 if facing_right else 18), 10, 18, 18))
    pygame.draw.ellipse(surface, white, (fx(30) - (0 if facing_right else 10), 18, 10, 10))

    # Big pointed ears
    if facing_right:
        pygame.draw.polygon(surface, orange, [(28, 14), (20, 0), (34, 10)])
        pygame.draw.polygon(surface, orange, [(40, 14), (48, 0), (38, 10)])
    else:
        pygame.draw.polygon(surface, orange, [(20, 14), (28, 0), (14, 10)])
        pygame.draw.polygon(surface, orange, [(8, 14), (0, 0), (10, 10)])

    # Eye
    ex = fx(36) - (0 if facing_right else 5)
    pygame.draw.circle(surface, (255, 255, 255), (ex, 16), 3)
    pygame.draw.circle(surface, eye, (ex, 17), 2)

    # Nose
    pygame.draw.ellipse(surface, nose, (fx(34) - (0 if facing_right else 5), 22, 5, 4))

    # Fluffy butt (no tail)
    pygame.draw.circle(surface, orange, (fx(8), 28), 6)


# ============== SNACK SPRITES (48x48 for 960x720 display) ==============

def create_snack_sprite(snack_id: str) -> pygame.Surface:
    """Create a 48x48 pixel art sprite for a snack (for 960x720 display)."""
    # Create at 24x24 then scale up to 48x48 for detailed retro look
    large_surface = pygame.Surface((24, 24), pygame.SRCALPHA)

    if snack_id == "pizza":
        _draw_pizza_sprite(large_surface)
    elif snack_id == "bone":
        _draw_bone_sprite(large_surface)
    elif snack_id == "broccoli":
        _draw_broccoli_sprite(large_surface)
    elif snack_id == "spicy_pepper":
        _draw_pepper_sprite(large_surface)
    elif snack_id == "bacon":
        _draw_bacon_sprite(large_surface)
    elif snack_id == "steak":
        _draw_steak_sprite(large_surface)
    else:
        pygame.draw.rect(large_surface, (200, 200, 200), (4, 4, 16, 16))

    # Scale up to 48x48 for full resolution display
    return pygame.transform.scale(large_surface, (48, 48))


def _draw_pizza_sprite(surface: pygame.Surface) -> None:
    """Draw a detailed pizza slice."""
    crust = (200, 150, 80)
    crust_dark = (170, 120, 60)
    cheese = (255, 210, 80)
    cheese_light = (255, 235, 140)
    pepperoni = (180, 50, 50)
    pepperoni_dark = (140, 35, 35)

    # Pizza triangle
    pygame.draw.polygon(surface, cheese, [(12, 2), (2, 22), (22, 22)])
    pygame.draw.polygon(surface, cheese_light, [(12, 4), (6, 18), (18, 18)])

    # Crust
    pygame.draw.polygon(surface, crust, [(2, 22), (22, 22), (20, 19), (4, 19)])
    pygame.draw.polygon(surface, crust_dark, [(4, 22), (20, 22), (19, 20), (5, 20)])

    # Pepperoni
    pygame.draw.circle(surface, pepperoni, (12, 12), 4)
    pygame.draw.circle(surface, pepperoni_dark, (12, 13), 3)
    pygame.draw.circle(surface, pepperoni, (8, 17), 3)
    pygame.draw.circle(surface, pepperoni_dark, (8, 18), 2)
    pygame.draw.circle(surface, pepperoni, (16, 17), 3)
    pygame.draw.circle(surface, pepperoni_dark, (16, 18), 2)


def _draw_bone_sprite(surface: pygame.Surface) -> None:
    """Draw a detailed dog bone."""
    white = (255, 252, 245)
    shadow = (230, 225, 215)
    highlight = (255, 255, 255)

    # Main shaft
    pygame.draw.rect(surface, white, (6, 10, 12, 4))
    pygame.draw.rect(surface, shadow, (6, 12, 12, 2))

    # Left end knobs
    pygame.draw.circle(surface, white, (6, 8), 4)
    pygame.draw.circle(surface, white, (6, 16), 4)
    pygame.draw.circle(surface, shadow, (6, 9), 3)
    pygame.draw.circle(surface, shadow, (6, 17), 3)
    pygame.draw.circle(surface, highlight, (5, 7), 1)
    pygame.draw.circle(surface, highlight, (5, 15), 1)

    # Right end knobs
    pygame.draw.circle(surface, white, (18, 8), 4)
    pygame.draw.circle(surface, white, (18, 16), 4)
    pygame.draw.circle(surface, shadow, (18, 9), 3)
    pygame.draw.circle(surface, shadow, (18, 17), 3)
    pygame.draw.circle(surface, highlight, (17, 7), 1)
    pygame.draw.circle(surface, highlight, (17, 15), 1)


def _draw_broccoli_sprite(surface: pygame.Surface) -> None:
    """Draw broccoli florets."""
    green = (60, 160, 60)
    green_light = (90, 200, 90)
    green_dark = (40, 120, 40)
    stem = (120, 100, 60)
    stem_light = (150, 130, 90)

    # Florets (bumpy top)
    pygame.draw.circle(surface, green, (12, 8), 6)
    pygame.draw.circle(surface, green, (7, 10), 5)
    pygame.draw.circle(surface, green, (17, 10), 5)
    pygame.draw.circle(surface, green_light, (12, 6), 4)
    pygame.draw.circle(surface, green_light, (8, 8), 3)
    pygame.draw.circle(surface, green_light, (16, 8), 3)
    pygame.draw.circle(surface, green_dark, (10, 12), 3)
    pygame.draw.circle(surface, green_dark, (14, 12), 3)

    # Stem
    pygame.draw.rect(surface, stem, (9, 13, 6, 10))
    pygame.draw.rect(surface, stem_light, (10, 14, 4, 8))


def _draw_pepper_sprite(surface: pygame.Surface) -> None:
    """Draw a spicy chili pepper."""
    red = (220, 45, 45)
    red_light = (255, 90, 80)
    red_dark = (180, 30, 30)
    green = (60, 150, 60)
    green_dark = (40, 110, 40)

    # Pepper body (curved)
    pygame.draw.ellipse(surface, red, (6, 6, 14, 8))
    pygame.draw.polygon(surface, red, [(12, 10), (6, 20), (12, 22), (18, 20)])
    pygame.draw.polygon(surface, red_light, [(12, 8), (8, 16), (12, 18)])
    pygame.draw.polygon(surface, red_dark, [(12, 12), (14, 18), (18, 16)])

    # Stem
    pygame.draw.rect(surface, green, (10, 2, 4, 6))
    pygame.draw.rect(surface, green_dark, (11, 3, 2, 4))


def _draw_bacon_sprite(surface: pygame.Surface) -> None:
    """Draw wavy bacon strips."""
    red = (180, 60, 60)
    red_dark = (150, 45, 45)
    pink = (240, 180, 180)
    pink_dark = (220, 150, 150)

    # Wavy bacon strips
    for i in range(3):
        y = 4 + i * 6
        # Main strip with wave
        pygame.draw.rect(surface, red, (3, y, 18, 4))
        pygame.draw.rect(surface, red_dark, (3, y + 2, 18, 2))
        # Fat stripes
        pygame.draw.rect(surface, pink, (5, y, 4, 3))
        pygame.draw.rect(surface, pink_dark, (5, y + 1, 4, 2))
        pygame.draw.rect(surface, pink, (13, y, 4, 3))
        pygame.draw.rect(surface, pink_dark, (13, y + 1, 4, 2))


def _draw_steak_sprite(surface: pygame.Surface) -> None:
    """Draw a juicy steak."""
    brown = (150, 90, 55)
    brown_dark = (120, 65, 40)
    brown_light = (180, 120, 80)
    grill = (70, 45, 30)
    fat = (240, 230, 210)

    # Steak shape
    pygame.draw.ellipse(surface, brown, (2, 6, 20, 14))
    pygame.draw.ellipse(surface, brown_light, (4, 8, 16, 10))
    pygame.draw.ellipse(surface, brown_dark, (6, 10, 12, 6))

    # Grill marks
    pygame.draw.line(surface, grill, (6, 8), (6, 16), 2)
    pygame.draw.line(surface, grill, (12, 8), (12, 16), 2)
    pygame.draw.line(surface, grill, (18, 8), (18, 16), 2)

    # Fat edge
    pygame.draw.ellipse(surface, fat, (2, 14, 6, 6))


# ============== SNACK ICONS (16x16) ==============

def create_snack_icon(snack_id: str) -> pygame.Surface:
    """Create a small 16x16 icon for HUD."""
    surface = pygame.Surface((16, 16), pygame.SRCALPHA)

    if snack_id == "pizza":
        pygame.draw.polygon(surface, (255, 210, 80), [(8, 1), (1, 14), (15, 14)])
        pygame.draw.polygon(surface, (200, 150, 80), [(1, 14), (15, 14), (14, 12), (2, 12)])
        pygame.draw.circle(surface, (180, 50, 50), (8, 8), 3)
    elif snack_id == "bone":
        pygame.draw.rect(surface, (255, 250, 240), (4, 7, 8, 2))
        pygame.draw.circle(surface, (255, 250, 240), (4, 6), 3)
        pygame.draw.circle(surface, (255, 250, 240), (4, 10), 3)
        pygame.draw.circle(surface, (255, 250, 240), (12, 6), 3)
        pygame.draw.circle(surface, (255, 250, 240), (12, 10), 3)
    elif snack_id == "bacon":
        for i in range(3):
            pygame.draw.rect(surface, (180, 60, 60), (2, 3 + i * 4, 12, 3))
            pygame.draw.rect(surface, (240, 180, 180), (4, 3 + i * 4, 3, 2))
    elif snack_id == "broccoli":
        pygame.draw.circle(surface, (60, 160, 60), (8, 5), 5)
        pygame.draw.rect(surface, (120, 100, 60), (6, 9, 4, 6))
    elif snack_id == "steak":
        pygame.draw.ellipse(surface, (150, 90, 55), (2, 4, 12, 8))
        pygame.draw.line(surface, (70, 45, 30), (5, 5), (5, 11), 2)
        pygame.draw.line(surface, (70, 45, 30), (9, 5), (9, 11), 2)
    elif snack_id == "spicy_pepper":
        pygame.draw.polygon(surface, (220, 45, 45), [(8, 2), (4, 12), (8, 14), (12, 12)])
        pygame.draw.rect(surface, (60, 150, 60), (6, 0, 4, 4))

    return surface


# ============== WOODEN FLOOR TILES ==============

def create_wood_plank_tile(variant: int = 0) -> pygame.Surface:
    """Create a 64x32 wooden plank floor tile for 960x720 display."""
    surface = pygame.Surface((64, 32))

    # Base colors for wood
    if variant == 0:
        base = (210, 165, 105)
        light = (235, 195, 140)
        dark = (175, 130, 75)
        grain = (190, 145, 90)
    elif variant == 1:
        base = (195, 150, 95)
        light = (220, 180, 125)
        dark = (160, 115, 65)
        grain = (175, 130, 80)
    else:
        base = (225, 180, 120)
        light = (245, 210, 160)
        dark = (190, 145, 90)
        grain = (205, 160, 105)

    # Fill base color
    surface.fill(base)

    # Wood grain lines (horizontal)
    for y in [6, 14, 22]:
        pygame.draw.line(surface, grain, (0, y), (64, y), 2)

    # Light edge (top of plank)
    pygame.draw.line(surface, light, (0, 0), (64, 0), 2)
    pygame.draw.line(surface, light, (0, 1), (64, 1), 1)

    # Dark edge (bottom of plank - shadow)
    pygame.draw.line(surface, dark, (0, 30), (64, 30), 2)
    pygame.draw.line(surface, dark, (0, 31), (64, 31), 1)

    # Wood knot (occasional)
    if variant == 1:
        pygame.draw.ellipse(surface, dark, (24, 10, 12, 10))
        pygame.draw.ellipse(surface, grain, (26, 12, 8, 6))

    # Vertical gaps between planks
    pygame.draw.line(surface, dark, (0, 0), (0, 32), 2)
    pygame.draw.line(surface, dark, (62, 0), (62, 32), 2)
    pygame.draw.line(surface, dark, (63, 0), (63, 32), 1)

    return surface


def draw_wooden_floor(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw wooden plank floor on the given surface area."""
    cache = SpriteCache()

    tile_width = 64
    tile_height = 32

    row = 0
    for y in range(rect.top, rect.bottom, tile_height):
        col = 0
        # Offset alternating rows for brick-like pattern
        x_offset = (tile_width // 2) if row % 2 == 1 else 0
        for x in range(rect.left - x_offset, rect.right, tile_width):
            # Vary tile appearance
            variant = (col + row) % 3
            tile = cache.get_floor_tile(variant)
            surface.blit(tile, (x, y))
            col += 1
        row += 1


# ============== WOODEN FENCE BORDER ==============

def create_fence_segment(segment_type: str) -> pygame.Surface:
    """Create a fence segment for arena borders (for 960x720 display)."""
    # Vertical plank segment
    if segment_type == "vertical":
        surface = pygame.Surface((16, 64), pygame.SRCALPHA)
        # Blue wood colors
        blue_main = (74, 130, 185)
        blue_light = (100, 160, 215)
        blue_dark = (50, 95, 145)
        blue_shadow = (35, 70, 110)

        # Plank body
        surface.fill(blue_main)
        # Light edge (left)
        pygame.draw.line(surface, blue_light, (2, 0), (2, 64), 2)
        # Dark edge (right)
        pygame.draw.line(surface, blue_dark, (12, 0), (12, 64), 2)
        # Shadow gap
        pygame.draw.line(surface, blue_shadow, (14, 0), (14, 64), 2)
        pygame.draw.line(surface, blue_shadow, (0, 0), (0, 64), 2)
        # Wood grain
        pygame.draw.line(surface, blue_dark, (6, 0), (6, 64), 2)

        return surface

    # Horizontal rail segment
    elif segment_type == "horizontal":
        surface = pygame.Surface((64, 16), pygame.SRCALPHA)
        blue_main = (74, 130, 185)
        blue_light = (100, 160, 215)
        blue_dark = (50, 95, 145)
        blue_shadow = (35, 70, 110)

        surface.fill(blue_main)
        pygame.draw.line(surface, blue_light, (0, 2), (64, 2), 2)
        pygame.draw.line(surface, blue_dark, (0, 12), (64, 12), 2)
        pygame.draw.line(surface, blue_shadow, (0, 14), (64, 14), 2)
        pygame.draw.line(surface, blue_shadow, (0, 0), (64, 0), 2)

        return surface

    return pygame.Surface((16, 16), pygame.SRCALPHA)


def draw_fence_border(surface: pygame.Surface, rect: pygame.Rect, thickness: int = 12) -> None:
    """Draw a wooden fence border around the given rectangle (for 960x720 display)."""
    cache = SpriteCache()

    blue_main = (74, 130, 185)
    blue_light = (100, 160, 215)
    blue_dark = (50, 95, 145)
    blue_shadow = (35, 70, 110)

    # Draw corner posts and planks
    # Top border
    pygame.draw.rect(surface, blue_main, (rect.left, rect.top, rect.width, thickness))
    pygame.draw.rect(surface, blue_light, (rect.left, rect.top, rect.width, 3))
    pygame.draw.rect(surface, blue_shadow, (rect.left, rect.top + thickness - 3, rect.width, 3))

    # Bottom border
    pygame.draw.rect(surface, blue_main, (rect.left, rect.bottom - thickness, rect.width, thickness))
    pygame.draw.rect(surface, blue_light, (rect.left, rect.bottom - thickness, rect.width, 3))
    pygame.draw.rect(surface, blue_shadow, (rect.left, rect.bottom - 3, rect.width, 3))

    # Left border
    pygame.draw.rect(surface, blue_main, (rect.left, rect.top, thickness, rect.height))
    pygame.draw.rect(surface, blue_light, (rect.left, rect.top, 3, rect.height))
    pygame.draw.rect(surface, blue_shadow, (rect.left + thickness - 3, rect.top, 3, rect.height))

    # Right border
    pygame.draw.rect(surface, blue_main, (rect.right - thickness, rect.top, thickness, rect.height))
    pygame.draw.rect(surface, blue_light, (rect.right - thickness, rect.top, 3, rect.height))
    pygame.draw.rect(surface, blue_shadow, (rect.right - 3, rect.top, 3, rect.height))

    # Vertical plank lines on top/bottom
    for x in range(rect.left + 32, rect.right - 16, 32):
        pygame.draw.line(surface, blue_shadow, (x, rect.top), (x, rect.top + thickness), 2)
        pygame.draw.line(surface, blue_shadow, (x, rect.bottom - thickness), (x, rect.bottom), 2)

    # Horizontal plank lines on sides
    for y in range(rect.top + 32, rect.bottom - 16, 32):
        pygame.draw.line(surface, blue_shadow, (rect.left, y), (rect.left + thickness, y), 2)
        pygame.draw.line(surface, blue_shadow, (rect.right - thickness, y), (rect.right, y), 2)


# Legacy compatibility
def draw_tiled_floor(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Legacy function - now draws wooden floor."""
    draw_wooden_floor(surface, rect)


def create_floor_tile(alt: bool = False) -> pygame.Surface:
    """Legacy function - returns a wood plank tile."""
    return create_wood_plank_tile(1 if alt else 0)
