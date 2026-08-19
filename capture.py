"""
capture.py — Stage 1: Capture.

Uses the Playwright async API to render a URL in headless Chromium and extract
everything later stages need: screenshots (desktop above-fold, a series of
section screenshots taken by scrolling the page, and mobile), post-JavaScript
HTML, inline + external CSS, meta tags, links, load timing, and console errors.

Rather than one huge full-page screenshot (which long pages push past the
vision API's size limits), the page is scrolled in viewport-height increments
and each viewport captured as its own 1440x900 PNG. These are already within
API limits, so no scaling or compression is applied.

Screenshots are written to `output_dir` as PNGs and their paths returned in the
captures dict. The rest of the data is returned inline.
"""

import math
import os
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright

# The page is scrolled and captured one viewport at a time; we cap the number
# of section screenshots so very long pages don't produce an unbounded number
# of images for the vision call.
MAX_SECTIONS = 8

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DESKTOP_VIEWPORT = {"width": 1440, "height": 900}
MOBILE_VIEWPORT = {"width": 390, "height": 844}

# CSS hosts we skip when fetching external stylesheet content (fonts / CDNs).
_SKIP_CSS_HINTS = ("fonts.googleapis", "fonts.gstatic", "cdnjs", "cdn.jsdelivr",
                   "use.typekit", "use.fontawesome", "googletagmanager")


def _is_internal(href, base_netloc):
    try:
        netloc = urlparse(href).netloc
    except ValueError:
        return True
    return (netloc == "") or (netloc == base_netloc)


async def capture(url, output_dir):
    """Render `url` and return a captures dict. Raises on navigation failure."""
    os.makedirs(output_dir, exist_ok=True)
    console_errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=CHROME_UA,
                viewport=DESKTOP_VIEWPORT,
                device_scale_factor=1,
            )
            page = await context.new_page()
            page.on("console", lambda msg: (
                console_errors.append(msg.text) if msg.type == "error" else None))

            # --- Navigate (networkidle + settle) ---------------------------------
            try:
                await page.goto(url, wait_until="networkidle", timeout=45000)
            except Exception:
                # networkidle can hang on pages with long-poll connections;
                # fall back to domcontentloaded so we still get a render.
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            # Extra settle time so late-loading dynamic content (e.g. G2 review
            # badges, lazy widgets) is painted before any screenshot is taken.
            await page.wait_for_timeout(3500)

            base_netloc = urlparse(page.url).netloc

            # --- Desktop above-fold screenshot -----------------------------------
            desktop_path = os.path.join(output_dir, "desktop.png")
            await page.screenshot(path=desktop_path, full_page=False)

            # --- Section screenshots (scroll the page one viewport at a time) ----
            # Each section is a full-resolution 1440x900 viewport capture, well
            # within the vision API's limits, so no scaling is needed.
            section_height = DESKTOP_VIEWPORT["height"]
            total_height = await page.evaluate(
                "() => Math.max(document.body.scrollHeight, "
                "document.documentElement.scrollHeight)"
            )
            section_count = max(1, math.ceil((total_height or section_height)
                                             / section_height))
            section_count = min(section_count, MAX_SECTIONS)
            section_paths = []
            for i in range(section_count):
                offset = i * section_height
                await page.evaluate("(y) => window.scrollTo(0, y)", offset)
                # Let lazy-loaded content for this viewport paint before capture.
                await page.wait_for_timeout(450)
                section_path = os.path.join(output_dir, f"section_{i + 1}.png")
                await page.screenshot(path=section_path, full_page=False)
                section_paths.append(section_path)
            # Return to the top so later measurements/captures are consistent.
            await page.evaluate("() => window.scrollTo(0, 0)")

            # --- Page data (post-JS) ---------------------------------------------
            html_source = await page.content()
            title = await page.title()

            inline_css = await page.evaluate(
                "() => Array.from(document.querySelectorAll('style'))"
                ".map(s => s.textContent).join('\\n')"
            )
            external_css_hrefs = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'link[rel=\"stylesheet\"]')).map(l => l.href)"
            )
            meta_tags = await page.evaluate(
                "() => { const o = {}; "
                "document.querySelectorAll('meta').forEach(m => { "
                "const k = m.getAttribute('name') || m.getAttribute('property'); "
                "if (k) o[k] = m.getAttribute('content') || ''; }); return o; }"
            )
            raw_links = await page.evaluate(
                "() => Array.from(document.querySelectorAll('a[href]'))"
                ".map(a => a.getAttribute('href'))"
            )
            load_timing = await page.evaluate(
                "() => { const t = window.performance && window.performance.timing; "
                "if (!t) return {}; return { navigationStart: t.navigationStart, "
                "domContentLoadedEventEnd: t.domContentLoadedEventEnd, "
                "loadEventEnd: t.loadEventEnd, responseEnd: t.responseEnd, "
                "domComplete: t.domComplete }; }"
            )

            # --- Classify links --------------------------------------------------
            links = {"internal": [], "external": []}
            for href in raw_links:
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    links["internal"].append(href or "")
                    continue
                absolute = urljoin(page.url, href)
                if _is_internal(absolute, base_netloc):
                    links["internal"].append(absolute)
                else:
                    links["external"].append(absolute)

            # --- Fetch external CSS (up to 5, skip font/CDN hosts) ---------------
            external_css_content = []
            fetched = 0
            for href in external_css_hrefs:
                if fetched >= 5:
                    break
                if any(hint in href for hint in _SKIP_CSS_HINTS):
                    continue
                try:
                    resp = await context.request.get(href, timeout=10000)
                    if resp.ok:
                        external_css_content.append(await resp.text())
                        fetched += 1
                except Exception:
                    continue

            # --- Mobile above-fold screenshot ------------------------------------
            await page.set_viewport_size(MOBILE_VIEWPORT)
            await page.wait_for_timeout(800)
            mobile_path = os.path.join(output_dir, "mobile.png")
            await page.screenshot(path=mobile_path, full_page=False)

            # --- Compute load durations (ms) -------------------------------------
            nav_start = load_timing.get("navigationStart") or 0
            dcl = load_timing.get("domContentLoadedEventEnd") or 0
            load_end = load_timing.get("loadEventEnd") or 0
            timing_summary = {
                "dom_content_loaded_ms": max(0, dcl - nav_start) if nav_start else None,
                "load_event_ms": max(0, load_end - nav_start) if nav_start else None,
                "raw": load_timing,
            }

            return {
                "final_url": page.url,
                "screenshot_desktop": desktop_path,
                "screenshot_sections": section_paths,
                "screenshot_mobile": mobile_path,
                "html_source": html_source,
                "inline_css": inline_css or "",
                "external_css_hrefs": external_css_hrefs,
                "external_css_content": external_css_content,
                "meta_tags": meta_tags,
                "title": title,
                "links": links,
                "load_timing": timing_summary,
                "console_errors": console_errors,
            }
        finally:
            await browser.close()
