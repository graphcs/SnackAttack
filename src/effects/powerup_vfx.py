"""Power-up visual effects system.

Provides visually striking effects for active power-ups:
  - Wings overlay (Red Bull boost)
  - Speed streak / afterimage trails (speed boost & boost)
  - Pulsing aura glow per effect type
  - Floating status indicator with timer bar
  - Pickup flash ring on collection
"""

import pygame
import math
import random
from typing import Dict, Any, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def _clamp(v: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Wings Effect  (Red Bull / boost)
# ---------------------------------------------------------------------------

class WingsEffect:
    """Sprite-based angel wings rendered behind the player. Falls back to procedural if sprites unavailable."""

    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg
        self.time = 0.0
        self.trail_particles: List[Dict[str, float]] = []
        self._wing_sprites: Dict[str, pygame.Surface] = {}  # Cached wing sprites
        self._try_load_sprites()

    # -- public api ----------------------------------------------------------

    def update(self, dt: float, active: bool, player_center: Tuple[float, float],
               facing_right: bool, is_flying: bool = False) -> None:
        self.time += dt

        if active and self.cfg.get("trail_particles", True):
            # More particles during active flight
            base_rate = self.cfg.get("trail_particle_rate", 3)
            rate = base_rate * 3 if is_flying else base_rate
            cx, cy = player_center
            for _ in range(rate):
                self.trail_particles.append({
                    "x": cx + random.uniform(-10, 10),
                    "y": cy + random.uniform(-5, 15),
                    "vy": random.uniform(-50, -25),
                    "vx": random.uniform(-12, 12),
                    "life": self.cfg.get("trail_particle_lifetime", 0.6),
                    "max_life": self.cfg.get("trail_particle_lifetime", 0.6),
                    "size": random.uniform(3, 7),
                })

        alive: List[Dict[str, float]] = []
        for p in self.trail_particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= dt
            if p["life"] > 0:
                alive.append(p)
        self.trail_particles = alive

    # -- internals -----------------------------------------------------------

    def _try_load_sprites(self) -> None:
        """Attempt to load wing sprites from disk. No-op if unavailable."""
        try:
            import os
            # Try multiple possible paths to find wings directory
            possible_paths = [
                # Path relative to this file (src/effects/powerup_vfx.py)
                os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "Sprite sheets", "wings"
                ),
                # Try current working directory
                os.path.join(os.getcwd(), "Sprite sheets", "wings"),
            ]
            
            wings_dir = None
            for path in possible_paths:
                if os.path.exists(path):
                    wings_dir = path
                    break
            
            if not wings_dir:
                return  # Silent fallback to procedural
                
            # Load wing sprites
            for frame in ["up", "down"]:
                frame_path = os.path.join(wings_dir, f"wing_{frame}.png")
                if os.path.exists(frame_path):
                    sprite = pygame.image.load(frame_path).convert_alpha()
                    # Scale to appropriate size
                    target_w = self.cfg.get("wing_width", 38) * 2
                    target_h = self.cfg.get("wing_height", 50) * 2
                    sprite = pygame.transform.scale(sprite, (target_w, target_h))
                    self._wing_sprites[frame] = sprite
        except Exception as e:
            pass  # Silently fall back to procedural if sprites unavailable

    # -- public api ----------------------------------------------------------

    def render(self, surface: pygame.Surface, render_cx: int, render_cy: int,
               sprite_w: int, sprite_h: int, facing_right: bool,
               arena_left: float, arena_top: float, offset: Tuple[int, int],
               is_flying: bool = False) -> None:
        """Draw wings (sprite-based or procedural) + golden trail behind the player."""
        base_flap_speed = self.cfg.get("flap_speed", 4.0)
        base_flap_amp = self.cfg.get("flap_amplitude", 18)

        # Enhanced flap during active flight
        if is_flying:
            flap_speed = base_flap_speed * 1.6
            flap_amp = base_flap_amp * 1.4
        else:
            flap_speed = base_flap_speed
            flap_amp = base_flap_amp

        # Flap offset via sine wave to select frame
        flap = math.sin(self.time * flap_speed * math.pi) * flap_amp
        frame_key = "up" if flap > 0 else "down"

        # Try sprite-based rendering first
        if self._wing_sprites:
            self._render_sprite_wings(surface, render_cx, render_cy,
                                      sprite_w, sprite_h, facing_right, frame_key)
        else:
            # Fall back to procedural
            self._render_procedural_wings(surface, render_cx, render_cy,
                                          sprite_w, sprite_h, facing_right, flap)

        # Draw golden trail particles (same for both modes)
        self._render_trail_particles(surface, arena_left, arena_top, offset)

        # Stronger golden glow aura during active flight
        if is_flying:
            self._render_flight_glow(surface, render_cx, render_cy, sprite_w, sprite_h)

    def _render_flight_glow(self, surface: pygame.Surface,
                            cx: int, cy: int, sw: int, sh: int) -> None:
        """Draw a bright golden glow behind the dog while flying."""
        pulse = math.sin(self.time * 4.0) * 0.15 + 0.85
        radius = int(max(sw, sh) * 0.7 * pulse)
        glow_size = radius * 2 + 4
        glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        gc = glow_size // 2
        # Outer soft gold glow
        pygame.draw.circle(glow_surf, (255, 215, 80, 35), (gc, gc), radius)
        # Inner brighter core
        pygame.draw.circle(glow_surf, (255, 230, 120, 55), (gc, gc), int(radius * 0.55))
        surface.blit(glow_surf, (cx - gc, cy - gc))

    def _render_sprite_wings(self, surface: pygame.Surface, render_cx: int, render_cy: int,
                             sprite_w: int, sprite_h: int, facing_right: bool,
                             frame_key: str) -> None:
        """Render sprite-based wings attached to the dog."""
        if frame_key not in self._wing_sprites:
            return

        wing_sprite = self._wing_sprites[frame_key]
        wing_w = wing_sprite.get_width()
        wing_h = wing_sprite.get_height()

        # Shoulder anchor tuned so wings emerge from upper torso/back.
        shoulder_y = render_cy + int(sprite_h * 0.05)
        for side in (-1, 1):
            wing_x = render_cx + side * int(sprite_w * 0.24)
            wing_y = shoulder_y

            # Flip left wing sprite
            if side == -1:
                wing = pygame.transform.flip(wing_sprite, True, False)
            else:
                wing = wing_sprite

            # Angle wings so roots point into torso and feathers open outward.
            base_angle = 5 if frame_key == "down" else 12
            wing = pygame.transform.rotate(wing, -side * base_angle)
            wing_w = wing.get_width()
            wing_h = wing.get_height()

            # Fade inner edge (wing root) so it visually blends into dog body.
            wing = self._apply_root_fade(wing, side)

            # Push wing root a bit into torso so sprite appears attached, not floating.
            root_inset = int(sprite_w * 0.12)
            draw_x = wing_x - wing_w // 2 + (-root_inset if side == -1 else root_inset)
            draw_y = wing_y - int(wing_h * 0.45)
            surface.blit(wing, (draw_x, draw_y))

    def _apply_root_fade(self, wing: pygame.Surface, side: int) -> pygame.Surface:
        """Fade alpha near body-side edge so wing appears to emerge from torso."""
        width, height = wing.get_size()
        fade_width = max(12, int(width * 0.32))

        mask = pygame.Surface((width, height), pygame.SRCALPHA)
        mask.fill((255, 255, 255, 255))

        if side == 1:
            # Right wing root is on left edge.
            for x in range(fade_width):
                alpha = int(255 * (x / max(1, fade_width - 1)))
                pygame.draw.line(mask, (255, 255, 255, alpha), (x, 0), (x, height))
        else:
            # Left wing root is on right edge.
            for x in range(fade_width):
                alpha = int(255 * (x / max(1, fade_width - 1)))
                target_x = width - 1 - x
                pygame.draw.line(mask, (255, 255, 255, alpha), (target_x, 0), (target_x, height))

        faded = wing.copy()
        faded.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return faded

    def render_attachment_overlay(self, surface: pygame.Surface,
                                  render_x: int, render_y: int,
                                  sprite_w: int, sprite_h: int,
                                  facing_right: bool) -> None:
        """Draw front overlay where wings meet the dog body for a realistic attachment look."""
        if not self._wing_sprites:
            return

        center_x = render_x + sprite_w // 2
        shoulder_y = render_y + int(sprite_h * 0.44)

        for side in (-1, 1):
            joint_x = center_x + side * int(sprite_w * 0.20)
            joint_y = shoulder_y

            # Body socket shadow: makes wing root look embedded in torso.
            socket_shadow = pygame.Surface((30, 18), pygame.SRCALPHA)
            pygame.draw.ellipse(socket_shadow, (12, 22, 35, 120), socket_shadow.get_rect())
            surface.blit(socket_shadow, (joint_x - 15, joint_y - 8))

            # Feather root tuft (front edge): visually overlaps body for attachment illusion.
            tuft = pygame.Surface((26, 20), pygame.SRCALPHA)
            pygame.draw.ellipse(tuft, (215, 248, 255, 175), (4, 5, 18, 10))
            pygame.draw.ellipse(tuft, (130, 210, 255, 140), (2, 7, 22, 9), 1)
            pygame.draw.ellipse(tuft, (255, 255, 255, 90), (7, 6, 10, 4))
            if side == -1:
                tuft = pygame.transform.flip(tuft, True, False)
            surface.blit(tuft, (joint_x - 13, joint_y - 10))

    def _render_procedural_wings(self, surface: pygame.Surface, render_cx: int, render_cy: int,
                                 sprite_w: int, sprite_h: int, facing_right: bool, flap: float) -> None:
        """Fallback procedural wing rendering (original code)."""
        color = tuple(self.cfg.get("color", [255, 215, 80]))
        glow = tuple(self.cfg.get("glow_color", [255, 240, 150]))
        opacity = self.cfg.get("opacity", 180)
        w = self.cfg.get("wing_width", 38)
        h = self.cfg.get("wing_height", 50)
        feathers = self.cfg.get("feather_count", 5)

        # Draw two wings (left and right of sprite centre)
        for side in (-1, 1):
            # Anchor at shoulder area
            wx = render_cx + side * (sprite_w // 2 - 8)
            wy = render_cy - 4

            wing_surf = pygame.Surface((w * 2, h * 2), pygame.SRCALPHA)
            cx_local = w
            cy_local = h

            # Outer glow ellipse
            glow_rect = pygame.Rect(
                cx_local - w - 4, cy_local - h // 2 - 4 + int(flap * 0.5),
                (w + 4) * 2, h + 8
            )
            glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(glow_surf, (*glow, opacity // 3), glow_surf.get_rect())
            wing_surf.blit(glow_surf, glow_rect.topleft)

            # Main wing ellipse
            main_rect = pygame.Rect(
                cx_local - w, cy_local - h // 2 + int(flap * 0.5),
                w * 2, h
            )
            pygame.draw.ellipse(wing_surf, (*color, opacity), main_rect)

            # Feather lines radiating outward
            for i in range(feathers):
                frac = (i + 1) / (feathers + 1)
                angle = math.radians(-60 + 120 * frac + flap * 0.4)
                fx = cx_local + side * int(math.cos(angle) * w * 0.85)
                fy = cy_local + int(math.sin(angle) * h * 0.4) + int(flap * 0.3)
                pygame.draw.line(
                    wing_surf, (*glow, opacity),
                    (cx_local, cy_local + int(flap * 0.3)),
                    (fx, fy), 2
                )

            # Flip wing for correct side
            if side == -1:
                wing_surf = pygame.transform.flip(wing_surf, True, False)

            surface.blit(wing_surf, (wx - w, wy - h))

    def _render_trail_particles(self, surface: pygame.Surface,
                                arena_left: float, arena_top: float,
                                offset: Tuple[int, int]) -> None:
        """Draw golden trail particles."""
        glow = tuple(self.cfg.get("glow_color", [255, 240, 150]))

        for p in self.trail_particles:
            px = int(p["x"] - arena_left + offset[0])
            py = int(p["y"] - arena_top + offset[1])
            frac = p["life"] / p["max_life"]
            alpha = int(200 * frac)
            size = max(1, int(p["size"] * frac))
            ps = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(ps, (*glow, alpha), (size, size), size)
            surface.blit(ps, (px - size, py - size))


# ---------------------------------------------------------------------------
# Speed Streak / Afterimage Effect
# ---------------------------------------------------------------------------

class SpeedStreakEffect:
    """Motion-blur streaks, speed particles and ghost afterimages."""

    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg
        self.streaks: List[Dict[str, float]] = []
        self.particles: List[Dict[str, float]] = []
        self.afterimage_positions: List[Tuple[float, float, float]] = []
        self._afterimage_timer = 0.0

    # -- public api ----------------------------------------------------------

    def update(self, dt: float, active: bool, effect_type: str,
               player_x: float, player_y: float,
               player_w: int, player_h: int,
               facing_right: bool) -> None:
        if active:
            self._spawn_streaks(dt, effect_type, player_x, player_y,
                                player_w, player_h, facing_right)
            self._spawn_particles(dt, effect_type, player_x, player_y,
                                  player_w, player_h, facing_right)
            self._record_afterimage(dt, player_x, player_y)

        self._tick(dt)

    def render_behind(self, surface: pygame.Surface, sprite: Optional[pygame.Surface],
                      render_x: int, render_y: int,
                      arena_left: float, arena_top: float,
                      offset: Tuple[int, int]) -> None:
        """Draw afterimages + streaks behind the sprite."""
        afterimage_count = self.cfg.get("afterimage_count", 3)
        base_alpha = self.cfg.get("afterimage_base_alpha", 90)

        # Afterimage ghosts
        if sprite is not None and self.afterimage_positions:
            step = max(1, len(self.afterimage_positions) // afterimage_count)
            for idx in range(0, min(len(self.afterimage_positions), afterimage_count * step), step):
                ax, ay, age = self.afterimage_positions[idx]
                ix = int(ax - arena_left + offset[0])
                iy = int(ay - arena_top + offset[1])
                fade = max(0, base_alpha - int(age * 300))
                if fade <= 0:
                    continue
                ghost = sprite.copy()
                ghost.set_alpha(fade)
                surface.blit(ghost, (ix, iy))

        # Streaks
        for s in self.streaks:
            sx = int(s["x"] - arena_left + offset[0])
            sy = int(s["y"] - arena_top + offset[1])
            alpha = _clamp(int(255 * (s["life"] / s["max_life"])))
            length = int(s["length"])
            color = (
                _clamp(int(s["cr"])),
                _clamp(int(s["cg"])),
                _clamp(int(s["cb"])),
                alpha,
            )
            ls = pygame.Surface((length, 4), pygame.SRCALPHA)
            pygame.draw.line(ls, color, (0, 2), (length, 2), 3)
            surface.blit(ls, (sx, sy - 2))

    def render_front(self, surface: pygame.Surface,
                     arena_left: float, arena_top: float,
                     offset: Tuple[int, int]) -> None:
        """Draw speed particles in front of the sprite."""
        for p in self.particles:
            px = int(p["x"] - arena_left + offset[0])
            py = int(p["y"] - arena_top + offset[1])
            frac = p["life"] / p["max_life"]
            alpha = _clamp(int(220 * frac))
            size = max(1, int(p["size"] * frac))
            color = (
                _clamp(int(p["cr"])),
                _clamp(int(p["cg"])),
                _clamp(int(p["cb"])),
                alpha,
            )
            ps = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(ps, color, (size, size), size)
            surface.blit(ps, (px - size, py - size))

    # -- internals -----------------------------------------------------------

    def _spawn_streaks(self, dt: float, effect_type: str,
                       px: float, py: float, pw: int, ph: int,
                       facing_right: bool) -> None:
        rate = self.cfg.get("streak_rate", 3)
        lifetime = self.cfg.get("streak_lifetime", 0.25)
        w_lo, w_hi = self.cfg.get("streak_width_range", [40, 80])
        color_key = "streak_color_boost" if effect_type == "boost" else "streak_color_speed"
        cr, cg, cb = self.cfg.get(color_key, [100, 200, 255])

        for _ in range(rate):
            if facing_right:
                sx = px - 10
            else:
                sx = px + pw + 10
            self.streaks.append({
                "x": sx,
                "y": py + random.uniform(20, ph - 20),
                "length": random.uniform(w_lo, w_hi),
                "life": lifetime,
                "max_life": lifetime,
                "facing_right": facing_right,
                "cr": cr + random.uniform(-20, 20),
                "cg": cg + random.uniform(-20, 20),
                "cb": cb + random.uniform(-20, 20),
            })

    def _spawn_particles(self, dt: float, effect_type: str,
                         px: float, py: float, pw: int, ph: int,
                         facing_right: bool) -> None:
        rate = self.cfg.get("particle_rate", 5)
        lifetime = self.cfg.get("particle_lifetime", 0.4)
        s_lo, s_hi = self.cfg.get("particle_size_range", [3, 7])
        color_key = "streak_color_boost" if effect_type == "boost" else "streak_color_speed"
        cr, cg, cb = self.cfg.get(color_key, [100, 200, 255])

        for _ in range(rate):
            # Particles spray behind the dog
            if facing_right:
                start_x = px - random.uniform(0, 20)
            else:
                start_x = px + pw + random.uniform(0, 20)
            self.particles.append({
                "x": start_x,
                "y": py + random.uniform(10, ph - 10),
                "vx": (-1 if facing_right else 1) * random.uniform(100, 250),
                "vy": random.uniform(-40, 40),
                "life": lifetime,
                "max_life": lifetime,
                "size": random.uniform(s_lo, s_hi),
                "cr": cr + random.uniform(-30, 30),
                "cg": cg + random.uniform(-30, 30),
                "cb": cb + random.uniform(-30, 30),
            })

    def _record_afterimage(self, dt: float, px: float, py: float) -> None:
        spacing = self.cfg.get("afterimage_spacing", 22)
        self._afterimage_timer += dt
        if self._afterimage_timer >= 0.03:  # ~33 FPS sampling
            self._afterimage_timer = 0.0
            self.afterimage_positions.append((px, py, 0.0))
        # Trim old positions
        max_count = self.cfg.get("afterimage_count", 3) * 6
        if len(self.afterimage_positions) > max_count:
            self.afterimage_positions = self.afterimage_positions[-max_count:]

    def _tick(self, dt: float) -> None:
        # Age afterimages
        self.afterimage_positions = [
            (x, y, age + dt) for x, y, age in self.afterimage_positions
            if age + dt < 0.5
        ]
        # Streaks
        alive: List[Dict[str, float]] = []
        for s in self.streaks:
            s["life"] -= dt
            if s["facing_right"]:
                s["x"] -= 500 * dt
            else:
                s["x"] += 500 * dt
            if s["life"] > 0:
                alive.append(s)
        self.streaks = alive
        # Particles
        palive: List[Dict[str, float]] = []
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= dt
            if p["life"] > 0:
                palive.append(p)
        self.particles = palive


# ---------------------------------------------------------------------------
# Pulsing Aura / Glow Ring
# ---------------------------------------------------------------------------

class AuraEffect:
    """Coloured pulsing aura ring + orbiting sparkles around the player."""

    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg
        self.time = 0.0

    def update(self, dt: float) -> None:
        self.time += dt

    def render(self, surface: pygame.Surface, render_cx: int, render_cy: int,
               sprite_w: int, sprite_h: int, effect_type: str) -> None:
        colors_map: Dict[str, List[int]] = self.cfg.get("colors", {})
        base_color = tuple(colors_map.get(effect_type, [255, 255, 255]))

        pulse_speed = self.cfg.get("pulse_speed", 3.0)
        base_r = max(sprite_w, sprite_h) // 2 + self.cfg.get("base_radius_padding", 15)
        pulse_amp = self.cfg.get("pulse_amplitude", 8)
        base_alpha = self.cfg.get("base_alpha", 50)
        ring_w = self.cfg.get("ring_width", 3)

        pulse = math.sin(self.time * pulse_speed * math.pi)
        radius = int(base_r + pulse * pulse_amp)
        alpha = _clamp(int(base_alpha + pulse * 20))

        # Glow fill
        glow_size = radius * 2 + 4
        glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        gc = glow_size // 2
        pygame.draw.circle(glow_surf, (*base_color, alpha // 2), (gc, gc), radius)
        surface.blit(glow_surf, (render_cx - gc, render_cy - gc))

        # Ring outline
        ring_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        pygame.draw.circle(ring_surf, (*base_color, alpha), (gc, gc), radius, ring_w)
        surface.blit(ring_surf, (render_cx - gc, render_cy - gc))

        # Orbiting sparkles
        sparkle_count = self.cfg.get("sparkle_count", 8)
        sparkle_speed = self.cfg.get("sparkle_speed", 2.5)
        sparkle_size = self.cfg.get("sparkle_size", 4)

        for i in range(sparkle_count):
            angle = self.time * sparkle_speed + (2 * math.pi * i / sparkle_count)
            sx = render_cx + int(math.cos(angle) * radius)
            sy = render_cy + int(math.sin(angle) * (radius * 0.7))
            spark_alpha = _clamp(int(200 + 55 * math.sin(angle * 3)))
            ss = pygame.Surface((sparkle_size * 2, sparkle_size * 2), pygame.SRCALPHA)
            pygame.draw.circle(ss, (*base_color, spark_alpha),
                               (sparkle_size, sparkle_size), sparkle_size)
            surface.blit(ss, (sx - sparkle_size, sy - sparkle_size))


# ---------------------------------------------------------------------------
# Status Indicator  (icon + timer bar above the dog)
# ---------------------------------------------------------------------------

class StatusIndicator:
    """Floating power-up icon and countdown bar above the player."""

    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg
        self.time = 0.0
        self._icon_cache: Dict[str, pygame.Surface] = {}

    def update(self, dt: float) -> None:
        self.time += dt

    def render(self, surface: pygame.Surface, render_cx: int, render_top: int,
               effect_type: str, time_remaining: float, duration: float) -> None:
        bar_w = self.cfg.get("bar_width", 50)
        bar_h = self.cfg.get("bar_height", 6)
        bar_oy = self.cfg.get("bar_offset_y", -12)
        icon_size = self.cfg.get("icon_size", 24)
        icon_oy = self.cfg.get("icon_offset_y", -38)
        bob_speed = self.cfg.get("icon_bob_speed", 2.0)
        bob_amp = self.cfg.get("icon_bob_amplitude", 3)

        bob = math.sin(self.time * bob_speed * math.pi) * bob_amp

        # Timer bar
        frac = max(0.0, min(1.0, time_remaining / max(duration, 0.01)))
        bar_x = render_cx - bar_w // 2
        bar_y = render_top + bar_oy

        # Background
        bg = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 140), (0, 0, bar_w, bar_h), border_radius=3)
        surface.blit(bg, (bar_x, bar_y))

        # Fill
        fill_w = max(1, int(bar_w * frac))
        color = self._effect_color(effect_type)
        fill = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(fill, (*color, 220), (0, 0, fill_w, bar_h), border_radius=3)
        surface.blit(fill, (bar_x, bar_y))

        # Icon above bar
        icon = self._get_icon(effect_type, icon_size)
        ix = render_cx - icon_size // 2
        iy = render_top + icon_oy + int(bob)
        surface.blit(icon, (ix, iy))

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _effect_color(effect_type: str) -> Tuple[int, int, int]:
        return {
            "boost": (80, 160, 255),
            "speed_boost": (255, 200, 80),
            "invincibility": (255, 255, 200),
            "chaos": (255, 60, 60),
            "slow": (60, 180, 60),
        }.get(effect_type, (200, 200, 200))

    def _get_icon(self, effect_type: str, size: int) -> pygame.Surface:
        if effect_type in self._icon_cache:
            return self._icon_cache[effect_type]

        icon = pygame.Surface((size, size), pygame.SRCALPHA)
        color = self._effect_color(effect_type)
        half = size // 2

        if effect_type == "boost":
            # Wing icon
            pygame.draw.ellipse(icon, (*color, 220), (2, half - 6, half - 2, 12))
            pygame.draw.ellipse(icon, (*color, 220), (half, half - 6, half - 2, 12))
            pygame.draw.circle(icon, (255, 255, 255, 200), (half, half), 3)
        elif effect_type == "speed_boost":
            # Lightning bolt
            pts = [(half - 2, 2), (half - 6, half), (half - 1, half),
                   (half + 2, size - 2), (half + 6, half), (half + 1, half)]
            pygame.draw.polygon(icon, (*color, 220), pts)
        elif effect_type == "invincibility":
            # Shield
            pygame.draw.polygon(icon, (*color, 220), [
                (half, 3), (size - 3, half - 4), (size - 5, size - 5),
                (half, size - 2), (5, size - 5), (3, half - 4)
            ])
        elif effect_type == "chaos":
            # Spiral / swirl
            for a in range(0, 360, 30):
                r = (a / 360) * (half - 2)
                px = half + int(math.cos(math.radians(a)) * r)
                py = half + int(math.sin(math.radians(a)) * r)
                pygame.draw.circle(icon, (*color, 200), (px, py), 2)
        elif effect_type == "slow":
            # Snail / clock
            pygame.draw.circle(icon, (*color, 200), (half, half), half - 2, 2)
            pygame.draw.line(icon, (*color, 220), (half, half), (half, 5), 2)
            pygame.draw.line(icon, (*color, 220), (half, half), (size - 6, half), 2)

        self._icon_cache[effect_type] = icon
        return icon


# ---------------------------------------------------------------------------
# Pickup Flash Ring
# ---------------------------------------------------------------------------

class PickupFlash:
    """Expanding ring flash when a power-up is collected."""

    def __init__(self, cfg: Dict[str, Any], x: float, y: float,
                 color: Tuple[int, int, int]) -> None:
        self.cfg = cfg
        self.x = x
        self.y = y
        self.color = color
        self.duration = cfg.get("duration", 0.3)
        self.time = 0.0
        self.alive = True

    def update(self, dt: float) -> None:
        self.time += dt
        if self.time >= self.duration:
            self.alive = False

    def render(self, surface: pygame.Surface, arena_left: float, arena_top: float,
               offset: Tuple[int, int]) -> None:
        if not self.alive:
            return
        frac = self.time / self.duration
        max_r = self.cfg.get("ring_max_radius", 60)
        max_alpha = self.cfg.get("max_alpha", 80)

        radius = int(frac * max_r)
        alpha = _clamp(int(max_alpha * (1.0 - frac)))

        rx = int(self.x - arena_left + offset[0])
        ry = int(self.y - arena_top + offset[1])

        size = radius * 2 + 4
        if size < 4:
            return
        ring = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        pygame.draw.circle(ring, (*self.color, alpha), (center, center), radius, 3)
        pygame.draw.circle(ring, (*self.color, alpha // 2), (center, center), radius)
        surface.blit(ring, (rx - center, ry - center))


# ---------------------------------------------------------------------------
# Snack Glow (makes power-up snacks visually obvious)
# ---------------------------------------------------------------------------

class SnackGlow:
    """Pulsing glow + orbiting sparkles rendered under / around a snack sprite."""

    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg
        self.time = 0.0

    def update(self, dt: float) -> None:
        self.time += dt

    def should_glow(self, snack_id: str) -> bool:
        ids: List[str] = self.cfg.get("powerup_snack_ids", [])
        return snack_id in ids

    def render(self, surface: pygame.Surface, cx: int, cy: int,
               snack_id: str, color: Tuple[int, int, int]) -> None:
        """Render glow and sparkles centred at (cx, cy)."""
        r_pad = self.cfg.get("glow_radius_padding", 12)
        pulse_speed = self.cfg.get("glow_pulse_speed", 3.5)
        base_alpha = self.cfg.get("glow_base_alpha", 40)
        pulse_alpha = self.cfg.get("glow_pulse_alpha", 30)

        pulse = math.sin(self.time * pulse_speed * math.pi)
        radius = 36 + r_pad + int(pulse * 4)
        alpha = _clamp(int(base_alpha + pulse * pulse_alpha))

        # Glow circle
        glow_size = radius * 2 + 4
        gs = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        gc = glow_size // 2
        pygame.draw.circle(gs, (*color, alpha), (gc, gc), radius)
        surface.blit(gs, (cx - gc, cy - gc))

        # Orbiting sparkles
        s_count = self.cfg.get("sparkle_count", 6)
        s_speed = self.cfg.get("sparkle_orbit_speed", 2.0)
        s_radius = self.cfg.get("sparkle_orbit_radius", 20) + int(pulse * 3)
        s_size = self.cfg.get("sparkle_size", 3)

        for i in range(s_count):
            angle = self.time * s_speed + (2 * math.pi * i / s_count)
            sx = cx + int(math.cos(angle) * s_radius)
            sy = cy + int(math.sin(angle) * (s_radius * 0.65))
            sa = _clamp(int(180 + 75 * math.sin(angle * 2)))
            spark = pygame.Surface((s_size * 2, s_size * 2), pygame.SRCALPHA)
            pygame.draw.circle(spark, (255, 255, 255, sa),
                               (s_size, s_size), s_size)
            surface.blit(spark, (sx - s_size, sy - s_size))

        # Vertical light beam
        if self.cfg.get("beam_enabled", True):
            bw = self.cfg.get("beam_width", 4)
            bh = self.cfg.get("beam_height", 30)
            ba = _clamp(int(self.cfg.get("beam_alpha", 60) + pulse * 20))
            beam = pygame.Surface((bw, bh), pygame.SRCALPHA)
            beam.fill((*color, ba))
            surface.blit(beam, (cx - bw // 2, cy - bh))


# ---------------------------------------------------------------------------
# Manager  – owns all sub-effects for one player
# ---------------------------------------------------------------------------

class PowerUpVFXManager:
    """Manages all power-up visual effects for a single player.

    Attach one instance per player. Call *update* each frame, then the two
    render passes (behind / in-front) around the normal sprite blit.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config
        self.wings = WingsEffect(config.get("wings", {}))
        self.streaks = SpeedStreakEffect(config.get("speed_streaks", {}))
        self.aura = AuraEffect(config.get("aura", {}))
        self.indicator = StatusIndicator(config.get("status_indicator", {}))
        self.pickup_flashes: List[PickupFlash] = []
        self.snack_glow = SnackGlow(config.get("snack_glow", {}))

    # -- per-frame -----------------------------------------------------------

    def update(self, dt: float, active_effects: List[Dict[str, Any]],
               player_x: float, player_y: float,
               player_w: int, player_h: int,
               facing_right: bool,
               is_flying: bool = False) -> None:
        """Update all sub-effects based on current active effects."""
        has_boost = any(e["type"] == "boost" for e in active_effects)
        has_speed = any(e["type"] in ("speed_boost", "boost") for e in active_effects)
        speed_type = "boost" if has_boost else "speed_boost"

        cx = player_x + player_w / 2
        cy = player_y + player_h / 2

        self.wings.update(dt, has_boost, (cx, cy), facing_right,
                          is_flying=is_flying)
        self.streaks.update(dt, has_speed, speed_type,
                            player_x, player_y, player_w, player_h, facing_right)
        self.aura.update(dt)
        self.indicator.update(dt)

        # Tick pickup flashes
        for pf in self.pickup_flashes:
            pf.update(dt)
        self.pickup_flashes = [pf for pf in self.pickup_flashes if pf.alive]

    def trigger_pickup_flash(self, x: float, y: float,
                             effect_type: str) -> None:
        """Spawn an expanding ring at (x, y) when a power-up is collected."""
        color = StatusIndicator._effect_color(effect_type)
        cfg = self._cfg.get("pickup_flash", {})
        self.pickup_flashes.append(PickupFlash(cfg, x, y, color))

    # -- rendering -----------------------------------------------------------

    def render_behind(self, surface: pygame.Surface,
                      sprite: Optional[pygame.Surface],
                      render_x: int, render_y: int,
                      sprite_w: int, sprite_h: int,
                      active_effects: List[Dict[str, Any]],
                      arena_left: float, arena_top: float,
                      offset: Tuple[int, int],
                      facing_right: bool = True,
                      render_wings: bool = True,
                      is_flying: bool = False) -> None:
        """Effects drawn *behind* the player sprite (call before blit)."""
        render_cx = render_x + sprite_w // 2
        render_cy = render_y + sprite_h // 2

        # Aura glow (behind sprite)
        for eff in active_effects:
            if self._cfg.get("aura", {}).get("enabled", True):
                self.aura.render(surface, render_cx, render_cy,
                                 sprite_w, sprite_h, eff["type"])

        # Wings (behind sprite, only for boost)
        has_boost = any(e["type"] == "boost" for e in active_effects)
        if has_boost and render_wings and self._cfg.get("wings", {}).get("enabled", True):
            self.wings.render(surface, render_cx, render_cy,
                              sprite_w, sprite_h, facing_right,
                              arena_left, arena_top, offset,
                              is_flying=is_flying)

        # Speed streaks / afterimages (behind sprite)
        has_speed = any(e["type"] in ("speed_boost", "boost") for e in active_effects)
        if has_speed and self._cfg.get("speed_streaks", {}).get("enabled", True):
            self.streaks.render_behind(surface, sprite, render_x, render_y,
                                       arena_left, arena_top, offset)

    def render_front(self, surface: pygame.Surface,
                     render_x: int, render_y: int,
                     sprite_w: int, sprite_h: int,
                     active_effects: List[Dict[str, Any]],
                     arena_left: float, arena_top: float,
                     offset: Tuple[int, int],
                     facing_right: bool = True,
                     render_wings: bool = True) -> None:
        """Effects drawn *in front of* the player sprite (call after blit)."""
        render_cx = render_x + sprite_w // 2

        has_boost = any(e["type"] == "boost" for e in active_effects)

        # Front shoulder overlay so wings look attached to the dog body.
        if has_boost and render_wings and self._cfg.get("wings", {}).get("enabled", True):
            self.wings.render_attachment_overlay(
                surface,
                render_x,
                render_y,
                sprite_w,
                sprite_h,
                facing_right,
            )

        # Speed particles (in front)
        has_speed = any(e["type"] in ("speed_boost", "boost") for e in active_effects)
        if has_speed and self._cfg.get("speed_streaks", {}).get("enabled", True):
            self.streaks.render_front(surface, arena_left, arena_top, offset)

        # Status indicator (timer bar + icon) for each active effect
        if self._cfg.get("status_indicator", {}).get("enabled", True):
            # Stack indicators above each other if multiple effects active
            top_y = render_y
            for i, eff in enumerate(active_effects):
                stacked_top = top_y - i * 44
                self.indicator.render(
                    surface, render_cx, stacked_top,
                    eff["type"], eff["time_remaining"], eff["duration"]
                )

        # Pickup flash rings
        for pf in self.pickup_flashes:
            pf.render(surface, arena_left, arena_top, offset)
