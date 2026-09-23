import json
import time

import httpx
from pydantic import ValidationError

from .config import Settings
from .storyboards import MotionPlan, ReviewVerdict, Storyboard, infer_motion


class GenerationError(Exception):
    pass


ELEMENT_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "label": {"type": "string"}, "detail": {"type": "string"}}, "required": ["label", "detail"]}
SCENE_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "heading": {"type": "string"}, "on_screen": {"type": "string"},
    "narration": {"type": "string"},
    "visual_kind": {"type": "string", "enum": ["sequence", "comparison", "particles"]},
    "elements": {"type": "array", "items": ELEMENT_SCHEMA}},
    "required": ["heading", "on_screen", "narration", "visual_kind", "elements"]}
STORY_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "title": {"type": "string"}, "scenes": {"type": "array", "items": SCENE_SCHEMA}},
    "required": ["title", "scenes"]}
REVIEW_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "relevant": {"type": "boolean"}, "obvious_error": {"type": "boolean"},
    "reason": {"type": "string"}}, "required": ["relevant", "obvious_error", "reason"]}
MOTION_MODES = ["share_electrons", "transfer_electron", "dissolve_ions", "concentration",
                "compare_bonds", "molecule_assembly", "particle_diffusion", "reaction",
                "atomic_structure", "phase_change", "reversible_reaction"]
MOTION_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "cues": {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "properties": {"mode": {"type": "string", "enum": MOTION_MODES}}, "required": ["mode"]}}},
    "required": ["cues"]}


def _format(name: str, schema: dict, settings: Settings) -> dict:
    if settings.response_format == "json_object":
        return {"type": "json_object"}
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}


def _chat(client: httpx.Client, settings: Settings, messages: list[dict], name: str, schema: dict) -> dict:
    body = {
        "model": settings.model, "stream": False, "reasoning_effort": "max",
        "messages": messages, "response_format": _format(name, schema, settings),
    }
    fresh_connection = False
    for attempt in range(3):
        try:
            sender = httpx.Client() if fresh_connection else client
            try:
                response = sender.post(settings.base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": "Bearer " + settings.api_key}, json=body, timeout=180)
            finally:
                if sender is not client:
                    sender.close()
        except httpx.HTTPError as exc:
            fresh_connection = True
            if attempt < 2:
                time.sleep(attempt + 1)
                continue
            raise GenerationError("Model endpoint unavailable") from exc
        if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
            time.sleep(attempt + 1)
            continue
        if response.status_code >= 400:
            raise GenerationError(f"Model endpoint returned HTTP {response.status_code}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return json.loads(content)
            raise ValueError("missing content")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise GenerationError("Model returned invalid JSON") from exc
    raise GenerationError("Model endpoint unavailable")


def generate_storyboard(concept: str, client: httpx.Client, settings: Settings) -> Storyboard:
    settings.validate_worker()
    last_error = "Model returned an unusable storyboard"
    for _ in range(3):
        try:
            payload = _chat(client, settings, [
                {"role": "system", "content": (
                    "You teach chemistry to a curious beginner. Answer the learner's exact question accurately "
                    "and directly in 3 to 5 short scenes. Give one concrete example. Each narration should be "
                    "15 to 30 spoken words. Each scene needs 2 or 3 specific labeled physical visual elements "
                    "such as atoms, ions, molecules, electrons, vessels, or particles. Do not use generic "
                    "labels like Step one or Attraction. Each scene also needs a "
                    "relationship: sequence (steps), comparison (contrasting ideas), or particles (atoms, ions, "
                    "molecules). On-screen text must match narration. Use plain spoken words for formulas. "
                    "Return only JSON matching this exact shape, with no other keys: "
                    "{\"title\":\"...\",\"scenes\":[{\"heading\":\"...\",\"on_screen\":\"...\","
                    "\"narration\":\"...\",\"visual_kind\":\"particles\",\"elements\":["
                    "{\"label\":\"...\",\"detail\":\"...\"},{\"label\":\"...\",\"detail\":\"...\"}]}]}. "
                    "Use exactly those scene keys in every scene; no scene number, visual, short_answer, or key_concept keys.")},
                {"role": "user", "content": concept},
            ], "chemistry_storyboard", STORY_SCHEMA)
            try:
                story = Storyboard.model_validate(payload)
            except ValidationError:
                repaired = _chat(client, settings, [
                    {"role": "system", "content": (
                        "Convert the supplied chemistry lesson JSON to this exact JSON shape, preserving its factual "
                        "meaning: {\"title\":\"...\",\"scenes\":[{\"heading\":\"...\",\"on_screen\":\"...\","
                        "\"narration\":\"...\",\"visual_kind\":\"sequence|comparison|particles\","
                        "\"elements\":[{\"label\":\"...\",\"detail\":\"...\"},{\"label\":\"...\","
                        "\"detail\":\"...\"}]}]}. Use 3 to 5 scenes, 2 or 3 specific visual elements in "
                        "each scene, and 15 to 30 spoken words of narration per scene. Keep the exact learner question "
                        "in mind. Return only the requested JSON keys; no markdown or extra fields.")},
                    {"role": "user", "content": json.dumps({"question": concept, "lesson": payload})},
                ], "chemistry_storyboard_repair", STORY_SCHEMA)
                story = Storyboard.model_validate(repaired)
            verdict = ReviewVerdict.model_validate(_chat(client, settings, [
                {"role": "system", "content": (
                    "Review this chemistry lesson against the original learner question. Return JSON. "
                    "Set relevant true only if it directly answers the question. Set obvious_error true for "
                    "clear chemical mistakes or internal contradictions. Be concise.")},
                {"role": "user", "content": json.dumps({"question": concept, "storyboard": story.model_dump()})},
            ], "chemistry_review", REVIEW_SCHEMA))
            if verdict.relevant and not verdict.obvious_error:
                fallback = [infer_motion(scene, concept) for scene in story.scenes]
                try:
                    motion = MotionPlan.model_validate(_chat(client, settings, [
                        {"role": "system", "content": (
                            "Choose exactly one 3D chemistry animation mode for each lesson scene, in order. "
                            "Use the mode that physically demonstrates the scene's explanation: "
                            "share_electrons for covalent sharing, transfer_electron for ionic transfer, "
                            "dissolve_ions for dissolving salt, concentration for pH or acid/base ion levels, "
                            "compare_bonds for ionic-versus-covalent comparisons, molecule_assembly for "
                            "forming molecules, particle_diffusion for spreading particles, reaction for "
                            "reactants becoming products, atomic_structure for nucleus or shells, phase_change "
                            "for melting or evaporation, reversible_reaction for equilibrium. "
                            "Choose based on what is said in each scene, not just the overall title. "
                            "Return only a JSON object with cues, each containing one mode.")},
                        {"role": "user", "content": json.dumps({"question": concept, "storyboard": story.model_dump()})},
                    ], "chemistry_motion", MOTION_SCHEMA))
                    cues = motion.cues if len(motion.cues) == len(story.scenes) else fallback
                except (GenerationError, ValidationError, ValueError):
                    cues = fallback
                return story.model_copy(update={
                    "motion": cues
                })
            last_error = "Storyboard did not pass chemistry relevance review"
        except (GenerationError, ValidationError, ValueError) as exc:
            last_error = str(exc) if isinstance(exc, GenerationError) else "Model returned an invalid storyboard"
    raise GenerationError(last_error)
