"""Compose narrated Blender animations into a verified MP4 artifact."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont

from .config import Settings, get_settings
from .speech import synthesize
from .storyboards import Storyboard, StoryScene, infer_motion


class RenderError(Exception):
    pass


_DISPLAY_TRANSLATION = str.maketrans({
    "⁺": "+", "⁻": "-", "₊": "+", "₋": "-",
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
})


def _display(value: str) -> str:
    return value.translate(_DISPLAY_TRANSLATION)


def _font(size: int, bold: bool = False):
    names = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _lines(draw: ImageDraw.ImageDraw, value: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in _display(value).split():
        proposal = f"{line} {word}".strip()
        if line and draw.textlength(proposal, font=font) > width:
            lines.append(line)
            line = word
        else:
            line = proposal
    if line:
        lines.append(line)
    return lines


def _overlay(scene: StoryScene, title: str, index: int, total: int, mode: str, path: Path) -> None:
    image = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((32, 23, 850, 142), radius=20, fill=(5, 19, 35, 202))
    draw.text((57, 38), _display(title.upper())[:72], font=_font(21, True), fill="#57e3d1")
    heading = _lines(draw, scene.heading, _font(37, True), 760)[:2]
    for line_no, line in enumerate(heading):
        draw.text((57, 67 + line_no * 36), line, font=_font(37, True), fill="white")
    draw.rounded_rectangle((32, 570, 1248, 700), radius=20, fill=(5, 19, 35, 214))
    summary_font = _font(28)
    summary = _lines(draw, scene.on_screen, summary_font, 1130)[:2]
    for line_no, line in enumerate(summary):
        draw.text((58, 586 + line_no * 34), line, font=summary_font, fill="white")
    labels = ("Lower pH: more H+   •   Higher pH: fewer H+" if mode == "concentration"
              else "   •   ".join(_display(element.label) for element in scene.elements))
    draw.text((58, 664), labels[:105], font=_font(19, True), fill="#57e3d1")
    draw.text((1170, 38), f"{index + 1} / {total}", font=_font(20, True), fill="white")
    guide = {
        "concentration": [(128, "10× more H+"), (765, "Fewer H+")],
        "compare_bonds": [(180, "IONIC: transfer"), (780, "COVALENT: sharing")],
        "share_electrons": [(456, "shared electron pair")],
        "transfer_electron": [(475, "electron transfer ->")],
    }.get(mode, [])
    for x, label in guide:
        width = int(draw.textlength(label, font=_font(22, True))) + 36
        draw.rounded_rectangle((x, 495, x + width, 533), radius=12, fill=(5, 19, 35, 198))
        draw.text((x + 18, 502), label, font=_font(22, True), fill="#57e3d1")
    image.save(path)


def _run(args: list[str], log: Path | None = None) -> subprocess.CompletedProcess | None:
    try:
        if log is not None:
            with log.open("w") as stream:
                subprocess.run(args, check=True, stdout=stream, stderr=subprocess.STDOUT)
            return None
        return subprocess.run(args, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RenderError("Local media tool failed") from exc


def _probe(path: Path) -> dict:
    try:
        result = _run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                       "-of", "json", str(path)])
        return json.loads(result.stdout)
    except (ValueError, KeyError, AttributeError) as exc:
        raise RenderError("Rendered media could not be verified") from exc


def render_video(job_id: str, claim_token: str, storyboard: Storyboard,
                 work_root: Path, artifact_root: Path, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    try:
        settings.validate_media()
        job_id = str(UUID(str(job_id)))
        if len(claim_token) != 32 or any(c not in "0123456789abcdef" for c in claim_token):
            raise ValueError("Invalid claim token")
    except ValueError as exc:
        raise RenderError(str(exc)) from exc
    attempt = Path(work_root) / job_id / claim_token
    attempt.mkdir(parents=True, exist_ok=True)
    output_dir = Path(artifact_root) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    published = output_dir / f"{claim_token}.mp4"
    blender_script = Path(__file__).with_name("blender_scene.py")
    try:
        clips = []
        for index, scene in enumerate(storyboard.scenes):
            scene_dir = attempt / f"scene-{index}"
            frames = scene_dir / "frames"
            frames.mkdir(parents=True)
            audio = scene_dir / "narration.wav"
            overlay = scene_dir / "overlay.png"
            clip = scene_dir / "clip.mp4"
            try:
                speech_duration = synthesize(scene.narration, audio, settings)
            except Exception as exc:
                raise RenderError("Local narration synthesis failed") from exc
            duration = max(speech_duration + 0.65, 2.0)
            mode = (storyboard.motion[index].mode if storyboard.motion and
                    index < len(storyboard.motion) else infer_motion(scene, storyboard.title).mode)
            spec = {
                "mode": mode, "labels": [element.label for element in scene.elements],
                "duration": duration, "fps": settings.render_fps,
                "width": settings.render_width, "height": settings.render_height,
                "frames_dir": str(frames),
            }
            spec_path = scene_dir / "scene.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            _run([str(settings.blender_bin), "--background", "--factory-startup",
                  "--python-exit-code", "1", "--python", str(blender_script),
                  "--", str(spec_path)], log=scene_dir / "blender.log")
            expected = max(2, round(duration * settings.render_fps))
            if len(list(frames.glob("frame_*.png"))) != expected:
                raise RenderError("Blender did not render all animation frames")
            _overlay(scene, storyboard.title, index, len(storyboard.scenes), mode, overlay)
            _run(["ffmpeg", "-v", "error", "-y", "-framerate", str(settings.render_fps),
                  "-i", str(frames / "frame_%04d.png"), "-loop", "1", "-i", str(overlay),
                  "-i", str(audio), "-filter_complex",
                  "[0:v]scale=1280:720:flags=lanczos[base];"
                  "[base][1:v]overlay=0:0:shortest=1,format=yuv420p[v]",
                  "-map", "[v]", "-map", "2:a", "-frames:v", str(expected),
                  "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,apad",
                  "-c:v", "libx264", "-preset", "veryfast",
                  "-crf", "23", "-c:a", "aac", "-b:a", "160k",
                  "-movflags", "+faststart", str(clip)])
            clips.append(clip)
        concat = attempt / "clips.txt"
        concat.write_text("".join(f"file 'scene-{i}/clip.mp4'\n" for i in range(len(clips))))
        candidate = attempt / "complete.mp4"
        _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
              "-i", str(concat), "-c", "copy", "-movflags", "+faststart", str(candidate)])
        result = _probe(candidate)
        streams = {stream.get("codec_type"): stream for stream in result.get("streams", [])}
        if (not {"video", "audio"}.issubset(streams) or
                streams["video"].get("codec_name") != "h264" or
                streams["audio"].get("codec_name") != "aac" or
                float(result["format"]["duration"]) < 5):
            raise RenderError("Rendered video lacks expected audio, video, or duration")
        os.replace(candidate, published)
        return published
    except Exception:
        published.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(attempt, ignore_errors=True)
