import json

import httpx
import pytest

from app.config import Settings
from app.generator import GenerationError, generate_storyboard


def settings(tmp_path):
    return Settings("https://example.test/v1", "secret", "cx/gpt-5.6-sol", "max",
                    "json_schema", 2, tmp_path, tmp_path)


def test_generator_validates_and_sends_max_effort(tmp_path):
    calls = []
    story = {"title": "Why salt dissolves", "scenes": [{
        "heading": f"Water and salt {i}", "on_screen": "Water pulls charged ions from salt.",
        "narration": "Water molecules surround the ions and pull them away from the salt crystal, so they spread through water.",
        "visual_kind": "particles", "elements": [
            {"label": "Water", "detail": "Polar molecules"},
            {"label": "Salt", "detail": "Charged ions"}]}
        for i in range(3)]}

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        content = story if len(calls) == 1 else {"relevant": True, "obvious_error": False, "reason": "Accurate"}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = generate_storyboard("Why does salt dissolve in water?", client, settings(tmp_path))
    assert len(result.scenes) == 3
    assert all(call["reasoning_effort"] == "max" for call in calls)
    assert all(call["model"] == "cx/gpt-5.6-sol" for call in calls)


def test_provider_failure_is_sanitized(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
        with pytest.raises(GenerationError, match="HTTP 503"):
            generate_storyboard("Why does salt dissolve?", client, settings(tmp_path))


def test_malformed_storyboard_retried_then_rejected(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"title":"Incomplete"}'}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GenerationError, match="invalid storyboard"):
            generate_storyboard("Why does salt dissolve?", client, settings(tmp_path))
    assert len(calls) == 6


def test_motion_planner_cues_are_used(tmp_path):
    story = {"title": "Why salt dissolves", "scenes": [{
        "heading": f"Water and salt {i}", "on_screen": "Water pulls charged ions from salt.",
        "narration": "Water molecules surround the ions and pull them away from the salt crystal, so they spread through water.",
        "visual_kind": "particles", "elements": [
            {"label": "Water", "detail": "Polar molecules"},
            {"label": "Salt", "detail": "Charged ions"}]}
        for i in range(3)]}
    replies = [story, {"relevant": True, "obvious_error": False, "reason": "Accurate"},
               {"cues": [{"mode": "dissolve_ions"} for _ in range(3)]}]

    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(replies.pop(0))}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = generate_storyboard("Why does salt dissolve in water?", client, settings(tmp_path))
    assert [cue.mode for cue in result.motion] == ["dissolve_ions"] * 3
