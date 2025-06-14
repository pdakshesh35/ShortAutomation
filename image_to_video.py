"""Utility to compose a video from images with simple director style instructions."""

from dataclasses import dataclass
from typing import List
from moviepy.editor import ImageClip, concatenate_videoclips, CompositeVideoClip, vfx


@dataclass
class SceneInstruction:
    """Represents a single image scene in the final video."""
    image_path: str
    duration: float = 3.0
    effect: str = "none"  # zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down


class ImageToVideoDirector:
    """Create a video from images applying simple pan/zoom effects."""

    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 24) -> None:
        self.width = width
        self.height = height
        self.fps = fps

    def _apply_effect(self, clip: ImageClip, instruction: SceneInstruction) -> ImageClip:
        effect = instruction.effect
        dur = instruction.duration
        # basic constant movement speed
        speed = 50

        def scaled(clip, dim, dur):
            dist = speed * dur
            scale = 1 + 2 * dist / dim
            c = clip.resize(scale)
            offset = (c.w - self.width) / 2 if dim == clip.w else (c.h - self.height) / 2
            return c, offset
        if effect == "zoom_in":
            return clip.resize(lambda t: 1 + 0.1 * t / dur)
        elif effect == "zoom_out":
            return clip.resize(lambda t: 1 + 0.1 * (1 - t / dur))
        elif effect == "pan_left":
            clip, off = scaled(clip, clip.w, dur)
            return clip.set_position(lambda t: (-speed * t - off, "center"))
        elif effect == "pan_right":
            clip, off = scaled(clip, clip.w, dur)
            return clip.set_position(lambda t: (speed * t - off, "center"))
        elif effect == "pan_up":
            clip, off = scaled(clip, clip.h, dur)
            return clip.set_position(lambda t: ("center", -speed * t - off))
        elif effect == "pan_down":
            clip, off = scaled(clip, clip.h, dur)
            return clip.set_position(lambda t: ("center", speed * t - off))
        return clip

    def create_video(self, instructions: List[SceneInstruction], output_file: str) -> None:
        clips = []
        for inst in instructions:
            clip = ImageClip(inst.image_path).set_duration(inst.duration)
            # Fit image to video size while preserving aspect
            clip = clip.resize(height=self.height)
            if clip.w < self.width:
                clip = clip.resize(width=self.width)
            clip = self._apply_effect(clip, inst)
            clips.append(clip)
        if not clips:
            raise ValueError("No scenes provided")
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_file, fps=self.fps, codec="libx264", audio=False)
