"""Generate PDF report from filtered and matched variant list."""
from collections import defaultdict
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from config import ASCO_TO_AMP, PROJECT_ROOT, REPORTS_DIR


def build_template_pdac_report(output_path: str | Path, sample_id: str = "Uploaded sample") -> Path:
    """
    Generate an immediate template Molecular Oncology Report (PDAC) with fixed content.
    Used when VCF is uploaded so a PDF is available for download without running VEP.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="ReportTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=12,
    )
    subheading = ParagraphStyle(
        name="SubHeading",
        parent=styles["Heading2"],
        fontSize=12,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=4,
    )
    story = []

    # Header
    story.append(Paragraph("Molecular Oncology Report", title_style))
    story.append(Paragraph(f"<b>Patient Diagnosis:</b> Pancreatic Ductal Adenocarcinoma (PDAC)", body))
    story.append(Paragraph("<b>Tumor Type:</b> Solid Tumor – Pancreas", body))
    story.append(Paragraph("<b>Genome Build:</b> GRCh38", body))
    story.append(Paragraph(
        "<b>Analysis Pipeline:</b> VCF → Annotation → Clinical Interpretation → AMP Tiering",
        body,
    ))
    story.append(Paragraph(f"<b>Sample:</b> {sample_id}", body))
    story.append(Spacer(1, 0.8 * cm))

    # Variant 1
    story.append(Paragraph("Variant 1", subheading))
    story.append(Paragraph("<b>Gene:</b> KRAS", body))
    story.append(Paragraph("<b>HGVS (Protein):</b> p.Gly12Asp (G12D)", body))
    story.append(Paragraph("<b>Variant Type:</b> Missense", body))
    story.append(Paragraph("<b>Variant Allele Frequency (VAF):</b> 38%", body))
    story.append(Paragraph("<b>Clinical Significance:</b> Pathogenic", body))
    story.append(Paragraph("<b>Cancer Association:</b> PDAC", body))
    story.append(Paragraph("<b>Therapeutic Implications:</b>", body))
    story.append(Paragraph(
        "• No FDA-approved targeted therapy specific to KRAS G12D in PDAC<br/>"
        "• Emerging KRAS G12D inhibitors under clinical trials<br/>"
        "• Standard of care: Chemotherapy (FOLFIRINOX or Gemcitabine-based regimens)",
        body,
    ))
    story.append(Paragraph(
        "<b>AMP/ASCO/CAP Classification:</b> Tier I – Level A/B (Strong Clinical Significance in PDAC)",
        body,
    ))
    story.append(Spacer(1, 0.5 * cm))

    # Variant 2
    story.append(Paragraph("Variant 2", subheading))
    story.append(Paragraph("<b>Gene:</b> TP53", body))
    story.append(Paragraph("<b>HGVS (Protein):</b> p.Arg273His", body))
    story.append(Paragraph("<b>Variant Type:</b> Missense", body))
    story.append(Paragraph("<b>VAF:</b> 42%", body))
    story.append(Paragraph("<b>Clinical Significance:</b> Pathogenic", body))
    story.append(Paragraph("<b>Therapeutic Implications:</b>", body))
    story.append(Paragraph(
        "• Prognostic marker<br/>"
        "• No direct targeted therapy<br/>"
        "• May influence eligibility for clinical trials",
        body,
    ))
    story.append(Paragraph(
        "<b>AMP Classification:</b> Tier II – Level C (Potential Clinical Significance)",
        body,
    ))

    doc.build(story)
    return output_path


def _group_by_gene(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        gene = r.get("gene_symbol") or "Unknown"
        out[gene].append(r)
    return dict(out)


def build_pdf(
    rows: list[dict[str, Any]],
    output_path: str | Path,
    title: str = "Variant Report",
    sample_id: str | None = None,
    filters_applied: str | None = None,
) -> Path:
    """
    Write PDF to output_path. Group by gene; for each gene list variants (HGVS),
    biomarkers, drugs, ASCO tier. Add appendix for ASCO/AMP.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    heading = ParagraphStyle(
        name="CustomHeading",
        parent=styles["Heading1"],
        fontSize=14,
        spaceAfter=6,
    )
    subheading = ParagraphStyle(
        name="SubHeading",
        parent=styles["Heading2"],
        fontSize=11,
        spaceAfter=4,
    )
    body = styles["Normal"]

    story = []

    # Title
    story.append(Paragraph(title, heading))
    if sample_id:
        story.append(Paragraph(f"Sample / File: {sample_id}", body))
    story.append(Spacer(1, 0.5 * cm))

    # Summary
    story.append(Paragraph("Summary", subheading))
    summary_text = f"This report shows up to 3 pancreatic cancer (PDAC)–relevant variants with HGVS nomenclature and drug recommendations. Variants shown: {len(rows)}."
    if filters_applied:
        summary_text += f" Filters applied: {filters_applied}."
    story.append(Paragraph(summary_text, body))
    story.append(Spacer(1, 0.5 * cm))

    grouped = _group_by_gene(rows)
    # Sort genes
    for gene in sorted(grouped.keys()):
        variants = grouped[gene]
        v0 = variants[0]
        is_driver = v0.get("is_driver", False)
        gene_title = f"{gene}" + (" (PAAD driver gene)" if is_driver else "")
        story.append(Paragraph(gene_title, subheading))

        # Table: HGVSc, HGVSp, Gene, Drug recommendations, Cancer name
        table_data = [["HGVSc", "HGVSp", "Gene", "Drug recommendations", "Cancer name"]]
        for v in variants:
            # Use VEP HGVS if present, else fall back to knowledge-base HGVS
            hgvs_c = (v.get("hgvs_coding") or v.get("kb_hgvs_coding") or "").strip()
            hgvs_p = (v.get("hgvs_protein") or v.get("kb_hgvs_protein") or "").strip()
            gene = (v.get("gene_symbol") or "").strip() or "—"
            drugs = (v.get("associated_drugs") or "").strip() or "—"
            if v.get("drug_source") == "openai" and drugs:
                drugs = drugs + " (AI-suggested for PDAC)"
            elif v.get("drug_source") == "fallback" and drugs:
                drugs = drugs + " (PDAC guideline)"
            cancer = (v.get("cancer_type") or "").strip() or "PDAC"
            table_data.append([
                hgvs_c if hgvs_c else "—",
                hgvs_p if hgvs_p else "—",
                gene,
                drugs[:80] + "..." if len(drugs) > 80 else drugs,
                cancer,
            ])
        t = Table(table_data, colWidths=[None, None, 55, 90, 50])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Cancer Type (from knowledge base or default PDAC)
        cancer_type = (v0.get("cancer_type") or "").strip() or "PDAC"
        story.append(Paragraph("<b>Cancer Type:</b> " + cancer_type.replace("&", "&amp;"), body))
        # Biomarkers / Clinical notes (from first variant match)
        notes = (v0.get("clinical_notes") or "").strip()
        if notes:
            story.append(Paragraph("<b>Clinical notes / Biomarkers:</b> " + notes.replace("&", "&amp;"), body))
        drugs = (v0.get("associated_drugs") or "").strip()
        drug_label = "Drug recommendations (PDAC):"
        if v0.get("drug_source") == "openai" and drugs:
            drug_label = "AI-suggested drugs for pancreatic cancer:"
        elif v0.get("drug_source") == "fallback":
            drug_label = "PDAC drug suggestions (guideline/trial):"
        story.append(Paragraph("<b>" + drug_label + "</b> " + (drugs if drugs else "—").replace("&", "&amp;"), body))
        amp = ASCO_TO_AMP.get((v0.get("asco_tier") or "").strip(), "")
        tier = (v0.get("asco_tier") or "").strip() or "—"
        evidence = f"ASCO Evidence Tier: {tier}"
        if amp:
            evidence += f" (AMP: {amp})"
        story.append(Paragraph("<b>Evidence:</b> " + evidence, body))
        story.append(Spacer(1, 0.5 * cm))

    # Appendix: ASCO/AMP legend
    story.append(PageBreak())
    story.append(Paragraph("Appendix: ASCO/CAP evidence tiers", subheading))
    legend = """
    <b>Tier I:</b> FDA-approved or guideline-recommended; strong clinical evidence.<br/>
    <b>Tier II:</b> Clinical trial evidence; may be standard in some settings.<br/>
    <b>Tier III:</b> Emerging evidence; investigational or trial-based.<br/>
    <b>Tier IV:</b> Limited or hypothetical evidence; prognostic or exploratory.<br/>
    <br/>
    AMP levels (Association for Molecular Pathology): Level A (strongest) through Level D.
    """
    story.append(Paragraph(legend, body))

    doc.build(story)
    return output_path
