"""Filter VEP results and match to knowledge base (CSV/TSV)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

from config import (
    DEBUG_LOG_PATH,
    DRIVER_GENES_TSV,
    KNOWLEDGE_BASE_CSV,
    MAX_POPULATION_AF,
    MISSING_AF_POLICY,
)
from logger import _log as log_message


def _log(msg: str) -> None:
    """Console and file log for filtering/matching."""
    log_message(msg, "filter_and_match")


def _debug_log(msg: str, data: dict | None = None, hypothesis_id: str | None = None) -> None:
    # #region agent log
    try:
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"id": f"log_fm_{hash(msg) % 10**6}", "timestamp": int(time.time() * 1000), "location": "filter_and_match", "message": msg, "data": data or {}}
        if hypothesis_id:
            payload["hypothesisId"] = hypothesis_id
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass
    # #endregion


def _get_af(vep_item: dict[str, Any]) -> float | None:
    """Extract population AF from VEP response (gnomad or similar)."""
    # Top-level (colocated_variants sometimes)
    for key in ("gnomad_af", "gnomad_genomes_af", "gnomad_exomes_af", "minor_allele_freq"):
        v = vep_item.get(key)
        if v is not None and isinstance(v, (int, float)):
            return float(v)
    # transcript_consequences
    for tc in vep_item.get("transcript_consequences") or []:
        for key in ("gnomad_af", "gnomad_genomes_af", "gnomad_exomes_af"):
            v = tc.get(key)
            if v is not None and isinstance(v, (int, float)):
                return float(v)
    return None


def _pick_transcript(vep_item: dict[str, Any]) -> dict[str, Any] | None:
    """Pick one transcript per variant: prefer canonical, then first with gene/HGVS."""
    tcs = vep_item.get("transcript_consequences") or []
    canon = [t for t in tcs if t.get("canonical") == 1]
    pool = canon if canon else tcs
    # Prefer one with gene symbol and HGVS
    for t in pool:
        if t.get("gene_symbol") or t.get("symbol") or t.get("hgvs_coding") or t.get("hgvs_protein"):
            return t
    return pool[0] if pool else None


def _is_synonymous(tc: dict[str, Any]) -> bool:
    terms = tc.get("consequence_terms") or []
    return "synonymous_variant" in terms or (len(terms) == 1 and terms[0] == "synonymous_variant")


def _normalize_hgvs(h: str | None) -> str:
    """Strip transcript prefix for matching (e.g. ENST0000123.4:c.35G>A -> c.35G>A)."""
    if not h or not isinstance(h, str):
        return ""
    h = h.strip()
    if ":" in h:
        return h.split(":", 1)[1].strip()
    return h


def flatten_and_filter_vep(
    vep_results: list[dict[str, Any]],
    max_af: float = MAX_POPULATION_AF,
    missing_af_policy: str = MISSING_AF_POLICY,
) -> list[dict[str, Any]]:
    """
    Flatten VEP results to one row per variant; keep canonical, AF < max_af, non-synonymous.
    Each row: gene_symbol, hgvs_coding, hgvs_protein, consequence_terms, impact, af, etc.
    """
    _log(f"Filtering {len(vep_results)} VEP result(s): max_af={max_af}, missing_af_policy={missing_af_policy}")
    rows: list[dict[str, Any]] = []
    stats = {
        "no_transcript": 0,
        "synonymous": 0,
        "not_canonical": 0,
        "af_too_high": 0,
        "missing_af_excluded": 0,
        "no_gene": 0,
        "passed": 0,
    }
    for vep_item in vep_results:
        tc = _pick_transcript(vep_item)
        if not tc:
            stats["no_transcript"] += 1
            continue
        if _is_synonymous(tc):
            stats["synonymous"] += 1
            continue
        if tc.get("canonical") != 1:
            # We already prefer canonical in _pick_transcript; if we only want canonical, skip others
            if not any(t.get("canonical") == 1 for t in (vep_item.get("transcript_consequences") or [])):
                stats["not_canonical"] += 1
                continue
        af = _get_af(vep_item)
        if af is not None and af >= max_af:
            stats["af_too_high"] += 1
            continue
        if af is None and missing_af_policy == "exclude":
            stats["missing_af_excluded"] += 1
            continue
        gene = tc.get("gene_symbol") or tc.get("symbol") or ""
        if not gene:
            stats["no_gene"] += 1
            continue
        # VEP may return hgvs_coding/hgvs_protein or HGVSc/HGVSp
        hgvs_c = tc.get("hgvs_coding") or tc.get("HGVSc") or ""
        hgvs_p = tc.get("hgvs_protein") or tc.get("HGVSp") or ""
        rows.append({
            "gene_symbol": gene,
            "hgvs_coding": hgvs_c,
            "hgvs_protein": hgvs_p,
            "consequence_terms": tc.get("consequence_terms") or [],
            "impact": tc.get("impact") or "",
            "af": af,
            "chromosome": vep_item.get("seq_region_name"),
            "start": vep_item.get("start"),
            "ref": vep_item.get("allele_string", "").split("/")[0] if vep_item.get("allele_string") else "",
            "alt": vep_item.get("allele_string", "").split("/")[-1] if vep_item.get("allele_string") else "",
        })
        stats["passed"] += 1
    _log(f"Filter results: {stats['passed']} passed, {stats['synonymous']} synonymous, {stats['af_too_high']} AF>={max_af}, {stats['no_transcript']} no transcript, {stats['not_canonical']} not canonical, {stats['no_gene']} no gene, {stats['missing_af_excluded']} missing AF excluded")
    return rows


def load_knowledge_base() -> pd.DataFrame:
    """Load PDAC HGVS knowledge base CSV."""
    path = Path(KNOWLEDGE_BASE_CSV)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8")
    df["HGVSc_norm"] = df.get("HGVSc", pd.Series(dtype=object)).map(lambda x: _normalize_hgvs(str(x) if pd.notna(x) else ""))
    df["HGVSp_norm"] = df.get("HGVSp", pd.Series(dtype=object)).map(lambda x: _normalize_hgvs(str(x) if pd.notna(x) else ""))
    return df


def load_driver_genes() -> set[str]:
    """Load PAAD driver gene symbols from IntOGen TSV."""
    path = Path(DRIVER_GENES_TSV)
    if not path.exists():
        return set()
    df = pd.read_csv(path, sep="\t", encoding="utf-8")
    col = "Symbol" if "Symbol" in df.columns else df.columns[0]
    return set(df[col].astype(str).str.strip().str.upper())


def match_to_knowledge_base(
    filtered_rows: list[dict[str, Any]],
    kb: pd.DataFrame | None = None,
    driver_genes: set[str] | None = None,
) -> list[dict[str, Any]]:
    """
    For each filtered variant, attach drug/tier/clinical notes from knowledge base.
    Match by Gene (symbol) and HGVSc or HGVSp (normalized). Add is_driver from IntOGen.
    """
    if kb is None:
        kb = load_knowledge_base()
    if driver_genes is None:
        driver_genes = load_driver_genes()

    _log(f"Matching {len(filtered_rows)} filtered variant(s) to knowledge base...")
    sample = [{"gene": (r.get("gene_symbol") or "").strip(), "hgvs_c": _normalize_hgvs(r.get("hgvs_coding") or ""), "hgvs_p": _normalize_hgvs(r.get("hgvs_protein") or "")} for r in filtered_rows[:5]]
    _debug_log("match_to_kb entry", {"n_rows": len(filtered_rows), "sample_rows": sample}, "H1")

    out: list[dict[str, Any]] = []
    fallback_skipped = []
    fallback_used = []
    exact_matches = 0
    gene_only_matches = 0
    no_matches = 0
    for row in filtered_rows:
        gene = (row.get("gene_symbol") or "").strip().upper()
        hgvs_c = _normalize_hgvs(row.get("hgvs_coding") or "")
        hgvs_p = _normalize_hgvs(row.get("hgvs_protein") or "")

        match = kb[
            (kb["Gene"].astype(str).str.strip().str.upper() == gene)
            & (
                (kb["HGVSc_norm"].astype(str).str.strip() == hgvs_c)
                | (kb["HGVSp_norm"].astype(str).str.strip() == hgvs_p)
            )
        ]
        if not match.empty:
            exact_matches += 1
        elif match.empty and (hgvs_c or hgvs_p):
            # Fallback: match by gene only (use first KB row for this gene)
            match = kb[kb["Gene"].astype(str).str.strip().str.upper() == gene]
            if not match.empty:
                fallback_used.append(gene)
                gene_only_matches += 1
        elif match.empty and not (hgvs_c or hgvs_p):
            fallback_skipped.append(gene)
        
        if not match.empty:
            m = match.iloc[0]
            row["associated_drugs"] = str(m.get("Associated Drug(s)", "") or "").strip()
            row["asco_tier"] = str(m.get("ASCO Evidence Tier", "") or "").strip()
            row["clinical_notes"] = str(m.get("Clinical Notes", "") or "").strip()
            row["cancer_type"] = str(m.get("Cancer Type", "") or "").strip()
            # Keep KB HGVS for display when VEP doesn't return it
            row["kb_hgvs_coding"] = str(m.get("HGVSc", "") or "").strip()
            row["kb_hgvs_protein"] = str(m.get("HGVSp", "") or "").strip()
        else:
            no_matches += 1
            row["associated_drugs"] = ""
            row["asco_tier"] = ""
            row["clinical_notes"] = "No drug recommendation in knowledge base."
            row["cancer_type"] = ""
            row["kb_hgvs_coding"] = ""
            row["kb_hgvs_protein"] = ""
        row["is_driver"] = gene in driver_genes
        out.append(row)
    matched_count = sum(1 for r in out if (r.get("associated_drugs") or "").strip() and (r.get("associated_drugs") or "").strip().upper() != "NONE")
    _log(f"Match results: {exact_matches} exact matches (gene+HGVS), {gene_only_matches} gene-only matches, {no_matches} no matches, {matched_count} with actual drugs (not 'None')")
    _debug_log("match_to_kb exit", {"matched_with_drugs": matched_count, "fallback_skipped_empty_hgvs": fallback_skipped[:10], "fallback_used": fallback_used[:10]}, "H2")
    return out
