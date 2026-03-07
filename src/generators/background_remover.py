"""Background removal using the rembg API service."""

import io
import requests
from typing import Optional
from src.core.env_loader import load_env,get_rembg_key


load_env()
# rembg API configuration
REMBG_API_URL = "https://api.rembg.com/rmbg"
REMBG_API_KEY = get_rembg_key()


def remove_background_api(image_bytes: bytes) -> bytes:
    """
    Remove the background from an image using the rembg API.

    Sends the image to the remote rembg service which uses AI-based
    segmentation for accurate background removal.

    Args:
        image_bytes: Raw image bytes (PNG, JPG, etc.)

    Returns:
        Processed PNG image bytes with transparent background

    Raises:
        ConnectionError: If the API request fails
    """
    headers = {
        "x-api-key": REMBG_API_KEY,
    }

    files = {
        "image": ("sprite.png", io.BytesIO(image_bytes), "image/png"),
    }

    data = {
        "format": "png",
        "mask": "false",
    }

    try:
        response = requests.post(
            REMBG_API_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=60,
        )

        if response.status_code == 200:
            return response.content
        else:
            raise ConnectionError(
                f"rembg API error {response.status_code}: {response.text}"
            )
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Failed to connect to rembg API: {e}") from e


def ensure_transparency(image_bytes: bytes, force_api: bool = False) -> bytes:
    """
    Ensure an image has a transparent background using the rembg API.

    Checks if the image already has a transparent background (by inspecting
    corner pixels). If not, sends it to the rembg API for removal.

    Args:
        image_bytes: Raw PNG image bytes
        force_api: If True, always send the image through rembg even if the
                   corner pixels already look transparent.

    Returns:
        Processed PNG image bytes with transparent background
    """
    from PIL import Image

    if force_api:
        return remove_background_api(image_bytes)

    # Quick check: if corners are already transparent, skip API call
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size
    pixels = img.load()

    corners = [
        (0, 0), (width - 1, 0),
        (0, height - 1), (width - 1, height - 1),
    ]
    transparent_corners = sum(
        1 for cx, cy in corners if pixels[cx, cy][3] < 10
    )
    if transparent_corners >= 3:
        # Already mostly transparent background
        return image_bytes

    # Use rembg API for accurate background removal
    return remove_background_api(image_bytes)
