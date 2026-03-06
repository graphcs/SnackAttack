"""Avatar generator - converts dog photos into game-ready pixel art sprites."""

import os
import io
import base64
import json
import threading
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field

from .openrouter_client import OpenRouterClient, GeneratedImage
from .background_remover import ensure_transparency


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


@dataclass
class GenerationProgress:
    """Tracks progress of avatar generation."""
    current_step: int = 0
    total_steps: int = 7
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
    WALK_SHEET_SIZE = (1430, 286)      # Walk sheets: 5 frames, horizontal strip
    BOOST_SPRITE_SIZE = (500, 500)     # Single boost sprite (winged form)

    # ----- STYLE REFERENCE -----
    STYLE_CORE = (
        "You MUST match the EXACT same pixel art style shown in the reference sprite image I am providing. "
        "Study the reference image carefully: copy its pixel density, thick black outlines, "
        "level of detail, chunky proportions, warm retro color palette, shading technique, and overall vibe. "
        "The output must look like it belongs in the same game as the reference sprite — "
        "same resolution feel, same outline thickness, same level of pixelation. "
        "CRITICAL: The background MUST be fully transparent (alpha = 0). "
        "Do NOT draw any ground, shadow, floor, scenery, or solid background color. "
        "The dog character must be the ONLY element in the image, floating on a transparent background. "
        "Output as PNG with transparency."
    )

    # Step 0: Describe the dog for consistency across all generations
    DESCRIBE_DOG_PROMPT = (
        "Look at this photo of a dog. Describe it in PRECISE detail so another artist can draw "
        "the EXACT same dog without seeing the photo. Include: breed/mix, size proportions (stocky/slim/etc), "
        "exact fur colors and pattern (e.g. 'golden tan body with white chest patch and black muzzle'), "
        "ear shape (floppy/pointed/folded), tail type, "
        "any unique markings (spots, patches, mask, socks). "
        "Keep the description to 3-4 sentences, very specific."
    )

    PROFILE_PROMPT = (
        "I am providing two images:\n"
        "IMAGE 1 (first image): A photo of a real dog.\n"
        "IMAGE 2 (second image): A reference pixel art sprite from my game — match this EXACT art style.\n\n"
        "DOG IDENTITY (you MUST match this dog exactly): {dog_description}\n\n"
        "Create a single pixel art PORTRAIT of this specific dog, drawn in the exact same style "
        "as the reference sprite. The portrait should show the dog sitting and facing slightly toward "
        "the viewer (3/4 front view), looking cute and happy with a visible tongue. "
        "The dog should be centered and fill most of the square image. "
        "This will be used as a character select portrait in a retro arcade game.\n\n"
        "{style_core}\n"
        "Output a single SQUARE image."
    )

    RUN_SPRITE_PROMPT = (
        "I am providing three images:\n"
        "IMAGE 1 (first image): A photo of a real dog.\n"
        "IMAGE 2 (second image): The pixel art version of this dog that I already created — "
        "you MUST draw the EXACT SAME dog character with identical colors, proportions, and markings.\n"
        "IMAGE 3 (third image): A reference RUN SPRITE SHEET from my game — match this EXACT layout.\n\n"
        "DOG IDENTITY (you MUST match this dog exactly): {dog_description}\n\n"
        "Create a HORIZONTAL SPRITE SHEET containing EXACTLY 3 animation frames of this dog RUNNING, "
        "arranged side by side in a single wide image (width = 3x height). "
        "Study the reference sprite sheet layout: 3 equally-sized frames placed left to right. "
        "Each frame shows the dog in side-view profile, facing RIGHT, in a different phase of a run cycle: "
        "Frame 1 (left): normal stance. "
        "Frame 2 (center): legs mid-stride, body bouncing up. "
        "Frame 3 (right): opposite leg positions from frame 1. "
        "The dog must be the SAME SIZE and in the SAME POSITION in all 3 frames. "
        "Only the legs should change between frames.\n\n"
        "CRITICAL: The dog in this sprite sheet must be the EXACT SAME character as in IMAGE 2. "
        "Same colors, same fur pattern, same ear shape, same proportions.\n\n"
        "{style_core}\n"
        "Output a SINGLE WIDE image with all 3 frames side by side."
    )

    EAT_SPRITE_PROMPT = (
        "I am providing three images:\n"
        "IMAGE 1 (first image): A photo of a real dog.\n"
        "IMAGE 2 (second image): The pixel art version of this dog that I already created — "
        "you MUST draw the EXACT SAME dog character with identical colors, proportions, and markings.\n"
        "IMAGE 3 (third image): A reference EAT/ATTACK SPRITE SHEET from my game — match this EXACT layout.\n\n"
        "DOG IDENTITY (you MUST match this dog exactly): {dog_description}\n\n"
        "Create a HORIZONTAL SPRITE SHEET containing EXACTLY 3 animation frames of this dog EATING/BITING, "
        "arranged side by side in a single wide image (width = 3x height). "
        "Study the reference sprite sheet layout: 3 equally-sized frames placed left to right. "
        "Each frame shows the dog in side-view profile, facing RIGHT: "
        "Frame 1 (left): Idle pose. Standing on all four short legs with a neutral expression and tail slightly raised. "
        "Frame 2 (center): Lunge/Attack pose. Body lowered, leaning forward with mouth wide open (showing pink tongue). Ears and tail sweeping back from momentum. "
        "Frame 3 (right): Leap pose. Jumping on hind legs, body angled upward. Front paws raised together, mouth open, ears flipped back."
        "The dog must be the SAME SIZE and in the SAME POSITION in all 3 frames. "
        "Only the mouth/head should change between frames.\n\n"
        "CRITICAL: The dog in this sprite sheet must be the EXACT SAME character as in IMAGE 2. "
        "Same colors, same fur pattern, same ear shape, same proportions.\n\n"
        "{style_core}\n"
        "Output a SINGLE WIDE image with all 3 frames side by side."
    )

    WALK_SPRITE_PROMPT = (
        "I am providing three images:\n"
        "IMAGE 1 (first image): A photo of a real dog.\n"
        "IMAGE 2 (second image): The pixel art version of this dog that I already created — "
        "you MUST draw the EXACT SAME dog character with identical colors, proportions, and markings.\n"
        "IMAGE 3 (third image): A reference RUN SPRITE from my game — match this EXACT art style.\n\n"
        "DOG IDENTITY (you MUST match this dog exactly): {dog_description}\n\n"
        "Create a HORIZONTAL SPRITE SHEET containing EXACTLY 5 animation frames of this dog WALKING "
        "Frame 1: The Stretch (Extended) :The front-right leg is extended forward, just touching the ground. The back-right leg is extended fully behind, pushing off the toe. The tail is curled upward."
        "Frame 2: The Plant (Down): The body weight shifts onto the front-right leg, which is now vertical under the shoulder. The back-left leg begins to pull forward, while the back-right leg is mid-lift."
        "Frame 3: The Passing (Mid):The front-right leg angles backward. The front-left leg is lifted and passing the stationary leg. The back-left leg is bent and moving forward under the belly."
        "Frame 4: The Lift (Up) :The front-left leg is lifted high, knee bent, preparing to step forward. The back-left leg is reaching toward its forward landing position. The tail stays curled."
        "Frame 5: The Reset (Contact): The front-left leg is fully extended forward for the next step. The back-right leg is planted firmly. This mirrors Frame 1 but with the opposite leg set, completing the loop."        
        "(not running — a slower, gentle walk), arranged side by side in a single wide image. "
        "Each frame shows the dog in side-view profile, facing RIGHT, in a different phase of a walk cycle. "
        "The dog must be the SAME SIZE in all 5 frames. Only the legs move between frames, "
        "showing a smooth walking gait.\n\n"
        "CRITICAL: The dog in this sprite sheet must be the EXACT SAME character as in IMAGE 2. "
        "Same colors, same fur pattern, same ear shape, same proportions.\n\n"
        "{style_core}\n"
        "Output a SINGLE WIDE image with all 5 frames side by side."
    )

    BOOST_SPRITE_PROMPT = (
        "I am providing multiple references:\n"
        "IMAGE 1: Real dog photo.\n"
        "IMAGE 2: Generated pixel-art profile of this exact dog.\n"
        "IMAGE 3: Pixel-art run reference from the game style.\n"
        "IMAGE 4/5: Wing reference images.\n\n"
        "DOG IDENTITY (you MUST match this dog exactly): {dog_description}\n\n"
        "Create ONE single side-view pixel-art sprite of this dog facing RIGHT, with wings naturally emerging "
        "from the shoulder/back area. The wings must look attached to the body (not floating), with feather roots "
        "blending into fur. Keep exactly the same character identity and palette as IMAGE 2.\n\n"
        "This is a boost state sprite for a retro arcade game.\n"
        "Output a SINGLE SQUARE image (transparent background).\n\n"
        "{style_core}"
    )

    # Reference sprite files to load (from existing characters)
    REFERENCE_SPRITES = {
        "profile": "Jazzy.png",          # Profile/ directory
        "run": "Jazzy run sprite.png",   # Sprite sheets/ directory
        "eat": "Jazzy eat:attack sprite.png",  # Sprite sheets/ directory
    }

    def __init__(self, api_key: str, base_dir: str):
        """
        Initialize the avatar generator.

        Args:
            api_key: OpenRouter API key
            base_dir: Project root directory
        """
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

    def _describe_dog(self, photo_b64: str) -> str:
        """
        Get a detailed text description of the dog from the photo.

        This description is injected into ALL subsequent image generation prompts
        to ensure the AI draws the exact same dog consistently across profile,
        run, eat, and walk sprites.

        Args:
            photo_b64: Base64-encoded photo of the dog

        Returns:
            Text description of the dog's appearance
        """
        try:
            description = self.client.analyze_image(
                photo_b64, self.DESCRIBE_DOG_PROMPT
            )
            if description and len(description.strip()) > 10:
                return description.strip()
        except Exception as e:
            print(f"[AvatarGenerator] Warning: Dog description failed ({e})")

        return "a cute dog matching the photo provided"

    def _save_image(self, image: GeneratedImage, output_path: str,
                    target_size: Optional[Tuple[int, int]] = None) -> None:
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

                if (iw, ih) != (tw, th):
                    is_sprite_sheet = tw > th * 1.2  # Wider than tall = sprite sheet

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
        1. First describing the dog in text (breed, colors, markings)
        2. Generating the profile portrait
        3. Sending BOTH the photo AND the generated profile to subsequent steps
           so the AI draws the exact same pixel-art dog every time
        4. Resizing all outputs to exact game dimensions

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
            # Step 1: Load photo + reference sprites + describe the dog
            update_progress(1, "Analyzing your dog's features...")
            photo_b64 = self._load_and_encode_photo(photo_path)
            character_id = self._generate_character_id(dog_name)
            display_name = dog_name.strip().title()

            # Get detailed text description of the dog for consistency
            dog_description = self._describe_dog(photo_b64)
            print(f"[AvatarGenerator] Dog description: {dog_description}")

            # Load reference sprites for style matching
            ref_profile = self._load_reference_sprite("profile")
            ref_run = self._load_reference_sprite("run")
            ref_eat = self._load_reference_sprite("eat")

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
            profile_prompt = self.PROFILE_PROMPT.format(
                style_core=self.STYLE_CORE,
                dog_description=dog_description,
            )
            ref_images = [ref_profile] if ref_profile else []
            profile_image = self.client.generate_image_from_photo(
                photo_b64, profile_prompt, reference_images=ref_images,
                model=model, aspect_ratio="1:1"
            )
            if profile_image is None:
                raise RuntimeError("Failed to generate profile portrait. Please try again.")
            self._save_image(profile_image, profile_path, target_size=self.PROFILE_SIZE)
            self._save_image(profile_image, os.path.join(backup_dir, "profile.png"), target_size=self.PROFILE_SIZE)

            # Encode the generated profile to use as identity reference for subsequent sprites
            profile_ref_b64 = base64.b64encode(profile_image.get_bytes()).decode("utf-8")

            # Step 3: Generate run sprite sheet
            # Send: photo + generated profile (identity) + Jazzy run (layout reference)
            update_progress(3, f"Creating {display_name}'s run animation...")
            run_prompt = self.RUN_SPRITE_PROMPT.format(
                style_core=self.STYLE_CORE,
                dog_description=dog_description,
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

            # Step 4: Generate eat/attack sprite sheet
            # Send: photo + generated profile (identity) + Jazzy eat (layout reference)
            update_progress(4, f"Creating {display_name}'s eat animation...")
            eat_prompt = self.EAT_SPRITE_PROMPT.format(
                style_core=self.STYLE_CORE,
                dog_description=dog_description,
            )
            ref_images = [profile_ref_b64]
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
            # Send: photo + generated profile (identity) + Jazzy run (style reference)
            update_progress(5, f"Creating {display_name}'s walk animation...")
            walk_prompt = self.WALK_SPRITE_PROMPT.format(
                style_core=self.STYLE_CORE,
                dog_description=dog_description,
            )
            ref_images = [profile_ref_b64]
            if ref_run:
                ref_images.append(ref_run)
            walk_image = self.client.generate_image_from_photo(
                photo_b64, walk_prompt, reference_images=ref_images,
                model=model, aspect_ratio="21:9"
            )
            if walk_image is None:
                # Walking is optional — don't fail the whole generation
                print(f"[AvatarGenerator] Warning: Walking sprite generation failed for {display_name}")
                walk_sprite_path = ""
            else:
                self._save_image(walk_image, walk_sprite_path, target_size=self.WALK_SHEET_SIZE)
                self._save_image(walk_image, os.path.join(backup_dir, "walk_sprite.png"), target_size=self.WALK_SHEET_SIZE)

            # Step 6: Generate single boost sprite (winged form)
            update_progress(6, f"Creating {display_name}'s winged boost form...")
            boost_prompt = self.BOOST_SPRITE_PROMPT.format(
                style_core=self.STYLE_CORE,
                dog_description=dog_description,
            )
            ref_images = [profile_ref_b64]
            if ref_run:
                ref_images.append(ref_run)
            ref_images.extend(self._load_wing_references())

            boost_image = self.client.generate_image_from_photo(
                photo_b64, boost_prompt, reference_images=ref_images,
                model=model, aspect_ratio="1:1"
            )
            if boost_image is None:
                print(f"[AvatarGenerator] Warning: Boost sprite generation failed for {display_name}")
                boost_sprite_path = ""
            else:
                self._save_image(boost_image, boost_sprite_path, target_size=self.BOOST_SPRITE_SIZE)
                self._save_image(boost_image, os.path.join(backup_dir, "boost.png"), target_size=self.BOOST_SPRITE_SIZE)

            # Step 7: Register the character
            update_progress(7, f"Registering {display_name}...")
            self._register_character(character_id, display_name, dog_description)
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
