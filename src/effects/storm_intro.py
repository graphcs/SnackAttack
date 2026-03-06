"""Lightning + Treat Storm intro sequence for the Treat Attack game mode.

Plays a cinematic intro animation before gameplay begins:
  1. Clouds gathering — multi-layered volumetric clouds with internal turbulence,
     wind-driven rain particle system, and progressive sky darkening.
  2. Lightning strike — multiple successive bolts with forked branches, a ground-
     impact bloom, per-bolt screen shake, and realistic afterglow decay.
  3. Screen flicker — organic flicker with varied intensity, colour temperature
     shifts, and a final thunder-rumble screen shake.
  4. Dogs march — dog walks in from off-screen with footstep dust puffs, a dynamic
     shadow, wind-swept rain, and a dramatic "GO!" title slam.
"""

import pygame
import math
import random
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
    IntroPhase.CLOUDS_GATHER: 3.0,
    IntroPhase.LIGHTNING_STRIKE: 1.6,
    IntroPhase.SCREEN_FLICKER: 0.9,
    IntroPhase.DOGS_MARCH: 2.2,
}

# Sky gradient endpoints (clear -> stormy)
_SKY_CLEAR_TOP = (135, 206, 235)
_SKY_CLEAR_BOT = (100, 165, 210)
_SKY_STORM_TOP = (22, 22, 38)
_SKY_STORM_BOT = (12, 12, 22)

# Lightning palette
_BOLT_CORE = (230, 230, 255)
_BOLT_INNER_GLOW = (180, 190, 255)
_BOLT_OUTER_GLOW = (120, 130, 220)
_FLASH_TINT = (200, 210, 255)

# Cloud palette (dark storm clouds with subtle colour variation)
_CLOUD_DARK = (40, 42, 55)
_CLOUD_MID = (60, 62, 78)
_CLOUD_LIGHT = (85, 88, 105)
_CLOUD_HIGHLIGHT = (110, 115, 135)
_CLOUD_UNDERBELLY = (30, 30, 42)

# Rain
_RAIN_COLOR = (160, 175, 200)
_RAIN_HEAVY_COLOR = (130, 150, 180)


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
# Cloud (volumetric, multi-blob with turbulence)
# ---------------------------------------------------------------------------

