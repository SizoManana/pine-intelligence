"""
code_audit.py — Stage 2: Code Audit.

Deterministic, programmatic analysis of the rendered HTML and CSS. Parses HTML
with BeautifulSoup and CSS with tinycss2. Computes WCAG contrast ratios from
scratch (relative-luminance formula). Returns a structured dict — one entry per
check group — that downstream stages and scoring consume.

Nothing here calls Claude. This is the "code truth" half of the cross-reference.
"""

import re

import tinycss2
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CTA classification keywords
# ---------------------------------------------------------------------------
STRONG_CTA = ("book", "demo", "start", "get", "request", "apply", "sign up",
              "signup", "try", "speak", "schedule", "claim", "join")
WEAK_CTA = ("learn more", "click here", "read more", "find out", "see more",
            "explore", "more info")
CTA_CLASS_HINTS = ("btn", "cta", "button", "demo", "trial")

TRUST_KEYWORDS = ("testimonial", "case study", "award", "accredited", "certified",
                  "regulated", "fca", "fsca", "trusted by", "years of experience",
                  "featured in", "recognised", "recognized", "iso", "partner",
                  "our clients")
SECURITY_KEYWORDS = ("ssl", "padlock", "secure", "encrypted", "256-bit", "https")
SOCIAL_HOSTS = ("linkedin", "twitter", "x.com", "instagram", "facebook", "youtube")

PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ADDRESS_HINTS = ("street", "road", "house", "floor", "avenue", "suite", "ave ", " st ")

NAMED_COLORS = {
    "white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0),
    "green": (0, 128, 0), "blue": (0, 0, 255), "gray": (128, 128, 128),
    "grey": (128, 128, 128), "silver": (192, 192, 192), "navy": (0, 0, 128),
    "transparent": None, "inherit": None, "currentcolor": None,
}


