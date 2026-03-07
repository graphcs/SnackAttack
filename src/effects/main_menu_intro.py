"""Startup storm intro for the main menu banner area."""

import math
import os
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import pygame

from ..sprites.sprite_sheet_loader import SpriteSheetLoader


class _IntroPhase(Enum):
    CLOUD_ROLL_IN = auto()
    LIGHTNING = auto()
    DOGS_MARCH = auto()
    COMPLETE = auto()


_PHASE_DURATIONS = {
    _IntroPhase.CLOUD_ROLL_IN: 1.85,
    _IntroPhase.LIGHTNING: 1.15,
    _IntroPhase.DOGS_MARCH: 1.7,
}

_DOG_IDS = ("jazzy", "snowy")


def _get_asset_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(here))
    return os.path.join(project_root, "ui", "storm_intro")


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * _clamp(t, 0.0, 1.0)


def _lerp_color(
    color_a: Tuple[int, int, int], color_b: Tuple[int, int, int], t: float
) -> Tuple[int, int, int]:
    return tuple(int(_lerp(a, b, t)) for a, b in zip(color_a, color_b))


def _ease_out_cubic(t: float) -> float:
    t = _clamp(t, 0.0, 1.0)
    return 1.0 - pow(1.0 - t, 3)


def _ease_in_out(t: float) -> float:
    t = _clamp(t, 0.0, 1.0)
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - pow(-2.0 * t + 2.0, 3) / 2.0