class _Cloud:
    """An animated storm cloud with layered blobs and internal turbulence."""

    def __init__(self, x: float, y: float, width: float, height: float,
                 speed: float, layer: int, target_x: float = 0.0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.speed = speed
        self.layer = layer  # 0 = far back, 1 = mid, 2 = front
        self.target_x = target_x  # Final resting x when gathered
        self.turbulence_offset = random.uniform(0, math.pi * 2)
        self._blobs: List[Tuple[float, float, float, float]] = []  # (ox, oy, rx, ry)
        self._generate_blobs()

    def _generate_blobs(self) -> None:
        """Generate overlapping ellipses that form a realistic cloud mass."""
        count = random.randint(6, 12)
        for _ in range(count):
            # Cluster blobs toward the centre for a denser core
            ox = random.gauss(0, self.width * 0.22)
            oy = random.gauss(self.height * 0.05, self.height * 0.18)
            rx = random.uniform(self.width * 0.2, self.width * 0.42)
            ry = random.uniform(self.height * 0.3, self.height * 0.55)
            self._blobs.append((ox, oy, rx, ry))

        # Large base blob for flat bottom typical of cumulonimbus
        self._blobs.append(
            (0, self.height * 0.15, self.width * 0.45, self.height * 0.3)
        )

    def render(self, surface: pygame.Surface, alpha: int, time: float,
               lightning_flash: float = 0.0) -> None:
        """Render cloud with internal lighting variation.

        Args:
            surface: Target surface.
            alpha: Base opacity (0-255).
            time: Current elapsed time for turbulence animation.
            lightning_flash: 0.0-1.0 intensity of lightning illumination.
        """
        buf_w = int(self.width * 1.6)
        buf_h = int(self.height * 2.4)
        cloud_surf = pygame.Surface((buf_w, buf_h), pygame.SRCALPHA)
        cx, cy = buf_w // 2, buf_h // 2

        # Pick base colour by layer depth
        if self.layer == 0:
            base = _CLOUD_DARK
        elif self.layer == 1:
            base = _CLOUD_MID
        else:
            base = _CLOUD_LIGHT

        # Lightning illumination tints clouds white
        if lightning_flash > 0:
            base = _lerp_color(base, (200, 205, 220), lightning_flash * 0.6)

        for ox, oy, rx, ry in self._blobs:
            # Turbulence: slightly shift blobs over time
            turb = math.sin(
                time * 1.5 + self.turbulence_offset + ox * 0.01
            ) * 3.0
            blob_x = cx + ox + turb
            blob_y = cy + oy

            # Vary opacity per blob for depth illusion
            blob_alpha = max(0, min(255, alpha - random.randint(0, 30)))
            color = (*base, blob_alpha)

            rect = pygame.Rect(
                int(blob_x - rx), int(blob_y - ry),
                int(rx * 2), int(ry * 2)
            )
            pygame.draw.ellipse(cloud_surf, color, rect)

        # Top highlight (sun/ambient light from above)
        hl_alpha = min(alpha, 70 + int(lightning_flash * 80))
        highlight = (*_CLOUD_HIGHLIGHT, hl_alpha)
        pygame.draw.ellipse(
            cloud_surf, highlight,
            pygame.Rect(
                cx - int(self.width * 0.25),
                cy - int(self.height * 0.5),
                int(self.width * 0.5),
                int(self.height * 0.35),
            )
        )

        # Dark underbelly
        belly_alpha = min(alpha, 120)
        belly_color = (*_CLOUD_UNDERBELLY, belly_alpha)
        pygame.draw.ellipse(
            cloud_surf, belly_color,
            pygame.Rect(
                cx - int(self.width * 0.35),
                cy + int(self.height * 0.05),
                int(self.width * 0.7),
                int(self.height * 0.35),
            )
        )

        surface.blit(cloud_surf, (int(self.x - cx), int(self.y - cy)))


# ---------------------------------------------------------------------------
# Lightning bolt generator
# ---------------------------------------------------------------------------

def _generate_bolt(
    start: Tuple[float, float],
    end: Tuple[float, float],
    detail: int = 7,
    offset_scale: float = 90.0,
) -> List[Tuple[float, float]]:
    """Recursively generate a jagged bolt path (mid-point displacement)."""
    if detail <= 0:
        return [start, end]

    mid_x = (start[0] + end[0]) / 2 + random.uniform(-offset_scale, offset_scale)
    mid_y = (start[1] + end[1]) / 2 + random.uniform(
        -offset_scale * 0.25, offset_scale * 0.25
    )
    mid = (mid_x, mid_y)

    left = _generate_bolt(start, mid, detail - 1, offset_scale * 0.52)
    right = _generate_bolt(mid, end, detail - 1, offset_scale * 0.52)
    return left + right[1:]


def _generate_branches(
    bolt: List[Tuple[float, float]],
    branch_chance: float = 0.3,
    branch_length: float = 80.0,
) -> List[List[Tuple[float, float]]]:
    """Generate forked side-branches off the main bolt."""
    branches: List[List[Tuple[float, float]]] = []
    for i, point in enumerate(bolt):
        if i < 2 or i > len(bolt) - 3:
            continue
        if random.random() < branch_chance:
            # Branch angle biased downward
            angle = random.uniform(math.pi * 0.15, math.pi * 0.65)
            if random.random() < 0.5:
                angle = -angle
            length = random.uniform(branch_length * 0.3, branch_length)
            end = (
                point[0] + math.cos(angle) * length,
                point[1] + math.sin(angle) * length * 0.6 + length * 0.4,
            )
            branch = _generate_bolt(point, end, detail=3, offset_scale=18.0)
            branches.append(branch)
            # Occasional sub-branch
            if random.random() < 0.3 and len(branch) > 2:
                sub_start = branch[len(branch) // 2]
                sub_angle = angle + random.uniform(-0.4, 0.4)
                sub_len = length * 0.4
                sub_end = (
                    sub_start[0] + math.cos(sub_angle) * sub_len,
                    sub_start[1] + math.sin(sub_angle) * sub_len * 0.5
                    + sub_len * 0.3,
                )
                sub_branch = _generate_bolt(
                    sub_start, sub_end, detail=2, offset_scale=10.0
                )
                branches.append(sub_branch)
    return branches


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
        # Outer glow
        pygame.draw.circle(
            s, (*_BOLT_OUTER_GLOW, self.alpha // 3),
            (centre, centre), int(self.radius)
        )
        # Inner glow
        pygame.draw.circle(
            s, (*_BOLT_INNER_GLOW, self.alpha // 2),
            (centre, centre), int(self.radius * 0.5)
        )
        # Core
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
# StormIntroSequence
# ---------------------------------------------------------------------------

class StormIntroSequence:
    """Orchestrates the full Lightning + Treat Storm intro animation.

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

        # Clouds (3 layers)
        self._clouds: List[_Cloud] = []

        # Rain particles
        self._rain: List[_RainDrop] = []
        self._rain_intensity = 0.0  # 0..1, ramps up over time
        self._wind = 0.0  # horizontal wind for rain

        # Lightning (supports multiple sequential bolts)
        self._bolts: List[dict] = []
        self._pending_bolt_times: List[float] = []
        self._lightning_flash = 0.0  # global flash intensity 0..1

        # Screen shake
        self._shake = _ScreenShake()

        # Flicker
        self._flicker_flash = 0.0  # intensity 0..1
        self._flicker_index = 0
        self._flicker_pattern = [
            # (duration, intensity, color_temp_shift)
            (0.06, 0.9, 0.0),
            (0.04, 0.0, 0.0),
            (0.08, 1.0, 0.1),
            (0.05, 0.0, 0.0),
            (0.04, 0.6, -0.05),
            (0.06, 0.0, 0.0),
            (0.10, 0.8, 0.05),
            (0.03, 0.3, 0.0),
            (0.07, 0.0, 0.0),
            (0.12, 0.5, -0.1),
            (0.25, 0.0, 0.0),
        ]
        self._flicker_sub_timer = 0.0
        self._flicker_temp_shift = 0.0

        # Dog march — supports two dogs coming from opposite sides
        self._dog1_sprite: Optional[pygame.Surface] = None
        self._dog2_sprite: Optional[pygame.Surface] = None
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

        # Title / GO text
        self._title_scale = 0.0
        self._title_alpha = 0
        self._go_alpha = 0
        self._title_font: Optional[pygame.font.Font] = None
        self._go_font: Optional[pygame.font.Font] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        dog1_sprite: Optional[pygame.Surface] = None,
        dog2_sprite: Optional[pygame.Surface] = None,
        dog_ground_y: float = 650.0,
    ) -> None:
        """Begin the intro sequence.

        Args:
            dog1_sprite: Player 1 sprite (faces right, enters from left).
            dog2_sprite: Player 2 sprite (faces left, enters from right).
            dog_ground_y: Y coordinate for the dogs' ground level.
        """
        self.phase = IntroPhase.CLOUDS_GATHER
        self.phase_timer = 0.0
        self.global_timer = 0.0
        self.is_complete = False

        # Dog 1 enters from left, walks right toward ~35% of screen
        self._dog1_sprite = dog1_sprite
        self._dog1_start_x = -140.0
        self._dog1_target_x = self.screen_width * 0.28
        self._dog1_current_x = self._dog1_start_x
        self._last_step_x1 = self._dog1_start_x

        # Dog 2 enters from right, walks left toward ~65% of screen
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

        self._bolts.clear()
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
        self._title_font = pygame.font.Font(None, 64)
        self._go_font = pygame.font.Font(None, 110)

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
        self._update_rain(dt)
        self._update_bolts(dt)
        self._shake.update(dt)

        # Phase-specific
        handler = {
            IntroPhase.CLOUDS_GATHER: self._update_clouds,
            IntroPhase.LIGHTNING_STRIKE: self._update_lightning_phase,
            IntroPhase.SCREEN_FLICKER: self._update_flicker,
            IntroPhase.DOGS_MARCH: self._update_march,
        }.get(self.phase)
        if handler:
            handler(dt)

        # Advance phase
        phase_dur = _PHASE_DURATIONS.get(self.phase, 1.0)
        if self.phase_timer >= phase_dur:
            self._advance_phase()

    def _advance_phase(self) -> None:
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
            self.phase_timer = 0.0

            if self.phase == IntroPhase.LIGHTNING_STRIKE:
                # Schedule 2-3 bolts at staggered times
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

        # Render to a buffer so we can apply screen-shake
        buf = pygame.Surface(
            (self.screen_width, self.screen_height), pygame.SRCALPHA
        )

        # 1) Sky
        self._render_sky(buf)
        # 2) Ground
        self._render_ground(buf)
        # 3) Back-layer clouds
        self._render_clouds(buf, layers=(0,))
        # 4) Rain (behind mid/front clouds)
        self._render_rain(buf)
        # 5) Mid + front clouds
        self._render_clouds(buf, layers=(1, 2))
        # 6) Lightning bolts & blooms
        self._render_bolts(buf)
        # 7) Phase overlays (flicker, dog march)
        self._render_phase_overlay(buf)

        # Apply screen-shake offset
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
    # Phase: Clouds Gather
    # ------------------------------------------------------------------

    def _build_clouds(self) -> None:
        self._clouds.clear()
        w = self.screen_width

        # Layer 0 - far back (large, slow) — 4 clouds evenly spread
        layer0_count = 4
        for i in range(layer0_count):
            # Spread targets evenly across the screen with some jitter
            target_x = (w / (layer0_count + 1)) * (i + 1) + random.uniform(-40, 40)
            side = -1 if i % 2 == 0 else 1
            cx = side * (w * 0.7 + random.uniform(100, 300))  # start off-screen
            cy = random.uniform(self.screen_height * 0.02, self.screen_height * 0.12)
            cw = random.uniform(220, 340)
            ch = random.uniform(70, 120)
            spd = random.uniform(100, 170)
            self._clouds.append(
                _Cloud(cx, cy, cw, ch, spd * (-side), layer=0, target_x=target_x)
            )

        # Layer 1 - mid — 5 clouds evenly spread
        layer1_count = 5
        for i in range(layer1_count):
            target_x = (w / (layer1_count + 1)) * (i + 1) + random.uniform(-30, 30)
            side = -1 if i % 2 == 0 else 1
            cx = side * (w * 0.6 + random.uniform(80, 280))  # start off-screen
            cy = random.uniform(self.screen_height * 0.06, self.screen_height * 0.18)
            cw = random.uniform(160, 280)
            ch = random.uniform(55, 100)
            spd = random.uniform(150, 260)
            self._clouds.append(
                _Cloud(cx, cy, cw, ch, spd * (-side), layer=1, target_x=target_x)
            )

        # Layer 2 - front (smaller, fastest) — 5 clouds spread
        layer2_count = 5
        for i in range(layer2_count):
            target_x = (w / (layer2_count + 1)) * (i + 1) + random.uniform(-25, 25)
            side = -1 if i % 2 == 0 else 1
            cx = side * (w * 0.55 + random.uniform(60, 250))  # start off-screen
            cy = random.uniform(self.screen_height * 0.01, self.screen_height * 0.13)
            cw = random.uniform(120, 200)
            ch = random.uniform(40, 80)
            spd = random.uniform(200, 340)
            self._clouds.append(
                _Cloud(cx, cy, cw, ch, spd * (-side), layer=2, target_x=target_x)
            )

    def _update_clouds(self, dt: float) -> None:
        dur = _PHASE_DURATIONS[IntroPhase.CLOUDS_GATHER]
        t = min(self.phase_timer / dur, 1.0)
        eased = _ease_in_out(t)

        for cloud in self._clouds:
            # Move toward each cloud's own target position (not all to centre)
            diff = cloud.target_x - cloud.x
            approach_speed = abs(cloud.speed) * (1.0 + (1.0 - eased) * 1.5)
            if abs(diff) > 2.0:
                direction = 1.0 if diff > 0 else -1.0
                cloud.x += direction * approach_speed * dt
                # Don't overshoot
                if (direction > 0 and cloud.x > cloud.target_x) or \
                   (direction < 0 and cloud.x < cloud.target_x):
                    cloud.x = cloud.target_x
            else:
                cloud.x = _lerp(cloud.x, cloud.target_x, dt * 2.0)
            # Gentle vertical drift
            cloud.y += (
                math.sin(self.global_timer * 0.7 + cloud.turbulence_offset)
                * 3.0 * dt
            )

        # Ramp wind & rain gradually
        self._wind = _lerp(0, -60, eased)
        self._rain_intensity = _lerp(0.0, 0.4, eased)

    def _render_clouds(
        self, surface: pygame.Surface, layers: Tuple[int, ...] = (0, 1, 2)
    ) -> None:
        overall_t = min(self.progress * 1.4, 1.0)
        alpha = int(160 + 95 * overall_t)
        flash = self._lightning_flash

        for layer in layers:
            for cloud in self._clouds:
                if cloud.layer == layer:
                    cloud.render(
                        surface, alpha, self.global_timer,
                        lightning_flash=flash,
                    )

    # ------------------------------------------------------------------
    # Rain (always-running subsystem)
    # ------------------------------------------------------------------

    def _update_rain(self, dt: float) -> None:
        spawn_rate = self._rain_intensity * 350  # drops per second
        spawn_count = int(spawn_rate * dt)
        if random.random() < (spawn_rate * dt) % 1:
            spawn_count += 1

        ground_y = self._dog_ground_y + 64
        for _ in range(spawn_count):
            x = random.uniform(-30, self.screen_width + 30)
            y = random.uniform(-20, -5)
            self._rain.append(
                _RainDrop(x, y, self._wind, max(0.3, self._rain_intensity))
            )

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
    # Lightning bolts (always-running subsystem)
    # ------------------------------------------------------------------

    def _spawn_bolt(self) -> None:
        """Generate a new bolt and add it to active list."""
        start = (
            self.screen_width * random.uniform(0.2, 0.8),
            random.uniform(5, 50),
        )
        end = (
            start[0] + random.uniform(-120, 120),
            self._dog_ground_y + 50,
        )
        points = _generate_bolt(start, end, detail=7, offset_scale=95.0)
        branches = _generate_branches(
            points, branch_chance=0.35, branch_length=90.0
        )
        bloom = _GroundBloom(end[0], end[1] - 10)

        self._bolts.append({
            "points": points,
            "branches": branches,
            "alpha": 0,
            "bloom": bloom,
            "age": 0.0,
            "duration": random.uniform(0.5, 0.7),
        })
        self._shake.trigger(intensity=12.0, decay=7.0)
        self._lightning_flash = 1.0

    def _update_bolts(self, dt: float) -> None:
        # Decay global flash
        self._lightning_flash = max(0.0, self._lightning_flash - dt * 4.0)

        alive = []
        for bolt in self._bolts:
            bolt["age"] += dt
            t = bolt["age"] / bolt["duration"]
            # Flash-in -> hold -> fade
            if t < 0.1:
                bolt["alpha"] = int(255 * (t / 0.1))
            elif t < 0.35:
                bolt["alpha"] = 255
            else:
                bolt["alpha"] = int(255 * max(0.0, 1.0 - (t - 0.35) / 0.65))

            bolt["bloom"].update(dt)
            if bolt["alpha"] > 0 or bolt["bloom"].alive:
                alive.append(bolt)
        self._bolts = alive

    def _render_bolts(self, surface: pygame.Surface) -> None:
        """Render all active bolts with glow layers and bloom."""
        if not self._bolts:
            return

        # Global flash tint
        if self._lightning_flash > 0.02:
            flash_alpha = int(self._lightning_flash * 80)
            flash_surf = pygame.Surface(
                (self.screen_width, self.screen_height), pygame.SRCALPHA
            )
            flash_surf.fill((*_FLASH_TINT, flash_alpha))
            surface.blit(flash_surf, (0, 0))

        bolt_surf = pygame.Surface(
            (self.screen_width, self.screen_height), pygame.SRCALPHA
        )

        for bolt in self._bolts:
            alpha = bolt["alpha"]
            if alpha <= 0:
                bolt["bloom"].render(surface)
                continue

            pts = bolt["points"]
            branches = bolt["branches"]
            if len(pts) < 2:
                continue

            int_pts = [(int(p[0]), int(p[1])) for p in pts]

            # Outer glow (wide, soft)
            outer_col = (*_BOLT_OUTER_GLOW, int(alpha * 0.25))
            pygame.draw.lines(bolt_surf, outer_col, False, int_pts, 10)

            # Inner glow
            inner_col = (*_BOLT_INNER_GLOW, int(alpha * 0.55))
            pygame.draw.lines(bolt_surf, inner_col, False, int_pts, 5)

            # Core bolt (bright, thin)
            core_col = (*_BOLT_CORE, alpha)
            pygame.draw.lines(bolt_surf, core_col, False, int_pts, 2)

            # Branches
            for branch in branches:
                if len(branch) < 2:
                    continue
                b_pts = [(int(p[0]), int(p[1])) for p in branch]
                pygame.draw.lines(
                    bolt_surf,
                    (*_BOLT_INNER_GLOW, int(alpha * 0.4)),
                    False, b_pts, 3,
                )
                pygame.draw.lines(
                    bolt_surf,
                    (*_BOLT_CORE, int(alpha * 0.7)),
                    False, b_pts, 1,
                )

            # Ground bloom
            bolt["bloom"].render(bolt_surf)

        surface.blit(bolt_surf, (0, 0))

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
        # Colour temperature shift: positive = warmer, negative = cooler
        r_shift = int(self._flicker_temp_shift * 40)
        base_r = min(255, max(0, 255 + r_shift))
        base_b = min(255, max(0, 255 - r_shift))
        alpha = int(self._flicker_flash * 160)
        overlay.fill((base_r, 255, base_b, alpha))
        surface.blit(overlay, (0, 0))

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

        # Footstep dust puffs for both dogs
        step_dist = 28
        if abs(self._dog1_current_x - self._last_step_x1) >= step_dist and t < 0.85:
            foot_y = self._dog_ground_y + 58
            self._dust_puffs.append(
                _DustPuff(self._dog1_current_x + 20, foot_y)
            )
            self._last_step_x1 = self._dog1_current_x

        if abs(self._dog2_current_x - self._last_step_x2) >= step_dist and t < 0.85:
            foot_y = self._dog_ground_y + 58
            self._dust_puffs.append(
                _DustPuff(self._dog2_current_x + 40, foot_y)
            )
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
        # Offset the bob slightly so they aren't perfectly in-sync
        bob_y2 = math.sin(self._march_bob_timer * 14.0 + 1.0) * 3.5
        tilt2 = math.sin(self._march_bob_timer * 14.0 + 1.0 + math.pi * 0.5) * 1.5
        self._render_single_dog(
            surface, self._dog2_sprite, self._dog2_current_x,
            facing_right=False, bob_y=bob_y2, tilt=tilt2,
        )

        # "TREAT STORM!" title
        if self._title_alpha > 0 and self._title_font:
            text = "TREAT STORM!"
            base_size = 64
            scaled_size = max(16, int(base_size * self._title_scale))
            font = pygame.font.Font(None, scaled_size)

            # Shadow — use SRCALPHA surface to avoid set_alpha() issues on macOS SDL2 Metal
            shadow_raw = font.render(text, True, (0, 0, 0))
            shadow = shadow_raw.convert_alpha()
            shadow.set_alpha(self._title_alpha // 2)
            sx = (self.screen_width - shadow.get_width()) // 2 + 3
            sy = self.screen_height // 2 - shadow.get_height() // 2 - 60 + 3
            surface.blit(shadow, (sx, sy))

            # Main text (gold)
            main_raw = font.render(text, True, (255, 200, 50))
            main = main_raw.convert_alpha()
            main.set_alpha(self._title_alpha)
            mx = (self.screen_width - main.get_width()) // 2
            my = self.screen_height // 2 - main.get_height() // 2 - 60
            surface.blit(main, (mx, my))

        # "GO!" text
        if self._go_alpha > 0 and self._go_font:
            go_text_raw = self._go_font.render("GO!", True, (255, 230, 50))
            go_shadow_raw = self._go_font.render("GO!", True, (80, 60, 0))
            go_shadow = go_shadow_raw.convert_alpha()
            go_text = go_text_raw.convert_alpha()
            go_shadow.set_alpha(self._go_alpha)
            go_text.set_alpha(self._go_alpha)

            gx = (self.screen_width - go_text.get_width()) // 2
            gy = self.screen_height // 2 - go_text.get_height() // 2 - 20
            surface.blit(go_shadow, (gx + 4, gy + 4))
            surface.blit(go_text, (gx, gy))

    def _render_single_dog(
        self, surface: pygame.Surface, sprite: Optional[pygame.Surface],
        x: float, facing_right: bool, bob_y: float, tilt: float,
    ) -> None:
        """Render one dog with shadow, bob, and tilt."""
        # The grass is at _dog_ground_y + 64, so position dog's bottom there
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
            if not facing_right:
                frame = pygame.transform.flip(frame, True, False)
            if abs(tilt) > 0.3:
                frame = pygame.transform.rotate(frame, tilt)
            
            # Position so the dog's bottom is at the grass line
            # Add small downward offset to sit directly on grass
            sprite_height = frame.get_height()
            dog_y = grass_y - sprite_height + bob_y + 8
            
            surface.blit(
                frame,
                (int(x), int(dog_y)),
            )
        else:
            # No sprite provided — skip (no brown box fallback)
            pass

    # ------------------------------------------------------------------
    # Shared rendering helpers
    # ------------------------------------------------------------------

    def _render_sky(self, surface: pygame.Surface) -> None:
        """Gradient sky that darkens as the storm builds."""
        t = min(self.progress * 1.25, 1.0)
        top = _lerp_color(_SKY_CLEAR_TOP, _SKY_STORM_TOP, t)
        bot = _lerp_color(_SKY_CLEAR_BOT, _SKY_STORM_BOT, t)

        for y in range(self.screen_height):
            ratio = y / self.screen_height
            color = _lerp_color(top, bot, ratio)
            pygame.draw.line(surface, color, (0, y), (self.screen_width, y))

    def _render_ground(self, surface: pygame.Surface) -> None:
        ground_y = int(self._dog_ground_y) + 64
        t = min(self.progress * 1.2, 1.0)

        # Dirt darkens with storm
        dirt = _lerp_color((101, 67, 33), (50, 35, 18), t)
        pygame.draw.rect(
            surface, dirt,
            (0, ground_y, self.screen_width, self.screen_height - ground_y),
        )

        # Wet sheen on ground when raining
        if self._rain_intensity > 0.3:
            sheen_alpha = int(30 * self._rain_intensity)
            sheen = pygame.Surface((self.screen_width, 6), pygame.SRCALPHA)
            sheen.fill((150, 170, 200, sheen_alpha))
            surface.blit(sheen, (0, ground_y))

        # Grass strip
        grass = _lerp_color((34, 139, 34), (18, 70, 18), t)
        pygame.draw.rect(
            surface, grass, (0, ground_y - 4, self.screen_width, 8)
        )
