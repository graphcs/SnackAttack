"""OpenRouter API client for image generation and vision analysis."""

import json
import base64
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class GeneratedImage:
    """Container for a generated image."""
    base64_data: str
    mime_type: str = "image/png"

    def get_bytes(self) -> bytes:
        """Decode base64 data to raw bytes."""
        return base64.b64decode(self.base64_data)


class OpenRouterClient:
    """Client for OpenRouter API supporting vision and image generation."""

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    # Google Nano Banana Pro — best image generation with identity preservation
    IMAGE_MODEL = "google/gemini-3.1-flash-image-preview"
    # Google Nano Banana — faster/cheaper alternative
    IMAGE_MODEL_FAST = "google/gemini-2.5-flash-image"
    # Legacy OpenAI models
    IMAGE_MODEL_GPT = "openai/gpt-5-image"
    IMAGE_MODEL_GPT_MINI = "openai/gpt-5-image-mini"

    # Model for vision-only analysis
    VISION_MODEL = "openai/gpt-4o"

    # Supported aspect ratios for Gemini image generation
    SUPPORTED_ASPECT_RATIOS = {
        "1:1", "2:3", "3:2", "3:4", "4:3",
        "4:5", "5:4", "9:16", "16:9", "21:9",
    }

    def __init__(self, api_key: str):
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://snackattack.game",
            "X-Title": "Jazzy's Treat Storm",
        }

    def _make_request(self, payload: Dict[str, Any], timeout: int = 120,
                      max_retries: int = 2) -> Dict[str, Any]:
        """
        Make a request to OpenRouter API with retry logic.

        Args:
            payload: Request body
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient errors (429, 500, 502, 503)

        Returns:
            Response JSON

        Raises:
            ConnectionError: If request fails after retries
            ValueError: If response is invalid
        """
        data = json.dumps(payload).encode("utf-8")

        for attempt in range(max_retries + 1):
            req = urllib.request.Request(
                self.API_URL,
                data=data,
                headers=self.headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    response_data = response.read().decode("utf-8")
                    return json.loads(response_data)
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8") if e.fp else ""
                # Retry on transient errors
                if e.code in (429, 500, 502, 503) and attempt < max_retries:
                    wait = (attempt + 1) * 5
                    print(f"[OpenRouter] HTTP {e.code}, retrying in {wait}s... "
                          f"(attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                    continue
                raise ConnectionError(
                    f"OpenRouter API error {e.code}: {error_body}"
                ) from e
            except urllib.error.URLError as e:
                if attempt < max_retries:
                    wait = (attempt + 1) * 3
                    print(f"[OpenRouter] Connection error, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise ConnectionError(
                    f"Failed to connect to OpenRouter: {e.reason}"
                ) from e

    def analyze_image(self, image_base64: str, prompt: str,
                      model: Optional[str] = None) -> str:
        """
        Analyze an image using a vision model.

        Args:
            image_base64: Base64-encoded image data
            prompt: Analysis prompt
            model: Model to use (defaults to VISION_MODEL)

        Returns:
            Text response from the model
        """
        model = model or self.VISION_MODEL

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 1000,
        }

        response = self._make_request(payload)
        return self._extract_text(response)

    def generate_image(self, prompt: str, 
                       reference_image_base64: Optional[str] = None,
                       model: Optional[str] = None,
                       aspect_ratio: Optional[str] = None) -> Optional[GeneratedImage]:
        """
        Generate an image using an image generation model.

        Args:
            prompt: Image generation prompt
            reference_image_base64: Optional reference image for style matching
            model: Model to use (defaults to IMAGE_MODEL)
            aspect_ratio: Optional aspect ratio (e.g. '1:1', '3:1', '16:9')

        Returns:
            GeneratedImage or None if generation failed
        """
        model = model or self.IMAGE_MODEL

        # Build message content
        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]

        if reference_image_base64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{reference_image_base64}",
                    "detail": "high",
                },
            })

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": content}
            ],
            "modalities": ["image", "text"],
            "max_tokens": 4096,
        }

        if aspect_ratio:
            if aspect_ratio not in self.SUPPORTED_ASPECT_RATIOS:
                print(f"[OpenRouter] Warning: '{aspect_ratio}' not supported. "
                      f"Supported: {sorted(self.SUPPORTED_ASPECT_RATIOS)}. Omitting.")
            else:
                payload["image_config"] = {"aspect_ratio": aspect_ratio}

        response = self._make_request(payload, timeout=180)
        return self._extract_image(response)

    def generate_image_from_photo(self, photo_base64: str, prompt: str,
                                  reference_images: Optional[List[str]] = None,
                                  model: Optional[str] = None,
                                  aspect_ratio: Optional[str] = None) -> Optional[GeneratedImage]:
        """
        Generate a styled image based on a reference photo.

        Sends the photo as vision input and requests image generation output.
        Optionally sends additional reference images for style matching.

        Args:
            photo_base64: Base64-encoded photo of the dog
            prompt: Detailed prompt for style conversion
            reference_images: Optional list of base64-encoded reference images
            model: Model to use
            aspect_ratio: Optional aspect ratio (e.g. '1:1', '3:2', '16:9')

        Returns:
            GeneratedImage or None
        """
        model = model or self.IMAGE_MODEL

        content: List[Dict[str, Any]] = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{photo_base64}",
                    "detail": "high",
                },
            },
        ]

        # Add reference images for style matching
        if reference_images:
            for ref_b64 in reference_images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{ref_b64}",
                        "detail": "high",
                    },
                })

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": content}
            ],
            "modalities": ["image", "text"],
            "max_tokens": 4096,
        }

        if aspect_ratio:
            if aspect_ratio not in self.SUPPORTED_ASPECT_RATIOS:
                print(f"[OpenRouter] Warning: '{aspect_ratio}' not supported. "
                      f"Supported: {sorted(self.SUPPORTED_ASPECT_RATIOS)}. Omitting.")
            else:
                payload["image_config"] = {"aspect_ratio": aspect_ratio}

        response = self._make_request(payload, timeout=180)
        return self._extract_image(response)

    def _extract_text(self, response: Dict[str, Any]) -> str:
        """Extract text content from API response."""
        try:
            choices = response.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")
                if isinstance(content, str):
                    return content
                # Some models return content as a list of parts
                if isinstance(content, list):
                    texts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            texts.append(part.get("text", ""))
                    return " ".join(texts)
        except (IndexError, KeyError, TypeError):
            pass
        return ""

    def _extract_image(self, response: Dict[str, Any]) -> Optional[GeneratedImage]:
        """Extract image from API response."""
        try:
            choices = response.get("choices", [])
            if not choices:
                return None

            message = choices[0].get("message", {})

            # Check for images array (OpenRouter format)
            images = message.get("images", [])
            if images:
                image_url = images[0].get("image_url", {}).get("url", "")
                if image_url.startswith("data:"):
                    # Parse data URL: data:image/png;base64,<data>
                    header, data = image_url.split(",", 1)
                    mime = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
                    return GeneratedImage(base64_data=data, mime_type=mime)

            # Fallback: check content for inline base64 image
            content = message.get("content", "")
            if content:
                # Some models return images embedded in content parts
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "image_url":
                            url = part.get("image_url", {}).get("url", "")
                            if url.startswith("data:"):
                                header, data = url.split(",", 1)
                                mime = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
                                return GeneratedImage(base64_data=data, mime_type=mime)

        except (IndexError, KeyError, TypeError, ValueError) as e:
            print(f"Error extracting image from response: {e}")

        return None

    def test_connection(self) -> bool:
        """Test if the API key is valid."""
        try:
            payload = {
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": "Say 'ok'"}],
                "max_tokens": 5,
            }
            response = self._make_request(payload, timeout=15)
            return bool(self._extract_text(response))
        except Exception:
            return False
