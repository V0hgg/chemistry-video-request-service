from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, repr=False)
class Settings:
    base_url: str
    api_key: str
    model: str
    reasoning_effort: str
    response_format: str
    worker_concurrency: int
    data_root: Path
    work_root: Path
    blender_bin: Path = Path("/Applications/Blender.app/Contents/MacOS/Blender")
    tts_model_path: Path = ROOT / "data/models/kokoro-v1.0.onnx"
    tts_voices_path: Path = ROOT / "data/models/voices-v1.0.bin"
    tts_voice: str = "af_heart"
    tts_speed: float = 0.94
    render_fps: int = 15
    render_width: int = 960
    render_height: int = 540

    def validate_worker(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or not self.api_key:
            raise ValueError("Worker needs OPENAI_BASE_URL and OPENAI_API_KEY")
        if self.reasoning_effort != "max":
            raise ValueError("OPENAI_REASONING_EFFORT must be max")
        if self.response_format not in {"json_schema", "json_object"}:
            raise ValueError("OPENAI_RESPONSE_FORMAT must be json_schema or json_object")
        if not 1 <= self.worker_concurrency <= 4:
            raise ValueError("VIDEO_WORKER_CONCURRENCY must be between 1 and 4")

    def validate_media(self) -> None:
        if not self.blender_bin.is_file():
            raise ValueError("Blender executable is missing; set BLENDER_BIN")
        if not self.tts_model_path.is_file() or not self.tts_voices_path.is_file():
            raise ValueError("Local voice model is missing; run the media setup instructions")
        if self.tts_voice not in {"af_heart", "af_sarah"}:
            raise ValueError("TTS_VOICE must be af_heart or af_sarah")
        if not 0.8 <= self.tts_speed <= 1.2:
            raise ValueError("TTS_SPEED must be between 0.8 and 1.2")
        if not 12 <= self.render_fps <= 24:
            raise ValueError("VIDEO_RENDER_FPS must be between 12 and 24")
        if not 640 <= self.render_width <= 1920 or not 360 <= self.render_height <= 1080:
            raise ValueError("VIDEO_RENDER_WIDTH and VIDEO_RENDER_HEIGHT are out of range")


def get_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=False)
    return Settings(
        base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
        api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-sol").strip(),
        reasoning_effort=os.getenv("OPENAI_REASONING_EFFORT", "max").strip(),
        response_format=os.getenv("OPENAI_RESPONSE_FORMAT", "json_schema").strip(),
        worker_concurrency=int(os.getenv("VIDEO_WORKER_CONCURRENCY", "2")),
        data_root=Path(os.getenv("VIDEO_DATA_ROOT", str(ROOT / "data"))),
        work_root=Path(os.getenv("VIDEO_WORK_ROOT", str(ROOT / "work"))),
        blender_bin=Path(os.getenv("BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender")),
        tts_model_path=Path(os.getenv("TTS_MODEL_PATH", str(ROOT / "data/models/kokoro-v1.0.onnx"))),
        tts_voices_path=Path(os.getenv("TTS_VOICES_PATH", str(ROOT / "data/models/voices-v1.0.bin"))),
        tts_voice=os.getenv("TTS_VOICE", "af_heart"),
        tts_speed=float(os.getenv("TTS_SPEED", "0.94")),
        render_fps=int(os.getenv("VIDEO_RENDER_FPS", "15")),
        render_width=int(os.getenv("VIDEO_RENDER_WIDTH", "960")),
        render_height=int(os.getenv("VIDEO_RENDER_HEIGHT", "540")),
    )
