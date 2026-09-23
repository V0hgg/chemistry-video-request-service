from uuid import uuid4

import pytest

from app.renderer import RenderError, render_video
from app.storyboards import Storyboard


def test_missing_media_tool_publishes_nothing(tmp_path, monkeypatch):
    story = Storyboard.model_validate({"title": "Why salt dissolves", "scenes": [{
        "heading": f"Water and salt {i}", "on_screen": "Water pulls charged ions from salt.",
        "narration": "Water molecules surround the ions and pull them away from the salt crystal, so they spread through water.",
        "visual_kind": "particles", "elements": [
            {"label": "Water", "detail": "Polar molecules"},
            {"label": "Salt", "detail": "Charged ions"}]}
        for i in range(3)]})
    monkeypatch.setenv("PATH", "")
    with pytest.raises(RenderError, match="Local media tool failed"):
        render_video(str(uuid4()), uuid4().hex, story, tmp_path / "work", tmp_path / "videos")
    assert not list((tmp_path / "videos").rglob("*.mp4"))