@dataclass
class _DustPuff:
    x: float
    y: float
    radius: float = 4.0
    life: float = 0.0
    duration: float = 0.42

    @property
    def alive(self) -> bool:
        return self.life < self.duration

    def update(self, dt: float) -> None:
        self.life += dt
        t = _clamp(self.life / self.duration, 0.0, 1.0)
        self.radius = _lerp(4.0, 17.0, _ease_out_cubic(t))
        self.y -= 16.0 * dt

    def render(self, surface: pygame.Surface) -> None:
        t = _clamp(self.life / self.duration, 0.0, 1.0)
        alpha = int(150 * (1.0 - t))
        if alpha <= 0:
            return
        size = int(self.radius * 2 + 8)
        puff = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        pygame.draw.circle(puff, (128, 118, 112, alpha), (center, center), int(self.radius))
        pygame.draw.circle(
            puff,
            (170, 160, 152, max(0, alpha // 2)),
            (center - 3, center - 1),
            max(1, int(self.radius * 0.55)),
        )
        surface.blit(puff, (int(self.x - center), int(self.y - center)))


class _StormCloud:
    def __init__(
        self,
        sprite: pygame.Surface,
        start_x: float,
        target_x: float,
        y: float,
        layer: int,
        scale: float,
        sway_speed: float,
    ):
        width = max(1, int(sprite.get_width() * scale))
        height = max(1, int(sprite.get_height() * scale))
        self.sprite = pygame.transform.smoothscale(sprite, (width, height))
        self.start_x = start_x
        self.target_x = target_x
        self.x = start_x
        self.base_y = y
        self.y = y
        self.layer = layer
        self.sway_speed = sway_speed
        self.sway_phase = random.uniform(0.0, math.tau)
        self.sway_amount = random.uniform(6.0, 14.0) * (1.0 + layer * 0.25)

    def update(self, gather_t: float, clock: float) -> None:
        travel_t = _ease_in_out(min(1.0, gather_t * (1.15 + self.layer * 0.1)))
        self.x = _lerp(self.start_x, self.target_x, travel_t)
        self.y = self.base_y + math.sin(clock * self.sway_speed + self.sway_phase) * self.sway_amount

    def render(
        self,
        surface: pygame.Surface,
        storm_t: float,
        flash_t: float,
        silver_glow: Optional[pygame.Surface],
    ) -> None:
        if silver_glow and storm_t > 0.2:
            glow_w = int(self.sprite.get_width() * 1.18)
            glow_h = int(self.sprite.get_height() * (0.6 + 0.08 * self.layer))
            glow = pygame.transform.smoothscale(silver_glow, (glow_w, glow_h))
            glow_alpha = int((storm_t - 0.2) / 0.8 * 120 + flash_t * 110)
            glow.set_alpha(max(0, min(220, glow_alpha)))
            glow_x = int(self.x - (glow_w - self.sprite.get_width()) * 0.5)
            glow_y = int(self.y - glow_h * 0.18)
            surface.blit(glow, (glow_x, glow_y), special_flags=pygame.BLEND_PREMULTIPLIED)

        cloud = self.sprite.copy()
        tint = int(_lerp(176, 118, storm_t))
        cloud.fill((tint, tint, min(255, tint + 18), 255), special_flags=pygame.BLEND_RGBA_MULT)
        alpha = int(_lerp(96, 245, storm_t) + flash_t * 20)
        cloud.set_alpha(max(0, min(255, alpha)))
        surface.blit(cloud, (int(self.x), int(self.y)))


class MainMenuStormIntro:
    """High-impact startup sequence behind the main menu logo."""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.phase = _IntroPhase.CLOUD_ROLL_IN
        self.phase_timer = 0.0
        self.global_timer = 0.0
        self.is_complete = True

        self.band_rect = pygame.Rect(0, 0, 0, 0)
        self.logo_rect = pygame.Rect(0, 0, 0, 0)
        self.dog_ground_y = 0.0

        self._assets: Dict[str, Optional[pygame.Surface]] = {}
        self._load_assets()

        self._clouds: List[_StormCloud] = []
        self._lightning_bolts: List[dict] = []
        self._pending_bolt_times: List[float] = []
        self._lightning_flash = 0.0
        self._logo_glow = 0.0

        self._dog_frames_left: List[pygame.Surface] = []
        self._dog_frames_right: List[pygame.Surface] = []
        self._dog_left_x = 0.0
        self._dog_left_target_x = 0.0
        self._dog_right_x = 0.0
        self._dog_right_target_x = 0.0
        self._dog_stride_timer = 0.0
        self._last_left_puff_x = 0.0
        self._last_right_puff_x = 0.0
        self._dust_puffs: List[_DustPuff] = []

    def _load_assets(self) -> None:
        asset_dir = _get_asset_dir()
        for name in (
            "storm_cloud_large",
            "storm_cloud_medium",
            "storm_cloud_small",
            "lightning_bolt",
            "lightning_flash",
            "silver_lining_glow",
        ):
            path = os.path.join(asset_dir, f"{name}.png")
            try:
                self._assets[name] = (
                    pygame.image.load(path).convert_alpha() if os.path.exists(path) else None
                )
            except pygame.error:
                self._assets[name] = None

    def _get_asset(self, name: str) -> Optional[pygame.Surface]:
        return self._assets.get(name)

    def start(self, logo_rect: pygame.Rect) -> None:
        self.logo_rect = logo_rect.copy()
        padding_x = int(self.screen_width * 0.08)
        band_top = max(0, logo_rect.y - 28)
        band_height = min(int(self.screen_height * 0.44), logo_rect.height + 210)
        self.band_rect = pygame.Rect(padding_x, band_top, self.screen_width - padding_x * 2, band_height)
        self.dog_ground_y = min(self.screen_height * 0.5, self.band_rect.bottom + 34)

        self.phase = _IntroPhase.CLOUD_ROLL_IN
        self.phase_timer = 0.0
        self.global_timer = 0.0
        self.is_complete = False
        self._lightning_bolts.clear()
        self._pending_bolt_times.clear()
        self._lightning_flash = 0.0
        self._logo_glow = 0.0
        self._dust_puffs.clear()
        self._dog_stride_timer = 0.0

        self._build_clouds()
        self._build_dogs()

    def skip(self) -> None:
        self.phase = _IntroPhase.COMPLETE
        self.is_complete = True

    def update(self, dt: float) -> None:
        if self.is_complete:
            return

        self.phase_timer += dt
        self.global_timer += dt
        self._update_lightning(dt)

        if self.phase == _IntroPhase.CLOUD_ROLL_IN:
            self._update_cloud_roll_in()
        elif self.phase == _IntroPhase.LIGHTNING:
            self._update_lightning_phase()
        elif self.phase == _IntroPhase.DOGS_MARCH:
            self._update_dogs(dt)

        phase_duration = _PHASE_DURATIONS.get(self.phase)
        if phase_duration is not None and self.phase_timer >= phase_duration:
            self._advance_phase()

    def _advance_phase(self) -> None:
        if self.phase == _IntroPhase.CLOUD_ROLL_IN:
            self.phase = _IntroPhase.LIGHTNING
            self.phase_timer = 0.0
            self._pending_bolt_times = [0.04, 0.21, 0.46, 0.82]
            return
        if self.phase == _IntroPhase.LIGHTNING:
            self.phase = _IntroPhase.DOGS_MARCH
            self.phase_timer = 0.0
            return
        self.skip()

    def _build_clouds(self) -> None:
        self._clouds.clear()
        specs = [
            ("storm_cloud_large", 0, 4, 0.68, 0.82),
            ("storm_cloud_medium", 1, 5, 0.52, 1.04),
            ("storm_cloud_small", 2, 6, 0.38, 1.26),
        ]
        for asset_name, layer, count, base_scale, sway_speed in specs:
            sprite = self._get_asset(asset_name)
            if not sprite:
                continue
            for index in range(count):
                side = -1 if index % 2 == 0 else 1
                start_x = side * (self.band_rect.width + random.uniform(120, 280))
                target_x = (
                    (self.band_rect.width / max(count, 1)) * index
                    - sprite.get_width() * (base_scale * 0.33)
                    + random.uniform(-30, 30)
                )
                y = (
                    random.uniform(0.0, self.band_rect.height * 0.2)
                    + layer * self.band_rect.height * 0.06
                )
                scale = base_scale + random.uniform(-0.08, 0.07)
                self._clouds.append(
                    _StormCloud(sprite, start_x, target_x, y, layer, scale, sway_speed)
                )

    def _build_dogs(self) -> None:
        loader = SpriteSheetLoader()
        left_frames = loader.get_animation_frames(_DOG_IDS[0], "run", True)
        right_frames = loader.get_animation_frames(_DOG_IDS[1], "run", False)
        dog_size = int(min(156, max(118, self.screen_width * 0.12)))
        target_size = (dog_size, dog_size)

        self._dog_frames_left = [
            pygame.transform.smoothscale(frame, target_size) for frame in left_frames[:3]
        ]
        self._dog_frames_right = [
            pygame.transform.smoothscale(frame, target_size) for frame in right_frames[:3]
        ]

        self._dog_left_x = -dog_size - 60
        self._dog_left_target_x = self.logo_rect.x - dog_size * 0.35
        self._dog_right_x = self.screen_width + 60
        self._dog_right_target_x = self.logo_rect.right - dog_size * 0.62
        self._last_left_puff_x = self._dog_left_x
        self._last_right_puff_x = self._dog_right_x

    def _update_cloud_roll_in(self) -> None:
        gather_t = self.phase_timer / _PHASE_DURATIONS[_IntroPhase.CLOUD_ROLL_IN]
        for cloud in self._clouds:
            cloud.update(gather_t, self.global_timer)
        self._logo_glow = _lerp(0.0, 0.25, gather_t)

    def _update_lightning_phase(self) -> None:
        remaining = []
        for trigger_time in self._pending_bolt_times:
            if self.phase_timer >= trigger_time:
                self._spawn_bolt()
            else:
                remaining.append(trigger_time)
        self._pending_bolt_times = remaining

        for cloud in self._clouds:
            cloud.update(1.0, self.global_timer)

    def _spawn_bolt(self) -> None:
        bolt_sprite = self._get_asset("lightning_bolt")
        local_x = random.uniform(self.band_rect.width * 0.14, self.band_rect.width * 0.86)
        local_y = random.uniform(self.band_rect.height * 0.03, self.band_rect.height * 0.08)
        bolt_height = int(self.band_rect.height * random.uniform(0.72, 0.95))

        if bolt_sprite:
            scale = bolt_height / max(1, bolt_sprite.get_height())
            bolt_width = max(26, int(bolt_sprite.get_width() * scale))
            sprite = pygame.transform.smoothscale(bolt_sprite, (bolt_width, bolt_height))
        else:
            sprite = pygame.Surface((36, bolt_height), pygame.SRCALPHA)
            pygame.draw.line(sprite, (230, 235, 255, 255), (18, 0), (18, bolt_height), 3)

        self._lightning_bolts.append(
            {
                "sprite": sprite,
                "x": local_x - sprite.get_width() * 0.5,
                "y": local_y,
                "age": 0.0,
                "duration": random.uniform(0.25, 0.38),
                "offset": random.uniform(-12, 12),
            }
        )
        self._lightning_flash = 1.0
        self._logo_glow = 0.92

    def _update_lightning(self, dt: float) -> None:
        self._lightning_flash = max(0.0, self._lightning_flash - dt * 4.8)
        self._logo_glow = max(0.0, self._logo_glow - dt * 0.65)

        alive_bolts = []
        for bolt in self._lightning_bolts:
            bolt["age"] += dt
            if bolt["age"] < bolt["duration"]:
                alive_bolts.append(bolt)
        self._lightning_bolts = alive_bolts

    def _update_dogs(self, dt: float) -> None:
        t = _ease_in_out(self.phase_timer / _PHASE_DURATIONS[_IntroPhase.DOGS_MARCH])
        self._dog_left_x = _lerp(self._dog_left_x, self._dog_left_target_x, dt * 4.2 + t * 0.08)
        self._dog_right_x = _lerp(self._dog_right_x, self._dog_right_target_x, dt * 4.2 + t * 0.08)
        self._dog_stride_timer += dt * (1.0 + (1.0 - t) * 0.75)
        self._logo_glow = max(self._logo_glow, _lerp(0.16, 0.36, t))

        if abs(self._dog_left_x - self._last_left_puff_x) >= 26:
            self._dust_puffs.append(_DustPuff(self._dog_left_x + 32, self.dog_ground_y + 2))
            self._last_left_puff_x = self._dog_left_x
        if abs(self._dog_right_x - self._last_right_puff_x) >= 26:
            self._dust_puffs.append(_DustPuff(self._dog_right_x + 44, self.dog_ground_y + 2))
            self._last_right_puff_x = self._dog_right_x

        alive = []
        for puff in self._dust_puffs:
            puff.update(dt)
            if puff.alive:
                alive.append(puff)
        self._dust_puffs = alive

    def render_background(self, surface: pygame.Surface) -> None:
        if self.is_complete or self.band_rect.width <= 0 or self.band_rect.height <= 0:
            return

        band = pygame.Surface(self.band_rect.size, pygame.SRCALPHA)
        storm_t = self._storm_progress()

        self._render_band_gradient(band, storm_t)
        self._render_cloud_shadows(band, storm_t)
        self._render_cloud_layers(band, storm_t, layers=(0, 1, 2))
        self._render_bolts(band)

        surface.blit(band, self.band_rect.topleft)

    def render_foreground(self, surface: pygame.Surface) -> None:
        if self.is_complete:
            return

        if self._lightning_flash > 0.02:
            self._render_flash_overlay(surface)

        if self._logo_glow > 0.04:
            self._render_logo_glow(surface)

        for puff in self._dust_puffs:
            puff.render(surface)

        if self.phase == _IntroPhase.DOGS_MARCH:
            self._render_dog(surface, self._dog_frames_left, self._dog_left_x)
            self._render_dog(surface, self._dog_frames_right, self._dog_right_x)

    def _storm_progress(self) -> float:
        if self.phase == _IntroPhase.CLOUD_ROLL_IN:
            return _clamp(self.phase_timer / _PHASE_DURATIONS[_IntroPhase.CLOUD_ROLL_IN], 0.0, 1.0)
        if self.phase == _IntroPhase.LIGHTNING:
            return 1.0
        if self.phase == _IntroPhase.DOGS_MARCH:
            return 1.0
        return 0.0

    def _render_band_gradient(self, surface: pygame.Surface, storm_t: float) -> None:
        width, height = surface.get_size()
        top_clear = (124, 163, 210)
        top_storm = (22, 29, 44)
        bottom_clear = (87, 133, 186)
        bottom_storm = (13, 17, 28)
        vignette_alpha = int(_lerp(0, 140, storm_t))

        for y in range(height):
            ratio = y / max(1, height - 1)
            base = _lerp_color(top_clear, bottom_clear, ratio)
            storm = _lerp_color(top_storm, bottom_storm, ratio)
            color = _lerp_color(base, storm, storm_t)
            alpha = int(_lerp(12, 198, storm_t) * (1.0 - ratio * 0.14))
            pygame.draw.line(surface, (*color, alpha), (0, y), (width, y))

        if vignette_alpha > 0:
            pygame.draw.ellipse(
                surface,
                (8, 12, 20, vignette_alpha),
                (-width * 0.12, -height * 0.38, width * 1.24, height * 1.05),
            )

    def _render_cloud_shadows(self, surface: pygame.Surface, storm_t: float) -> None:
        if storm_t <= 0.05:
            return
        width, height = surface.get_size()
        shadow = pygame.Surface((width, height), pygame.SRCALPHA)
        for index in range(3):
            travel = (self.global_timer * (12 + index * 5) + index * 130) % (width + 280)
            shadow_x = int(travel - 220)
            shadow_y = int(height * (0.03 + index * 0.11))
            shadow_w = int(width * 0.42)
            shadow_h = int(height * (0.26 + index * 0.05))
            alpha = int((45 + index * 18) * storm_t)
            pygame.draw.ellipse(shadow, (14, 18, 28, alpha), (shadow_x, shadow_y, shadow_w, shadow_h))
        surface.blit(shadow, (0, 0))

    def _render_cloud_layers(
        self, surface: pygame.Surface, storm_t: float, layers: Tuple[int, ...]
    ) -> None:
        silver_glow = self._get_asset("silver_lining_glow")
        flash_t = self._lightning_flash
        for cloud in self._clouds:
            if cloud.layer not in layers:
                continue
            cloud.render(surface, storm_t, flash_t, silver_glow)

    def _render_bolts(self, surface: pygame.Surface) -> None:
        for bolt in self._lightning_bolts:
            t = bolt["age"] / max(0.001, bolt["duration"])
            if t < 0.22:
                alpha = int(255 * (t / 0.22))
            elif t < 0.56:
                alpha = 255
            else:
                alpha = int(255 * max(0.0, 1.0 - (t - 0.56) / 0.44))
            if alpha <= 0:
                continue
            sprite = bolt["sprite"].copy()
            sprite.set_alpha(alpha)
            surface.blit(sprite, (int(bolt["x"]), int(bolt["y"])))

            branch = sprite.copy()
            branch.set_alpha(max(0, alpha // 3))
            surface.blit(branch, (int(bolt["x"] + bolt["offset"]), int(bolt["y"] + 10)))

    def _render_flash_overlay(self, surface: pygame.Surface) -> None:
        flash = pygame.Surface(self.band_rect.size, pygame.SRCALPHA)
        flash_asset = self._get_asset("lightning_flash")
        alpha = int(self._lightning_flash * 110)
        if flash_asset:
            scaled = pygame.transform.smoothscale(flash_asset, self.band_rect.size)
            scaled.set_alpha(alpha)
            flash.blit(scaled, (0, 0))
        else:
            flash.fill((214, 226, 255, alpha))
        surface.blit(flash, self.band_rect.topleft)

    def _render_logo_glow(self, surface: pygame.Surface) -> None:
        glow = pygame.Surface(
            (self.logo_rect.width + 90, self.logo_rect.height + 70), pygame.SRCALPHA
        )
        glow_alpha = int(self._logo_glow * 135)
        pygame.draw.ellipse(
            glow,
            (184, 205, 255, glow_alpha),
            (0, 8, glow.get_width(), glow.get_height() - 16),
        )
        pygame.draw.ellipse(
            glow,
            (235, 240, 255, glow_alpha // 2),
            (22, 18, glow.get_width() - 44, glow.get_height() - 36),
        )
        surface.blit(glow, (self.logo_rect.x - 45, self.logo_rect.y - 28), special_flags=pygame.BLEND_PREMULTIPLIED)

    def _render_dog(
        self, surface: pygame.Surface, frames: List[pygame.Surface], x: float
    ) -> None:
        if not frames:
            return
        frame = frames[int(self._dog_stride_timer * 10.0) % len(frames)]
        bob = math.sin(self._dog_stride_timer * 12.0 + x * 0.01) * 4.0
        y = self.dog_ground_y - frame.get_height() + bob
        shadow = pygame.Surface((80, 18), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 72), (0, 0, 80, 18))
        surface.blit(shadow, (int(x + 24), int(self.dog_ground_y + 2)))
        surface.blit(frame, (int(x), int(y)))