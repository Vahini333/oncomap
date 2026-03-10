"""Generate pancreatic cancer (PDAC) drug recommendations using OpenAI from variant biomarkers."""
import json
import os
from typing import Any

# Optional: only import openai when key is set
def _get_client():
    try:
        from openai import OpenAI
        return OpenAI()
    except ImportError:
        return None


def get_openai_api_key() -> str | None:
    """Read OpenAI API key from environment."""
    return os.getenv("OPENAI_API_KEY", "").strip() or None


def fetch_drug_recommendations_for_variants(
    variants: list[dict[str, Any]],
    job_id: str = "",
    log_callback: None | Any = None,
) -> dict[tuple[str, str, str], dict[str, str]]:
    """
    Call OpenAI to get drug recommendations for pancreatic cancer (PDAC) for each variant.
    variants: list of dicts with gene_symbol, hgvs_coding, hgvs_protein, impact, consequence_terms.
    Returns: dict keyed by (gene, hgvs_coding, hgvs_protein) -> { "drugs": "...", "rationale": "..." }.
    """
    api_key = get_openai_api_key()
    if not api_key:
        if log_callback:
            log_callback("OPENAI_API_KEY not set; skipping AI drug recommendations.")
        return {}

    client = _get_client()
    if not client:
        if log_callback:
            log_callback("OpenAI package not installed; skipping AI drug recommendations.")
        return {}

    # Deduplicate by (gene, hgvs_coding, hgvs_protein)
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for v in variants:
        gene = (v.get("gene_symbol") or "").strip()
        hgvs_c = (v.get("hgvs_coding") or "").strip()
        hgvs_p = (v.get("hgvs_protein") or "").strip()
        key = (gene, hgvs_c, hgvs_p)
        if key in seen or not gene:
            continue
        seen.add(key)
        unique.append(v)

    if not unique:
        return {}

    # Build a compact summary for the prompt (limit tokens)
    variant_lines = []
    for v in unique[:80]:  # cap to avoid token limit
        gene = v.get("gene_symbol") or "?"
        hgvs_c = (v.get("hgvs_coding") or "").strip() or "—"
        hgvs_p = (v.get("hgvs_protein") or "").strip() or "—"
        impact = (v.get("impact") or "").strip() or "—"
        terms = v.get("consequence_terms") or []
        cons = ", ".join(terms[:3]) if terms else "—"
        variant_lines.append(f"- Gene: {gene} | HGVSc: {hgvs_c} | HGVSp: {hgvs_p} | Impact: {impact} | Consequence: {cons}")

    prompt = f"""You are a clinical oncology expert focused on pancreatic ductal adenocarcinoma (PDAC). Given the following list of somatic variants (biomarkers) from a patient's sequencing, provide brief, evidence-based drug recommendations for pancreatic cancer for each variant.

Rules:
- Recommend only drugs or drug classes relevant to PDAC and the specific gene/pathway (e.g. KRAS inhibitors for KRAS, PARP inhibitors for BRCA/ATM, immunotherapy for high TMB, etc.).
- Be specific: use drug names (e.g. Olaparib, Sotorasib, pembrolizumab) or clear drug classes (e.g. PARP inhibitors, MEK inhibitors).
- Keep each recommendation to one short line. Include evidence level if helpful (e.g. "FDA-approved in other cancers", "clinical trial").
- If a variant has no established PDAC actionability, say "Consider trial or germline counseling" and briefly why.
- Output valid JSON only, no markdown or extra text.

Variants:
{chr(10).join(variant_lines)}

Respond with a JSON object where each key is the gene symbol and value is an object with "drugs" (string: comma-separated drug recommendations) and "rationale" (one short sentence). Example:
{{ "KRAS": {{ "drugs": "Sotorasib, Adagrasib (G12C); investigational G12D inhibitors in trial", "rationale": "KRAS G12D is a PDAC driver; G12C inhibitors approved in NSCLC; G12D-specific trials ongoing." }}, "ATM": {{ "drugs": "Olaparib, PARP inhibitors", "rationale": "DDR pathway; PARP inhibitors have activity in DDR-deficient PDAC." }}}}
"""

    result_map: dict[tuple[str, str, str], dict[str, str]] = {}
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a clinical oncology expert. Reply only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = (response.choices[0].message.content or "").strip()
        # Strip markdown code block if present
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        data = json.loads(text)
        if not isinstance(data, dict):
            if log_callback:
                log_callback("OpenAI returned non-dict; skipping AI drugs.")
            return {}
        # Map gene -> (drugs, rationale) and then back to (gene, hgvs_c, hgvs_p) for each variant
        for v in unique:
            gene = (v.get("gene_symbol") or "").strip()
            hgvs_c = (v.get("hgvs_coding") or "").strip()
            hgvs_p = (v.get("hgvs_protein") or "").strip()
            key = (gene, hgvs_c, hgvs_p)
            gene_data = data.get(gene) if isinstance(data.get(gene), dict) else None
            if gene_data:
                drugs = (gene_data.get("drugs") or "").strip()
                rationale = (gene_data.get("rationale") or "").strip()
                if drugs:
                    result_map[key] = {"drugs": drugs, "rationale": rationale}
        if log_callback:
            log_callback(f"OpenAI returned drug recommendations for {len(result_map)} variant(s).")
    except json.JSONDecodeError as e:
        if log_callback:
            log_callback(f"OpenAI response was not valid JSON: {e}")
    except Exception as e:
        if log_callback:
            log_callback(f"OpenAI request failed: {e}")
    return result_map
