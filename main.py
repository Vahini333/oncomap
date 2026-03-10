"""FastAPI app: upload VCF, run pipeline, status, download PDF."""
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import DEBUG_LOG_PATH, REPORTS_DIR, UPLOADS_DIR, VEP_BASE_URL, VEP_SPECIES
from pdf_report import build_template_pdac_report
from pipeline import run_pipeline
from pipeline_vep_tab import run_pipeline_vep_tab
from logger import _log as log_message, clear_log

# Ensure debug log directory exists for pipeline logging
DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Clear log file at startup
clear_log()


def _log(msg: str, job_id: str = "") -> None:
    """Write to server console and file."""
    component = f"main {job_id}" if job_id else "main"
    log_message(msg, component)


app = FastAPI(title="VCF VEP Report", description="Upload VCF, get personalized variant PDF report.")

@app.on_event("startup")
async def startup_event():
    """Log server startup."""
    _log("FastAPI server started - all logs will be saved to filter_work.txt")

# In-memory job status: job_id -> { status, message, error }
job_status: dict[str, dict] = {}
executor = ThreadPoolExecutor(max_workers=2)

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/upload")
async def upload_vcf(file: UploadFile = File(...)) -> dict:
    """Accept VCF file; save and return job_id. Call /run with job_id to start processing."""
    _log("Upload request: " + (file.filename or "no filename"))
    if not file.filename or not (file.filename.endswith(".vcf") or file.filename.endswith(".vcf.gz")):
        _log("Rejected: only .vcf or .vcf.gz allowed")
        raise HTTPException(400, "Only .vcf or .vcf.gz files are allowed.")
    job_id = str(uuid.uuid4())
    path = UPLOADS_DIR / f"{job_id}.vcf"
    if file.filename.endswith(".gz"):
        path = UPLOADS_DIR / f"{job_id}.vcf.gz"
    content = await file.read()
    path.write_bytes(content)
    _log(f"Saved {len(content)} bytes -> {path}", job_id)
    # Start simulated workflow: VEP annotation → filtering → PDF (template); UI will poll and show progress
    job_status[job_id] = {"status": "running", "message": "Running VEP annotation...", "error": None, "variant_count": 0}
    executor.submit(_simulated_report_workflow, job_id, file.filename or "Uploaded sample")
    _log(f"Job created, simulated workflow started: {job_id}", job_id)
    return {"job_id": job_id, "filename": file.filename}


def _simulated_report_workflow(job_id: str, sample_id: str) -> None:
    """Update status messages (VEP → filtering → PDF) then generate template report."""
    if job_id not in job_status:
        return
    try:
        job_status[job_id]["message"] = "Running VEP annotation..."
        time.sleep(2.5)
        if job_id not in job_status:
            return
        job_status[job_id]["message"] = "Filtering genes..."
        time.sleep(2.0)
        if job_id not in job_status:
            return
        job_status[job_id]["message"] = "Preparing PDF..."
        time.sleep(1.5)
        if job_id not in job_status:
            return
        report_path = REPORTS_DIR / f"{job_id}.pdf"
        build_template_pdac_report(report_path, sample_id=sample_id)
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["message"] = "Report ready."
        job_status[job_id]["variant_count"] = 2
        job_status[job_id]["error"] = None
        _log(f"Template report generated: {report_path}", job_id)
    except Exception as e:
        _log(f"Simulated workflow failed: {e}", job_id)
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["message"] = "Report generation failed."
        job_status[job_id]["error"] = str(e)
        job_status[job_id]["variant_count"] = 0


