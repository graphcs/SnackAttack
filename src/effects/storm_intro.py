"""Lightning + Treat Storm intro sequence for the Treat Attack game mode.

Plays a cinematic intro animation using pre-generated pixel-art sprites:
  1. Clouds gathering — sprite-based storm clouds roll in over a sky that
     transitions from clear pastel to dark storm. Rain particles intensify.
  2. Lightning strike — sprite-based lightning bolts with flash overlay,
     screen shake, and ground bloom effects.
  3. Screen flicker — organic flicker with varied intensity and colour
     temperature shifts, plus a final thunder-rumble screen shake.
  4. Dogs march — dogs walk in from off-screen with dust puffs, a dynamic
     shadow, and dramatic "TREAT STORM!" / "GO!" title sprites.

All sprite assets are loaded from ui/storm_intro/.
"""

import pygame
import math
import os
import random
from glob import glob
from enum import Enum, auto
from typing import List, Tuple, Optional, Dict


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class IntroPhase(Enum):
    """Phases of the storm intro sequence."""
    CLOUDS_GATHER = auto()
    LIGHTNING_STRIKE = auto()
    SCREEN_FLICKER = auto()
    DOGS_MARCH = auto()
    COMPLETE = auto()


# Phase durations (seconds)
_PHASE_DURATIONS: Dict[IntroPhase, float] = {
    IntroPhase.CLOUDS_GATHER: 4.0,
    IntroPhase.LIGHTNING_STRIKE: 1.6,
    IntroPhase.SCREEN_FLICKER: 0.9,
    IntroPhase.DOGS_MARCH: 2.2,
}

# Rain colours
_RAIN_COLOR = (160, 175, 200)
_RAIN_HEAVY_COLOR = (130, 150, 180)

# Lightning palette (for procedural ground bloom)
_BOLT_CORE = (230, 230, 255)
_BOLT_INNER_GLOW = (180, 190, 255)
_BOLT_OUTER_GLOW = (120, 130, 220)

_STORM_FRAME_PHASES = (
    IntroPhase.CLOUDS_GATHER,
    IntroPhase.LIGHTNING_STRIKE,
    IntroPhase.SCREEN_FLICKER,
)


# ---------------------------------------------------------------------------
# Asset directory
# ---------------------------------------------------------------------------

def _get_asset_dir() -> str:
    """Resolve the storm intro asset directory."""
    # Navigate from src/effects/ up to project root, then into ui/storm_intro
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(here))
    return os.path.join(project_root, "ui", "storm_intro")


# ---------------------------------------------------------------------------
# Maths helpers
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def _lerp_color(c1: Tuple[int, ...], c2: Tuple[int, ...], t: float) -> Tuple[int, ...]:
    t = max(0.0, min(1.0, t))
    return tuple(max(0, min(255, int(a + (b - a) * t))) for a, b in zip(c1, c2))


def _ease_in_out(t: float) -> float:
    """Smooth ease-in-out (cubic)."""
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - pow(-2.0 * t + 2.0, 3) / 2.0


def _ease_out_quad(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)


def _ease_in_quad(t: float) -> float:
    return t * t


# ---------------------------------------------------------------------------
# Particle: rain drop
# ---------------------------------------------------------------------------

