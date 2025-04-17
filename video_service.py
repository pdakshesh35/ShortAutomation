import json
from typing import Dict
from payload_parser import Payload
from video_generator import VideoGenerator
import requests
import os
import tempfile
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self, width: int, height: int):
        self.generator = VideoGenerator(width, height)

    def generate_from_dict(self, data: Dict, output_file: str):
        """
        Generate a video directly from the given scene dictionary.
        The dictionary must have string keys "1", "2", ... for each scene,
        and may include a 'scenes' key for count.
        """
        if "scenes" not in data:
            count = len([k for k in data.keys() if k.isdigit()])
            data["scenes"] = str(count)
        self.generator.create_final_video(data, output_file)

    def generate_from_json(self, json_str: str, output_file: str):
        """
        Parse the JSON string into a Payload, build the scene dict, and generate the video.
        """
        payload = Payload.load_from_json(json_str)
        scene_dict = {
            str(i + 1): scene.to_dict()
            for i, scene in enumerate(payload.get_all_scenes())
        }
        scene_dict["scenes"] = str(len(payload.get_all_scenes()))
        self.generate_from_dict(scene_dict, output_file)

    def generate_from_file(self, filepath: str, output_file: str):
        """
        Load JSON from a file path and generate the video.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            json_str = f.read()
        self.generate_from_json(json_str, output_file)

    def generate(self, input_json_path: str, output_video_path: str):
        """
        Load payload from a JSON file, download images and stitch scenes into a single video,
        then generate an SRT subtitle file with word-sync for social media.
        """
        # Validate input JSON file
        if not os.path.exists(input_json_path):
            logger.error(f"Input JSON file not found: {input_json_path}")
            raise FileNotFoundError(f"Input JSON file not found: {input_json_path}")

        # Load payload
        try:
            payload = Payload.load_from_file(input_json_path)
        except Exception as e:
            logger.error(f"Failed to parse JSON file {input_json_path}: {e}")
            raise

        scenes = payload.get_all_scenes()
        if not scenes:
            logger.error("No scenes found in payload")
            raise ValueError("No scenes found in payload")

        # Create temporary directory for downloaded images
        tmp_dir = tempfile.mkdtemp()

        # Build scene dict for VideoGenerator
        scene_dict = {}
        for idx, scene in enumerate(scenes, start=1):
            # Validate audio file existence
            audio_path = scene.audio_path
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found: {audio_path}")
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            # Download image from URL
            try:
                img_resp = requests.get(scene.image_url)
                img_resp.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Failed to download image for scene {idx}: {scene.image_url}, error: {e}")
                raise

            # Use unique file name based on index
            img_path = os.path.join(tmp_dir, f"scene_{idx}.jpg")
            with open(img_path, "wb") as img_file:
                img_file.write(img_resp.content)

            # Populate scene entry
            scene_dict[str(idx)] = {
                "script": scene.script,
                "imagePath": img_path,
                "audioPath": audio_path
            }
            logger.info(f"Scene {idx}: image={img_path}, audio={audio_path}, scene_id={scene.scene_id}")

        # Add total scenes count
        scene_dict["scenes"] = str(len(scenes))

        # Generate video
        try:
            self.generate_from_dict(scene_dict, output_video_path)
        finally:
            # Clean up temporary directory
            for file in os.listdir(tmp_dir):
                os.remove(os.path.join(tmp_dir, file))
            os.rmdir(tmp_dir)