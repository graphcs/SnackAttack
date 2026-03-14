"""Avatar generator - converts dog photos into game-ready pixel art sprites."""

import os
import io
import base64
import json
import threading
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass

from .flight_asset_generator import FlightAssetGenerator
from .openrouter_client import OpenRouterClient, GeneratedImage
from .background_remover import ensure_transparency
from .prompts import (
    BOOST_SPRITE_PROMPT,
    EAT_SPRITE_PROMPT,
    PROFILE_PROMPT,
    RUN_SPRITE_PROMPT,
    STYLE_CORE,
    WALK_SPRITE_PROMPT,
)


@dataclass
class AvatarGenerationResult:
    """Result of avatar generation."""
    success: bool
    character_id: str = ""
    character_name: str = ""
    error_message: str = ""
    profile_path: str = ""
    run_sprite_path: str = ""
    eat_sprite_path: str = ""
    walk_sprite_path: str = ""
    boost_sprite_path: str = ""
    flight_sprite_path: str = ""


@dataclass
class GenerationProgress:
    """Tracks progress of avatar generation."""
    current_step: int = 0
    total_steps: int = 8
    step_description: str = "Initializing..."
    is_complete: bool = False
    is_error: bool = False
    error_message: str = ""
    result: Optional[AvatarGenerationResult] = None


