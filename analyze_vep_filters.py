"""
Analyze VEP response with detailed filter-by-filter statistics.
Shows how each filter (AF, canonical, impact, consequence, driver genes) affects the data.
"""
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from config import MAX_POPULATION_AF, DRIVER_GENES_TSV, KNOWLEDGE_BASE_CSV
from filter_and_match import load_driver_genes, load_knowledge_base
from logger import _log as log_message, clear_log


def log(msg: str) -> None:
    """Log to console and filter_work.txt"""
    log_message(msg, "analyze_filters")


def get_af(vep_item: dict[str, Any]) -> float | None:
    """Extract population allele frequency."""
    for key in ("gnomad_af", "gnomad_genomes_af", "gnomad_exomes_af", "minor_allele_freq"):
        v = vep_item.get(key)
        if v is not None and isinstance(v, (int, float)):
            return float(v)
    for tc in vep_item.get("transcript_consequences") or []:
        for key in ("gnomad_af", "gnomad_genomes_af", "gnomad_exomes_af"):
            v = tc.get(key)
            if v is not None and isinstance(v, (int, float)):
                return float(v)
    return None


def analyze_vep_file(vep_json_path: str | Path):
    """
    Load VEP response and apply filters step-by-step with detailed logging.
    
    Filters applied:
    1. Population frequency (AF < 0.01 = rare variants)
    2. Canonical transcript
    3. Impact severity (HIGH or MODERATE)
    4. Functional consequence (non-synonymous)
    5. Has gene symbol
    6. Driver gene annotation
    7. Drug match from knowledge base
    """
    vep_json_path = Path(vep_json_path)
    
    log("=" * 80)
    log(f"ANALYZING VEP RESPONSE: {vep_json_path.name}")
    log("=" * 80)
    
    # Load data
    log("Loading VEP response JSON...")
    with open(vep_json_path, "r", encoding="utf-8") as f:
        vep_results = json.load(f)
    
    log(f"Total VEP results (variants): {len(vep_results)}")
    log("")
    
    # Load reference data
    log("Loading driver genes and knowledge base...")
    driver_genes = load_driver_genes()
    kb = load_knowledge_base()
    log(f"Driver genes loaded: {len(driver_genes)} genes")
    log(f"Knowledge base loaded: {len(kb)} entries")
    log("")
    
    # Track variants through each filter
    variants = []
    for idx, vep_item in enumerate(vep_results):
        tcs = vep_item.get("transcript_consequences", [])
        if not tcs:
            continue
        
        # Process each transcript
        for tc in tcs:
            variants.append({
                "variant_idx": idx,
                "chr": vep_item.get("seq_region_name"),
                "pos": vep_item.get("start"),
                "ref_alt": vep_item.get("allele_string", ""),
                "transcript_id": tc.get("transcript_id", ""),
                "gene": tc.get("gene_symbol") or tc.get("symbol") or "",
                "canonical": tc.get("canonical") == 1,
                "impact": tc.get("impact", ""),
                "consequence": tc.get("consequence_terms", []),
                "hgvs_c": tc.get("hgvs_coding") or tc.get("HGVSc") or "",
                "hgvs_p": tc.get("hgvs_protein") or tc.get("HGVSp") or "",
                "af": get_af(vep_item),
            })
    
    df = pd.DataFrame(variants)
    log(f"Total transcript consequences: {len(df)}")
    log("")
    
    # Filter 1: Population frequency (rare variants)
    log("-" * 80)
    log("FILTER 1: POPULATION FREQUENCY (Rare Variants)")
    log("-" * 80)
    log(f"Threshold: AF < {MAX_POPULATION_AF} (rare variants)")
    
    before = len(df)
    df["has_af"] = df["af"].notna()
    df["af_pass"] = (df["af"].isna()) | (df["af"] < MAX_POPULATION_AF)
    
    af_stats = df.groupby("af_pass").size()
    missing_af = df[df["af"].isna()].shape[0]
    high_af = df[(df["af"].notna()) & (df["af"] >= MAX_POPULATION_AF)].shape[0]
    low_af = df[(df["af"].notna()) & (df["af"] < MAX_POPULATION_AF)].shape[0]
    
    log(f"Missing AF (kept): {missing_af}")
    log(f"AF < {MAX_POPULATION_AF} (PASS): {low_af}")
    log(f"AF >= {MAX_POPULATION_AF} (FAIL - too common): {high_af}")
    
    if high_af > 0:
        common_genes = df[(df["af"].notna()) & (df["af"] >= MAX_POPULATION_AF)]["gene"].value_counts().head(5)
        log("Top 5 genes with common variants (AF >= 0.01):")
        for gene, count in common_genes.items():
            log(f"  {gene}: {count} transcript(s)")
    
    df = df[df["af_pass"]].copy()
    log(f"After frequency filter: {len(df)} / {before} ({100*len(df)/before:.1f}%)")
    log("")
    
    # Filter 2: Canonical transcript
    log("-" * 80)
    log("FILTER 2: CANONICAL TRANSCRIPT")
    log("-" * 80)
    
    before = len(df)
    canonical_count = df["canonical"].sum()
    non_canonical_count = (~df["canonical"]).sum()
    
    log(f"Canonical (PASS): {canonical_count}")
    log(f"Non-canonical (FAIL): {non_canonical_count}")
    
    df = df[df["canonical"]].copy()
    log(f"After canonical filter: {len(df)} / {before} ({100*len(df)/before:.1f}%)")
    log("")
    
    # Filter 3: Impact severity
    log("-" * 80)
    log("FILTER 3: IMPACT SEVERITY")
    log("-" * 80)
    log("Accepted: HIGH, MODERATE")
    log("Rejected: MODIFIER, LOW")
    
    before = len(df)
    impact_counts = df["impact"].value_counts()
    log("Impact distribution:")
    for impact, count in impact_counts.items():
        status = "PASS" if impact in ["HIGH", "MODERATE"] else "FAIL"
        log(f"  {impact}: {count} ({status})")
    
    df["impact_pass"] = df["impact"].isin(["HIGH", "MODERATE"])
    df = df[df["impact_pass"]].copy()
    log(f"After impact filter: {len(df)} / {before} ({100*len(df)/before:.1f}%)")
    log("")
    
    # Filter 4: Functional consequence (non-synonymous)
    log("-" * 80)
    log("FILTER 4: FUNCTIONAL CONSEQUENCE (Non-Synonymous)")
    log("-" * 80)
    
    before = len(df)
    df["consequence_str"] = df["consequence"].apply(lambda x: ",".join(x) if isinstance(x, list) else str(x))
    df["is_synonymous"] = df["consequence_str"].str.contains("synonymous_variant", na=False)
    
    synonymous_count = df["is_synonymous"].sum()
    non_synonymous_count = (~df["is_synonymous"]).sum()
    
    log(f"Synonymous variants (FAIL): {synonymous_count}")
    log(f"Non-synonymous variants (PASS): {non_synonymous_count}")
    
    if non_synonymous_count > 0:
        consequence_types = df[~df["is_synonymous"]]["consequence_str"].value_counts().head(10)
        log("Top 10 consequence types (non-synonymous):")
        for cons, count in consequence_types.items():
            log(f"  {cons}: {count}")
    
    df = df[~df["is_synonymous"]].copy()
    log(f"After consequence filter: {len(df)} / {before} ({100*len(df)/before:.1f}%)")
    log("")
    
    # Filter 5: Has gene symbol
    log("-" * 80)
    log("FILTER 5: HAS GENE SYMBOL")
    log("-" * 80)
    
    before = len(df)
    df["has_gene"] = df["gene"].notna() & (df["gene"] != "")
    
    with_gene = df["has_gene"].sum()
    without_gene = (~df["has_gene"]).sum()
    
    log(f"With gene symbol (PASS): {with_gene}")
    log(f"Without gene symbol (FAIL): {without_gene}")
    
    df = df[df["has_gene"]].copy()
    log(f"After gene filter: {len(df)} / {before} ({100*len(df)/before:.1f}%)")
    log("")
    
    # Analysis 6: Driver genes
    log("-" * 80)
    log("ANALYSIS 6: DRIVER GENE ANNOTATION")
    log("-" * 80)
    
    df["gene_upper"] = df["gene"].str.strip().str.upper()
    df["is_driver"] = df["gene_upper"].isin(driver_genes)
    
    driver_count = df["is_driver"].sum()
    non_driver_count = (~df["is_driver"]).sum()
    
    log(f"Driver genes (from IntOGen PAAD): {driver_count}")
    log(f"Non-driver genes: {non_driver_count}")
    
    if driver_count > 0:
        driver_list = df[df["is_driver"]]["gene"].value_counts()
        log(f"Driver genes found ({len(driver_list)} unique):")
        for gene, count in driver_list.items():
            log(f"  {gene}: {count} variant(s)")
    log("")
    
    # Analysis 7: Drug match
    log("-" * 80)
    log("ANALYSIS 7: KNOWLEDGE BASE DRUG MATCH")
    log("-" * 80)
    
    # Match to knowledge base
    kb["Gene_upper"] = kb["Gene"].str.strip().str.upper()
    
    def normalize_hgvs(h):
        if not h or not isinstance(h, str):
            return ""
        h = h.strip()
        if ":" in h:
            return h.split(":", 1)[1].strip()
        return h
    
    df["hgvs_c_norm"] = df["hgvs_c"].apply(normalize_hgvs)
    df["hgvs_p_norm"] = df["hgvs_p"].apply(normalize_hgvs)
    kb["HGVSc_norm"] = kb.get("HGVSc", pd.Series(dtype=object)).apply(lambda x: normalize_hgvs(str(x) if pd.notna(x) else ""))
    kb["HGVSp_norm"] = kb.get("HGVSp", pd.Series(dtype=object)).apply(lambda x: normalize_hgvs(str(x) if pd.notna(x) else ""))
    
    # Merge
    merged = pd.merge(
        df,
        kb[["Gene_upper", "HGVSc_norm", "HGVSp_norm", "Associated Drug(s)", "ASCO Evidence Tier", "Cancer Type"]],
        left_on=["gene_upper", "hgvs_p_norm"],
        right_on=["Gene_upper", "HGVSp_norm"],
        how="left"
    )
    
    merged["has_drug_match"] = merged["Associated Drug(s)"].notna()
    merged["has_real_drug"] = (
        merged["Associated Drug(s)"].notna() &
        (merged["Associated Drug(s)"].astype(str).str.strip().str.upper() != "NONE") &
        (merged["Associated Drug(s)"].astype(str).str.strip() != "")
    )
    
    with_match = merged["has_drug_match"].sum()
    with_real_drug = merged["has_real_drug"].sum()
    no_match = (~merged["has_drug_match"]).sum()
    
    log(f"Matched to knowledge base: {with_match}")
    log(f"With actual drug recommendations (not 'None'): {with_real_drug}")
    log(f"No match in knowledge base: {no_match}")
    
    if with_real_drug > 0:
        drug_variants = merged[merged["has_real_drug"]][["gene", "hgvs_p_norm", "Associated Drug(s)", "ASCO Evidence Tier"]].drop_duplicates()
        log(f"\nVariants with drug recommendations ({len(drug_variants)}):")
        for _, row in drug_variants.iterrows():
            log(f"  {row['gene']} {row['hgvs_p_norm']}: {row['Associated Drug(s)']} (Tier: {row['ASCO Evidence Tier']})")
    
    log("")
    
    # Final summary
    log("=" * 80)
    log("FINAL SUMMARY")
    log("=" * 80)
    log(f"Started with: {len(vep_results)} variants from VEP")
    log(f"After all filters: {len(df)} variants")
    log(f"With drug recommendations: {with_real_drug} variants")
    log(f"Reduction: {100*(1 - len(df)/len(vep_results)):.1f}% filtered out")
    log("")
    
    # Save filtered results
    output_csv = vep_json_path.parent / f"{vep_json_path.stem}_filtered.csv"
    df.to_csv(output_csv, index=False)
    log(f"Filtered results saved to: {output_csv}")
    
    output_with_drugs = vep_json_path.parent / f"{vep_json_path.stem}_with_drugs.csv"
    merged[merged["has_real_drug"]].to_csv(output_with_drugs, index=False)
    log(f"Variants with drugs saved to: {output_with_drugs}")
    
    log("=" * 80)
    log("Analysis complete. All logs saved to filter_work.txt")
    log("=" * 80)


if __name__ == "__main__":
    # Clear log file
    clear_log()
    
    if len(sys.argv) > 1:
        vep_file = sys.argv[1]
    else:
        # Find the most recent VEP response file
        vep_work = Path(__file__).parent / "vep_work"
        vep_files = list(vep_work.glob("*_vep_rest_response.json"))
        if not vep_files:
            log("ERROR: No VEP response files found in vep_work/")
            log("Usage: python analyze_vep_filters.py [path/to/vep_response.json]")
            sys.exit(1)
        vep_file = max(vep_files, key=lambda p: p.stat().st_mtime)
        log(f"Using most recent VEP file: {vep_file.name}")
        log("")
    
    analyze_vep_file(vep_file)
