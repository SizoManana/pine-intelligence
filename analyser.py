"""
analyser.py — Orchestrates the 5-stage pipeline.

Runs Capture -> Code Audit -> Visual Audit -> Cross-Reference -> Report, emitting
progress events through a callback so the Flask SSE endpoint can stream status.

Resilience: Playwright failure (Stage 1) aborts the job with a clear error.
Claude failures in later stages are caught per-stage and the stage is marked
'partial' rather than killing the whole job (per the brief).
"""

import logging

import anthropic

import capture as capture_mod
import code_audit
import crossref as crossref_mod
import report as report_mod
import scoring
import visual_audit

# Users only ever see the plain messages below, but every caught stage failure
# is logged in full server-side so nothing fails silently for operators.
log = logging.getLogger("pine.analyser")

# Shown to the user whenever a single (non-fatal) stage can't be completed.
# Deliberately plain — never surfaces Python exceptions or error codes.
PARTIAL_STAGE_MSG = ("This section could not be completed for this site. "
                     "All other findings remain valid.")
# Shown when the page itself cannot be loaded at all (a fatal, stage-1 failure).
CAPTURE_FAIL_MSG = ("We were unable to load this site for analysis. This can "
                    "happen when a site blocks automated browsers or fails to "
                    "respond. Please check the URL and try again.")


async def run_analysis(url, context, output_dir, progress, mode="full"):
    """
    Execute the pipeline. `progress(stage, status, message, **extra)` is a
    callback. Returns the assembled result dict (also suitable for /report).

    `mode` selects the depth of analysis:
      - "full"  -> the full five-stage CRO audit (capture, code, visual,
                   cross-reference, consultant report).
      - "uiux"  -> a visual-only UI/UX pass: capture + the three vision calls +
                   a shorter visual report. The code-audit and cross-reference
                   stages are skipped entirely.
    """
    visual_only = (mode == "uiux")
    client = anthropic.Anthropic()
    result = {
        "url": url,
        "context": context,
        "mode": mode,
        "partial_stages": [],
    }

    # --- Stage 1: Capture --------------------------------------------------
    progress("capture", "running", "Rendering page in headless Chrome...")
    try:
        captures = await capture_mod.capture(url, output_dir)
    except Exception:
        log.exception("Capture stage failed for %s", url)
        progress("capture", "error", CAPTURE_FAIL_MSG)
        raise RuntimeError(CAPTURE_FAIL_MSG)
    result["captures_meta"] = {
        "final_url": captures.get("final_url"),
        "title": captures.get("title"),
        "console_errors": captures.get("console_errors", []),
    }
    result["screenshots"] = report_mod.encode_screenshots(captures)
    progress("capture", "done", "Screenshots captured")

    # --- Stage 2: Code Audit ----------------------------------------------
    # Skipped entirely in UI/UX mode — that pass is visual-only.
    if visual_only:
        code_findings = {}
    else:
        progress("code", "running", "Auditing HTML and CSS...")
        try:
            code_findings = code_audit.audit(captures, context)
            progress("code", "done", "Code audit complete")
        except Exception:
            log.exception("Code audit stage failed for %s", url)
            code_findings = {}
            result["partial_stages"].append("code")
            progress("code", "error", PARTIAL_STAGE_MSG)
    result["code"] = code_findings

    # --- Stage 3: Visual Audit --------------------------------------------
    # Above-fold desktop and mobile are single-image calls; the section pass is
    # one multi-image call over every section screenshot, returning both a
    # descriptive section-by-section read and a scored page-level assessment.
    progress("visual", "running", "Analysing design with Claude Vision...")
    visual_findings = {}
    result["sections"] = []

    def _mark_visual_partial():
        if "visual" not in result["partial_stages"]:
            result["partial_stages"].append("visual")

    try:
        visual_findings["above_fold"] = visual_audit.analyse_above_fold(
            client, captures, context)
    except Exception:
        log.exception("Visual sub-analysis 'above_fold' failed for %s", url)
        _mark_visual_partial()
        progress("visual", "running", PARTIAL_STAGE_MSG)

    try:
        sections = visual_audit.analyse_sections(client, captures, context)
        visual_findings["full_page"] = sections.get("page_assessment", {})
        result["sections"] = sections.get("sections", []) or []
    except Exception:
        log.exception("Visual sub-analysis 'sections' failed for %s", url)
        _mark_visual_partial()
        progress("visual", "running", PARTIAL_STAGE_MSG)

    try:
        visual_findings["mobile"] = visual_audit.analyse_mobile(
            client, captures, context)
    except Exception:
        log.exception("Visual sub-analysis 'mobile' failed for %s", url)
        _mark_visual_partial()
        progress("visual", "running", PARTIAL_STAGE_MSG)

    if visual_findings and "visual" not in result["partial_stages"]:
        progress("visual", "done", "Visual analysis complete")
    elif visual_findings:
        progress("visual", "done", "Visual analysis complete")
    else:
        progress("visual", "error", PARTIAL_STAGE_MSG)
    result["visual"] = visual_findings

    # --- Scoring (deterministic, from structured outputs) ------------------
    result["scores"] = scoring.compute_scores(visual_findings, code_findings)

    # --- Stage 4: Cross-Reference -----------------------------------------
    # Skipped in UI/UX mode — there are no code findings to cross-reference.
    if visual_only:
        crossref_findings = []
    else:
        progress("crossref", "running",
                 "Cross-referencing visual and code findings...")
        try:
            crossref_findings = crossref_mod.cross_reference(
                client, code_findings, visual_findings, context)
            progress("crossref", "done", "Cross-reference complete")
        except Exception:
            log.exception("Cross-reference stage failed for %s", url)
            crossref_findings = []
            result["partial_stages"].append("crossref")
            progress("crossref", "error", PARTIAL_STAGE_MSG)
    result["crossref"] = crossref_findings

    # --- Stage 5: Consultant Report ---------------------------------------
    progress("report", "running", "Drafting consultant analysis...")
    try:
        if visual_only:
            report = report_mod.generate_visual_report(
                client, url, context, visual_findings)
        else:
            report = report_mod.generate_report(
                client, url, context, code_findings, visual_findings,
                crossref_findings)
        progress("report", "done", "Consultant report drafted")
    except Exception:
        log.exception("Report stage failed for %s", url)
        report = {
            "executive_summary": ("The written consultant report could not be "
                                  "generated for this site. The scores, visual "
                                  "findings, and captured renders above remain "
                                  "valid."),
            "overall_verdict": "Needs Work",
            "key_strength": "",
            "critical_gap": "",
            "recommendations": [],
        }
        result["partial_stages"].append("report")
        progress("report", "error", PARTIAL_STAGE_MSG)
    result["report"] = report
    result["references"] = report_mod.collect_references(report, crossref_findings)

    return result
