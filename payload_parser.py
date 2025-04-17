import json
from typing import Dict, List, Optional

class Scene:
    def __init__(self, scene_id: str, script: str, image_prompt: str,
                 audio_path: str, image_url: str):
        self.scene_id = scene_id
        self.script = script
        self.image_prompt = image_prompt
        self.audio_path = audio_path
        self.image_url = image_url

    @classmethod
    def from_dict(cls, data: Dict) -> "Scene":
        return cls(
            scene_id=data.get("scene_id", ""),
            script=data.get("script", ""),
            image_prompt=data.get("imagePrompt", ""),
            audio_path=data.get("audioPath", ""),
            image_url=data.get("imageUrl", "")
        )

    def to_dict(self) -> Dict:
        return {
            "scene_id": self.scene_id,
            "script": self.script,
            "imagePrompt": self.image_prompt,
            "audioPath": self.audio_path,
            "imageUrl": self.image_url
        }

class Payload:
    def __init__(self, scenes: List[Scene], metadata: Dict, request_id: str):
        self._scenes = scenes
        self.metadata = metadata
        self.request_id = request_id

    @classmethod
    def load_from_json(cls, json_str: str) -> "Payload":
        data = json.loads(json_str)
        metadata = data.get("metadata", {})
        request_id = data.get("request_id", "")
        scene_keys = sorted(
            (k for k in data.keys() if k.isdigit()),
            key=lambda x: int(x)
        )
        scenes = [Scene.from_dict(data[key]) for key in scene_keys]
        return cls(scenes=scenes, metadata=metadata, request_id=request_id)

    @classmethod
    def load_from_file(cls, filepath: str) -> "Payload":
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.load_from_json(f.read())

    def get_scene(self, number: int) -> Optional[Scene]:
        for scene in self._scenes:
            # match based on numeric order of the scenes
            if int(scene.scene_id.split("-")[0]) == number:
                return scene
        return None

    def get_all_scenes(self) -> List[Scene]:
        return self._scenes

    def get_metadata(self) -> Dict:
        return self.metadata

    def get_request_id(self) -> str:
        return self.request_id