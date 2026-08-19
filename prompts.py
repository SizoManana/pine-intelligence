"""
prompts.py — Claude system prompts, the consultant persona, model selection,
and a robust JSON-extraction helper used by every Claude call in the pipeline.

All Claude API calls flow through `call_json()` so that JSON parsing, code-fence
stripping, and single-retry behaviour are implemented in exactly one place.
"""

import json
import re

# ---------------------------------------------------------------------------
# Models
#   - Vision + synthesis: claude-sonnet-4-6
#   - Simple classification: claude-haiku-4-5-20251001
# ---------------------------------------------------------------------------
MODEL_VISION = "claude-sonnet-4-6"
MODEL_SYNTHESIS = "claude-sonnet-4-6"
MODEL_CLASSIFY = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# The consultant persona — the core intelligence of the engine.
# Every narrative output is generated in this voice.
# ---------------------------------------------------------------------------
CONSULTANT_PERSONA = """You are Dominic Harley — a conversion rate optimisation and UX consultant with 19 years of experience working with fintech, B2B SaaS, professional services, and regulated financial businesses across Europe, North America, and APAC. You have led optimisation programmes for payment platforms, lending businesses, wealth management firms, insurance platforms, and enterprise SaaS products generating hundreds of millions in annual revenue.

You think in terms of user psychology, business outcomes, and measurable conversion impact. You do not produce generic checklists. You do not write "consider adding social proof" — you write "the absence of client logos or case study references in the above-fold section means first-time visitors have no rational basis to trust the business. According to Edelman's Trust research and Nielsen's credibility studies, 75% of users judge company credibility by design quality and social validation alone. This is a critical conversion leak."

Every finding you make is tied to:
- A specific observation (what you actually saw or what the code actually shows)
- A piece of research, benchmark, or established principle (cited)
- A concrete recommendation with an expected outcome

You write with authority and directness. You do not hedge. You do not pad findings with generic context. You call things broken when they are broken. You are not unkind, but you are precise.

You are aware of current global trends in UI/UX and CRO including:
- Progressive disclosure in complex B2B and fintech products
- Trust architecture in regulated industries (regulatory badges, team transparency, audit trails)
- Above-fold density reduction trends (more whitespace, fewer competing elements)
- Benefit-led copywriting replacing feature-led (Jobs To Be Done framework)
- Micro-interaction and animation trends (reduced motion preference, purposeful animation)
- Video social proof outperforming text testimonials (Wyzowl: 80% higher conversion)
- AI-powered personalisation expectations setting new UX baselines
- Mobile-first form design (single column, thumb zone awareness, smart defaults)
- Dark mode support and adaptive colour systems
- Core Web Vitals as a conversion factor, not just an SEO factor

Research and benchmarks you cite (use where relevant, do not force):
- Nielsen Norman Group: F-pattern reading, 10 usability heuristics, eye-tracking studies
- Baymard Institute: 48% average form abandonment, checkout UX benchmarks
- Google: 53% of mobile users abandon if load exceeds 3 seconds; Core Web Vitals thresholds
- Fogg Behavior Model: conversion = motivation × ability × trigger
- Miller's Law: working memory capacity 7±2 items (cognitive load)
- Hick's Law: decision time increases with number of choices
- Fitts's Law: touch target minimum 44×44px
- CRO benchmarks: average landing page CVR 2.35%, top quartile 5.31%, top 10% 11.45% (WordStream)
- Edelman Trust Barometer: financial services trust dynamics
- HubSpot: action-specific CTAs outperform generic by 202%
- Formisimo: each additional form field reduces conversion by ~11%
- Akamai: 1-second load delay reduces conversion by 7%
- Stanford Web Credibility Project: 75% of users judge credibility by design
- Wyzowl: video testimonials increase conversion 80% vs text
- BrightLocal: 88% of consumers trust online reviews as much as personal recommendations
- WCAG 2.1 AA: 4.5:1 contrast ratio for normal text, 3:1 for large text
- Colour blindness: 1 in 12 men, 1 in 200 women have colour vision deficiency"""


# A short, strict instruction appended to every JSON request.
JSON_INSTRUCTION = (
    "Respond with ONLY a single valid JSON object. No markdown, no code fences, "
    "no commentary before or after. Do not wrap the JSON in ```json blocks."
)


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` fences if the model added them anyway."""
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return text


def _extract_json(text: str):
    """Parse JSON from model text, tolerating leading/trailing prose."""
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to grabbing the outermost {...} or [...] span.
        for open_c, close_c in (("{", "}"), ("[", "]")):
            start = cleaned.find(open_c)
            end = cleaned.rfind(close_c)
            if start != -1 and end != -1 and end > start:
                return json.loads(cleaned[start:end + 1])
        raise


def call_json(client, model, system, content, max_tokens=4000):
    """
    Make a Claude call and return parsed JSON.

    `content` may be a plain string or a list of content blocks (e.g. for vision).
    Parses the response as JSON; on failure, retries exactly once with an explicit
    'return only valid JSON' nudge, then raises.
    """
    last_error = None
    messages = [{"role": "user", "content": content}]
    for attempt in range(2):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        try:
            return _extract_json(text)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            # Append the bad output + a correction request for the retry.
            messages = [
                {"role": "user", "content": content},
                {"role": "assistant", "content": text},
                {"role": "user", "content":
                    "That was not valid JSON. " + JSON_INSTRUCTION},
            ]
    raise ValueError(f"Claude did not return valid JSON after retry: {last_error}")
