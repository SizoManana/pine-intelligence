"""
app.py — Flask server, routes, and the SSE progress stream.

Playwright runs async; Flask is sync. We bridge by running each analysis job in
a background thread with its own asyncio event loop. The pipeline emits progress
events into a per-job thread-safe queue; the SSE endpoint drains that queue and
streams `data: {...}` events to the browser until 'complete'.

Job state lives in an in-memory dict keyed by UUID (single-process dev server).
"""

import asyncio
import json
import logging
import os
import queue
import threading
import uuid

from dotenv import load_dotenv
from flask import (Flask, Response, abort, jsonify, render_template, request,
                   stream_with_context)

# Surface full server-side tracebacks (incl. per-stage failures logged by the
# analyser) while users continue to see only plain, professional messages.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

load_dotenv()

import analyser  # noqa: E402  (import after load_dotenv so the key is in env)

app = Flask(__name__)

TMP_ROOT = "/tmp/pine"
os.makedirs(TMP_ROOT, exist_ok=True)

# job_id -> {"queue": Queue, "result": dict|None, "error": str|None, ...}
JOBS = {}

STAGES = ["capture", "code", "visual", "crossref", "report"]

# Plain, professional copy shown to the user when the whole analysis can't be
# completed. Technical details are kept server-side only, never sent to the UI.
GENERIC_FAIL_MSG = ("We were unable to complete the analysis for this site. "
                    "This can happen when a site blocks automated browsers or "
                    "fails to load. Please check the URL and try again.")


def _run_job(job_id, url, context, mode):
    """Background worker: runs the async pipeline and feeds the progress queue."""
    job = JOBS[job_id]
    q = job["queue"]
    output_dir = os.path.join(TMP_ROOT, job_id)

    def progress(stage, status, message, **extra):
        event = {"stage": stage, "status": status, "message": message}
        event.update(extra)
        q.put(event)

    try:
        result = asyncio.run(
            analyser.run_analysis(url, context, output_dir, progress, mode))
        job["result"] = result
        q.put({"stage": "complete", "status": "done",
               "report_url": f"/report/{job_id}"})
    except Exception as exc:  # capture-stage failure or unexpected crash
        # Keep the technical detail server-side; show the user plain language.
        job["error"] = str(exc)
        q.put({"stage": "error", "status": "error", "message": GENERIC_FAIL_MSG})
    finally:
        q.put(None)  # sentinel: stream may close


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyse", methods=["POST"])
def analyse():
    data = request.get_json(silent=True) or request.form
    url = (data.get("url") or "").strip()
    context = (data.get("context") or "").strip()
    mode = (data.get("mode") or "full").strip()
    if mode not in ("full", "uiux"):
        mode = "full"
    if not url:
        return jsonify({"error": "A URL is required."}), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"queue": queue.Queue(), "result": None, "error": None,
                    "url": url, "context": context, "mode": mode}
    thread = threading.Thread(
        target=_run_job, args=(job_id, url, context, mode), daemon=True)
    thread.start()
    return jsonify({"job_id": job_id})


@app.route("/stream/<job_id>")
def stream(job_id):
    job = JOBS.get(job_id)
    if not job:
        abort(404)
    q = job["queue"]

    @stream_with_context
    def generate():
        # Initial comment keeps some proxies from buffering the SSE connection.
        yield ": stream open\n\n"
        while True:
            try:
                event = q.get(timeout=120)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(generate(), headers=headers)


@app.route("/report/<job_id>")
def report(job_id):
    job = JOBS.get(job_id)
    if not job:
        abort(404)
    if job.get("error") and not job.get("result"):
        return render_template("report.html", error=GENERIC_FAIL_MSG,
                               url=job.get("url", ""))
    result = job.get("result")
    if not result:
        # Job still running — bounce the user back so they keep watching progress.
        return render_template("report.html", pending=True,
                               url=job.get("url", ""))
    return render_template("report.html", r=result, url=result.get("url", ""))


if __name__ == "__main__":
    # threaded=True so the SSE stream and the worker thread coexist with requests.
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
