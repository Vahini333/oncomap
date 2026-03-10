"""App configuration."""
import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent

# Data paths (prefer data/ then project root)
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_BASE_CSV = DATA_DIR / "pdac_hgvs_knowledge_base.csv"
DRIVER_GENES_TSV = DATA_DIR / "IntOGen-DriverGenes_PAAD.tsv"
if not KNOWLEDGE_BASE_CSV.exists():
    KNOWLEDGE_BASE_CSV = PROJECT_ROOT / "pdac_hgvs_knowledge_base (1).csv"
if not DRIVER_GENES_TSV.exists():
    DRIVER_GENES_TSV = PROJECT_ROOT / "IntOGen-DriverGenes_PAAD.tsv"

# Output
REPORTS_DIR = PROJECT_ROOT / "reports"
UPLOADS_DIR = PROJECT_ROOT / "uploads"

# VEP
VEP_BASE_URL = os.getenv("VEP_BASE_URL", "https://rest.ensembl.org")
VEP_SPECIES = "homo_sapiens"
VEP_BATCH_SIZE = min(200, int(os.getenv("VEP_BATCH_SIZE", "200")))
VEP_REQUEST_DELAY = float(os.getenv("VEP_REQUEST_DELAY", "0.5"))  # seconds between batches
# Parallel VEP: max concurrent requests (chunks of VEP_BATCH_SIZE each)
VEP_PARALLEL_WORKERS = min(20, max(1, int(os.getenv("VEP_PARALLEL_WORKERS", "10"))))

# Filtering
MAX_POPULATION_AF = float(os.getenv("MAX_POPULATION_AF", "0.01"))
MISSING_AF_POLICY = os.getenv("MISSING_AF_POLICY", "pass")  # pass | exclude

# Debug log (NDJSON)
DEBUG_LOG_PATH = PROJECT_ROOT / ".cursor" / "debug.log"

# Local VEP (command-line)
VEP_CMD = os.getenv("VEP_CMD", "vep")
VEP_ASSEMBLY = os.getenv("VEP_ASSEMBLY", "GRCh38")

# OpenAI (optional): drug recommendations for PDAC biomarkers
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip() or None
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Fallback drug recommendations for PDAC when KB/AI have no match (gene -> drug text)
PDAC_FALLBACK_DRUGS: dict[str, str] = {
    "KRAS": "KRAS G12C inhibitors (sotorasib, adagrasib); investigational G12D inhibitors in clinical trials",
    "TP53": "Clinical trials; p53-targeting therapies; consider chemotherapy sensitivity testing",
    "SMAD4": "Consider clinical trial; associated with poor prognosis; supportive care",
    "CDKN2A": "CDK4/6 inhibitors (palbociclib, ribociclib) in trials for PDAC",
    "BRCA1": "PARP inhibitors (olaparib); platinum-based chemotherapy",
    "BRCA2": "PARP inhibitors (olaparib); platinum-based chemotherapy",
    "ATM": "Olaparib, PARP inhibitors (DDR pathway)",
    "ARID1A": "ATR inhibitors, immunotherapy (trial)",
    "PIK3CA": "PI3K inhibitors (alpelisib) in trial",
    "MYC": "BET inhibitors, clinical trials",
    "GNAS": "Consider surveillance; common in IPMN",
    "RNF43": "Wnt inhibitors (trial)",
    "TGFBR2": "TGF-beta inhibitors (trial)",
    "LRP1B": "Immune checkpoint inhibitors (exploratory)",
    "KDM6A": "EZH2 inhibitors (trial)",
    "SMARCA4": "EZH2 inhibitors (trial)",
    "FBXW7": "mTOR inhibitors (exploratory)",
}

# ASCO tier -> AMP level (optional display)
ASCO_TO_AMP = {
    "Tier I": "Level A",
    "Tier II": "Level B",
    "Tier III": "Level C",
    "Tier IV": "Level D",
}
