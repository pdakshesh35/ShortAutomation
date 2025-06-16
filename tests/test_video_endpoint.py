import shutil
from pathlib import Path
import types
import sys
import pytest
from fastapi.responses import FileResponse

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

# Dummy modules to satisfy imports in app.py and its dependencies
sys.modules.setdefault('httpx', types.ModuleType('httpx'))

dummy_newsapi = types.ModuleType('newsapi')
class DummyNewsApiClient:
    def __init__(self, *a, **kw):
        pass
    def get_top_headlines(self, **kwargs):
        return {"articles": []}

dummy_newsapi.NewsApiClient = DummyNewsApiClient
sys.modules.setdefault('newsapi', dummy_newsapi)

dummy_dotenv = types.ModuleType('dotenv')
setattr(dummy_dotenv, 'load_dotenv', lambda *a, **kw: None)
sys.modules.setdefault('dotenv', dummy_dotenv)

dummy_openai = types.ModuleType('openai')
class DummyOpenAI:
    class chat:
        class completions:
            @staticmethod
            def create(*a, **kw):
                class DummyChoice:
                    def __init__(self):
                        self.message = types.SimpleNamespace(content='{}')
                class DummyResp:
                    def __init__(self):
                        self.choices = [DummyChoice()]
                return DummyResp()

dummy_openai.OpenAI = lambda api_key=None: DummyOpenAI()
sys.modules.setdefault('openai', dummy_openai)

dummy_runware = types.ModuleType('runware')
class DummyRunware:
    pass
class DummyIImageInference:
    pass

dummy_runware.Runware = DummyRunware
dummy_runware.IImageInference = DummyIImageInference
sys.modules.setdefault('runware', dummy_runware)

dummy_requests = types.ModuleType('requests')
class DummyResponse:
    def __init__(self, content=b''):
        self.content = content
    def raise_for_status(self):
        pass

def dummy_get(url):
    return DummyResponse(b'')

dummy_requests.get = dummy_get
sys.modules.setdefault('requests', dummy_requests)

# Stub out VideoGenerator to avoid heavy imports
stub_video_gen = types.ModuleType('core.video_generator')
class StubVideoGenerator:
    def __init__(self, *a, **kw):
        pass
    def create_final_video(self, data, output_file):
        pass
stub_video_gen.VideoGenerator = StubVideoGenerator
sys.modules.setdefault('core.video_generator', stub_video_gen)

import app

BASE_VIDEO = Path("data/a47bf841-39e2-4556-b414-32c6ce0682d1/final_video.mp4")

@pytest.fixture(autouse=True)
def cleanup_test_video():
    path = Path("data/test_video.mp4")
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()

def test_test_video_endpoint(monkeypatch, tmp_path):
    """Call test_video endpoint handler and verify video output."""

    def dummy_generate(self, input_json, output_video):
        shutil.copyfile(BASE_VIDEO, output_video)

    monkeypatch.setattr("core.video_service.VideoService.generate", dummy_generate)

    response = app.test_video()
    assert isinstance(response, FileResponse)

    output_path = tmp_path / "response_video.mp4"
    with open(response.path, "rb") as f:
        output_path.write_bytes(f.read())

    assert output_path.exists()
    assert output_path.stat().st_size == BASE_VIDEO.stat().st_size
