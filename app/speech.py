"""Local Kokoro narration, with a compatibility fix for the v1.0 ONNX export."""

import threading
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
from kokoro_onnx.config import MAX_PHONEME_LENGTH, SAMPLE_RATE

from .config import Settings


_local = threading.local()


class _KokoroFloatSpeed(Kokoro):
    def _create_audio(self, phonemes, voice, speed):
        tokens = np.asarray(self.tokenizer.tokenize(phonemes[:MAX_PHONEME_LENGTH]), dtype=np.int64)
        if len(tokens) > MAX_PHONEME_LENGTH:
            raise ValueError("Narration phrase is too long")
        style = np.asarray(voice[len(tokens)], dtype=np.float32)
        inputs = {
            "input_ids": np.asarray([[0, *tokens, 0]], dtype=np.int64),
            "style": style,
            "speed": np.asarray([speed], dtype=np.float32),
        }
        audio = self.sess.run(None, inputs)[0]
        return audio, SAMPLE_RATE


def synthesize(text: str, destination: Path, settings: Settings) -> float:
    key = (str(settings.tts_model_path), str(settings.tts_voices_path))
    if getattr(_local, "key", None) != key:
        _local.model = _KokoroFloatSpeed(*key)
        _local.key = key
    samples, rate = _local.model.create(
        text, voice=settings.tts_voice, speed=settings.tts_speed, lang="en-us"
    )
    if len(samples) < rate:
        raise ValueError("Narration audio is unexpectedly short")
    sf.write(destination, np.asarray(samples, dtype=np.float32), rate)
    return len(samples) / rate
