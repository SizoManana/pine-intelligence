"""
crossref.py — Stage 4: Cross-Reference.

Feeds the structured code-audit (Stage 2) and visual-audit (Stage 3) outputs to
Claude and asks it to surface where the two layers confirm, conflict, or expose
hidden issues. This is where the engine's intelligence shows — not "is there an
H1" but "the H1 looks prominent yet reads as a brand tagline, not a value prop".

Returns a list of cross-reference findings.
"""

import json

from prompts import CONSULTANT_PERSONA, JSON_INSTRUCTION, MODEL_SYNTHESIS, call_json

_SCHEMA = """{
  "findings": [
    {
      "type": "gap|contradiction|hidden|confirmation",
      "title": "Short title",
      "visual_finding": "What Claude saw",
      "code_finding": "What the code says",
      "implication": "Why this matters for conversion / UX",
      "severity": "critical|high|medium|low"
    }
  ]
}"""


def _summarise_code(code):
    """Compact the code audit so the synthesis stays inside token limits."""
    summary = {}
    for group, data in code.items():
        if not isinstance(data, dict):
            summary[group] = data
            continue
        compact = {}
        for k, v in data.items():
            if isinstance(v, list) and len(v) > 8:
                compact[k] = v[:8] + [f"... (+{len(v) - 8} more)"]
            else:
                compact[k] = v
        summary[group] = compact
    return summary


def cross_reference(client, code_findings, visual_findings, context):
    ctx = f"Business context: {context}.\n" if context else ""
    code_json = json.dumps(_summarise_code(code_findings), indent=2)
    visual_json = json.dumps(visual_findings, indent=2)

    prompt = (
        f"{ctx}You have two independent analyses of the same website.\n\n"
        "=== CODE AUDIT (programmatic truth — HTML/CSS/meta/contrast) ===\n"
        f"{code_json}\n\n"
        "=== VISUAL AUDIT (what Claude Vision saw in the rendered screenshots) ===\n"
        f"{visual_json}\n\n"
        "Cross-reference these two layers. Identify, with specific evidence:\n"
        "1. Confirmations — visual and code agree, reinforcing a finding.\n"
        "2. Gaps — something exists visually but the code doesn't support it "
        "(e.g. a form looks simple but has hidden fields; social proof shown but no "
        "schema markup).\n"
        "3. Contradictions — visual suggests one thing, code says another (e.g. page "
        "looks fast but has 12 render-blocking scripts; looks mobile-optimised but "
        "the viewport meta is missing).\n"
        "4. Hidden issues — things only the code reveals (no error-validation markup, "
        "missing alt text, form fields without labels).\n\n"
        "Prioritise the most consequential findings. Return 6-12 findings.\n\n"
        f"Return JSON exactly matching:\n{_SCHEMA}\n\n" + JSON_INSTRUCTION
    )

    # 6-12 findings, each with several prose fields, need real headroom; a
    # 1000-token cap truncates the JSON and silently drops the whole stage.
    result = call_json(client, MODEL_SYNTHESIS, CONSULTANT_PERSONA, prompt,
                       max_tokens=4000)
    return result.get("findings", []) if isinstance(result, dict) else []
