#!/usr/bin/env python3
"""Generate one winged boost sprite per dog using Nano Banana.

Output:
- Sprite sheets/boost_wings/<Name> boost.png

This is a single static sprite used when boost is active.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.env_loader import load_env, get_openrouter_key
from src.generators.openrouter_client import OpenRouterClient, GeneratedImage


BOOST_STYLE = (
    "Create one pixel-art dog sprite in the exact same style and palette as the provided reference. "
    "The dog identity, body size, fur colors, outline thickness, and proportions must remain unchanged. "
    "Add natural angel wings growing from the shoulder blades, integrated into the body silhouette. "
    "Wings must look anatomically attached (no floating stickers), with feather root blending into fur. "
    "Transparent background only. No text, no shadows, no floor."
)

BOOST_PROMPT = (
    "You are given: (1) base dog sprite reference, (2) wing reference image A, (3) wing reference image B. "
    "Generate a SINGLE dog sprite facing RIGHT with wings integrated into the body. "
    "Keep the same character identity and proportions as the base reference. "
    "Pose: neutral standing/running-ready side view. "
    "Output one transparent PNG image (not a sprite sheet). "
    f"{BOOST_STYLE}"
)


def read_b64(path: Path) -> str:
    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def save_generated_image(image: GeneratedImage, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        f.write(image.get_bytes())


def load_characters(config_path: Path) -> List[Dict[str, Any]]:
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("characters", [])


def display_name(char: Dict[str, Any]) -> str:
    return char.get("display_name") or char.get("name") or char.get("id", "dog").capitalize()


def find_base_sprite(base_dir: Path, char: Dict[str, Any]) -> Optional[Path]:
    """Find base sprite reference for a character (prefer run sprite)."""
    cid = char.get("id", "")
    name = display_name(char)

    sprite_dir = base_dir / "Sprite sheets"
    custom_dir = base_dir / "custom_avatars" / cid

    # Built-in naming variants in Sprite sheets/
    run_candidates = [
        sprite_dir / f"{name} run sprite.png",
        sprite_dir / f"{name} run.png",
        sprite_dir / f"{name} running.png",
    ]
    # Custom avatar fallback naming
    run_candidates.extend([
        custom_dir / "run_sprite.png",
    ])

    return next((p for p in run_candidates if p.exists()), None)


def build_output_path(base_dir: Path, char: Dict[str, Any]) -> Path:
    name = display_name(char)
    out_dir = base_dir / "Sprite sheets" / "boost_wings"
    return out_dir / f"{name} boost.png"


def generate_sprite(
    client: OpenRouterClient,
    prompt: str,
    base_sprite_b64: str,
    wing_up_b64: str,
    wing_down_b64: str,
    model: str,
    aspect_ratio: str = "1:1",
) -> Optional[GeneratedImage]:
    refs = [wing_up_b64, wing_down_b64]
    return client.generate_image_from_photo(
        photo_base64=base_sprite_b64,
        prompt=prompt,
        reference_images=refs,
        model=model,
        aspect_ratio=aspect_ratio,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one winged boost sprite per dog")
    parser.add_argument("--pro", action="store_true", help="Use Nano Banana Pro image model")
    parser.add_argument("--model", default="", help="Override model id")
    parser.add_argument("--only", default="", help="Comma-separated character ids to generate")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs")
    args = parser.parse_args()

    load_env()
    api_key = get_openrouter_key()
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set in environment/.env")
        return 1

    client = OpenRouterClient(api_key)
    model = args.model or (client.IMAGE_MODEL if args.pro else client.IMAGE_MODEL_FAST)

    config_path = ROOT / "config" / "characters.json"
    chars = load_characters(config_path)

    selected_ids = {s.strip().lower() for s in args.only.split(",") if s.strip()} if args.only else set()
    if selected_ids:
        chars = [c for c in chars if c.get("id", "").lower() in selected_ids]

    wings_dir = ROOT / "Sprite sheets" / "wings"
    wing_up = wings_dir / "wing_up.png"
    wing_down = wings_dir / "wing_down.png"
    if not wing_up.exists() or not wing_down.exists():
        print("ERROR: Missing wing references. Expected:")
        print(f"  - {wing_up}")
        print(f"  - {wing_down}")
        return 1

    wing_up_b64 = read_b64(wing_up)
    wing_down_b64 = read_b64(wing_down)

    print(f"Using model: {model}")
    print(f"Characters: {len(chars)}")

    ok = 0
    skipped = 0
    failed = 0

    for char in chars:
        cid = char.get("id", "unknown")
        name = display_name(char)

        base_sprite = find_base_sprite(ROOT, char)
        if not base_sprite:
            print(f"[SKIP] {cid}: missing base sprite reference")
            skipped += 1
            continue

        out_path = build_output_path(ROOT, char)
        if not args.force and out_path.exists():
            print(f"[SKIP] {cid}: outputs already exist")
            skipped += 1
            continue

        print(f"[GEN] {cid} ({name})")

        try:
            base_b64 = read_b64(base_sprite)

            boost_img = generate_sprite(
                client=client,
                prompt=BOOST_PROMPT,
                base_sprite_b64=base_b64,
                wing_up_b64=wing_up_b64,
                wing_down_b64=wing_down_b64,
                model=model,
            )
            if boost_img is None:
                raise RuntimeError("boost sprite generation returned no image")
            save_generated_image(boost_img, out_path)

            print(f"  -> {out_path.relative_to(ROOT)}")
            ok += 1
        except Exception as e:
            print(f"[FAIL] {cid}: {e}")
            failed += 1

    print("\nDone.")
    print(f"  Success: {ok}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed : {failed}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