class AvatarGenerator:
    """Generates game-ready pixel art sprites from a dog photo using existing sprites as style reference."""

    # ----- TARGET SIZES (must match existing sprites exactly) -----
    PROFILE_SIZE = (350, 350)          # All profiles are 350x350
    SPRITE_SHEET_SIZE = (1500, 500)    # Run/eat sheets: 1500x500 (3 frames of 500x500)
    WALK_SHEET_SIZE = (2500, 500)      # Walk sheets: 5 frames of 500x500, horizontal strip
    BOOST_SPRITE_SIZE = (500, 500)     # Single boost sprite (winged form)

    # Reference sprite files to load (from existing characters)
    REFERENCE_SPRITES = {
        "profile": "Jazzy.png",          # Profile/ directory
        "run": "Jazzy run sprite.png",   # Sprite sheets/ directory
        "eat": "Jazzy eat:attack sprite.png",  # Sprite sheets/ directory
        "walk": "Jazzy walking.png",
        "boost": "Jazzy boost-Photoroom.png",
    }

    def __init__(self, api_key: str, base_dir: str):
        """
        Initialize the avatar generator.

        Args:
            api_key: OpenRouter API key
            base_dir: Project root directory
        """
        self.api_key = api_key
        self.client = OpenRouterClient(api_key)
        self.base_dir = base_dir
        self.profile_dir = os.path.join(base_dir, "Profile")
        self.sprite_dir = os.path.join(base_dir, "Sprite sheets")
        self.config_path = os.path.join(base_dir, "config", "characters.json")
        self.custom_dir = os.path.join(base_dir, "custom_avatars")

        # Ensure directories exist
        os.makedirs(self.custom_dir, exist_ok=True)

        # Cache for reference sprite base64 data
        self._ref_cache: Dict[str, str] = {}

    def _load_and_encode_photo(self, photo_path: str) -> str:
        """Load a photo file and encode it as base64."""
        with open(photo_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _load_reference_sprite(self, ref_key: str) -> Optional[str]:
        """
        Load a reference sprite image as base64 for style matching.

        Args:
            ref_key: Key from REFERENCE_SPRITES ('profile', 'run', 'eat')

        Returns:
            Base64-encoded image string, or None
        """
        if ref_key in self._ref_cache:
            return self._ref_cache[ref_key]

        filename = self.REFERENCE_SPRITES.get(ref_key)
        if not filename:
            return None

        if ref_key == "profile":
            filepath = os.path.join(self.profile_dir, filename)
        elif ref_key == "boost":
            filepath = os.path.join(self.sprite_dir, "boost_wings", filename)
        else:
            filepath = os.path.join(self.sprite_dir, filename)

        if not os.path.exists(filepath):
            print(f"[AvatarGenerator] Reference sprite not found: {filepath}")
            return None

        try:
            with open(filepath, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            self._ref_cache[ref_key] = data
            return data
        except Exception as e:
            print(f"[AvatarGenerator] Error loading reference sprite: {e}")
            return None

    def _load_wing_references(self) -> List[str]:
        """Load wing reference images as base64 strings, if available."""
        wing_dir = os.path.join(self.sprite_dir, "wings")
        files = [
            os.path.join(wing_dir, "wing_up.png"),
            os.path.join(wing_dir, "wing_down.png"),
        ]

        refs: List[str] = []
        for path in files:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "rb") as f:
                    refs.append(base64.b64encode(f.read()).decode("utf-8"))
            except Exception as e:
                print(f"[AvatarGenerator] Warning: Could not load wing reference {path}: {e}")
        return refs

    @staticmethod
    def _normalize_pil_frame(frame, target_size: Tuple[int, int],
                             min_fill: float = 0.58,
                             max_fill: float = 0.82,
                             target_fill: float = 0.70):
        """Scale and centre sprite content so each frame has consistent visual fill."""
        from PIL import Image as PILImage

        alpha = frame.getchannel("A")
        bounds = alpha.getbbox()
        if bounds is None:
            return PILImage.new("RGBA", target_size, (0, 0, 0, 0))

        frame_w, frame_h = target_size
        content = frame.crop(bounds)
        content_w, content_h = content.size
        dim_fill = max(content_w / max(frame_w, 1), content_h / max(frame_h, 1))

        if min_fill <= dim_fill <= max_fill:
            scale = 1.0
        else:
            scale = target_fill / max(dim_fill, 0.01)

        new_w = max(1, min(frame_w, int(round(content_w * scale))))
        new_h = max(1, min(frame_h, int(round(content_h * scale))))
        content = content.resize((new_w, new_h), PILImage.NEAREST)

        canvas = PILImage.new("RGBA", target_size, (0, 0, 0, 0))
        offset_x = (frame_w - new_w) // 2
        offset_y = (frame_h - new_h) // 2
        canvas.paste(content, (offset_x, offset_y), content)
        return canvas

    def _normalize_sprite_sheet(self, img, target_size: Tuple[int, int],
                                asset_kind: str = "generic"):
        """Normalize a horizontal sprite sheet using one shared scale across all frames."""
        from PIL import Image as PILImage

        sheet_w, sheet_h = target_size
        frame_count = max(1, round(sheet_w / max(sheet_h, 1)))
        frame_w = sheet_w // frame_count
        normalized_sheet = PILImage.new("RGBA", target_size, (0, 0, 0, 0))

        if asset_kind == "walk":
            min_fill = 0.74
            max_fill = 0.90
            target_fill = 0.82
        else:
            min_fill = 0.58
            max_fill = 0.82
            target_fill = 0.70

        frames = []
        max_content_w = 0
        max_content_h = 0

        for index in range(frame_count):
            left = index * frame_w
            right = sheet_w if index == frame_count - 1 else left + frame_w
            frame = img.crop((left, 0, right, sheet_h))
            alpha = frame.getchannel("A")
            bounds = alpha.getbbox()
            frames.append((left, right, frame, bounds))
            if bounds is None:
                continue
            bounds_w = bounds[2] - bounds[0]
            bounds_h = bounds[3] - bounds[1]
            max_content_w = max(max_content_w, bounds_w)
            max_content_h = max(max_content_h, bounds_h)

        if max_content_w == 0 or max_content_h == 0:
            return normalized_sheet

        max_dim_fill = max(max_content_w / max(frame_w, 1), max_content_h / max(sheet_h, 1))
        if min_fill <= max_dim_fill <= max_fill:
            shared_scale = 1.0
        else:
            shared_scale = target_fill / max(max_dim_fill, 0.01)

        for left, right, frame, bounds in frames:
            if bounds is None:
                normalized = PILImage.new("RGBA", (right - left, sheet_h), (0, 0, 0, 0))
                normalized_sheet.paste(normalized, (left, 0), normalized)
                continue

            content = frame.crop(bounds)
            new_w = max(1, min(right - left, int(round(content.size[0] * shared_scale))))
            new_h = max(1, min(sheet_h, int(round(content.size[1] * shared_scale))))
            content = content.resize((new_w, new_h), PILImage.NEAREST)

            normalized = PILImage.new("RGBA", (right - left, sheet_h), (0, 0, 0, 0))
            offset_x = ((right - left) - new_w) // 2
            offset_y = (sheet_h - new_h) // 2
            if asset_kind == "walk":
                offset_y = max(0, sheet_h - new_h - 18)
            normalized.paste(content, (offset_x, offset_y), content)
            normalized_sheet.paste(normalized, (left, 0), normalized)

        return normalized_sheet

    def _normalize_square_asset(self, img, target_size: Tuple[int, int],
                                asset_kind: str):
        """Normalize square assets to match the framing of shipped assets."""
        if asset_kind == "profile":
            return self._normalize_pil_frame(
                img, target_size, min_fill=0.88, max_fill=0.99, target_fill=0.96
            )
        if asset_kind == "boost":
            return self._normalize_pil_frame(
                img, target_size, min_fill=0.76, max_fill=0.94, target_fill=0.88
            )
        if asset_kind == "front_flight":
            return self._normalize_pil_frame(
                img, target_size, min_fill=0.72, max_fill=0.90, target_fill=0.84
            )
        return img

    def _save_image(self, image: GeneratedImage, output_path: str,
                    target_size: Optional[Tuple[int, int]] = None,
                    asset_kind: str = "generic") -> None:
        """Save a generated image to disk with background removal and proper sizing.

        For sprite sheets (wider than tall), scales to match target width exactly
        and pads/crops height as needed. This ensures sprite frames are correctly
        proportioned since sprites are sliced by width.

        For square images (profiles), proportionally fits within target.

        Args:
            image: Generated image data
            output_path: Path to save the file
            target_size: Optional (width, height) to fit into. Ensures exact pixel
                         dimensions match existing game sprites without distortion.
        """
        from PIL import Image as PILImage

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        raw_bytes = image.get_bytes()

        # Post-process: ensure transparent background via rembg API
        try:
            processed_bytes = ensure_transparency(raw_bytes)
            print(f"[AvatarGenerator] Background removal applied to {os.path.basename(output_path)}")
        except Exception as e:
            print(f"[AvatarGenerator] Warning: Background removal failed ({e}), using original")
            processed_bytes = raw_bytes

        # Fit into target dimensions without proportion distortion
        if target_size:
            try:
                img = PILImage.open(io.BytesIO(processed_bytes)).convert("RGBA")
                tw, th = target_size
                iw, ih = img.size
                is_sprite_sheet = tw > th * 1.2

                if (iw, ih) != (tw, th):
                    if is_sprite_sheet:
                        # For sprite sheets: scale to match target WIDTH exactly,
                        # then pad/crop height. This keeps frame proportions correct
                        # since frames are sliced vertically by width.
                        scale = tw / iw
                        new_w = tw
                        new_h = int(ih * scale)
                        img = img.resize((new_w, new_h), PILImage.LANCZOS)

                        # Create canvas and center vertically
                        canvas = PILImage.new("RGBA", target_size, (0, 0, 0, 0))
                        offset_y = max(0, (th - new_h) // 2)
                        # If generated image is taller than target, crop from center
                        if new_h > th:
                            crop_y = (new_h - th) // 2
                            img = img.crop((0, crop_y, new_w, crop_y + th))
                            canvas.paste(img, (0, 0), img)
                        else:
                            canvas.paste(img, (0, offset_y), img)
                        img = canvas
                        img = self._normalize_sprite_sheet(img, target_size, asset_kind)
                    else:
                        # For profiles/squares: proportionally fit and center
                        scale = min(tw / iw, th / ih)
                        new_w = int(iw * scale)
                        new_h = int(ih * scale)
                        img = img.resize((new_w, new_h), PILImage.LANCZOS)

                        canvas = PILImage.new("RGBA", target_size, (0, 0, 0, 0))
                        offset_x = (tw - new_w) // 2
                        offset_y = (th - new_h) // 2
                        canvas.paste(img, (offset_x, offset_y), img)
                        img = canvas

                if is_sprite_sheet:
                    img = self._normalize_sprite_sheet(img, target_size, asset_kind)
                else:
                    img = self._normalize_square_asset(img, target_size, asset_kind)

                print(f"[AvatarGenerator] Fitted {os.path.basename(output_path)} to {target_size}")

                buf = io.BytesIO()
                img.save(buf, format="PNG")
                processed_bytes = buf.getvalue()
            except Exception as e:
                print(f"[AvatarGenerator] Warning: Resize failed ({e}), keeping original size")

        with open(output_path, "wb") as f:
            f.write(processed_bytes)

    def _generate_character_id(self, dog_name: str) -> str:
        """Generate a unique character ID from the dog name."""
        char_id = dog_name.lower().strip().replace(" ", "_")
        char_id = "".join(c for c in char_id if c.isalnum() or c == "_")

        if not char_id:
            char_id = "custom_dog"

        existing_ids = self._get_existing_character_ids()
        base_id = char_id
        counter = 1
        while char_id in existing_ids:
            char_id = f"{base_id}_{counter}"
            counter += 1

        return char_id

    def _get_existing_character_ids(self) -> set:
        """Get all existing character IDs from config."""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            return {c.get("id", "") for c in config.get("characters", [])}
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def _register_character(self, character_id: str, dog_name: str,
                            breed_description: str) -> None:
        """Register a new custom character in the config."""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            config = {"characters": []}

        new_character = {
            "id": character_id,
            "name": dog_name,
            "display_name": dog_name,
            "breed": breed_description,
            "base_speed": 1.0,
            "color": [200, 180, 150],
            "hitbox": [52, 56],
            "custom": True,
        }

        config["characters"].append(new_character)

        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

    def _update_sprite_loader_mappings(self, character_id: str, display_name: str) -> None:
        """Update the SpriteSheetLoader character name mapping at runtime."""
        try:
            from ..sprites.sprite_sheet_loader import SpriteSheetLoader
            loader = SpriteSheetLoader()
            loader.register_custom_character(character_id, display_name)
        except ImportError:
            pass

    def generate_avatar(self, photo_path: str, dog_name: str,
                        progress_callback: Optional[Callable[[GenerationProgress], None]] = None,
                        model: Optional[str] = None) -> AvatarGenerationResult:
        """
        Generate a complete avatar (profile + all sprite sheets) from a dog photo.

        Pipeline ensures consistency by:
        1. Generating the profile portrait from the photo + reference sprite
        2. Sending BOTH the photo AND the generated profile to subsequent steps
           so the AI draws the exact same pixel-art dog every time
        3. Resizing all outputs to exact game dimensions

        Args:
            photo_path: Path to the dog's photo
            dog_name: Name for the dog character
            progress_callback: Optional callback for progress updates
            model: OpenRouter model to use

        Returns:
            AvatarGenerationResult with paths to generated files
        """
        progress = GenerationProgress(total_steps=7)

        def update_progress(step: int, description: str):
            progress.current_step = step
            progress.step_description = description
            if progress_callback:
                progress_callback(progress)

        try:
            # Step 1: Load photo + reference sprites
            update_progress(1, "Loading references...")
            photo_b64 = self._load_and_encode_photo(photo_path)
            character_id = self._generate_character_id(dog_name)
            display_name = dog_name.strip().title()

            # Load reference sprites for style matching
            ref_profile = self._load_reference_sprite("profile")
            ref_run = self._load_reference_sprite("run")
            ref_eat = self._load_reference_sprite("eat")
            ref_walk = self._load_reference_sprite("walk")
            ref_boost = self._load_reference_sprite("boost")

            # File paths
            profile_path = os.path.join(self.profile_dir, f"{display_name}.png")
            run_sprite_path = os.path.join(self.sprite_dir, f"{display_name} run sprite.png")
            eat_sprite_path = os.path.join(self.sprite_dir, f"{display_name} eat:attack sprite.png")
            walk_sprite_path = os.path.join(self.sprite_dir, f"{display_name} walking.png")
            boost_sprite_path = os.path.join(self.sprite_dir, "boost_wings", f"{display_name} boost.png")

            # Backup directory
            backup_dir = os.path.join(self.custom_dir, character_id)
            os.makedirs(backup_dir, exist_ok=True)

            # Step 2: Generate profile portrait (with Jazzy profile as reference)
            update_progress(2, f"Creating {display_name}'s portrait...")
            profile_prompt = PROFILE_PROMPT.format(
                style_core=STYLE_CORE,
            )
            ref_images = [ref_profile] if ref_profile else []
            profile_image = self.client.generate_image_from_photo(
                photo_b64, profile_prompt, reference_images=ref_images,
                model=model, aspect_ratio="1:1"
            )
            if profile_image is None:
                raise RuntimeError("Failed to generate profile portrait. Please try again.")
            self._save_image(profile_image, profile_path, target_size=self.PROFILE_SIZE, asset_kind="profile")
            self._save_image(
                profile_image,
                os.path.join(backup_dir, "profile.png"),
                target_size=self.PROFILE_SIZE,
                asset_kind="profile",
            )

            # Encode the generated profile to use as identity reference for subsequent sprites
            profile_ref_b64 = base64.b64encode(profile_image.get_bytes()).decode("utf-8")

            # Step 3: Generate run sprite sheet
            # Send: photo + generated profile (identity) + Jazzy run (layout reference)
            update_progress(3, f"Creating {display_name}'s run animation...")
            run_prompt = RUN_SPRITE_PROMPT.format(
                style_core=STYLE_CORE,
            )
            ref_images = [profile_ref_b64]  # The generated profile is the identity anchor
            if ref_run:
                ref_images.append(ref_run)   # Jazzy run sprite for layout reference
            run_image = self.client.generate_image_from_photo(
                photo_b64, run_prompt, reference_images=ref_images,
                model=model, aspect_ratio="21:9"
            )
            if run_image is None:
                raise RuntimeError("Failed to generate run animation. Please try again.")
            self._save_image(run_image, run_sprite_path, target_size=self.SPRITE_SHEET_SIZE)
            self._save_image(run_image, os.path.join(backup_dir, "run_sprite.png"), target_size=self.SPRITE_SHEET_SIZE)

            # Encode the generated run sprite as side-view identity anchor for subsequent sprites
            run_ref_b64 = base64.b64encode(run_image.get_bytes()).decode("utf-8")

            # Step 4: Generate eat/attack sprite sheet
            # Send: photo + generated profile + generated run (identity) + Jazzy eat (layout)
            update_progress(4, f"Creating {display_name}'s eat animation...")
            eat_prompt = EAT_SPRITE_PROMPT.format(
                style_core=STYLE_CORE,
            )
            ref_images = [profile_ref_b64, run_ref_b64]
            if ref_eat:
                ref_images.append(ref_eat)
            eat_image = self.client.generate_image_from_photo(
                photo_b64, eat_prompt, reference_images=ref_images,
                model=model, aspect_ratio="21:9"
            )
            if eat_image is None:
                raise RuntimeError("Failed to generate eat animation. Please try again.")
            self._save_image(eat_image, eat_sprite_path, target_size=self.SPRITE_SHEET_SIZE)
            self._save_image(eat_image, os.path.join(backup_dir, "eat_sprite.png"), target_size=self.SPRITE_SHEET_SIZE)

            # Step 5: Generate walking sprite sheet
            # Send: photo + generated profile + generated run (identity) + Jazzy walk (layout)
            update_progress(5, f"Creating {display_name}'s walk animation...")
            walk_prompt = WALK_SPRITE_PROMPT.format(
                style_core=STYLE_CORE,
            )
            ref_images = [profile_ref_b64, run_ref_b64]
            if ref_walk:
                ref_images.append(ref_walk)
            walk_image = self.client.generate_image_from_photo(
                photo_b64, walk_prompt, reference_images=ref_images,
                model=model, aspect_ratio="21:9"
            )
            if walk_image is None:
                raise RuntimeError("Failed to generate walk animation. Please try again.")
            self._save_image(walk_image, walk_sprite_path, target_size=self.WALK_SHEET_SIZE, asset_kind="walk")
            self._save_image(
                walk_image,
                os.path.join(backup_dir, "walk_sprite.png"),
                target_size=self.WALK_SHEET_SIZE,
                asset_kind="walk",
            )

            # Step 6: Generate single boost sprite (winged form)
            # Send: photo + generated profile + generated run (identity) + Jazzy boost + wing refs
            update_progress(6, f"Creating {display_name}'s winged boost form...")
            boost_prompt = BOOST_SPRITE_PROMPT.format(
                style_core=STYLE_CORE,
            )
            ref_images = [profile_ref_b64, run_ref_b64]
            if ref_boost:
                ref_images.append(ref_boost)  # Jazzy boost as primary style reference
            ref_images.extend(self._load_wing_references())

            boost_image = self.client.generate_image_from_photo(
                photo_b64, boost_prompt, reference_images=ref_images,
                model=model, aspect_ratio="1:1"
            )
            if boost_image is None:
                raise RuntimeError("Failed to generate boost sprite. Please try again.")
            self._save_image(boost_image, boost_sprite_path, target_size=self.BOOST_SPRITE_SIZE, asset_kind="boost")
            self._save_image(
                boost_image,
                os.path.join(backup_dir, "boost.png"),
                target_size=self.BOOST_SPRITE_SIZE,
                asset_kind="boost",
            )

            # Step 7: Generate front-facing flight sprite from the generated assets.
            update_progress(7, f"Creating {display_name}'s front-flight sprite...")
            flight_generator = FlightAssetGenerator(self.api_key, self.base_dir)
            flight_result = flight_generator.generate_front_flight_sprite(
                {
                    "id": character_id,
                    "name": display_name,
                    "display_name": display_name,
                    "breed": "custom",
                    "custom": True,
                },
                model=model,
                force=True,
            )
            if not flight_result.success:
                raise RuntimeError(
                    f"Failed to generate front-flight sprite: {flight_result.error_message}"
                )
            flight_sprite_path = flight_result.output_path

            # Register the character
            self._register_character(character_id, display_name, "custom")
            self._update_sprite_loader_mappings(character_id, display_name)

            # Build result
            result = AvatarGenerationResult(
                success=True,
                character_id=character_id,
                character_name=display_name,
                profile_path=profile_path,
                run_sprite_path=run_sprite_path,
                eat_sprite_path=eat_sprite_path,
                walk_sprite_path=walk_sprite_path,
                boost_sprite_path=boost_sprite_path,
                flight_sprite_path=flight_sprite_path,
            )

            progress.is_complete = True
            progress.result = result
            if progress_callback:
                progress_callback(progress)

            return result

        except Exception as e:
            error_msg = str(e)
            progress.is_error = True
            progress.error_message = error_msg
            if progress_callback:
                progress_callback(progress)

            return AvatarGenerationResult(
                success=False,
                error_message=error_msg,
            )

    def generate_avatar_async(self, photo_path: str, dog_name: str,
                              progress_callback: Optional[Callable[[GenerationProgress], None]] = None,
                              completion_callback: Optional[Callable[[AvatarGenerationResult], None]] = None,
                              model: Optional[str] = None) -> threading.Thread:
        """
        Generate avatar asynchronously in a background thread.

        Args:
            photo_path: Path to the dog's photo
            dog_name: Name for the dog character
            progress_callback: Callback for progress updates (called from background thread)
            completion_callback: Callback when generation completes
            model: OpenRouter model to use

        Returns:
            The background thread (already started)
        """
        def _run():
            result = self.generate_avatar(photo_path, dog_name,
                                          progress_callback=progress_callback,
                                          model=model)
            if completion_callback:
                completion_callback(result)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread
