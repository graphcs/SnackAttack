"""Round-start storm intro used by the main gameplay screen."""

import math
from typing import List, Optional

import pygame

from .storm_intro import StormIntroSequence


class RoundStartIntro(StormIntroSequence):
	"""Compatibility wrapper around the shared storm intro sequence.

	The gameplay screen expects a round-start intro that accepts optional run
	animation frame lists for each dog. The base storm intro already handles
	the timing and the general presentation, so this class only adapts the API
	and swaps in run-cycle frames during the dog march.
	"""

	def __init__(self, screen_width: int, screen_height: int):
		super().__init__(screen_width, screen_height)
		self._dog1_frames: List[pygame.Surface] = []
		self._dog2_frames: List[pygame.Surface] = []

	def start(
		self,
		dog1_frames: Optional[List[pygame.Surface]] = None,
		dog2_frames: Optional[List[pygame.Surface]] = None,
		dog1_sprite: Optional[pygame.Surface] = None,
		dog2_sprite: Optional[pygame.Surface] = None,
		dog_ground_y: float = 650.0,
	) -> None:
		self._dog1_frames = [frame for frame in (dog1_frames or []) if frame is not None]
		self._dog2_frames = [
			self._ensure_right_facing(frame) for frame in (dog2_frames or []) if frame is not None
		]

		fallback_dog1 = dog1_sprite or (self._dog1_frames[0] if self._dog1_frames else None)
		fallback_dog2 = dog2_sprite or (dog2_frames[0] if dog2_frames else None)
		fallback_dog2 = self._ensure_right_facing(fallback_dog2)

		super().start(
			dog1_sprite=fallback_dog1,
			dog2_sprite=fallback_dog2,
			dog_ground_y=dog_ground_y,
		)

	def _ensure_right_facing(self, sprite: Optional[pygame.Surface]) -> Optional[pygame.Surface]:
		if sprite is None:
			return None
		return pygame.transform.flip(sprite, True, False)

	def _select_march_frame(
		self,
		frames: List[pygame.Surface],
		fallback: Optional[pygame.Surface],
		phase_offset: float,
	) -> Optional[pygame.Surface]:
		if not frames:
			return fallback
		frame_time = self._march_bob_timer * 10.0 + phase_offset
		frame_index = int(math.floor(frame_time)) % len(frames)
		return frames[frame_index]

	def _render_dog_march(self, surface: pygame.Surface) -> None:
		original_dog1 = self._dog1_sprite
		original_dog2 = self._dog2_sprite

		self._dog1_sprite = self._select_march_frame(self._dog1_frames, original_dog1, 0.0)
		self._dog2_sprite = self._select_march_frame(self._dog2_frames, original_dog2, 0.5)

		try:
			super()._render_dog_march(surface)
		finally:
			self._dog1_sprite = original_dog1
			self._dog2_sprite = original_dog2
