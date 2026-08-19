"""
scoring.py — Deterministic score computation.

Scores are derived only from the structured JSON outputs of Stage 2 (code) and
Stage 3 (visual) — never from narrative text. UI Score /100 and UX Score /100,
each broken down by criterion per the brief's rubric.

Visual criteria already carry a score within a known max from the vision calls;
we clamp and re-weight those. Code-derived criteria are computed from booleans
and counts. Where a visual call failed (missing key), we fall back to a neutral
60% of the available points so a partial run still yields a usable score.
"""

NEUTRAL = 0.6  # fallback fraction when a visual sub-score is missing


def _vis(visual, section, key, max_pts):
    """Pull a 0..N visual score, clamp to [0, max_pts], else neutral fallback."""
    try:
        raw = visual[section][key]["score"]
        return max(0, min(float(raw), max_pts))
    except (KeyError, TypeError, ValueError):
        return NEUTRAL * max_pts


def _frac(value, max_pts):
    return max(0.0, min(1.0, value)) * max_pts


def _safe(code, group, key, default=None):
    try:
        return code[group][key]
    except (KeyError, TypeError):
        return default


def compute_scores(visual, code):
    ui = _ui_score(visual, code)
    ux = _ux_score(visual, code)
    return {
        "ui_score": round(ui["total"]),
        "ux_score": round(ux["total"]),
        "ui_breakdown": ui["breakdown"],
        "ux_breakdown": ux["breakdown"],
    }


# ---------------------------------------------------------------------------
# UI Score /100
# ---------------------------------------------------------------------------
def _ui_score(visual, code):
    breakdown = {}

    # Visual hierarchy & above-fold impact (20, Visual)
    breakdown["Visual hierarchy & above-fold impact"] = {
        "score": round(_vis(visual, "above_fold", "visual_hierarchy", 20), 1),
        "max": 20}

    # Colour harmony & contrast (15, Visual + Code)
    colour_vis = _vis(visual, "above_fold", "colour_harmony", 10)  # 0..10
    contrast = code.get("color_contrast", {})
    checked = contrast.get("pairs_checked", 0)
    failing = contrast.get("failing_pairs", 0)
    if checked:
        contrast_frac = 1.0 - (failing / checked)
    else:
        contrast_frac = NEUTRAL
    colour_code = _frac(contrast_frac, 5)
    breakdown["Colour harmony & contrast (WCAG)"] = {
        "score": round(colour_vis / 10 * 10 + colour_code, 1), "max": 15}

    # Typography legibility (10, Visual)
    breakdown["Typography legibility"] = {
        "score": round(_vis(visual, "above_fold", "typography_legibility", 10), 1),
        "max": 10}

    # CTA prominence & copy quality (15, Visual + Code)
    cta_vis = _vis(visual, "above_fold", "cta_prominence", 15) / 15 * 10  # 0..10
    ctas = code.get("ctas", {})
    total_cta = ctas.get("cta_count", 0)
    strong = ctas.get("strong_count", 0)
    cta_code = _frac(strong / total_cta if total_cta else NEUTRAL, 5)
    breakdown["CTA prominence & copy quality"] = {
        "score": round(cta_vis + cta_code, 1), "max": 15}

    # Navigation & structure (10, Code)
    nav = code.get("navigation", {})
    struct = code.get("structure", {})
    nav_pts = 0.0
    nav_pts += 4 if nav.get("nav_present") else 0
    nav_pts += 3 if struct.get("h1_count") == 1 else (1.5 if struct.get("h1_present") else 0)
    nav_pts += 3 if not struct.get("skipped_heading_levels") else 0
    breakdown["Navigation & structure"] = {"score": round(nav_pts, 1), "max": 10}

    # Technical markup (15, Code)
    meta = code.get("meta_seo", {})
    tech = 0.0
    tech += 4 if meta.get("title") else 0
    tech += 4 if meta.get("meta_description") else 0
    tech += 3 if meta.get("viewport_ok") else 0
    tech += 2 if meta.get("canonical") else 0
    semantic = struct.get("semantic_elements", 0)
    tech += 2 if semantic >= 3 else (1 if semantic else 0)
    breakdown["Technical markup (meta, OG, semantic)"] = {
        "score": round(tech, 1), "max": 15}

    # Favicon, OG image, schema (5, Code)
    extras = 0.0
    og = meta.get("open_graph", {})
    extras += 2 if og.get("image") else 0
    extras += 1 if og.get("title") else 0
    extras += 2 if meta.get("schema_jsonld_present") else 0
    breakdown["Favicon, OG image, schema"] = {"score": round(extras, 1), "max": 5}

    # Accessibility basics (10, Code)
    acc = code.get("accessibility", {})
    a = 0.0
    a += 3 if acc.get("lang_present") else 0
    a += 3 if acc.get("focus_visible_styles") else 0
    a += 2 if acc.get("skip_navigation_link") else 0
    imgs = code.get("images", {})
    a += 2 if imgs.get("alt_coverage_pct", 0) >= 90 else (
        1 if imgs.get("alt_coverage_pct", 0) >= 50 else 0)
    breakdown["Accessibility basics"] = {"score": round(a, 1), "max": 10}

    total = sum(b["score"] for b in breakdown.values())
    return {"total": total, "breakdown": breakdown}


