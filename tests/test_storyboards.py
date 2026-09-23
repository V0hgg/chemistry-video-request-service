from app.storyboards import ReviewVerdict, Storyboard, infer_motion


def test_long_but_renderable_comparison_caption():
    caption = ("Sodium gives one electron to chlorine. Sodium becomes positive, chlorine becomes negative, "
               "and their electrical attraction forms sodium chloride.")
    story = Storyboard.model_validate({"title": "Ionic and covalent bonds", "scenes": [{
        "heading": f"Bond comparison {i}", "on_screen": caption,
        "narration": "Ionic bonding transfers electrons, while covalent bonding shares electrons between atoms. Both can make stable substances.",
        "visual_kind": "comparison", "elements": [
            {"label": "Ionic", "detail": "Electron transfer"},
            {"label": "Covalent", "detail": "Electron sharing"}]}
        for i in range(3)]})
    assert len(story.scenes[0].on_screen) > 140


def test_review_can_omit_optional_reason():
    verdict = ReviewVerdict.model_validate({"relevant": True, "obvious_error": False})
    assert verdict.relevant and not verdict.obvious_error


def test_ph_comparison_does_not_become_bond_comparison():
    scene = Storyboard.model_validate({"title": "Comparing pH", "scenes": [{
        "heading": f"Compare pH values {i}",
        "on_screen": "Compare the hydrogen ion concentration in two solutions.",
        "narration": "A lower pH means more hydrogen ions in the solution. Each one unit change represents a tenfold difference in concentration.",
        "visual_kind": "comparison", "elements": [
            {"label": "Hydrogen ions", "detail": "Higher concentration"},
            {"label": "Solution", "detail": "Lower concentration"}]}
        for i in range(3)]}).scenes[0]
    assert infer_motion(scene, "How does the pH scale work?").mode == "concentration"
