"""Orchestrate VCF parse -> VEP -> filter -> match -> PDF."""
import json
import sys
from pathlib import Path
from typing import Any

from filter_and_match import (
    flatten_and_filter_vep,
    load_knowledge_base,
    load_driver_genes,
    match_to_knowledge_base,
)
from openai_drug_recommendations import fetch_drug_recommendations_for_variants
from pdf_report import build_pdf
from vep_client import fetch_vep_all_parallel, variants_to_payload_strings
from vcf_parser import parse_vcf

from config import PDAC_FALLBACK_DRUGS, REPORTS_DIR, UPLOADS_DIR
from logger import _log as log_message

# Max variants to include in the report
REPORT_TOP_N = 3


def _log(msg: str, job_id: str = "") -> None:
    """Write step message to console and file."""
    component = f"pipeline {job_id}" if job_id else "pipeline"
    log_message(msg, component)


def run_pipeline(
    vcf_path: str | Path,
    job_id: str,
    sample_id: str | None = None,
    progress_callback: None | Any = None,
) -> dict[str, Any]:
    """
    Run full pipeline; save PDF to reports/<job_id>.pdf.
    progress_callback(status: str) optional for UI updates.
    Returns dict with success, message, report_path, variant_count, error.
    """
    def progress(msg: str) -> None:
        _log(msg, job_id)
        if progress_callback:
            progress_callback(msg)

    result: dict[str, Any] = {
        "success": False,
        "message": "",
        "report_path": None,
        "variant_count": 0,
        "error": None,
    }
    try:
        progress("Step 1/5: Parsing VCF...")
        variants, sid = parse_vcf(vcf_path)
        sample_id = sample_id or sid
        _log(f"Parsed {len(variants)} variants, sample_id={sample_id or 'N/A'}", job_id)
        if not variants:
            result["message"] = "No variants found in VCF."
            result["variant_count"] = 0
            _log("No variants in VCF; stopping.", job_id)
            return result

        progress("Step 2/5: Annotating with Ensembl VEP (this may take 1–2 min)...")
        try:
            # Save full variant array (as sent in POST) to payload file for parallel curl
            vep_work_dir = Path(REPORTS_DIR).parent / "vep_work"
            vep_work_dir.mkdir(parents=True, exist_ok=True)
            payload_path = vep_work_dir / "payload.json"
            variant_strings = variants_to_payload_strings(variants)
            with open(payload_path, "w", encoding="utf-8") as f:
                json.dump(variant_strings, f, indent=0)
            _log(f"VEP payload saved to {payload_path} ({len(variant_strings)} variants; use for parallel curl).", job_id)

            vep_results = fetch_vep_all_parallel(variants)
            _log(f"VEP returned {len(vep_results)} annotation(s) for {len(variants)} variant(s).", job_id)
            # Dump VEP REST response to file for inspection
            vep_dump_dir = Path(REPORTS_DIR).parent / "vep_work"
            vep_dump_dir.mkdir(parents=True, exist_ok=True)
            vep_dump_path = vep_dump_dir / f"{job_id}_vep_rest_response.json"
            with open(vep_dump_path, "w", encoding="utf-8") as f:
                json.dump(vep_results, f, indent=2)
            _log(f"VEP REST response saved to {vep_dump_path}", job_id)
        except Exception as e:
            _log(f"VEP annotation failed: {e}", job_id)
            result["error"] = str(e)
            result["message"] = f"VEP failed: {e}"
            return result

        progress("Step 3/5: Filtering variants (AF < 0.01, canonical, non-synonymous)...")
        try:
            filtered = flatten_and_filter_vep(vep_results)
            _log(f"After filtering: {len(filtered)} variant(s).", job_id)
        except Exception as e:
            _log(f"Filter failed: {e}", job_id)
            result["error"] = str(e)
            result["message"] = f"Filter failed: {e}"
            return result
        if not filtered:
            result["message"] = "No variants remained after filtering (AF < 0.01, canonical, non-synonymous)."
            result["variant_count"] = 0
            _log("No variants passed filter; stopping.", job_id)
            return result

        progress("Step 4/5: Matching to knowledge base...")
        try:
            matched = match_to_knowledge_base(filtered)
            _log(f"After matching: {len(matched)} variant(s) (including those without drugs).", job_id)
        except Exception as e:
            _log(f"Knowledge base match failed: {e}", job_id)
            result["error"] = str(e)
            result["message"] = f"Match failed: {e}"
            return result

        progress("Step 4b/5: AI drug recommendations for pancreatic cancer...")
        try:
            ai_map = fetch_drug_recommendations_for_variants(
                matched,
                job_id=job_id,
                log_callback=lambda msg: _log(msg, job_id),
            )
            for m in matched:
                key = (
                    (m.get("gene_symbol") or "").strip(),
                    (m.get("hgvs_coding") or "").strip(),
                    (m.get("hgvs_protein") or "").strip(),
                )
                ai = ai_map.get(key)
                if ai:
                    m["ai_drug_recommendations"] = ai.get("drugs") or ""
                    m["ai_rationale"] = ai.get("rationale") or ""
                else:
                    m["ai_drug_recommendations"] = ""
                    m["ai_rationale"] = ""
        except Exception as e:
            _log(f"AI drug step failed (continuing with KB only): {e}", job_id)
            for m in matched:
                m["ai_drug_recommendations"] = ""
                m["ai_rationale"] = ""

        # Build list of variants that have KB or AI drug recommendations
        for m in matched:
            kb_drugs = str(m.get("associated_drugs", "")).strip().upper()
            has_kb = kb_drugs and kb_drugs != "NONE"
            has_ai = bool((m.get("ai_drug_recommendations") or "").strip())
            if has_kb or has_ai:
                if not has_kb and has_ai:
                    m["associated_drugs"] = (m.get("ai_drug_recommendations") or "").strip()
                    m["clinical_notes"] = (m.get("clinical_notes") or "").strip()
                    if m.get("ai_rationale"):
                        m["clinical_notes"] = (m["clinical_notes"] + " [AI: " + m["ai_rationale"] + "]").strip()
                    m["drug_source"] = "openai"
                else:
                    m["drug_source"] = "knowledge_base"
            else:
                # Fallback: assign PDAC drug suggestion by gene so we always have something to report
                gene = (m.get("gene_symbol") or "").strip().upper()
                m["associated_drugs"] = PDAC_FALLBACK_DRUGS.get(gene, "Consider clinical trial or molecular tumor board for PDAC.")
                m["cancer_type"] = m.get("cancer_type") or "PDAC"
                m["drug_source"] = "fallback"

        # Pick top REPORT_TOP_N variants: prefer with KB/AI drugs, then driver genes, then HIGH/MODERATE impact
        def _sort_key(m: dict) -> tuple:
            has_drug = (m.get("drug_source") or "") in ("knowledge_base", "openai")
            is_driver = m.get("is_driver", False)
            impact = (m.get("impact") or "").upper()
            impact_order = ("HIGH", "MODERATE", "LOW", "MODIFIER")
            imp = next((i for i, x in enumerate(impact_order) if x == impact), 99)
            return (not has_drug, not is_driver, imp)

        matched_sorted = sorted(matched, key=_sort_key)
        seen = set()
        report_variants = []
        for m in matched_sorted:
            if len(report_variants) >= REPORT_TOP_N:
                break
            key = (m.get("gene_symbol"), m.get("hgvs_coding"), m.get("hgvs_protein"))
            if key not in seen:
                seen.add(key)
                report_variants.append(m)
        _log(f"Report will include {len(report_variants)} variant(s) (top {REPORT_TOP_N} for PDAC).", job_id)

        progress("Step 5/5: Generating PDF report...")
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            report_path = REPORTS_DIR / f"{job_id}.pdf"
            filters_applied = "Population AF < 0.01, canonical transcript, non-synonymous"
            build_pdf(
                report_variants,
                report_path,
                title="Pancreatic Cancer (PDAC) – Top Variants & Drug Recommendations",
                sample_id=sample_id,
                filters_applied=filters_applied,
            )
            _log(f"PDF written to {report_path}", job_id)
        except Exception as e:
            _log(f"PDF generation failed: {e}", job_id)
            result["error"] = str(e)
            result["message"] = f"PDF failed: {e}"
            return result

        result["success"] = True
        result["message"] = "Report generated."
        result["report_path"] = str(report_path)
        result["variant_count"] = len(report_variants)
        _log("Pipeline completed successfully.", job_id)
    except FileNotFoundError as e:
        _log(f"FileNotFoundError: {e}", job_id)
        result["error"] = str(e)
        result["message"] = "VCF file not found."
    except Exception as e:
        _log(f"Unexpected error: {e}", job_id)
        result["error"] = str(e)
        result["message"] = getattr(e, "message", str(e))
    return result
