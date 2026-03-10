"""
VEP tab pipeline: filter (AF < 0.01, CANONICAL, IMPACT, non-synonymous),
merge with drug DB, generate PDF only from merged variants with drug match.
With debug logging.
"""
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from config import (
    ASCO_TO_AMP,
    DEBUG_LOG_PATH,
    KNOWLEDGE_BASE_CSV,
    REPORTS_DIR,
)
from pdf_report import build_pdf
from vep_local import run_vep_local
from vep_tab_io import read_vep_tab
from logger import _log as log_message


def _log(msg: str, job_id: str = "") -> None:
    """Write to console and file for step-by-step visibility."""
    component = f"pipeline_vep_tab {job_id}" if job_id else "pipeline_vep_tab"
    log_message(msg, component)


def _debug_log(message: str, data: dict | None = None, hypothesis_id: str | None = None) -> None:
    # #region agent log
    try:
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": f"log_pl_{hash(message) % 10**6}",
            "timestamp": __import__("time").time() * 1000,
            "location": "pipeline_vep_tab",
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


def _normalize_hgvs(s: Any) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return str(s).strip()


def run_pipeline_vep_tab(
    vcf_path: str | Path,
    job_id: str,
    sample_id: str | None = None,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    """
    STEP 1: Run local VEP -> output.vep
    STEP 2: Read tab, validate HGVSc/HGVSp
    STEP 3: Filter (AF < 0.01, CANONICAL == YES, IMPACT in HIGH/MODERATE, not synonymous)
    STEP 4: Merge with drug DB on SYMBOL/Gene and HGVSp
    STEP 5: PDF from merged only; exclude variants with no drug match
    STEP 6: Debug logging throughout
    """
    def progress(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    result = {"success": False, "message": "", "report_path": None, "variant_count": 0, "error": None}
    _log("Pipeline started (local VEP)", job_id)
    _debug_log("Pipeline started", {"job_id": job_id, "vcf_path": str(vcf_path)}, "H0")
    vcf_path = Path(vcf_path)
    work_dir = Path(REPORTS_DIR).parent / "vep_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_vep = work_dir / f"{job_id}.vep.tsv"

    try:
        # STEP 1: VEP execution
        progress("Step 1/5: Running local VEP...")
        _log("Step 1: Running local VEP -> " + str(output_vep), job_id)
        ok, err = run_vep_local(vcf_path, output_vep)
        if not ok:
            _log("Step 1 failed: " + err, job_id)
            result["message"] = err
            result["error"] = err
            _debug_log("VEP execution failed", {"error": err}, "H1")
            return result
        _log("Step 1 OK: VEP output written", job_id)

        # STEP 2: Read and validate columns
        progress("Step 2/5: Reading VEP output...")
        _log("Step 2: Reading VEP tab", job_id)
        df = read_vep_tab(output_vep)
        if df.empty:
            _log("Step 2: VEP produced no variant rows", job_id)
            result["message"] = "VEP produced no variant rows."
            result["error"] = "VEP produced no variant rows."
            _debug_log("VEP empty", {}, "H2")
            return result
        _log(f"Step 2 OK: {len(df)} rows, columns: {list(df.columns)[:10]}", job_id)
        # Save a copy of the VEP output for inspection
        import shutil
        vep_copy = work_dir / f"{job_id}_vep_local_output.tsv"
        shutil.copy(output_vep, vep_copy)
        _log(f"VEP output copied to {vep_copy}", job_id)

        # STEP 3: Filter
        # Normalize column names for filter (VEP tab may use different caps)
        for col in list(df.columns):
            if col.upper() == "CANONICAL":
                df = df.rename(columns={col: "CANONICAL"})
            if col.upper() == "IMPACT":
                df = df.rename(columns={col: "IMPACT"})
            if col == "Consequence" or (col.upper() == "CONSEQUENCE"):
                df = df.rename(columns={col: "Consequence"})
            if col.upper() == "SYMBOL":
                df = df.rename(columns={col: "SYMBOL"})
        if "SYMBOL" not in df.columns and "Gene" in df.columns:
            df = df.rename(columns={"Gene": "SYMBOL"})

        # AF: coerce to numeric; missing -> 0 so (AF < 0.01) keeps them
        af_col = None
        for c in df.columns:
            if c.upper() == "AF":
                af_col = c
                break
        if af_col:
            df["AF"] = pd.to_numeric(df[af_col], errors="coerce").fillna(0)
        else:
            df["AF"] = 0.0
        if "CANONICAL" not in df.columns:
            df["CANONICAL"] = "YES"
        can_col = [c for c in df.columns if c.upper() == "CANONICAL"]
        if can_col:
            df["CANONICAL"] = df[can_col[0]].astype(str).str.strip().str.upper()
        if "IMPACT" not in df.columns:
            df["IMPACT"] = ""
        imp_col = [c for c in df.columns if c.upper() == "IMPACT"]
        if imp_col:
            df["IMPACT"] = df[imp_col[0]].astype(str).str.strip().str.upper()
        if "Consequence" not in df.columns:
            df["Consequence"] = ""
        cons_col = [c for c in df.columns if "onsequence" in c or c == "Consequence"]
        if cons_col:
            df["Consequence"] = df[cons_col[0]].astype(str)

        total_before = len(df)
        can_ok = df["CANONICAL"].astype(str).str.strip().str.upper().isin(["YES", "1"])
        filtered = df[
            (df["AF"] < 0.01)
            & can_ok
            & (df["IMPACT"].astype(str).str.strip().str.upper().isin(["HIGH", "MODERATE"]))
            & (~df["Consequence"].astype(str).str.contains("synonymous_variant", na=False))
        ].copy()
        total_after = len(filtered)
        _log(f"Step 3: Filter: {total_before} -> {total_after} variants", job_id)
        _debug_log("Filter counts", {"total_before": total_before, "total_after": total_after}, "H3")
        progress(f"Step 3/5: Filtering variants... ({total_after} passed)")

        if filtered.empty:
            result["message"] = f"No variants passed filter (before={total_before}, after=0)."
            result["error"] = result["message"]
            _log("Step 3: No variants passed filter", job_id)
            return result

        # STEP 4: Load drug DB and merge
        progress("Step 4/5: Matching to drug database...")
        _log("Step 4: Loading drug DB and merging", job_id)
        drug_path = Path(KNOWLEDGE_BASE_CSV)
        if not drug_path.exists():
            result["message"] = f"Drug database not found: {drug_path}"
            result["error"] = result["message"]
            _log("Step 4 failed: drug DB not found", job_id)
            return result
        drug_db = pd.read_csv(drug_path, encoding="utf-8")
        drug_db = drug_db.rename(columns=lambda x: x.strip())
        # Normalize for merge: Gene, HGVSp (and optionally HGVSc)
        for c in ["Gene", "HGVSc", "HGVSp"]:
            if c in drug_db.columns:
                drug_db[c] = drug_db[c].astype(str).apply(_normalize_hgvs)
        filtered["HGVSp_norm"] = filtered["HGVSp"].astype(str).apply(_normalize_hgvs)
        filtered["SYMBOL_norm"] = filtered["SYMBOL"].astype(str).str.strip().str.upper()
        drug_db["Gene_norm"] = drug_db["Gene"].astype(str).str.strip().str.upper()

        drug_db["HGVSp_norm"] = drug_db["HGVSp"].astype(str).apply(_normalize_hgvs)
        merged = pd.merge(
            filtered,
            drug_db,
            left_on=["SYMBOL_norm", "HGVSp_norm"],
            right_on=["Gene_norm", "HGVSp_norm"],
            how="left",
            suffixes=("", "_drug"),
        )
        drug_col = "Associated Drug(s)" if "Associated Drug(s)" in merged.columns else (([c for c in merged.columns if "Drug" in str(c)] or [None])[0])
        if drug_col is None:
            result["message"] = "Drug database has no 'Associated Drug(s)' column."
            result["error"] = result["message"]
            _log("Step 4 failed: no drug column", job_id)
            return result
        with_drug = merged[drug_col].notna() & (merged[drug_col].astype(str).str.strip().str.upper() != "NONE")
        merged_with_drug = merged[with_drug].copy()
        _log(f"Step 4: merged {len(merged)}, with_drug {len(merged_with_drug)}", job_id)
        _debug_log("Merge counts", {"merged_total": len(merged), "with_drug_match": len(merged_with_drug)}, "H4")

        if merged_with_drug.empty:
            _log("Step 4: No variants had drug match", job_id)
            _debug_log("No drug matches", {"sample_HGVSp": filtered["HGVSp"].head().tolist(), "drug_HGVSp": drug_db["HGVSp"].head().tolist()}, "H4")
            result["message"] = "No variants had a drug match. Check HGVSp format."
            result["error"] = result["message"]
            return result

        # STEP 5: Build rows for PDF (only merged with drug)
        rows = []
        for _, r in merged_with_drug.iterrows():
            tier = str(r.get("ASCO Evidence Tier", "") or "").strip()
            amp = ASCO_TO_AMP.get(tier, "")
            rows.append({
                "gene_symbol": str(r.get("SYMBOL", r.get("Gene", "")) or "").strip(),
                "hgvs_coding": str(r.get("HGVSc", "") or "").strip(),
                "hgvs_protein": str(r.get("HGVSp", "") or "").strip(),
                "consequence_terms": [x.strip() for x in str(r.get("Consequence", "") or "").split(",") if x.strip()],
                "impact": str(r.get("IMPACT", "") or "").strip(),
                "af": r.get("AF"),
                "clinical_notes": str(r.get("Clinical Notes", "") or "").strip(),
                "associated_drugs": str(r.get(drug_col, "") or "").strip(),
                "asco_tier": tier,
                "cancer_type": str(r.get("Cancer Type", "") or "").strip(),
                "is_driver": False,
                "kb_hgvs_coding": str(r.get("HGVSc", "") or "").strip(),
                "kb_hgvs_protein": str(r.get("HGVSp", "") or "").strip(),
                "amp_level": amp,
            })
        progress("Step 5/5: Generating PDF report...")
        _log("Step 5: Building PDF", job_id)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / f"{job_id}.pdf"
        build_pdf(
            rows,
            report_path,
            title="Variant Report – Personalized Drug Recommendations",
            sample_id=sample_id,
            filters_applied="AF < 0.01, canonical, HIGH/MODERATE impact, non-synonymous; drug-matched only",
        )
        result["success"] = True
        result["message"] = "Report generated."
        result["report_path"] = str(report_path)
        result["variant_count"] = len(rows)
        _log(f"Step 5 OK: PDF written, {len(rows)} variants", job_id)
        _debug_log("PDF generated", {"variant_count": len(rows), "report_path": str(report_path)}, "H5")
    except Exception as e:
        _log("Pipeline exception: " + str(e), job_id)
        result["error"] = str(e)
        result["message"] = str(e)
        _debug_log("Pipeline exception", {"error": str(e)}, "H5")
    return result
