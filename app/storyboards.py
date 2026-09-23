import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MotionMode = Literal[
    "share_electrons", "transfer_electron", "dissolve_ions", "concentration",
    "compare_bonds", "molecule_assembly", "particle_diffusion", "reaction",
    "atomic_structure", "phase_change", "reversible_reaction",
]


class MotionCue(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mode: MotionMode


class MotionPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cues: list[MotionCue]


class VisualElement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str = Field(min_length=1, max_length=38)
    detail: str = Field(min_length=1, max_length=100)


class StoryScene(BaseModel):
    model_config = ConfigDict(extra="ignore")
    heading: str = Field(min_length=3, max_length=64)
    on_screen: str = Field(min_length=8, max_length=220)
    narration: str = Field(min_length=35, max_length=420)
    visual_kind: Literal["sequence", "comparison", "particles"]
    elements: list[VisualElement] = Field(min_length=2, max_length=3)

    @field_validator("narration")
    @classmethod
    def spoken_length(cls, value: str) -> str:
        if not 10 <= len(value.split()) <= 65:
            raise ValueError("narration must be 10 to 65 words")
        return value


class Storyboard(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=5, max_length=90)
    scenes: list[StoryScene] = Field(min_length=3, max_length=5)
    motion: list[MotionCue] | None = None


class ReviewVerdict(BaseModel):
    model_config = ConfigDict(extra="ignore")
    relevant: bool
    obvious_error: bool
    reason: str = "No explanation supplied"


def infer_motion(scene: StoryScene, concept: str) -> MotionCue:
    scene_text = " ".join((scene.heading, scene.on_screen, scene.narration)).lower()
    question = concept.lower()
    bond_comparison = ("ionic" in scene_text and "covalent" in scene_text)
    if bond_comparison and any(x in scene_text for x in ("versus", "vs.", "difference between", "compare")):
        mode = "compare_bonds"
    elif "electron" in scene_text and any(x in scene_text for x in ("transfer", "gives", "donates")):
        mode = "transfer_electron"
    elif "electron" in scene_text and any(x in scene_text for x in ("share", "covalent")):
        mode = "share_electrons"
    elif re.search(r"\bpH\b", scene.heading + " " + scene.on_screen + " " + scene.narration, re.I) or any(x in scene_text for x in ("acidic", "basic", "hydrogen ion concentration")):
        mode = "concentration"
    elif any(x in scene_text for x in ("dissolv", "hydration", "salt crystal")):
        mode = "dissolve_ions"
    elif any(x in scene_text for x in ("equilibrium", "reversible")):
        mode = "reversible_reaction"
    elif any(x in scene_text for x in ("isotope", "nucleus", "proton", "neutron", "electron shell")):
        mode = "atomic_structure"
    elif any(x in scene_text for x in ("melting", "freezing", "evaporat", "phase change")):
        mode = "phase_change"
    elif any(x in scene_text for x in ("diffus", "spread out", "disperse")):
        mode = "particle_diffusion"
    elif any(x in scene_text for x in ("reaction", "reactant", "product")):
        mode = "reaction"
    elif re.search(r"\bpH\b", concept, re.I) or "acid" in question or "base" in question:
        mode = "concentration"
    elif "dissolv" in question or "solubility" in question:
        mode = "dissolve_ions"
    elif "covalent" in question and "ionic" in question:
        mode = "compare_bonds"
    elif "covalent" in question:
        mode = "share_electrons"
    else:
        mode = "molecule_assembly" if scene.visual_kind == "particles" else "particle_diffusion"
    return MotionCue(mode=mode)