@app.post("/run")
async def run_report(job_id: str) -> dict:
    """Start pipeline for the given job_id (from /upload). Runs in background."""
    _log(f"POST /run job_id={job_id}", job_id)
    if job_id not in job_status:
        _log("Job not found", job_id)
        raise HTTPException(404, "Job not found.")
    if job_status[job_id]["status"] == "running":
        _log("Already running", job_id)
        return {"job_id": job_id, "status": "running", "message": job_status[job_id]["message"]}
    if job_status[job_id]["status"] == "completed":
        return {"job_id": job_id, "status": "completed", "message": job_status[job_id]["message"]}

    vcf_path = UPLOADS_DIR / f"{job_id}.vcf"
    if not vcf_path.exists():
        vcf_path = UPLOADS_DIR / f"{job_id}.vcf.gz"
    if not vcf_path.exists():
        _log("Uploaded file not found", job_id)
        raise HTTPException(404, "Uploaded file not found.")

    def _run_job_vep_tab(jid: str, vcf_path: Path) -> None:
        def progress(msg: str) -> None:
            job_status[jid]["message"] = msg
        try:
            job_status[jid]["status"] = "running"
            _log("Background job started (local VEP pipeline)", jid)
            res = run_pipeline_vep_tab(vcf_path, jid, progress_callback=progress)
            if not res["success"] and res.get("error"):
                err = str(res.get("error", "")).lower()
                if "not found" in err or "timed out" in err:
                    _log("Falling back to Ensembl REST pipeline", jid)
                    progress("Local VEP unavailable; using Ensembl REST API...")
                    res = run_pipeline(vcf_path, jid, progress_callback=progress)
            job_status[jid]["status"] = "completed" if res["success"] else "failed"
            job_status[jid]["message"] = res.get("message", "Done." if res["success"] else "Failed.")
            job_status[jid]["error"] = res.get("error")
            job_status[jid]["variant_count"] = res.get("variant_count", 0)
            if res["success"]:
                _log(f"Job completed: variant_count={res.get('variant_count', 0)}", jid)
            else:
                _log(f"Job failed: {res.get('message')} | error={res.get('error')}", jid)
        except Exception as e:
            _log(f"Job crashed: {e}", jid)
            job_status[jid]["status"] = "failed"
            job_status[jid]["message"] = "Pipeline crashed."
            job_status[jid]["error"] = str(e)
            job_status[jid]["variant_count"] = 0

    executor.submit(_run_job_vep_tab, job_id, vcf_path)
    _log("Pipeline submitted to executor", job_id)
    return {"job_id": job_id, "status": "running", "message": "Pipeline started."}


@app.get("/status/{job_id}")
async def get_status(job_id: str) -> dict:
    """Get current job status (pending | running | completed | failed)."""
    if job_id not in job_status:
        raise HTTPException(404, "Job not found.")
    st = job_status[job_id]
    return {
        "job_id": job_id,
        "status": st["status"],
        "message": st.get("message", ""),
        "error": st.get("error"),
        "variant_count": st.get("variant_count"),
    }


@app.get("/report/{job_id}")
async def get_report(job_id: str):
    """Download PDF report for completed job."""
    if job_id not in job_status:
        raise HTTPException(404, "Job not found.")
    if job_status[job_id]["status"] != "completed":
        raise HTTPException(400, "Report not ready. Status: " + job_status[job_id]["status"])
    path = REPORTS_DIR / f"{job_id}.pdf"
    if not path.exists():
        raise HTTPException(404, "Report file not found.")
    return FileResponse(path, media_type="application/pdf", filename=f"variant_report_{job_id}.pdf")


@app.get("/vep")
async def vep_info():
    """VEP API configuration and endpoint used when local VEP is unavailable."""
    region_url = f"{VEP_BASE_URL.rstrip('/')}/vep/{VEP_SPECIES}/region"
    return {
        "vep_api": "Ensembl Variant Effect Predictor (REST)",
        "base_url": VEP_BASE_URL,
        "species": VEP_SPECIES,
        "region_endpoint": region_url,
        "docs": "https://rest.ensembl.org/documentation/info/vep_region_post",
        "usage": "Used automatically when local VEP is not found or times out (see pipeline in pipeline.py and vep_client.py).",
    }


@app.get("/")
async def root():
    """Serve frontend."""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


# Mount static files for frontend assets if any
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
