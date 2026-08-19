"""
visual_audit.py — Stage 3: Visual Audit.

Sends rendered screenshots to Claude's vision API (claude-sonnet-4-6) in the
consultant persona and parses structured JSON findings. Three calls:

  1. Above-fold desktop  -> value prop, hierarchy, CTA, trust, colour, etc.
  2. Sections            -> all section screenshots in a SINGLE multi-image call:
                            a section-by-section read of the page (what's there,
                            colour palette, element visibility, overlapping or
                            obscuring elements) plus a scored page-level
                            assessment (content flow, social proof, forms, ...).
  3. Mobile              -> mobile value prop, CTA, tap targets, readability, nav

Each scored finding is {score, observation, verdict, detail}. Failures are
caught by the caller (analyser) so a partial visual audit never kills the job.
"""

import base64

from prompts import CONSULTANT_PERSONA, JSON_INSTRUCTION, MODEL_VISION, call_json


def _image_block(path):
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": data},
    }


_ABOVE_FOLD_SCHEMA = """{
  "value_proposition": {"score": 0-20, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
  "visual_hierarchy": {"score": 0-20, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
  "cta_prominence": {"score": 0-15, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
  "trust_signals_above_fold": {"score": 0-15, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
  "colour_harmony": {"score": 0-10, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
  "whitespace_and_density": {"score": 0-10, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
  "typography_legibility": {"score": 0-10, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."}
}"""

# The section call returns a per-section descriptive read plus a scored,
# page-level assessment (the latter feeds the deterministic scoring module).
_SECTION_SCHEMA = """{
  "sections": [
    {
      "index": 1,
      "what_is_here": "What this section of the page contains (one or two sentences).",
      "colour_palette": "Dominant colours used in this section.",
      "element_visibility": "Are key elements clearly visible / legible here?",
      "overlapping_or_obscuring": "Any chat widget, sticky bar, cookie banner or popup overlapping or obscuring content (or 'none')."
    }
  ],
  "page_assessment": {
    "content_flow": {"score": 0-15, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
    "social_proof_placement": {"score": 0-15, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
    "form_visual_design": {"score": 0-10, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
    "footer_completeness": {"score": 0-10, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
    "visual_consistency": {"score": 0-10, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
    "page_length_and_structure": {"score": 0-10, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."}
  }
}"""

_MOBILE_SCHEMA = """{
  "mobile_value_prop": {"score": 0-15, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
  "mobile_cta": {"score": 0-15, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
  "tap_targets": {"score": 0-10, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
  "mobile_readability": {"score": 0-10, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."},
  "mobile_nav": {"score": 0-10, "observation": "...", "verdict": "pass|partial|fail", "detail": "..."}
}"""


def _prompt(context, what, schema):
    ctx = f" The business context is: {context}." if context else ""
    return (
        f"You are reviewing the {what} of a website.{ctx} Analyse it as a senior "
        "CRO/UX consultant. For each criterion: assign a score within the stated "
        "range, give a specific observation of what you actually see (quote visible "
        "copy where relevant), a verdict (pass/partial/fail), and a detail explaining "
        "the conversion/UX implication. Be precise and evidence-based.\n\n"
        f"Return JSON exactly matching this shape:\n{schema}\n\n" + JSON_INSTRUCTION
    )


def analyse_above_fold(client, captures, context):
    content = [
        _image_block(captures["screenshot_desktop"]),
        {"type": "text", "text": _prompt(
            context, "above-the-fold desktop view", _ABOVE_FOLD_SCHEMA)},
    ]
    return call_json(client, MODEL_VISION, CONSULTANT_PERSONA, content, max_tokens=3000)


def _section_prompt(context, count):
    ctx = f" The business context is: {context}." if context else ""
    return (
        f"You are reviewing a full web page that has been captured as {count} "
        f"sequential screenshots, scrolling from the top of the page to the "
        f"bottom.{ctx} The images are provided in order and labelled "
        "\"Section 1\", \"Section 2\", and so on.\n\n"
        "Analyse the page section by section. For EACH section, describe what is "
        "in it, its dominant colour palette, whether key elements are clearly "
        "visible and legible, and call out any element that overlaps or obscures "
        "content — chat widgets, sticky bars, cookie banners, or popups.\n\n"
        "Then give a scored page-level assessment across the stated criteria. "
        "Keep every text field to one or two concise sentences. Be specific and "
        "evidence-based — quote visible copy where relevant.\n\n"
        f"Return JSON exactly matching this shape:\n{_SECTION_SCHEMA}\n\n"
        + JSON_INSTRUCTION
    )


def analyse_sections(client, captures, context):
    """Single multi-image vision call over every section screenshot.

    Returns a dict with `sections` (per-section descriptive read) and
    `page_assessment` (scored criteria consumed by scoring.py as `full_page`).
    """
    paths = captures.get("screenshot_sections") or []
    content = []
    for i, path in enumerate(paths, start=1):
        content.append({"type": "text", "text": f"Section {i}:"})
        content.append(_image_block(path))
    content.append({"type": "text", "text": _section_prompt(context, len(paths))})
    # Up to 8 sections (four fields each) plus the scored page_assessment block
    # overruns a 2000-token cap; truncation here would zero out the full_page
    # scores and the section read, so give it room.
    return call_json(client, MODEL_VISION, CONSULTANT_PERSONA, content,
                     max_tokens=4000)


def analyse_mobile(client, captures, context):
    content = [
        _image_block(captures["screenshot_mobile"]),
        {"type": "text", "text": _prompt(
            context, "mobile (390x844) above-the-fold view", _MOBILE_SCHEMA)},
    ]
    return call_json(client, MODEL_VISION, CONSULTANT_PERSONA, content, max_tokens=2500)


def run_visual_audit(client, captures, context):
    """Run all three vision calls. Each may independently raise; caller handles."""
    sections = analyse_sections(client, captures, context)
    return {
        "above_fold": analyse_above_fold(client, captures, context),
        "full_page": sections.get("page_assessment", {}),
        "sections": sections.get("sections", []),
        "mobile": analyse_mobile(client, captures, context),
    }