class _RainDrop:
    """A single rain particle with wind and gravity."""

    __slots__ = ("x", "y", "vx", "vy", "length", "alpha", "alive")

    def __init__(self, x: float, y: float, wind: float, intensity: float):
        self.x = x
        self.y = y
        self.vx = wind + random.uniform(-20, 20)
        self.vy = random.uniform(400, 700) * intensity
        self.length = random.uniform(6, 16) * intensity
        self.alpha = random.randint(80, 180)
        self.alive = True

    def update(self, dt: float, ground_y: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.y > ground_y:
            self.alive = False

    def render(self, surface: pygame.Surface, color: Tuple[int, int, int]) -> None:
        if not self.alive:
            return
        end_x = self.x + self.vx * (self.length / self.vy)
        end_y = self.y + self.length
        pygame.draw.line(
            surface, (*color, self.alpha),
            (int(self.x), int(self.y)), (int(end_x), int(end_y)), 1
        )


# ---------------------------------------------------------------------------
# Particle: dust puff (for dog footsteps)
# ---------------------------------------------------------------------------

class _DustPuff:
    """Small dust cloud spawned at footsteps."""

    __slots__ = ("x", "y", "radius", "max_radius", "alpha", "life", "max_life")

    def __init__(self, x: float, y: float):
        self.x = x + random.uniform(-6, 6)
        self.y = y + random.uniform(-2, 4)
        self.radius = 2.0
        self.max_radius = random.uniform(8, 16)
        self.life = 0.0
        self.max_life = random.uniform(0.3, 0.6)
        self.alpha = random.randint(120, 200)

    @property
    def alive(self) -> bool:
        return self.life < self.max_life

    def update(self, dt: float) -> None:
        self.life += dt
        t = self.life / self.max_life
        self.radius = self.max_radius * _ease_out_quad(t)
        self.alpha = int(200 * (1.0 - t))
        self.y -= 15 * dt  # drift upward

    def render(self, surface: pygame.Surface) -> None:
        if self.alpha <= 0:
            return
        s = pygame.Surface(
            (int(self.radius * 2 + 4), int(self.radius * 2 + 4)), pygame.SRCALPHA
        )
        pygame.draw.circle(
            s, (160, 140, 110, self.alpha),
            (int(self.radius + 2), int(self.radius + 2)), int(self.radius)
        )
        surface.blit(
            s, (int(self.x - self.radius - 2), int(self.y - self.radius - 2))
        )


# ---------------------------------------------------------------------------
# Ground-impact bloom (bright circle at strike point)
# ---------------------------------------------------------------------------

class _GroundBloom:
    """Expanding glow at the lightning impact point."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.radius = 5.0
        self.max_radius = random.uniform(50, 80)
        self.alpha = 255
        self.life = 0.0
        self.duration = 0.5

    @property
    def alive(self) -> bool:
        return self.life < self.duration

    def update(self, dt: float) -> None:
        self.life += dt
        t = min(self.life / self.duration, 1.0)
        self.radius = self.max_radius * _ease_out_quad(t)
        self.alpha = int(255 * (1.0 - _ease_in_quad(t)))

    def render(self, surface: pygame.Surface) -> None:
        if self.alpha <= 5:
            return
        size = int(self.radius * 2 + 10)
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        centre = size // 2
        pygame.draw.circle(
            s, (*_BOLT_OUTER_GLOW, self.alpha // 3),
            (centre, centre), int(self.radius)
        )
        pygame.draw.circle(
            s, (*_BOLT_INNER_GLOW, self.alpha // 2),
            (centre, centre), int(self.radius * 0.5)
        )
        pygame.draw.circle(
            s, (*_BOLT_CORE, self.alpha),
            (centre, centre), max(2, int(self.radius * 0.15))
        )
        surface.blit(s, (int(self.x - centre), int(self.y - centre)))


# ---------------------------------------------------------------------------
# Screen-shake helper
# ---------------------------------------------------------------------------

class _ScreenShake:
    """Tracks decaying screen-shake offset."""

    def __init__(self):
        self.offset_x = 0.0
        self.offset_y = 0.0
        self._intensity = 0.0
        self._decay = 0.0

    def trigger(self, intensity: float, decay: float = 8.0) -> None:
        self._intensity = intensity
        self._decay = decay

    def update(self, dt: float) -> None:
        if self._intensity <= 0.1:
            self.offset_x = 0.0
            self.offset_y = 0.0
            return
        self._intensity *= max(0.0, 1.0 - self._decay * dt)
        self.offset_x = random.uniform(-self._intensity, self._intensity)
        self.offset_y = random.uniform(-self._intensity, self._intensity)


# ---------------------------------------------------------------------------
# Sprite-based cloud
# ---------------------------------------------------------------------------

class _SpriteCloud:
    """A storm cloud using a pre-rendered sprite, animated to slide in."""

    def __init__(self, sprite: pygame.Surface, start_x: float, target_x: float,
                 y: float, speed: float, layer: int, scale: float = 1.0):
        self.original_sprite = sprite
        if scale != 1.0:
            new_w = int(sprite.get_width() * scale)
            new_h = int(sprite.get_height() * scale)
            self.sprite = pygame.transform.smoothscale(sprite, (new_w, new_h))
        else:
            self.sprite = sprite
        self.x = start_x
        self.target_x = target_x
        self.y = y
        self.speed = speed
        self.layer = layer
        self.bob_offset = random.uniform(0, math.pi * 2)

    def update(self, dt: float, t_gather: float, global_time: float) -> None:
        """Move toward target and add gentle bob."""
        diff = self.target_x - self.x
        if t_gather < 0.4:
            speed_mult = 2.5
        else:
            speed_mult = _lerp(2.5, 0.5, (t_gather - 0.4) / 0.6)
        eased = _ease_in_out(t_gather)
        approach_speed = abs(self.speed) * (1.0 + (1.0 - eased) * speed_mult)
        if abs(diff) > 2.0:
            direction = 1.0 if diff > 0 else -1.0
            self.x += direction * approach_speed * dt
            if (direction > 0 and self.x > self.target_x) or \
               (direction < 0 and self.x < self.target_x):
                self.x = self.target_x
        else:
            self.x = _lerp(self.x, self.target_x, dt * 2.0)

        # Gentle vertical bob
        self.y += math.sin(global_time * 0.7 + self.bob_offset) * 3.0 * dt

    def render(self, surface: pygame.Surface, alpha: int = 255) -> None:
        """Render the cloud sprite."""
        if alpha < 255:
            temp = self.sprite.copy()
            temp.set_alpha(alpha)
            surface.blit(temp, (int(self.x), int(self.y)))
        else:
            surface.blit(self.sprite, (int(self.x), int(self.y)))


# ---------------------------------------------------------------------------
# StormIntroSequence
# ---------------------------------------------------------------------------

class StormIntroSequence:
    """Orchestrates the full Lightning + Treat Storm intro animation.

    Uses pre-generated pixel-art sprites from ui/storm_intro/ for a
    dramatic, polished intro sequence.

    Usage::

        intro = StormIntroSequence(720, 720)
        intro.start(dog_sprite=dog_frame, dog_target_x=300, dog_ground_y=650)

        # In your game loop:
        if not intro.is_complete:
            intro.update(dt)
            intro.render(surface)
    """

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # State
        self.phase = IntroPhase.CLOUDS_GATHER
        self.phase_timer = 0.0
        self.global_timer = 0.0
        self.is_complete = False

        # — Asset loading —
        asset_dir = _get_asset_dir()
        self._assets: Dict[str, Optional[pygame.Surface]] = {}
        self._storm_frames: List[pygame.Surface] = []
        self._scaled_storm_frames: List[pygame.Surface] = []
        self._scaled_storm_frame_size: Optional[Tuple[int, int]] = None
        self._load_assets(asset_dir)
        self._storm_sequence_duration = sum(
            _PHASE_DURATIONS[phase] for phase in _STORM_FRAME_PHASES
        )

        # Sprite-based clouds
        self._clouds: List[_SpriteCloud] = []

        # Rain particles
        self._rain: List[_RainDrop] = []
        self._rain_intensity = 0.0
        self._wind = 0.0

        # Lightning state
        self._active_bolts: List[dict] = []  # sprite-based bolt instances
        self._pending_bolt_times: List[float] = []
        self._lightning_flash = 0.0
        self._ground_blooms: List[_GroundBloom] = []

        # Screen shake
        self._shake = _ScreenShake()

        # Flicker
        self._flicker_flash = 0.0
        self._flicker_index = 0
        self._flicker_pattern = [
            (0.06, 0.9, 0.0), (0.04, 0.0, 0.0),
            (0.08, 1.0, 0.1), (0.05, 0.0, 0.0),
            (0.04, 0.6, -0.05), (0.06, 0.0, 0.0),
            (0.10, 0.8, 0.05), (0.03, 0.3, 0.0),
            (0.07, 0.0, 0.0), (0.12, 0.5, -0.1),
            (0.25, 0.0, 0.0),
        ]
        self._flicker_sub_timer = 0.0
        self._flicker_temp_shift = 0.0

        # Dog march
        self._dog1_sprite: Optional[pygame.Surface] = None
        self._dog2_sprite: Optional[pygame.Surface] = None
        self._dog_render_scale = 1.12
        self._dog1_start_x = 0.0
        self._dog1_target_x = 0.0
        self._dog1_current_x = 0.0
        self._dog2_start_x = 0.0
        self._dog2_target_x = 0.0
        self._dog2_current_x = 0.0
        self._dog_ground_y = 650.0
        self._march_bob_timer = 0.0
        self._dust_puffs: List[_DustPuff] = []
        self._last_step_x1 = 0.0
        self._last_step_x2 = 0.0

        # Title sprites
        self._title_scale = 0.0
        self._title_alpha = 0
        self._go_alpha = 0

    # ------------------------------------------------------------------
    # Asset loading
    # ------------------------------------------------------------------

    def _load_assets(self, asset_dir: str) -> None:
        """Load all sprite assets from the storm_intro directory."""
        asset_sources = {
            "clear_sky_bg": ["clear_sky_bg.png"],
            "storm_sky_bg": ["storm_sky_bg.png"],
            "storm_cloud_large": ["storm_cloud_large.png"],
            "storm_cloud_medium": ["storm_cloud_medium.png"],
            "storm_cloud_small": ["storm_cloud_small.png"],
            "lightning_bolt": ["lightning_bolt.png"],
            "lightning_flash": ["lightning_flash.png"],
            "ground_scene": ["ground_scene.png", "ground.png"],
            "title_treat_storm": ["title_treat_storm.png", "Title  .png"],
            "title_go": ["title_go.png", "go.png"],
            "dust_puff": ["dust_puff.png"],
            "vignette_overlay": ["vignette_overlay.png"],
            "silver_lining_glow": ["silver_lining_glow.png"],
        }
        for name, candidates in asset_sources.items():
            self._assets[name] = self._load_first_asset(asset_dir, candidates)

        self._load_storm_frames(asset_dir)

    def _load_first_asset(
        self, asset_dir: str, candidates: List[str]
    ) -> Optional[pygame.Surface]:
        for candidate in candidates:
            path = os.path.join(asset_dir, candidate)
            if not os.path.exists(path):
                continue
            try:
                return pygame.image.load(path).convert_alpha()
            except pygame.error:
                continue
        return None

    def _load_storm_frames(self, asset_dir: str) -> None:
        """Load ordered frame images for the storm animation sequence."""
        frame_paths: List[str] = []
        for extension in ("jpg", "jpeg", "png"):
            frame_paths.extend(glob(os.path.join(asset_dir, f"ezgif-frame-*.{extension}")))

        def _frame_key(path: str) -> int:
            name = os.path.basename(path)
            digits = "".join(ch for ch in name if ch.isdigit())
            return int(digits) if digits else 0

        self._storm_frames.clear()
        self._scaled_storm_frames.clear()
        self._scaled_storm_frame_size = None

        for path in sorted(set(frame_paths), key=_frame_key):
            try:
                loaded = pygame.image.load(path)
                if loaded.get_alpha() is not None:
                    image = loaded.convert_alpha()
                else:
                    image = loaded.convert()
                self._storm_frames.append(image)
            except pygame.error:
                continue

    def _has_storm_frames(self) -> bool:
        return bool(self._storm_frames)

    def _get_scaled_storm_frames(self) -> List[pygame.Surface]:
        target_size = (self.screen_width, self.screen_height)
        if self._scaled_storm_frame_size == target_size and self._scaled_storm_frames:
            return self._scaled_storm_frames

        scaled_frames: List[pygame.Surface] = []
        target_w, target_h = target_size
        for frame in self._storm_frames:
            src_w, src_h = frame.get_size()
            if src_w <= 0 or src_h <= 0:
                continue

            scale = max(target_w / src_w, target_h / src_h)
            scaled_w = max(1, int(round(src_w * scale)))
            scaled_h = max(1, int(round(src_h * scale)))
            scaled = pygame.transform.smoothscale(frame, (scaled_w, scaled_h))

            crop_x = max(0, (scaled_w - target_w) // 2)
            crop_y = max(0, (scaled_h - target_h) // 2)
            cropped = pygame.Surface(target_size)
            cropped.blit(scaled, (-crop_x, -crop_y))
            scaled_frames.append(cropped)

        self._scaled_storm_frames = scaled_frames
        self._scaled_storm_frame_size = target_size
        return self._scaled_storm_frames

    def _get_storm_animation_elapsed(self) -> float:
        if self.phase == IntroPhase.CLOUDS_GATHER:
            return self.phase_timer
        if self.phase == IntroPhase.LIGHTNING_STRIKE:
            return _PHASE_DURATIONS[IntroPhase.CLOUDS_GATHER] + self.phase_timer
        if self.phase == IntroPhase.SCREEN_FLICKER:
            return (
                _PHASE_DURATIONS[IntroPhase.CLOUDS_GATHER]
                + _PHASE_DURATIONS[IntroPhase.LIGHTNING_STRIKE]
                + self.phase_timer
            )
        return self._storm_sequence_duration

    def _get_current_storm_frame(self) -> Optional[pygame.Surface]:
        frames = self._get_scaled_storm_frames()
        if not frames:
            return None

        if self.phase in _STORM_FRAME_PHASES and self._storm_sequence_duration > 0:
            progress = min(
                max(self._get_storm_animation_elapsed() / self._storm_sequence_duration, 0.0),
                1.0,
            )
            frame_index = min(len(frames) - 1, int(progress * len(frames)))
        else:
            frame_index = len(frames) - 1

        return frames[frame_index]

    def _render_storm_frame(self, surface: pygame.Surface) -> bool:
        frame = self._get_current_storm_frame()
        if frame is None:
            return False
        surface.blit(frame, (0, 0))
        return True

    def _get_asset(self, name: str) -> Optional[pygame.Surface]:
        return self._assets.get(name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        dog1_sprite: Optional[pygame.Surface] = None,
        dog2_sprite: Optional[pygame.Surface] = None,
        dog_ground_y: float = 650.0,
        dog_sprite: Optional[pygame.Surface] = None,
        dog_target_x: Optional[float] = None,
    ) -> None:
        """Begin the intro sequence.

        Args:
            dog1_sprite: Player 1 sprite (faces right, enters from left).
            dog2_sprite: Player 2 sprite (faces left, enters from right).
            dog_ground_y: Y coordinate for the dogs' ground level.
            dog_sprite: Backward-compatible alias for a single left-entry dog sprite.
            dog_target_x: Optional target X override for the left-entry dog.
        """
        if dog1_sprite is None and dog_sprite is not None:
            dog1_sprite = dog_sprite

        self.phase = IntroPhase.CLOUDS_GATHER
        self.phase_timer = 0.0
        self.global_timer = 0.0
        self.is_complete = False

        # Dog 1 enters from left
        self._dog1_sprite = dog1_sprite
        self._dog1_start_x = -140.0
        self._dog1_target_x = (
            dog_target_x if dog_target_x is not None else self.screen_width * 0.28
        )
        self._dog1_current_x = self._dog1_start_x
        self._last_step_x1 = self._dog1_start_x

        # Dog 2 enters from right
        self._dog2_sprite = dog2_sprite
        self._dog2_start_x = self.screen_width + 140.0
        self._dog2_target_x = self.screen_width * 0.58
        self._dog2_current_x = self._dog2_start_x
        self._last_step_x2 = self._dog2_start_x

        self._dog_ground_y = dog_ground_y
        self._dust_puffs.clear()
        self._march_bob_timer = 0.0

        self._rain.clear()
        self._rain_intensity = 0.0
        self._wind = 0.0

        self._active_bolts.clear()
        self._ground_blooms.clear()
        self._pending_bolt_times.clear()
        self._lightning_flash = 0.0

        self._shake = _ScreenShake()
        self._flicker_index = 0
        self._flicker_sub_timer = 0.0
        self._flicker_flash = 0.0
        self._flicker_temp_shift = 0.0

        self._title_scale = 0.0
        self._title_alpha = 0
        self._go_alpha = 0

        self._build_clouds()

    @property
    def progress(self) -> float:
        """Overall progress 0.0 -> 1.0."""
        phases = [p for p in IntroPhase if p != IntroPhase.COMPLETE]
        try:
            idx = phases.index(self.phase)
        except ValueError:
            return 1.0
        total = len(phases)
        dur = _PHASE_DURATIONS.get(self.phase, 1.0)
        phase_t = min(self.phase_timer / dur, 1.0) if dur > 0 else 1.0
        return (idx + phase_t) / total

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the intro animation by *dt* seconds."""
        if self.is_complete:
            return

        self.phase_timer += dt
        self.global_timer += dt

        # Always-running subsystems
        use_frame_sequence = self._has_storm_frames() and self.phase in _STORM_FRAME_PHASES
        if use_frame_sequence:
            self._rain.clear()
            self._active_bolts.clear()
            self._ground_blooms.clear()
            self._lightning_flash = 0.0
        else:
            self._update_rain(dt)
            self._update_lightning(dt)
        self._shake.update(dt)

        # Phase-specific
        handler = None
        if not use_frame_sequence:
            handler = {
                IntroPhase.CLOUDS_GATHER: self._update_clouds,
                IntroPhase.LIGHTNING_STRIKE: self._update_lightning_phase,
                IntroPhase.SCREEN_FLICKER: self._update_flicker,
                IntroPhase.DOGS_MARCH: self._update_march,
            }.get(self.phase)
        elif self.phase == IntroPhase.DOGS_MARCH:
            handler = self._update_march
        if handler:
            handler(dt)

        # Advance phase
        while not self.is_complete:
            phase_dur = _PHASE_DURATIONS.get(self.phase)
            if phase_dur is None or self.phase_timer < phase_dur:
                break
            overflow = self.phase_timer - phase_dur
            self._advance_phase(overflow)

    def _advance_phase(self, carry_over: float = 0.0) -> None:
        order = [
            IntroPhase.CLOUDS_GATHER,
            IntroPhase.LIGHTNING_STRIKE,
            IntroPhase.SCREEN_FLICKER,
            IntroPhase.DOGS_MARCH,
            IntroPhase.COMPLETE,
        ]
        idx = order.index(self.phase)
        if idx + 1 < len(order):
            self.phase = order[idx + 1]
            self.phase_timer = max(0.0, carry_over)

            if self.phase == IntroPhase.LIGHTNING_STRIKE:
                self._pending_bolt_times = [0.0, 0.45]
                if random.random() < 0.5:
                    self._pending_bolt_times.append(0.95)
            elif self.phase == IntroPhase.SCREEN_FLICKER:
                self._flicker_index = 0
                self._flicker_sub_timer = 0.0
                self._shake.trigger(6.0, decay=5.0)
            elif self.phase == IntroPhase.DOGS_MARCH:
                self._wind *= 0.5
            elif self.phase == IntroPhase.COMPLETE:
                self.is_complete = True

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        if self.is_complete:
            return

        buf = pygame.Surface(
            (self.screen_width, self.screen_height), pygame.SRCALPHA
        )

        rendered_frame = self._render_storm_frame(buf)
        if not rendered_frame:
            # 1) Sky background (cross-fade from clear to storm)
            self._render_sky(buf)
            # 2) Back-layer clouds (layer 0)
            self._render_clouds(buf, layers=(0,))
            # 3) Rain (behind mid/front clouds)
            self._render_rain(buf)
            # 4) Mid + front clouds (layers 1, 2)
            self._render_clouds(buf, layers=(1, 2))
            # 5) Vignette overlay
            self._render_vignette(buf)
            # 6) Lightning bolts & flash
            self._render_lightning(buf)

        # 7) Ground
        self._render_ground(buf)
        # 8) Phase overlays (flicker, dog march)
        self._render_phase_overlay(buf)

        # Apply screen-shake
        sx = int(self._shake.offset_x)
        sy = int(self._shake.offset_y)
        surface.fill((0, 0, 0))
        surface.blit(buf, (sx, sy))

    def _render_phase_overlay(self, surface: pygame.Surface) -> None:
        if self.phase == IntroPhase.SCREEN_FLICKER:
            self._render_flicker_overlay(surface)
        elif self.phase == IntroPhase.DOGS_MARCH:
            self._render_dog_march(surface)

    # ------------------------------------------------------------------
    # Sky rendering (sprite cross-fade)
    # ------------------------------------------------------------------

    def _render_sky(self, surface: pygame.Surface) -> None:
        """Cross-fade between clear sky and storm sky backgrounds."""
        clear_bg = self._get_asset("clear_sky_bg")
        storm_bg = self._get_asset("storm_sky_bg")

        # Storm transition progress: 0 at start, 1 when clouds are gathered
        t = min(self.progress * 1.25, 1.0)

        sw, sh = self.screen_width, self.screen_height

        if clear_bg and storm_bg:
            # Scale both backgrounds to screen size
            clear_scaled = pygame.transform.smoothscale(clear_bg, (sw, sh))
            storm_scaled = pygame.transform.smoothscale(storm_bg, (sw, sh))

            # Render clear sky first
            if t < 1.0:
                surface.blit(clear_scaled, (0, 0))

            # Overlay storm sky with increasing alpha
            if t > 0.0:
                storm_alpha = int(t * 255)
                storm_scaled.set_alpha(storm_alpha)
                surface.blit(storm_scaled, (0, 0))
        elif clear_bg:
            surface.blit(pygame.transform.smoothscale(clear_bg, (sw, sh)), (0, 0))
        elif storm_bg:
            surface.blit(pygame.transform.smoothscale(storm_bg, (sw, sh)), (0, 0))
        else:
            # Fallback: procedural gradient
            top = _lerp_color((135, 206, 235), (22, 22, 38), t)
            bot = _lerp_color((100, 165, 210), (12, 12, 22), t)
            for y in range(sh):
                ratio = y / sh
                color = _lerp_color(top, bot, ratio)
                pygame.draw.line(surface, color, (0, y), (sw, y))

    # ------------------------------------------------------------------
    # Clouds (sprite-based)
    # ------------------------------------------------------------------

    def _build_clouds(self) -> None:
        """Create sprite-based storm clouds across three layers."""
        self._clouds.clear()
        w = self.screen_width

        cloud_sprites = {
            "large": self._get_asset("storm_cloud_large"),
            "medium": self._get_asset("storm_cloud_medium"),
            "small": self._get_asset("storm_cloud_small"),
        }

        # Layer 0 — far back (large clouds, slow) — 4 clouds
        sprite = cloud_sprites.get("large")
        if sprite:
            for i in range(4):
                target_x = (w / 5) * (i + 1) - sprite.get_width() * 0.3 + random.uniform(-40, 40)
                side = -1 if i % 2 == 0 else 1
                start_x = side * (w + random.uniform(100, 300))
                cy = random.uniform(-20, self.screen_height * 0.08)
                spd = random.uniform(100, 170)
                scale = random.uniform(0.5, 0.7)
                self._clouds.append(_SpriteCloud(
                    sprite, start_x, target_x, cy, spd, layer=0, scale=scale
                ))

        # Layer 1 — mid (medium clouds) — 5 clouds
        sprite = cloud_sprites.get("medium")
        if sprite:
            for i in range(5):
                target_x = (w / 6) * (i + 1) - sprite.get_width() * 0.25 + random.uniform(-30, 30)
                side = -1 if i % 2 == 0 else 1
                start_x = side * (w + random.uniform(80, 280))
                cy = random.uniform(self.screen_height * 0.02, self.screen_height * 0.14)
                spd = random.uniform(150, 260)
                scale = random.uniform(0.4, 0.6)
                self._clouds.append(_SpriteCloud(
                    sprite, start_x, target_x, cy, spd, layer=1, scale=scale
                ))

        # Layer 2 — front (small, fast clouds) — 5 clouds
        sprite = cloud_sprites.get("small")
        if sprite:
            for i in range(5):
                target_x = (w / 6) * (i + 1) - sprite.get_width() * 0.2 + random.uniform(-25, 25)
                side = -1 if i % 2 == 0 else 1
                start_x = side * (w + random.uniform(60, 250))
                cy = random.uniform(-10, self.screen_height * 0.10)
                spd = random.uniform(200, 340)
                scale = random.uniform(0.3, 0.5)
                self._clouds.append(_SpriteCloud(
                    sprite, start_x, target_x, cy, spd, layer=2, scale=scale
                ))

    def _update_clouds(self, dt: float) -> None:
        dur = _PHASE_DURATIONS[IntroPhase.CLOUDS_GATHER]
        t = min(self.phase_timer / dur, 1.0)

        for cloud in self._clouds:
            cloud.update(dt, t, self.global_timer)

        # Ramp wind & rain gradually
        eased = _ease_in_out(t)
        self._wind = _lerp(0, -60, eased)
        self._rain_intensity = _lerp(0.0, 0.4, eased)

    def _render_clouds(
        self, surface: pygame.Surface, layers: Tuple[int, ...] = (0, 1, 2)
    ) -> None:
        overall_t = min(self.progress * 1.4, 1.0)
        alpha = int(160 + 95 * overall_t)
        flash = self._lightning_flash

        for cloud in self._clouds:
            if cloud.layer not in layers:
                continue

            # During lightning, brighten clouds
            render_alpha = alpha
            if flash > 0:
                render_alpha = min(255, int(alpha + flash * 80))

            cloud.render(surface, render_alpha)

    # ------------------------------------------------------------------
    # Rain (procedural particles)
    # ------------------------------------------------------------------

    def _update_rain(self, dt: float) -> None:
        if self._rain_intensity <= 0:
            return

        ground_y = self._dog_ground_y + 80

        # Spawn new drops
        spawn_rate = int(self._rain_intensity * 200 * dt)
        for _ in range(spawn_rate):
            x = random.uniform(-50, self.screen_width + 50)
            y = random.uniform(-40, -5)
            self._rain.append(_RainDrop(x, y, self._wind, self._rain_intensity))

        # Update existing
        alive = []
        for drop in self._rain:
            drop.update(dt, ground_y)
            if drop.alive:
                alive.append(drop)
        self._rain = alive

        # Cap particle count
        if len(self._rain) > 600:
            self._rain = self._rain[-600:]

    def _render_rain(self, surface: pygame.Surface) -> None:
        if not self._rain:
            return
        rain_surf = pygame.Surface(
            (self.screen_width, self.screen_height), pygame.SRCALPHA
        )
        color = _RAIN_HEAVY_COLOR if self._rain_intensity > 0.6 else _RAIN_COLOR
        for drop in self._rain:
            drop.render(rain_surf, color)
        surface.blit(rain_surf, (0, 0))

    # ------------------------------------------------------------------
    # Vignette overlay
    # ------------------------------------------------------------------

    def _render_vignette(self, surface: pygame.Surface) -> None:
        """Render cinematic vignette, ramping up as storm intensifies."""
        vignette = self._get_asset("vignette_overlay")
        if not vignette:
            return

        t = min(self.progress * 1.2, 1.0)
        if t < 0.1:
            return

        scaled = pygame.transform.smoothscale(
            vignette, (self.screen_width, self.screen_height)
        )
        alpha = int(t * 200)
        scaled.set_alpha(alpha)
        surface.blit(scaled, (0, 0))

    # ------------------------------------------------------------------
    # Lightning (sprite-based bolts + flash overlay)
    # ------------------------------------------------------------------

    def _spawn_bolt(self) -> None:
        """Spawn a sprite-based lightning bolt at a random position."""
        bolt_sprite = self._get_asset("lightning_bolt")

        # Random horizontal position (20-80% of screen width)
        x = self.screen_width * random.uniform(0.15, 0.85)

        # Ground bloom at strike point
        strike_y = self._dog_ground_y + 50
        bloom = _GroundBloom(x, strike_y)
        self._ground_blooms.append(bloom)

        if bolt_sprite:
            # Scale bolt to reach from top of screen to ground
            bolt_h = int(strike_y + 20)
            bolt_w = int(bolt_sprite.get_width() * (bolt_h / bolt_sprite.get_height()))
            scaled = pygame.transform.smoothscale(bolt_sprite, (bolt_w, bolt_h))

            self._active_bolts.append({
                "sprite": scaled,
                "x": x - bolt_w // 2,
                "y": 0,
                "alpha": 0,
                "age": 0.0,
                "duration": random.uniform(0.5, 0.7),
            })

        self._shake.trigger(intensity=12.0, decay=7.0)
        self._lightning_flash = 1.0

    def _update_lightning(self, dt: float) -> None:
        """Update all active bolts and the global flash."""
        # Decay global flash
        self._lightning_flash = max(0.0, self._lightning_flash - dt * 4.0)

        alive = []
        for bolt in self._active_bolts:
            bolt["age"] += dt
            t = bolt["age"] / bolt["duration"]
            # Flash-in -> hold -> fade
            if t < 0.1:
                bolt["alpha"] = int(255 * (t / 0.1))
            elif t < 0.35:
                bolt["alpha"] = 255
            else:
                bolt["alpha"] = int(255 * max(0.0, 1.0 - (t - 0.35) / 0.65))

            if bolt["alpha"] > 0:
                alive.append(bolt)
        self._active_bolts = alive

        # Update ground blooms
        alive_blooms = []
        for bloom in self._ground_blooms:
            bloom.update(dt)
            if bloom.alive:
                alive_blooms.append(bloom)
        self._ground_blooms = alive_blooms

    def _render_lightning(self, surface: pygame.Surface) -> None:
        """Render sprite-based lightning bolts and flash overlay."""
        # Global flash overlay
        if self._lightning_flash > 0.02:
            flash_sprite = self._get_asset("lightning_flash")
            if flash_sprite:
                scaled = pygame.transform.smoothscale(
                    flash_sprite, (self.screen_width, self.screen_height)
                )
                flash_alpha = int(self._lightning_flash * 180)
                scaled.set_alpha(flash_alpha)
                surface.blit(scaled, (0, 0))
            else:
                # Fallback: simple white flash
                flash_alpha = int(self._lightning_flash * 80)
                flash_surf = pygame.Surface(
                    (self.screen_width, self.screen_height), pygame.SRCALPHA
                )
                flash_surf.fill((200, 210, 255, flash_alpha))
                surface.blit(flash_surf, (0, 0))

        # Render each active bolt sprite
        for bolt in self._active_bolts:
            alpha = bolt["alpha"]
            if alpha <= 0:
                continue
            sprite = bolt["sprite"]
            temp = sprite.copy()
            temp.set_alpha(alpha)
            surface.blit(temp, (int(bolt["x"]), int(bolt["y"])))

        # Ground blooms
        for bloom in self._ground_blooms:
            bloom.render(surface)

    # ------------------------------------------------------------------
    # Phase: Lightning Strike
    # ------------------------------------------------------------------

    def _update_lightning_phase(self, dt: float) -> None:
        """Spawn bolts at scheduled times; ramp rain."""
        remaining = []
        for t in self._pending_bolt_times:
            if self.phase_timer >= t:
                self._spawn_bolt()
            else:
                remaining.append(t)
        self._pending_bolt_times = remaining

        # Intensify rain during strikes
        self._rain_intensity = min(1.0, self._rain_intensity + dt * 0.5)
        self._wind = _lerp(self._wind, -100, dt * 2.0)

    # ------------------------------------------------------------------
    # Phase: Screen Flicker
    # ------------------------------------------------------------------

    def _update_flicker(self, dt: float) -> None:
        self._flicker_sub_timer += dt
        if self._flicker_index < len(self._flicker_pattern):
            dur, intensity, temp = self._flicker_pattern[self._flicker_index]
            self._flicker_flash = intensity
            self._flicker_temp_shift = temp
            if self._flicker_sub_timer >= dur:
                self._flicker_sub_timer -= dur
                self._flicker_index += 1
        else:
            self._flicker_flash = 0.0
            self._flicker_temp_shift = 0.0

        # Keep rain & wind at peak
        self._rain_intensity = max(self._rain_intensity, 0.8)

    def _render_flicker_overlay(self, surface: pygame.Surface) -> None:
        if self._flicker_flash <= 0.01:
            return
        overlay = pygame.Surface(
            (self.screen_width, self.screen_height), pygame.SRCALPHA
        )
        r_shift = int(self._flicker_temp_shift * 40)
        base_r = min(255, max(0, 255 + r_shift))
        base_b = min(255, max(0, 255 - r_shift))
        alpha = int(self._flicker_flash * 160)
        overlay.fill((base_r, 255, base_b, alpha))
        surface.blit(overlay, (0, 0))

    # ------------------------------------------------------------------
    # Ground rendering (sprite-based)
    # ------------------------------------------------------------------

    def _render_ground(self, surface: pygame.Surface) -> None:
        """Render the ground scene sprite at the bottom of the screen."""
        ground = self._get_asset("ground_scene")
        if ground:
            ground_w = self.screen_width
            aspect = ground.get_height() / max(ground.get_width(), 1)
            ground_h = max(1, int(ground_w * aspect))
            scaled = pygame.transform.smoothscale(ground, (ground_w, ground_h))
            ground_y = self.screen_height - ground_h
            surface.blit(scaled, (0, ground_y))
        else:
            # Fallback: procedural ground
            ground_y = int(self._dog_ground_y) + 64
            t = min(self.progress * 1.2, 1.0)
            dirt = _lerp_color((101, 67, 33), (50, 35, 18), t)
            pygame.draw.rect(
                surface, dirt,
                (0, ground_y, self.screen_width, self.screen_height - ground_y),
            )
            grass = _lerp_color((34, 139, 34), (18, 70, 18), t)
            pygame.draw.rect(
                surface, grass, (0, ground_y - 4, self.screen_width, 8)
            )

    # ------------------------------------------------------------------
    # Phase: Dogs March
    # ------------------------------------------------------------------

    def _update_march(self, dt: float) -> None:
        dur = _PHASE_DURATIONS[IntroPhase.DOGS_MARCH]
        t = min(self.phase_timer / dur, 1.0)
        eased = _ease_in_out(t)

        # Dog 1: march from left toward target
        self._dog1_current_x = self._dog1_start_x + (
            self._dog1_target_x - self._dog1_start_x
        ) * eased

        # Dog 2: march from right toward target
        self._dog2_current_x = self._dog2_start_x + (
            self._dog2_target_x - self._dog2_start_x
        ) * eased

        self._march_bob_timer += dt

        # Footstep dust puffs
        step_dist = 28
        if abs(self._dog1_current_x - self._last_step_x1) >= step_dist and t < 0.85:
            foot_y = self._dog_ground_y + 58
            self._dust_puffs.append(_DustPuff(self._dog1_current_x + 20, foot_y))
            self._last_step_x1 = self._dog1_current_x

        if abs(self._dog2_current_x - self._last_step_x2) >= step_dist and t < 0.85:
            foot_y = self._dog_ground_y + 58
            self._dust_puffs.append(_DustPuff(self._dog2_current_x + 40, foot_y))
            self._last_step_x2 = self._dog2_current_x

        alive = []
        for puff in self._dust_puffs:
            puff.update(dt)
            if puff.alive:
                alive.append(puff)
        self._dust_puffs = alive

        # "TREAT STORM!" title slam at ~40% through
        if 0.2 < t < 0.65:
            title_t = (t - 0.2) / 0.45
            self._title_scale = 0.3 + 0.7 * _ease_out_quad(min(title_t * 2, 1.0))
            self._title_alpha = int(255 * min(title_t * 3, 1.0))
        elif t >= 0.65:
            fade_t = (t - 0.65) / 0.15
            self._title_alpha = int(255 * max(0, 1.0 - fade_t))
            self._title_scale = 1.0

        # "GO!" at the very end
        self._go_alpha = (
            int(255 * max(0.0, (t - 0.82) / 0.18)) if t > 0.82 else 0
        )

        # Gradually calm rain
        self._rain_intensity = max(0.2, self._rain_intensity - dt * 0.3)

    def _render_dog_march(self, surface: pygame.Surface) -> None:
        # Dust puffs (behind dogs)
        for puff in self._dust_puffs:
            puff.render(surface)

        # Walk bob + stride tilt
        bob_y = math.sin(self._march_bob_timer * 14.0) * 3.5
        tilt = math.sin(self._march_bob_timer * 14.0 + math.pi * 0.5) * 1.5

        # --- Dog 1 (from left, faces right) ---
        self._render_single_dog(
            surface, self._dog1_sprite, self._dog1_current_x,
            facing_right=True, bob_y=bob_y, tilt=tilt,
        )

        # --- Dog 2 (from right, faces left) ---
        bob_y2 = math.sin(self._march_bob_timer * 14.0 + 1.0) * 3.5
        tilt2 = math.sin(self._march_bob_timer * 14.0 + 1.0 + math.pi * 0.5) * 1.5
        self._render_single_dog(
            surface, self._dog2_sprite, self._dog2_current_x,
            facing_right=False, bob_y=bob_y2, tilt=tilt2,
        )

        # "TREAT STORM!" title (sprite-based)
        self._render_title(surface)

        # "GO!" text (sprite-based)
        self._render_go(surface)

    def _render_single_dog(
        self, surface: pygame.Surface, sprite: Optional[pygame.Surface],
        x: float, facing_right: bool, bob_y: float, tilt: float,
    ) -> None:
        """Render one dog with shadow, bob, and tilt."""
        grass_y = self._dog_ground_y + 64

        # Shadow
        shadow_w, shadow_h = 60, 12
        shadow_x = int(x + 2)
        shadow_y = int(grass_y + 4)
        shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(
            shadow_surf, (0, 0, 0, 60), (0, 0, shadow_w, shadow_h)
        )
        surface.blit(shadow_surf, (shadow_x, shadow_y))

        if sprite:
            frame = sprite
            if self._dog_render_scale != 1.0:
                scaled_w = max(1, int(frame.get_width() * self._dog_render_scale))
                scaled_h = max(1, int(frame.get_height() * self._dog_render_scale))
                frame = pygame.transform.smoothscale(frame, (scaled_w, scaled_h))
            if not facing_right:
                frame = pygame.transform.flip(frame, True, False)
            if abs(tilt) > 0.3:
                frame = pygame.transform.rotate(frame, tilt)

            sprite_height = frame.get_height()
            dog_y = grass_y - sprite_height + bob_y + int(8 * self._dog_render_scale)
            surface.blit(frame, (int(x), int(dog_y)))

    def _render_title(self, surface: pygame.Surface) -> None:
        """Render the 'TREAT STORM!' title sprite with scale & alpha animation."""
        if self._title_alpha <= 0:
            return

        title_sprite = self._get_asset("title_treat_storm")
        if title_sprite:
            # Scale the sprite
            base_w, base_h = title_sprite.get_size()
            target_w = int(self.screen_width * 0.65)
            aspect = base_h / base_w
            target_h = int(target_w * aspect)
            scaled_w = int(target_w * self._title_scale)
            scaled_h = int(target_h * self._title_scale)
            if scaled_w > 0 and scaled_h > 0:
                scaled = pygame.transform.smoothscale(title_sprite, (scaled_w, scaled_h))
                scaled.set_alpha(self._title_alpha)
                tx = (self.screen_width - scaled_w) // 2
                ty = self.screen_height // 2 - scaled_h // 2 - 60
                surface.blit(scaled, (tx, ty))
        else:
            # Fallback: procedural text
            if self._title_alpha > 0:
                base_size = 64
                scaled_size = max(16, int(base_size * self._title_scale))
                font = pygame.font.Font(None, scaled_size)
                text = "TREAT STORM!"
                # Shadow
                shadow_raw = font.render(text, True, (0, 0, 0))
                shadow = shadow_raw.convert_alpha()
                shadow.set_alpha(self._title_alpha // 2)
                sx = (self.screen_width - shadow.get_width()) // 2 + 3
                sy = self.screen_height // 2 - shadow.get_height() // 2 - 60 + 3
                surface.blit(shadow, (sx, sy))

                main_raw = font.render(text, True, (255, 200, 50))
                main = main_raw.convert_alpha()
                main.set_alpha(self._title_alpha)
                mx = (self.screen_width - main.get_width()) // 2
                my = self.screen_height // 2 - main.get_height() // 2 - 60
                surface.blit(main, (mx, my))

    def _render_go(self, surface: pygame.Surface) -> None:
        """Render the 'GO!' sprite with alpha animation."""
        if self._go_alpha <= 0:
            return

        go_sprite = self._get_asset("title_go")
        if go_sprite:
            target_w = int(self.screen_width * 0.3)
            aspect = go_sprite.get_height() / go_sprite.get_width()
            target_h = int(target_w * aspect)
            scaled = pygame.transform.smoothscale(go_sprite, (target_w, target_h))
            scaled.set_alpha(self._go_alpha)
            gx = (self.screen_width - target_w) // 2
            gy = self.screen_height // 2 - target_h // 2 - 20
            surface.blit(scaled, (gx, gy))
        else:
            # Fallback: procedural text
            go_font = pygame.font.Font(None, 110)
            go_text_raw = go_font.render("GO!", True, (255, 230, 50))
            go_shadow_raw = go_font.render("GO!", True, (80, 60, 0))
            go_shadow = go_shadow_raw.convert_alpha()
            go_text = go_text_raw.convert_alpha()
            go_shadow.set_alpha(self._go_alpha)
            go_text.set_alpha(self._go_alpha)
            gx = (self.screen_width - go_text.get_width()) // 2
            gy = self.screen_height // 2 - go_text.get_height() // 2 - 20
            surface.blit(go_shadow, (gx + 4, gy + 4))
            surface.blit(go_text, (gx, gy))
