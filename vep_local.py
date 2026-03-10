"""Run local Ensembl VEP and produce tab output. With debug logging."""
import json
import subprocess
import sys
from pathlib import Path

from config import DEBUG_LOG_PATH, VEP_ASSEMBLY, VEP_CMD
from logger import _log as log_message


def _log(msg: str) -> None:
    log_message(msg, "vep_local")


def _debug_log(message: str, data: dict | None = None, hypothesis_id: str | None = None) -> None:
    # #region agent log
    try:
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": f"log_vep_{hash(message) % 10**6}",
            "timestamp": __import__("time").time() * 1000,
            "location": "vep_local",
            "message": message,
            "data": data or {},
        }
        if hypothesis_id:
            payload["hypothesisId"] = hypothesis_id
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass
    # #endregion


def run_vep_local(
    input_vcf: str | Path,
    output_vep: str | Path,
) -> tuple[bool, str]:
    """
    Run: vep -i input.vcf -o output.vep --cache --assembly GRCh38
         --everything --hgvs --symbol --canonical --af --tab
    Wait for completion. If output missing, return (False, error_message).
    Log first 5 data rows to debug.log.
    """
    input_vcf = Path(input_vcf)
    output_vep = Path(output_vep)
    output_vep.parent.mkdir(parents=True, exist_ok=True)

    _log(f"Running local VEP: input={input_vcf} -> output={output_vep}")
    _debug_log("VEP run_vep_local entered", {"input": str(input_vcf), "output": str(output_vep)}, "H1")
    cmd = [
        VEP_CMD,
        "-i", str(input_vcf),
        "-o", str(output_vep),
        "--cache",
        "--assembly", VEP_ASSEMBLY,
        "--everything",
        "--hgvs",
        "--symbol",
        "--canonical",
        "--af",
        "--tab",
    ]
    _debug_log("VEP execution start", {"cmd": cmd}, "H1")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        _log(f"VEP process finished: returncode={proc.returncode}")
        _debug_log(
            "VEP execution finished",
            {"returncode": proc.returncode, "stderr_preview": (proc.stderr or "")[:500]},
            "H1",
        )
        if proc.returncode != 0:
            err = f"VEP exited with code {proc.returncode}: {proc.stderr or 'no stderr'}"
            _log("VEP failed: " + err[:200])
            return False, err
        if not output_vep.exists():
            _log("VEP output file was not created: " + str(output_vep))
            return False, f"VEP output file was not created: {output_vep}"
        # Log first 5 data rows (skip ## and # header)
        lines = output_vep.read_text(encoding="utf-8", errors="replace").splitlines()
        data_rows = [l for l in lines if l.strip() and not l.startswith("#")]
        _log(f"VEP OK: {len(data_rows)} data row(s) in output")
        first_5 = data_rows[:5]
        _debug_log("VEP output first 5 data rows", {"rows": first_5, "total_data_rows": len(data_rows)}, "H2")
        return True, ""
    except FileNotFoundError:
        _log("VEP command not found: " + VEP_CMD)
        _debug_log("VEP command not found", {"cmd": VEP_CMD}, "H1")
        return False, f"VEP command not found: {VEP_CMD}. Install VEP or set VEP_CMD."
    except subprocess.TimeoutExpired:
        _log("VEP timed out (600s)")
        _debug_log("VEP timeout", {}, "H1")
        return False, "VEP timed out (600s)."
    except Exception as e:
        _log("VEP exception: " + str(e))
        _debug_log("VEP exception", {"error": str(e)}, "H1")
        return False, str(e)