# ---------------------------------------------------------------------------
# WCAG contrast — implemented from scratch
# ---------------------------------------------------------------------------
def _linearize(channel):
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    r, g, b = (_linearize(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(rgb1, rgb2):
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


# ---------------------------------------------------------------------------
# Colour parsing
# ---------------------------------------------------------------------------
def parse_color(value):
    """Return (r, g, b) tuple or None. Handles hex, rgb/rgba, hsl/hsla, names."""
    if not value:
        return None
    value = value.strip().lower()

    if value in NAMED_COLORS:
        return NAMED_COLORS[value]

    # Hex
    m = re.match(r"^#([0-9a-f]{3}|[0-9a-f]{6})$", value)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    # rgb() / rgba()
    m = re.match(r"^rgba?\(([^)]+)\)$", value)
    if m:
        parts = [p.strip() for p in m.group(1).replace("/", ",").split(",")]
        try:
            return tuple(int(round(float(parts[i].rstrip("%")))) for i in range(3))
        except (ValueError, IndexError):
            return None

    # hsl() / hsla()
    m = re.match(r"^hsla?\(([^)]+)\)$", value)
    if m:
        parts = [p.strip() for p in m.group(1).replace("/", ",").split(",")]
        try:
            h = float(parts[0]) % 360
            s = float(parts[1].rstrip("%")) / 100.0
            light = float(parts[2].rstrip("%")) / 100.0
            return _hsl_to_rgb(h, s, light)
        except (ValueError, IndexError):
            return None

    return None


def _hsl_to_rgb(h, s, light):
    c = (1 - abs(2 * light - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = light - c / 2
    if h < 60:
        rp, gp, bp = c, x, 0
    elif h < 120:
        rp, gp, bp = x, c, 0
    elif h < 180:
        rp, gp, bp = 0, c, x
    elif h < 240:
        rp, gp, bp = 0, x, c
    elif h < 300:
        rp, gp, bp = x, 0, c
    else:
        rp, gp, bp = c, 0, x
    return tuple(int(round((v + m) * 255)) for v in (rp, gp, bp))


# ---------------------------------------------------------------------------
# CSS parsing with tinycss2
# ---------------------------------------------------------------------------
def _parse_rules(css_text):
    """Return list of (selector_text, {prop: value}) and a :root vars dict."""
    rules = []
    root_vars = {}
    try:
        parsed = tinycss2.parse_stylesheet(
            css_text, skip_whitespace=True, skip_comments=True)
    except Exception:
        return rules, root_vars

    for rule in parsed:
        if rule.type != "qualified-rule":
            continue
        selector = tinycss2.serialize(rule.prelude).strip()
        decls = {}
        for d in tinycss2.parse_declaration_list(
                rule.content, skip_whitespace=True, skip_comments=True):
            if getattr(d, "type", None) != "declaration":
                continue
            name = d.lower_name
            val = tinycss2.serialize(d.value).strip()
            decls[name] = val
            if selector == ":root" and name.startswith("--"):
                root_vars[name] = val
        rules.append((selector, decls))
    return rules, root_vars


def _resolve_var(value, root_vars, depth=0):
    """Resolve a single var(--x[, fallback]) reference against :root vars."""
    if not value or depth > 5:
        return value
    m = re.match(r"var\((--[\w-]+)\s*(?:,\s*(.+))?\)", value.strip())
    if not m:
        return value
    name, fallback = m.group(1), m.group(2)
    resolved = root_vars.get(name, fallback)
    if resolved and resolved.strip().startswith("var("):
        return _resolve_var(resolved, root_vars, depth + 1)
    return resolved


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _present(value):
    return value is not None and str(value).strip() != ""


def _verdict(ok, partial=False):
    if ok:
        return "pass"
    return "partial" if partial else "fail"


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------
def audit(captures, context=None):
    soup = BeautifulSoup(captures["html_source"], "html.parser")
    meta = captures.get("meta_tags", {})
    css_text = (captures.get("inline_css", "") + "\n"
                + "\n".join(captures.get("external_css_content", [])))
    rules, root_vars = _parse_rules(css_text)
    text_blob = soup.get_text(" ", strip=True).lower()
    html_lower = captures["html_source"].lower()

    findings = {}

    # --- Structure & Semantics ---------------------------------------------
    h1s = soup.find_all("h1")
    h1_text = h1s[0].get_text(strip=True) if h1s else ""
    headings = [h.name for h in soup.find_all(re.compile(r"^h[1-6]$"))]
    skipped = _detect_skipped_headings(soup)
    landmarks = {tag: bool(soup.find(tag)) for tag in
                 ("nav", "main", "header", "footer", "aside")}
    semantic_count = len(soup.find_all(["section", "article", "aside"]))
    div_count = len(soup.find_all("div"))
    findings["structure"] = {
        "h1_present": bool(h1s),
        "h1_count": len(h1s),
        "h1_text": h1_text,
        "h1_word_count": len(h1_text.split()),
        "heading_sequence": headings[:25],
        "skipped_heading_levels": skipped,
        "landmarks": landmarks,
        "semantic_elements": semantic_count,
        "div_count": div_count,
        "verdict": _verdict(
            len(h1s) == 1 and not skipped and landmarks["main"],
            partial=bool(h1s)),
    }

    # --- Meta & SEO --------------------------------------------------------
    title = captures.get("title", "")
    desc = meta.get("description", "")
    canonical = bool(soup.find("link", rel="canonical"))
    viewport = meta.get("viewport", "")
    og = {k: meta.get(f"og:{k}", "") for k in ("title", "description", "image", "type")}
    twitter = {k: v for k, v in meta.items() if k.startswith("twitter:")}
    jsonld_types = _jsonld_types(soup)
    findings["meta_seo"] = {
        "title": title,
        "title_length": len(title),
        "title_ideal": 50 <= len(title) <= 60,
        "meta_description": desc,
        "description_length": len(desc),
        "description_ideal": 120 <= len(desc) <= 160,
        "canonical": canonical,
        "viewport": viewport,
        "viewport_ok": "width=device-width" in viewport.replace(" ", "").lower(),
        "open_graph": og,
        "og_complete": all(og.values()),
        "twitter_card": twitter,
        "schema_jsonld_present": bool(jsonld_types),
        "schema_types": jsonld_types,
        "verdict": _verdict(
            _present(title) and _present(desc) and viewport != "" and bool(og["title"]),
            partial=_present(title)),
    }

    # --- Images ------------------------------------------------------------
    imgs = soup.find_all("img")
    with_alt = sum(1 for i in imgs if _present(i.get("alt")))
    lazy = sum(1 for i in imgs if i.get("loading") == "lazy")
    nextgen = sum(1 for i in imgs if re.search(
        r"\.(webp|avif)", (i.get("src", "") + i.get("srcset", "")), re.I))
    findings["images"] = {
        "total": len(imgs),
        "alt_coverage_pct": round(100 * with_alt / len(imgs)) if imgs else 100,
        "with_alt": with_alt,
        "lazy_loaded": lazy,
        "nextgen_formats": nextgen,
        "verdict": _verdict(
            not imgs or with_alt == len(imgs),
            partial=bool(imgs) and with_alt > 0),
    }

    # --- Forms -------------------------------------------------------------
    forms = soup.find_all("form")
    form_details = []
    for form in forms:
        fields = [el for el in form.find_all(["input", "textarea", "select"])
                  if el.get("type") not in ("hidden", "submit", "button", "reset", "image")]
        labelled = 0
        for el in fields:
            if el.get("aria-label") or el.get("aria-labelledby"):
                labelled += 1
            elif el.get("id") and form.find("label", attrs={"for": el.get("id")}):
                labelled += 1
        required = sum(1 for el in fields
                       if el.has_attr("required") or el.get("aria-required") == "true")
        autocompletes = sum(1 for el in fields if el.get("autocomplete"))
        has_error_markup = bool(
            form.find(attrs={"aria-describedby": True})
            or form.select('[class*="error"], [class*="invalid"]'))
        form_details.append({
            "field_count": len(fields),
            "labelled_fields": labelled,
            "all_labelled": len(fields) > 0 and labelled == len(fields),
            "required_fields": required,
            "autocomplete_fields": autocompletes,
            "inline_error_handling": has_error_markup,
        })
    findings["forms"] = {
        "form_count": len(forms),
        "forms": form_details,
        "verdict": _verdict(
            not forms or all(f["all_labelled"] for f in form_details),
            partial=bool(forms)),
    }

    # --- Navigation --------------------------------------------------------
    nav = soup.find("nav")
    nav_items = len(nav.find_all("a")) if nav else 0
    sticky = bool(re.search(r"(nav|header)[^{]*\{[^}]*position\s*:\s*(fixed|sticky)",
                            css_text, re.I)) or "sticky" in html_lower
    nav_cta = False
    if nav:
        for a in nav.find_all("a"):
            cls = " ".join(a.get("class", [])).lower()
            if any(h in cls for h in CTA_CLASS_HINTS):
                nav_cta = True
                break
    findings["navigation"] = {
        "nav_present": bool(nav),
        "primary_nav_items": nav_items,
        "sticky_or_fixed": sticky,
        "cta_in_nav": nav_cta,
        "verdict": _verdict(bool(nav) and nav_items > 0, partial=bool(nav)),
    }

    # --- CTAs & Conversion -------------------------------------------------
    cta_texts = _collect_cta_texts(soup)
    classified = []
    for t in cta_texts:
        low = t.lower()
        if any(w in low for w in STRONG_CTA):
            klass = "strong"
        elif any(w in low for w in WEAK_CTA):
            klass = "weak"
        else:
            klass = "neutral"
        classified.append({"text": t, "class": klass})
    strong_n = sum(1 for c in classified if c["class"] == "strong")
    findings["ctas"] = {
        "cta_count": len(classified),
        "ctas": classified[:30],
        "strong_count": strong_n,
        "weak_count": sum(1 for c in classified if c["class"] == "weak"),
        "first_cta_text": classified[0]["text"] if classified else "",
        "verdict": _verdict(strong_n > 0, partial=bool(classified)),
    }

    # --- Trust signals -----------------------------------------------------
    trust_found = [k for k in TRUST_KEYWORDS if k in text_blob]
    phones = PHONE_RE.findall(text_blob)
    emails = EMAIL_RE.findall(captures["html_source"])
    has_address = any(h in text_blob for h in ADDRESS_HINTS)
    privacy = bool(soup.find("a", string=re.compile("privacy", re.I))
                   or soup.find("a", href=re.compile("privacy", re.I)))
    cookie = "cookie" in text_blob and ("consent" in text_blob or "accept" in text_blob)
    security = [k for k in SECURITY_KEYWORDS if k in text_blob]
    socials = sorted({h for h in SOCIAL_HOSTS
                      for link in captures["links"]["external"] if h in link.lower()})
    findings["trust"] = {
        "trust_keywords_found": trust_found,
        "phone_present": bool(phones),
        "email_present": bool(emails),
        "physical_address_hint": has_address,
        "privacy_policy_link": privacy,
        "cookie_consent": cookie,
        "security_indicators": security,
        "social_media_links": socials,
        "verdict": _verdict(
            len(trust_found) >= 2 and (bool(phones) or bool(emails)),
            partial=bool(trust_found) or bool(socials)),
    }

    # --- Performance indicators -------------------------------------------
    head = soup.find("head")
    head_scripts = head.find_all("script", src=True) if head else []
    blocking_scripts = [s for s in head_scripts
                        if not s.has_attr("defer") and not s.has_attr("async")]
    head_stylesheets = head.find_all("link", rel="stylesheet") if head else []
    inline_critical = bool(head.find("style")) if head else False
    timing = captures.get("load_timing", {})
    findings["performance"] = {
        "render_blocking_scripts": len(blocking_scripts),
        "render_blocking_stylesheets": len(head_stylesheets),
        "inline_critical_css": inline_critical,
        "dom_content_loaded_ms": timing.get("dom_content_loaded_ms"),
        "load_event_ms": timing.get("load_event_ms"),
        "console_errors": len(captures.get("console_errors", [])),
        "verdict": _verdict(
            len(blocking_scripts) <= 2 and len(head_stylesheets) <= 3,
            partial=len(blocking_scripts) <= 5),
    }

    # --- Colour & contrast -------------------------------------------------
    contrast_pairs = _contrast_pairs(rules, root_vars)
    failing = [p for p in contrast_pairs if not p["passes_aa_normal"]]
    color_vars = {k: v for k, v in root_vars.items()
                  if any(t in k for t in ("color", "colour", "bg", "background",
                                          "primary", "accent", "text"))}
    findings["color_contrast"] = {
        "css_color_variables": color_vars,
        "pairs_checked": len(contrast_pairs),
        "pairs": contrast_pairs[:20],
        "failing_pairs": len(failing),
        "verdict": _verdict(
            contrast_pairs and not failing,
            partial=bool(contrast_pairs)),
    }

    # --- Accessibility -----------------------------------------------------
    html_tag = soup.find("html")
    lang = html_tag.get("lang") if html_tag else None
    skip_link = bool(soup.find("a", href=re.compile(r"^#(main|content|skip)", re.I))
                     or soup.find("a", string=re.compile("skip to", re.I)))
    icon_buttons = soup.find_all("button")
    icon_btn_labeled = sum(1 for b in icon_buttons
                           if b.get_text(strip=True) or b.get("aria-label"))
    focus_styles = ":focus" in css_text
    findings["accessibility"] = {
        "html_lang": lang,
        "lang_present": _present(lang),
        "skip_navigation_link": skip_link,
        "buttons_total": len(icon_buttons),
        "buttons_labeled": icon_btn_labeled,
        "focus_visible_styles": focus_styles,
        "verdict": _verdict(
            _present(lang) and focus_styles,
            partial=_present(lang)),
    }

    return findings


# ---------------------------------------------------------------------------
# Sub-helpers
# ---------------------------------------------------------------------------
def _detect_skipped_headings(soup):
    levels = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
    skipped = []
    prev = 0
    for lvl in levels:
        if prev and lvl > prev + 1:
            skipped.append(f"h{prev}->h{lvl}")
        prev = lvl
    return skipped


def _jsonld_types(soup):
    types = []
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text() or ""
        for m in re.findall(r'"@type"\s*:\s*"([^"]+)"', raw):
            types.append(m)
    return sorted(set(types))


def _collect_cta_texts(soup):
    texts = []
    for el in soup.find_all(["button"]):
        t = el.get_text(strip=True)
        if t:
            texts.append(t)
    for el in soup.find_all("input", type=re.compile("submit|button", re.I)):
        if el.get("value"):
            texts.append(el["value"])
    for a in soup.find_all("a"):
        cls = " ".join(a.get("class", [])).lower()
        if any(h in cls for h in CTA_CLASS_HINTS):
            t = a.get_text(strip=True)
            if t:
                texts.append(t)
    # De-dupe preserving order
    seen, out = set(), []
    for t in texts:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


_TARGET_SELECTORS = ("body", "h1", "h2", "h3", "a", "button", ".btn", ".button",
                     ".cta", "p")


def _contrast_pairs(rules, root_vars):
    """Find color + background-color pairs on key selectors and rate contrast."""
    pairs = []
    for selector, decls in rules:
        sel_low = selector.lower()
        if not any(t in sel_low for t in _TARGET_SELECTORS):
            continue
        color_raw = decls.get("color")
        bg_raw = decls.get("background-color") or decls.get("background")
        if not color_raw or not bg_raw:
            continue
        color = parse_color(_resolve_var(color_raw, root_vars))
        bg = parse_color(_resolve_var(bg_raw, root_vars))
        if not color or not bg:
            continue
        ratio = contrast_ratio(color, bg)
        pairs.append({
            "selector": selector[:60],
            "foreground": "#%02x%02x%02x" % color,
            "background": "#%02x%02x%02x" % bg,
            "ratio": ratio,
            "passes_aa_normal": ratio >= 4.5,
            "passes_aa_large": ratio >= 3.0,
        })
    return pairs
