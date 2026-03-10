# VCF VEP Personalized Report

Web app: upload VCF → Ensembl VEP → filter (AF < 0.01, canonical, non-synonymous) → match to PDAC knowledge base → PDF report with genes, HGVS, biomarkers, and drug recommendations (ASCO/CAP tier).

## Setup

```bash
cd vibeathon
pip install -r requirements.txt
```

Data files (CSV/TSV) should be in `data/`:
- `data/pdac_hgvs_knowledge_base.csv`
- `data/IntOGen-DriverGenes_PAAD.tsv`

If missing, the app falls back to the same files in the project root.

**Optional – AI drug recommendations for pancreatic cancer:**  
Set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`, default `gpt-4o-mini`) so the report includes OpenAI-generated drug suggestions for PDAC biomarkers when the knowledge base has no match.

```bash
set OPENAI_API_KEY=sk-your-key-here
```

## Run

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — upload a VCF, click "Run report", then download the PDF when ready.

## API

- `POST /upload` — upload VCF file; returns `job_id`
- `POST /run?job_id=<id>` — start pipeline for that job (runs in background)
- `GET /status/<job_id>` — pending | running | completed | failed
- `GET /report/<job_id>` — download PDF (when status is completed)

## Notes

- VEP uses Ensembl REST (GRCh38). Rate limit: 200 variants per request; batches are throttled.
- For large VCFs, consider subsetting or running local VEP.
- Reference genome: ensure VCF is GRCh38 (or use `grch37.rest.ensembl.org` and set `VEP_BASE_URL`).