# ---------------------------------------------------------------------------
# UX Score /100
# ---------------------------------------------------------------------------
def _ux_score(visual, code):
    breakdown = {}

    # Value proposition clarity (25, Visual + Code)
    vp_vis = _vis(visual, "above_fold", "value_proposition", 20) / 20 * 18  # 0..18
    struct = code.get("structure", {})
    wc = struct.get("h1_word_count", 0)
    vp_code = 7 if 4 <= wc <= 14 else (4 if struct.get("h1_present") else 0)
    breakdown["Value proposition clarity"] = {
        "score": round(vp_vis + vp_code, 1), "max": 25}

    # Trust & credibility signals (20, Visual + Code)
    trust_vis = _vis(visual, "above_fold", "trust_signals_above_fold", 15) / 15 * 12
    trust = code.get("trust", {})
    tcode = 0.0
    tcode += 3 if len(trust.get("trust_keywords_found", [])) >= 2 else (
        1.5 if trust.get("trust_keywords_found") else 0)
    tcode += 2 if (trust.get("phone_present") or trust.get("email_present")) else 0
    tcode += 1.5 if trust.get("privacy_policy_link") else 0
    tcode += 1.5 if trust.get("social_media_links") else 0
    breakdown["Trust & credibility signals"] = {
        "score": round(trust_vis + tcode, 1), "max": 20}

    # Conversion pathway (20, Code + Visual)
    ctas = code.get("ctas", {})
    forms = code.get("forms", {})
    conv = 0.0
    conv += 5 if ctas.get("strong_count", 0) > 0 else (2 if ctas.get("cta_count") else 0)
    if forms.get("form_count"):
        avg_fields = sum(f["field_count"] for f in forms["forms"]) / forms["form_count"]
        conv += 5 if avg_fields <= 5 else (3 if avg_fields <= 8 else 1)
        conv += 2 if all(f["all_labelled"] for f in forms["forms"]) else 0
    else:
        conv += 5  # no form = no form friction on this page
    conv += _vis(visual, "full_page", "form_visual_design", 10) / 10 * 8
    breakdown["Conversion pathway (CTA, form, friction)"] = {
        "score": round(min(conv, 20), 1), "max": 20}

    # Content structure & messaging (15, Visual)
    content = (_vis(visual, "full_page", "content_flow", 15) / 15 * 8
               + _vis(visual, "full_page", "page_length_and_structure", 10) / 10 * 7)
    breakdown["Content structure & messaging"] = {
        "score": round(content, 1), "max": 15}

    # Mobile experience (10, Visual)
    mobile = (_vis(visual, "mobile", "mobile_value_prop", 15) / 15 * 4
              + _vis(visual, "mobile", "tap_targets", 10) / 10 * 3
              + _vis(visual, "mobile", "mobile_readability", 10) / 10 * 3)
    breakdown["Mobile experience"] = {"score": round(mobile, 1), "max": 10}

    # Social proof & testimonials (10, Visual + Code)
    sp_vis = _vis(visual, "full_page", "social_proof_placement", 15) / 15 * 6
    trust_kw = code.get("trust", {}).get("trust_keywords_found", [])
    sp_code = 4 if any(k in trust_kw for k in
                       ("testimonial", "case study", "trusted by", "our clients")) else (
        2 if trust_kw else 0)
    breakdown["Social proof & testimonials"] = {
        "score": round(sp_vis + sp_code, 1), "max": 10}

    total = sum(b["score"] for b in breakdown.values())
    return {"total": total, "breakdown": breakdown}
