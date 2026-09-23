"""Download and verify the local Kokoro voice assets used by the renderer."""

import hashlib
import os
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "models"
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
FILES = {
    "kokoro-v1.0.onnx": "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for filename, expected in FILES.items():
        final = DEST / filename
        if final.is_file() and digest(final) == expected:
            print(f"{filename}: verified")
            continue
        partial = DEST / (filename + ".part")
        print(f"{filename}: downloading", flush=True)
        with urlopen(BASE + filename, timeout=60) as source, partial.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        if digest(partial) != expected:
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"{filename}: SHA-256 mismatch")
        os.replace(partial, final)
        print(f"{filename}: verified")


if __name__ == "__main__":
    main()
