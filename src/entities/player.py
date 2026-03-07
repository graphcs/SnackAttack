"""Player entity - controlled by keyboard input."""

import pygame
import math
import time
from typing import Dict, Any, Tuple, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..sprites.animation_controller import AnimationController
    from ..effects.powerup_vfx import PowerUpVFXManager


class Player:
    """A player-controlled dog character."""

    def __init__(self, character_config: Dict[str, Any], arena_bounds: pygame.Rect,
                 player_num: int = 1, horizontal_only: bool = False):
        """
        Initialize a player.

        Args:
            character_config: Character configuration from characters.json
            arena_bounds: The playable area boundaries
            player_num: Player number (1 or 2)
            horizontal_only: If True, only allow horizontal movement
        """
        self.character_id = character_config.get("id", "unknown")
        self.name = character_config.get("name", "Unknown")
        self.base_speed = character_config.get("base_speed", 1.0)
        self.color = tuple(character_config.get("color", [255, 255, 255]))

        # Use character-specific sprite size from SpriteSheetLoader
        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        size = SpriteSheetLoader.CHARACTER_SIZES.get(
            self.character_id, SpriteSheetLoader.GAMEPLAY_SIZE
        )
        self.width = size[0]
        self.height = size[1]

        self.arena_bounds = arena_bounds
        self.player_num = player_num
        self.horizontal_only = horizontal_only

        # Position (center of arena horizontally)
        self.x = arena_bounds.centerx - self.width // 2
        self.y = arena_bounds.centery - self.height // 2

        # Resting Y position — used to return to ground after flight ends
        # (updated by gameplay screen when positioning on ground level)
        self._resting_y = self.y

        # How far up the dog can fly as a fraction of ground‑to‑top distance
        self.FLIGHT_HEIGHT_FRACTION = 0.35

        # Movement - faster for larger screen
        self.base_move_speed = 350  # pixels per second
        self.velocity_x = 0
        self.velocity_y = 0

        # State
        self.score = 0
        self.active_effects: List[Dict[str, Any]] = []
        self.is_invincible = False
        self.controls_flipped = False

        # Leash system - controls horizontal movement boundaries
        self.leash_base_min_x = arena_bounds.left
        self.leash_base_max_x = arena_bounds.right - self.width
        self.leash_min_x = self.leash_base_min_x
        self.leash_max_x = self.leash_base_max_x
        self.leash_effect_timer = 0.0
        self.leash_effect_duration = 8.0  # seconds (longer to see the effect)
        # Calculate arena width for dramatic effects
        arena_width = arena_bounds.width
        self.leash_extend_amount = int(arena_width * 0.15)  # Extend 15% more
        self.leash_yank_amount = int(arena_width * 0.35)  # Restrict by 35% (very noticeable!)

        # Animation state - player 1 faces right, player 2 faces left
        self.facing_right = (player_num == 1)
        self.is_moving = False

        # Animation controller (lazy initialization)
        self._animation_controller: Optional['AnimationController'] = None

        # Steam particles for chaos/chilli effect
        self.steam_particles: List[Dict[str, float]] = []

        # Speed lines for boost effect (legacy — kept for compatibility)
        self.speed_lines: List[Dict[str, float]] = []

        # Power-up visual effects manager (lazy initialization)
        self._vfx_manager: Optional['PowerUpVFXManager'] = None

        # Free-flight state (active during boost / Red Bull)
        self._flight_hover_offset = 0.0   # Current Y offset for hover bob
        self._flight_lift_offset = 0.0    # Smooth lift transition (0 -> -15)
        self._flight_tilt_angle = 0.0     # Head-tilt rotation in degrees
        self._flight_time = 0.0           # Elapsed time for sinusoidal bob

    @property
    def rect(self) -> pygame.Rect:
        """Get the player's collision rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    @property
    def center(self) -> Tuple[float, float]:
        """Get the player's center position."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def animation_controller(self) -> 'AnimationController':
        """Lazy initialization of animation controller."""
        if self._animation_controller is None:
            from ..sprites.animation_controller import AnimationController
            self._animation_controller = AnimationController(self.character_id)
        return self._animation_controller

    @property
    def vfx(self) -> 'PowerUpVFXManager':
        """Lazy initialization of power-up VFX manager."""
        if self._vfx_manager is None:
            from ..effects.powerup_vfx import PowerUpVFXManager
            from ..core.config_manager import ConfigManager
            cfg = ConfigManager().get("powerup_visuals", {})
            self._vfx_manager = PowerUpVFXManager(cfg)
        return self._vfx_manager

    def trigger_eat_animation(self) -> None:
        """Trigger the eat/attack animation when collecting a snack."""
        self.animation_controller.trigger_eat_animation()

    def get_speed_multiplier(self) -> float:
        """Calculate current speed multiplier from active effects."""
        multiplier = 1.0
        for effect in self.active_effects:
            if effect["type"] in ("speed_boost", "slow", "boost"):
                multiplier *= effect["magnitude"]
        return multiplier

    def get_score_multiplier(self) -> float:
        """Calculate current score multiplier from active effects (boost mode)."""
        multiplier = 1.0
        for effect in self.active_effects:
            if effect["type"] == "boost":
                multiplier *= effect["magnitude"]
        return multiplier

    def has_boost_effect(self) -> bool:
        """Check if player has boost effect active."""
        return any(e["type"] == "boost" for e in self.active_effects)

    def get_flight_ceiling(self) -> float:
        """Return the highest Y the dog may reach while flying.

        Limited to FLIGHT_HEIGHT_FRACTION of the ground‑to‑top gap so dogs
        hover modestly rather than flying to the very top of the arena.
        """
        max_lift = (self._resting_y - self.arena_bounds.top) * self.FLIGHT_HEIGHT_FRACTION
        return self._resting_y - max_lift

    def _get_boost_sprite_override(self) -> Optional[pygame.Surface]:
        """Get single boost-wing sprite override, if available."""
        if not self.has_boost_effect():
            return None

        from ..sprites.sprite_sheet_loader import SpriteSheetLoader

        return SpriteSheetLoader().get_boost_sprite(
            self.character_id,
            self.facing_right,
        )

    def _get_front_flight_sprite_override(self) -> Optional[pygame.Surface]:
        """Get front-facing flight sprite while the dog is airborne during boost."""
        if not self.has_boost_effect():
            return None

        height_above_ground = self._resting_y - self.y
        is_airborne = height_above_ground > 12.0
        strong_vertical_motion = (
            abs(self.velocity_y) >= 80 and
            abs(self.velocity_y) >= abs(self.velocity_x) * 0.75
        )
        if not is_airborne and not strong_vertical_motion:
            return None

        from ..sprites.sprite_sheet_loader import SpriteSheetLoader

        return SpriteSheetLoader().get_front_flight_sprite(self.character_id)

    def apply_effect(self, effect_type: str, magnitude: float, duration: float) -> None:
        """Apply a power-up or penalty effect."""
        effect = {
            "type": effect_type,
            "magnitude": magnitude,
            "duration": duration,
            "time_remaining": duration
        }
        self.active_effects.append(effect)

        if effect_type == "invincibility":
            self.is_invincible = True
        elif effect_type == "chaos":
            self.controls_flipped = True

        # Trigger visual pickup flash at player centre
        cx, cy = self.center
        self.vfx.trigger_pickup_flash(cx, cy, effect_type)

    def update_effects(self, dt: float) -> List[Dict[str, Any]]:
        """
        Update effect timers and remove expired effects.

        Returns:
            List of expired effects
        """
        expired = []
        still_active = []

        for effect in self.active_effects:
            effect["time_remaining"] -= dt
            if effect["time_remaining"] <= 0:
                expired.append(effect)
                # Reset state flags
                if effect["type"] == "invincibility":
                    self.is_invincible = False
                elif effect["type"] == "chaos":
                    self.controls_flipped = False
            else:
                still_active.append(effect)

        self.active_effects = still_active
        return expired

    def handle_input(self, keys_pressed: Dict[str, bool]) -> None:
        """
        Handle keyboard input for movement.

        Args:
            keys_pressed: Dictionary of control keys to their pressed state
        """
        dx = 0
        dy = 0

        # Free-flight: allow vertical movement when boost is active,
        # even in horizontal_only mode
        can_move_vertical = not self.horizontal_only or self.has_boost_effect()

        if can_move_vertical:
            if keys_pressed.get("up", False):
                dy = -1
            if keys_pressed.get("down", False):
                dy = 1

        if keys_pressed.get("left", False):
            dx = -1
        if keys_pressed.get("right", False):
            dx = 1

        # Apply chaos effect (flip controls)
        if self.controls_flipped:
            dx = -dx
            dy = -dy

        # Normalize diagonal movement (only if vertical movement is allowed)
        if can_move_vertical and dx != 0 and dy != 0:
            dx *= 0.707  # 1/sqrt(2)
            dy *= 0.707

        speed = self.base_move_speed * self.base_speed * self.get_speed_multiplier()
        self.velocity_x = dx * speed
        self.velocity_y = dy * speed if can_move_vertical else 0

        # Soften upward velocity when approaching flight ceiling
        if can_move_vertical and self.horizontal_only and self.velocity_y < 0:
            ceiling = self.get_flight_ceiling()
            margin = 30.0  # px – start dampening before hitting ceiling
            if self.y <= ceiling + margin:
                damp = max(0.0, (self.y - ceiling) / margin)
                self.velocity_y *= damp

        # Update facing direction
        if dx > 0:
            self.facing_right = True
        elif dx < 0:
            self.facing_right = False

        self.is_moving = dx != 0 or (can_move_vertical and dy != 0)

    def update(self, dt: float) -> None:
        """Update player position and state."""
        # Update leash effect timer
        if self.leash_effect_timer > 0:
            self.leash_effect_timer -= dt
            if self.leash_effect_timer <= 0:
                self.reset_leash()

        # Return-to-ground: when horizontal_only and NOT boosting, pull
        # the dog back toward its resting Y so it doesn't float after flight.
        if self.horizontal_only and not self.has_boost_effect():
            diff = self._resting_y - self.y
            if abs(diff) > 1.0:
                # Smooth return: fast enough to not look sluggish
                self.velocity_y = diff * 5.0  # spring-like pull
            else:
                self.y = self._resting_y
                self.velocity_y = 0

        # Update position
        new_x = self.x + self.velocity_x * dt
        new_y = self.y + self.velocity_y * dt

        # Clamp to leash bounds (horizontal) and arena bounds (vertical)
        new_x = max(self.leash_min_x, min(new_x, self.leash_max_x))
        # Use flight ceiling instead of full arena top when boosting
        min_y = self.arena_bounds.top
        if self.horizontal_only and self.has_boost_effect():
            min_y = self.get_flight_ceiling()
        new_y = max(min_y, min(new_y, self.arena_bounds.bottom - self.height))

        self.x = new_x
        self.y = new_y

        # Update animation controller
        self.animation_controller.update(dt, self.is_moving, self.facing_right)

        # Update effects
        self.update_effects(dt)

        # Update free-flight visuals (hover bob, lift, tilt)
        self._update_flight_state(dt)

        # Update steam particles
        self._update_steam_particles(dt)

        # Update power-up VFX
        self.vfx.update(
            dt, self.active_effects,
            self.x, self.y, self.width, self.height,
            self.facing_right,
            is_flying=self.has_boost_effect()
        )

    def extend_leash(self, cross_arena_max_x: int = None) -> None:
        """Extend the leash, allowing more movement range.

        Args:
            cross_arena_max_x: If provided, allows dog to cross into other arena up to this x position
        """
        if cross_arena_max_x is not None:
            # Allow crossing into other arena!
            self.leash_max_x = cross_arena_max_x
        else:
            self.leash_max_x = self.leash_base_max_x + self.leash_extend_amount
        self.leash_effect_timer = self.leash_effect_duration

    def yank_leash(self) -> None:
        """Yank the leash, restricting movement range."""
        # Calculate restricted max_x (can't go below min_x + some minimum space)
        min_range = self.width * 2  # At least 2 dog widths of movement
        self.leash_max_x = max(
            self.leash_base_max_x - self.leash_yank_amount,
            self.leash_min_x + min_range
        )
        self.leash_effect_timer = self.leash_effect_duration

    def reset_leash(self) -> None:
        """Reset leash to default boundaries."""
        self.leash_min_x = self.leash_base_min_x
        self.leash_max_x = self.leash_base_max_x
        self.leash_effect_timer = 0.0

    # ------------------------------------------------------------------
    # Free-flight helpers (active during boost / Red Bull)
    # ------------------------------------------------------------------

    def _update_flight_state(self, dt: float) -> None:
        """Update hover bob, lift offset, and tilt angle for flight mode."""
        boosting = self.has_boost_effect()
        if boosting:
            self._flight_time += dt
            # Sinusoidal hover bob (subtle up/down float)
            self._flight_hover_offset = math.sin(self._flight_time * 3.0) * 6.0
            # Smooth lift transition toward -15px (float above ground)
            self._flight_lift_offset += (-15.0 - self._flight_lift_offset) * min(1.0, dt * 5.0)
            # Tilt based on velocity: up -> tilt nose-up, down -> tilt nose-down
            target_tilt = 0.0
            if self.velocity_y < -50:
                target_tilt = 8.0   # nose-up
            elif self.velocity_y > 50:
                target_tilt = -8.0  # nose-down
            if self.velocity_x != 0:
                # Slight lean forward/back in strafe direction
                lean = 4.0 if self.velocity_x > 0 else -4.0
                if not self.facing_right:
                    lean = -lean
                target_tilt += lean * 0.3
            self._flight_tilt_angle += (target_tilt - self._flight_tilt_angle) * min(1.0, dt * 8.0)
        else:
            # Smoothly return to ground
            self._flight_time = 0.0
            self._flight_hover_offset *= max(0.0, 1.0 - dt * 6.0)
            self._flight_lift_offset *= max(0.0, 1.0 - dt * 6.0)
            self._flight_tilt_angle *= max(0.0, 1.0 - dt * 8.0)

    def get_leash_state(self) -> str:
        """Get current leash state for visual feedback."""
        if self.leash_effect_timer <= 0:
            return "normal"
        elif self.leash_max_x > self.leash_base_max_x:
            return "extended"
        elif self.leash_max_x < self.leash_base_max_x:
            return "yanked"
        return "normal"

    def add_score(self, points: int) -> None:
        """Add points to the player's score."""
        self.score += points
        if self.score < 0:
            self.score = 0

    def reset_position(self) -> None:
        """Reset player to center of arena."""
        self.x = self.arena_bounds.centerx - self.width // 2
        self.y = self.arena_bounds.centery - self.height // 2
        self._resting_y = self.y
        self.velocity_x = 0
        self.velocity_y = 0

    def reset(self) -> None:
        """Reset player state for new round."""
        self.reset_position()
        self.score = 0
        self.active_effects.clear()
        self.is_invincible = False
        self.controls_flipped = False
        self.reset_leash()
        self.steam_particles.clear()
        self.speed_lines.clear()

        # Reset flight state
        self._flight_hover_offset = 0.0
        self._flight_lift_offset = 0.0
        self._flight_tilt_angle = 0.0
        self._flight_time = 0.0

        # Reset facing direction: player 1 faces right, player 2 faces left
        self.facing_right = (self.player_num == 1)

        # Reset animation state
        if self._animation_controller is not None:
            self._animation_controller.reset()

    def _update_steam_particles(self, dt: float) -> None:
        """Update steam particles for chaos/chilli effect."""
        import random

        # Check if chaos effect is active
        has_chaos_effect = any(e["type"] == "chaos" for e in self.active_effects)

        # Spawn new steam particles if chaos effect active
        if has_chaos_effect:
            # Spawn 2-3 particles per frame
            for _ in range(random.randint(2, 3)):
                self.steam_particles.append({
                    "x": self.x + self.width // 2 + random.uniform(-20, 20),
                    "y": self.y + 10,
                    "vx": random.uniform(-15, 15),
                    "vy": random.uniform(-60, -40),
                    "life": 0.8,
                    "size": random.uniform(6, 12)
                })

        # Update existing particles
        for p in self.steam_particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= dt
            p["size"] += 8 * dt  # Grow as they rise

        # Remove dead particles
        self.steam_particles = [p for p in self.steam_particles if p["life"] > 0]

        # Update speed lines for boost effect
        self._update_speed_lines(dt)

    def _update_speed_lines(self, dt: float) -> None:
        """Update speed lines for boost effect."""
        import random

        # Check if boost effect is active
        has_boost = self.has_boost_effect()

        # Spawn new speed lines if boost active
        if has_boost:
            # Spawn 1-2 lines per frame
            for _ in range(random.randint(1, 2)):
                # Lines spawn behind the dog based on facing direction
                if self.facing_right:
                    start_x = self.x - 10
                else:
                    start_x = self.x + self.width + 10

                self.speed_lines.append({
                    "x": start_x,
                    "y": self.y + random.uniform(20, self.height - 20),
                    "length": random.uniform(30, 60),
                    "life": 0.3,
                    "facing_right": self.facing_right
                })

        # Update existing speed lines
        for line in self.speed_lines:
            line["life"] -= dt
            # Lines move opposite to facing direction
            if line["facing_right"]:
                line["x"] -= 400 * dt
            else:
                line["x"] += 400 * dt

        # Remove dead lines
        self.speed_lines = [l for l in self.speed_lines if l["life"] > 0]

    def render(self, surface: pygame.Surface, offset: Tuple[int, int] = (0, 0)) -> None:
        """
        Render the player using sprite sheet animations.

        Args:
            surface: Surface to render to
            offset: Offset for rendering within arena
        """
        render_x = int(self.x - self.arena_bounds.left + offset[0])
        render_y = int(self.y - self.arena_bounds.top + offset[1])

        # Apply free-flight visual offsets (hover bob + lift)
        flight_y_offset = int(self._flight_lift_offset + self._flight_hover_offset)
        render_y += flight_y_offset

        # Adjust Prissy's position slightly downward
        if self.character_id == 'prissy':
            render_y += 15

        # Get current animation frame from animation controller
        sprite = self.animation_controller.get_current_sprite()

        # Fallback to procedural sprite if animation not available
        if sprite is None:
            from ..sprites.pixel_art import SpriteCache
            cache = SpriteCache()
            sprite = cache.get_dog_sprite(self.character_id, self.facing_right)

        # Use generated boost-specific sprite overrides when available.
        front_flight_override = self._get_front_flight_sprite_override()
        boost_sprite_override = None if front_flight_override is not None else self._get_boost_sprite_override()
        using_boost_sheet = front_flight_override is not None or boost_sprite_override is not None
        if front_flight_override is not None:
            sprite = front_flight_override
        elif boost_sprite_override is not None:
            sprite = boost_sprite_override

        # Apply head-tilt rotation during free-flight
        if front_flight_override is None and abs(self._flight_tilt_angle) > 0.5:
            rotated = pygame.transform.rotate(sprite, self._flight_tilt_angle)
            # Re-centre after rotation (rotation expands bounding box)
            old_center = sprite.get_rect(topleft=(render_x, render_y)).center
            new_rect = rotated.get_rect(center=old_center)
            render_x, render_y = new_rect.topleft
            sprite = rotated

        # Handle invincibility flashing
        if self.is_invincible:
            if int(time.time() * 10) % 2 == 0:
                # Create a white-tinted version
                # Use BLEND_RGB_ADD (not RGBA) to avoid alpha channel corruption on macOS
                flash_sprite = sprite.copy()
                flash_sprite.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGB_ADD)
                sprite = flash_sprite

        # Handle slow effect (broccoli) - turn green
        has_slow_effect = any(e["type"] == "slow" for e in self.active_effects)
        if has_slow_effect:
            green_sprite = sprite.copy()
            green_sprite.fill((0, 150, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
            sprite = green_sprite

        # Handle chaos effect (chilli) - turn red
        has_chaos_effect = any(e["type"] == "chaos" for e in self.active_effects)
        if has_chaos_effect:
            red_sprite = sprite.copy()
            red_sprite.fill((150, 0, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
            sprite = red_sprite

        # Handle boost effect (red bull) - add blue tint
        if self.has_boost_effect() and not using_boost_sheet:
            blue_sprite = sprite.copy()
            blue_sprite.fill((0, 50, 150, 0), special_flags=pygame.BLEND_RGB_ADD)
            sprite = blue_sprite

        # Draw speed lines BEHIND the sprite (legacy simple lines)
        for line in self.speed_lines:
            line_x = int(line["x"] - self.arena_bounds.left + offset[0])
            line_y = int(line["y"] - self.arena_bounds.top + offset[1])
            alpha = int(255 * (line["life"] / 0.3))
            length = int(line["length"])

            line_surface = pygame.Surface((length, 4), pygame.SRCALPHA)
            pygame.draw.line(line_surface, (100, 200, 255, alpha), (0, 2), (length, 2), 3)
            surface.blit(line_surface, (line_x, line_y - 2))

        # --- Power-up VFX: behind-sprite pass (aura, wings, afterimages) ---
        self.vfx.render_behind(
            surface, sprite, render_x, render_y,
            self.width, self.height, self.active_effects,
            self.arena_bounds.left, self.arena_bounds.top, offset,
            facing_right=self.facing_right,
            render_wings=not using_boost_sheet,
            is_flying=self.has_boost_effect()
        )

        # Draw the sprite
        surface.blit(sprite, (render_x, render_y))

        # --- Power-up VFX: front-sprite pass (particles, indicators, flashes) ---
        self.vfx.render_front(
            surface, render_x, render_y,
            self.width, self.height, self.active_effects,
            self.arena_bounds.left, self.arena_bounds.top, offset,
            facing_right=self.facing_right,
            render_wings=not using_boost_sheet
        )

        # Draw steam particles (for chaos/chilli effect)
        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        steam_sprite = SpriteSheetLoader().get_steam_sprite()
        
        for p in self.steam_particles:
            particle_x = int(p["x"] - self.arena_bounds.left + offset[0])
            particle_y = int(p["y"] - self.arena_bounds.top + offset[1])
            alpha = int(255 * (p["life"] / 0.8))
            size = int(p["size"])

            if steam_sprite:
                # Use sprite
                sprite_size = size * 2
                scaled_steam = pygame.transform.scale(steam_sprite, (sprite_size, sprite_size))
                # Use BLEND_RGBA_MULT for reliable alpha fading on macOS SDL2 Metal
                faded_steam = scaled_steam.copy()
                fade_mask = pygame.Surface(faded_steam.get_size(), pygame.SRCALPHA)
                fade_mask.fill((255, 255, 255, alpha))
                faded_steam.blit(fade_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                surface.blit(faded_steam, (particle_x - size, particle_y - size))
            else:
                # Draw steam puff (white/gray circle with transparency) fallback
                steam_surface = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                pygame.draw.circle(steam_surface, (255, 255, 255, alpha), (size, size), size)
                surface.blit(steam_surface, (particle_x - size, particle_y - size))
