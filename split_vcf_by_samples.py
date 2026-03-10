"""
Split a multi-sample VCF into one VCF per sample.
Reads GSE144833_suit2.vcf and writes 9 single-sample VCFs.
"""
import re
from pathlib import Path

VCF_PATH = Path(__file__).parent / "GSE144833_suit2.vcf"
OUTPUT_DIR = Path(__file__).parent / "GSE144833_suit2_samples"
# Fixed columns in VCF: CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO, FORMAT
FIXED_COLS = 9


def safe_filename(name: str) -> str:
    """Make a safe filename from sample name."""
    return re.sub(r'[^\w\-.]', '_', name).strip('_')


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    meta_lines: list[str] = []
    chrom_header: str = ""
    sample_names: list[str] = []
    file_handles: list = []
    out_paths: list[Path] = []

    with open(VCF_PATH, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("##"):
                meta_lines.append(line)
                continue
            if line.startswith("#CHROM"):
                parts = line.rstrip("\n").split("\t")
                # parts[0:9] = #CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO, FORMAT
                # parts[9:] = sample names
                sample_names = parts[FIXED_COLS:]
                n = len(sample_names)
                if n == 0:
                    raise SystemExit("No sample columns found in VCF header.")
                print(f"Found {n} samples: {sample_names}")

                # Open one file per sample and write meta + per-sample header
                for i, name in enumerate(sample_names):
                    path = OUTPUT_DIR / f"{safe_filename(name)}.vcf"
                    out_paths.append(path)
                    handle = open(path, "w", encoding="utf-8", newline="\n")
                    file_handles.append(handle)
                    for m in meta_lines:
                        handle.write(m)
                    # New header: fixed columns + this sample only
                    new_header = "\t".join(parts[:FIXED_COLS] + [name]) + "\n"
                    handle.write(new_header)
                chrom_header = line
                break

        # Process variant lines
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < FIXED_COLS + len(sample_names):
                continue
            fixed = parts[:FIXED_COLS]
            for i, handle in enumerate(file_handles):
                sample_col = parts[FIXED_COLS + i]
                handle.write("\t".join(fixed + [sample_col]) + "\n")

    for handle in file_handles:
        handle.close()

    print(f"Wrote {len(out_paths)} VCFs to {OUTPUT_DIR}:")
    for p in out_paths:
        print(f"  {p.name}")


if __name__ == "__main__":
    main()
