"""
report.py — Stage 5: Consultant Report.

Two responsibilities:
  1. generate_report(): the final aggregated Claude call that produces the
     executive summary, verdict, key strength, critical gap, and the prioritised
     8-16 recommendations — all in the consultant persona.
  2. Asset helpers: base64 data URIs for screenshots (so the report HTML is
     fully self-contained) and extraction of the research references actually
     cited across the report.

The HTML itself is rendered by Flask (templates/report.html) in app.py.
"""

import base64
import json
import os

from prompts import CONSULTANT_PERSONA, JSON_INSTRUCTION, MODEL_SYNTHESIS, call_json

_SCHEMA = """{
  "executive_summary": "3-4 sentences. Blunt overall assessment for the CEO.",
  "overall_verdict": "Strong|Solid|Needs Work|Critical",
  "key_strength": "The one thing this site does notably well, with specific evidence.",
  "critical_gap": "The single most damaging conversion/UX failure, with evidence and a research citation.",
  "recommendations": [
    {
      "rank": 1,
      "severity": "critical|high|medium|low",
      "title": "Short title",
      "finding": "Specific, not generic. Quote copy, describe visuals, reference code.",
      "research": "The specific research or principle that makes this a problem.",
      "recommendation": "Exactly what to do — briefable to a designer or developer.",
      "expected_impact": "Expected improvement in conversion/trust/UX and why."
    }
  ]
}"""

# Benchmarks the persona may cite — used to surface a references list.
KNOWN_REFERENCES = [
    ("Nielsen Norman Group", "F-pattern reading, 10 usability heuristics, eye-tracking"),
    ("Baymard Institute", "48% average form abandonment; checkout UX benchmarks"),
    ("Google", "53% of mobile users abandon if load exceeds 3s; Core Web Vitals"),
    ("Fogg Behavior Model", "conversion = motivation × ability × trigger"),
    ("Miller's Law", "working memory 7±2 items"),
    ("Hick's Law", "decision time rises with number of choices"),
    ("Fitts's Law", "touch target minimum 44×44px"),
    ("WordStream", "avg landing page CVR 2.35%, top 10% 11.45%"),
    ("Edelman", "financial services trust dynamics"),
    ("HubSpot", "action-specific CTAs outperform generic by 202%"),
    ("Formisimo", "each additional form field reduces conversion ~11%"),
    ("Akamai", "1s load delay reduces conversion by 7%"),
    ("Stanford", "75% of users judge credibility by design"),
    ("Wyzowl", "video testimonials increase conversion 80% vs text"),
    ("BrightLocal", "88% trust online reviews as much as personal recommendations"),
    ("WCAG", "4.5:1 contrast for normal text, 3:1 for large text"),
]


def generate_report(client, url, context, code, visual, crossref_findings):
    ctx = f"Business context: {context}.\n" if context else ""
    code_json = json.dumps(_compact(code), indent=2)
    visual_json = json.dumps(visual, indent=2)
    cross_json = json.dumps(crossref_findings, indent=2)

    prompt = (
        f"{ctx}Site under review: {url}\n\n"
        "You have completed a five-stage intelligence audit. Here are the aggregated "
        "findings:\n\n"
        f"=== CODE AUDIT ===\n{code_json}\n\n"
        f"=== VISUAL AUDIT ===\n{visual_json}\n\n"
        f"=== CROSS-REFERENCE FINDINGS ===\n{cross_json}\n\n"
        "Write the final consultant report. Be blunt, specific, and evidence-led — "
        "quote copy, describe visual elements, reference the code. Tie every "
        "recommendation to a specific observation, a cited research/benchmark, and an "
        "expected outcome. Produce between 8 and 16 recommendations, prioritised by "
        "severity then impact (rank 1 = most important).\n\n"
        f"Return JSON exactly matching:\n{_SCHEMA}\n\n" + JSON_INSTRUCTION
    )

    # 8-16 detailed recommendations plus the summary fields run to several
    # thousand output tokens; too small a ceiling truncates the JSON mid-object
    # and the whole report stage fails. Keep generous headroom.
    report = call_json(client, MODEL_SYNTHESIS, CONSULTANT_PERSONA, prompt,
                       max_tokens=8000)
    # Normalise recommendations: sort by severity then rank.
    recs = report.get("recommendations", []) or []
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recs.sort(key=lambda r: (order.get(str(r.get("severity", "low")).lower(), 9),
                             r.get("rank", 99)))
    for i, r in enumerate(recs, start=1):
        r["rank"] = i
    report["recommendations"] = recs
    return report


def generate_visual_report(client, url, context, visual):
    """Shorter, visual-only report for UI/UX mode.

    Draws solely on the three vision passes (no code audit, no cross-reference)
    and asks for fewer, tightly visual recommendations. Returns the same shape
    as generate_report() so the report template renders unchanged.
    """
    ctx = f"Business context: {context}.\n" if context else ""
    visual_json = json.dumps(visual, indent=2)

    prompt = (
        f"{ctx}Site under review: {url}\n\n"
        "You have completed a focused UI/UX visual review — three vision passes: "
        "the above-the-fold desktop view, the full-page scroll, and the mobile "
        "view. There is NO code audit and NO cross-reference data for this run; "
        "base your assessment strictly on the visual findings below.\n\n"
        f"=== VISUAL AUDIT ===\n{visual_json}\n\n"
        "Write a concise UI/UX report. Be blunt, specific, and evidence-led — "
        "quote visible copy and describe what you actually see. Tie every "
        "recommendation to a specific visual observation, a cited research/"
        "benchmark, and an expected outcome. Produce between 5 and 8 "
        "recommendations focused on visual design, hierarchy, and UX, "
        "prioritised by severity then impact (rank 1 = most important). Do not "
        "raise issues that would require code or backend inspection.\n\n"
        f"Return JSON exactly matching:\n{_SCHEMA}\n\n" + JSON_INSTRUCTION
    )

    report = call_json(client, MODEL_SYNTHESIS, CONSULTANT_PERSONA, prompt,
                       max_tokens=6000)
    recs = report.get("recommendations", []) or []
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recs.sort(key=lambda r: (order.get(str(r.get("severity", "low")).lower(), 9),
                             r.get("rank", 99)))
    for i, r in enumerate(recs, start=1):
        r["rank"] = i
    report["recommendations"] = recs
    return report


def _compact(code):
    out = {}
    for group, data in code.items():
        if not isinstance(data, dict):
            out[group] = data
            continue
        compact = {}
        for k, v in data.items():
            compact[k] = (v[:8] + [f"... (+{len(v) - 8})"]
                          if isinstance(v, list) and len(v) > 8 else v)
        out[group] = compact
    return out


def _data_uri(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.standard_b64encode(f.read()).decode()


def encode_screenshots(captures):
    sections = captures.get("screenshot_sections") or []
    return {
        "desktop": _data_uri(captures.get("screenshot_desktop")),
        "sections": [uri for uri in (_data_uri(p) for p in sections) if uri],
        "mobile": _data_uri(captures.get("screenshot_mobile")),
    }


def collect_references(report, crossref_findings):
    """Return the subset of known benchmarks actually cited in the report text."""
    blob = json.dumps(report).lower() + json.dumps(crossref_findings).lower()
    cited = []
    for name, desc in KNOWN_REFERENCES:
        key = name.lower().split()[0]
        if key in blob or name.lower() in blob:
            cited.append({"name": name, "detail": desc})
    return cited
