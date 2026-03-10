# Run Filter Analysis

## Quick Start

Run this command to analyze your VEP response file with detailed filter statistics:

```bash
python analyze_vep_filters.py
```

This will:
1. **Automatically find** the most recent VEP response file in `vep_work/`
2. **Apply all filters** step-by-step with detailed logging
3. **Save results** to `filter_work.txt`
4. **Create CSV files** with filtered results

## Or specify a file:

```bash
python analyze_vep_filters.py vep_work/fc8e14f8-b504-406f-9403-b2d6bd0a6189_vep_rest_response.json
```

## Filters Applied (in order):

1. **Population Frequency Filter** (AF < 0.01)
   - Shows: how many variants are rare vs common
   - Removes: common variants (AF >= 0.01)

2. **Canonical Transcript Filter**
   - Shows: canonical vs non-canonical count
   - Keeps: only canonical transcripts

3. **Impact Severity Filter** (HIGH, MODERATE)
   - Shows: distribution of MODIFIER, LOW, MODERATE, HIGH
   - Keeps: only HIGH and MODERATE impact

4. **Functional Consequence Filter** (non-synonymous)
   - Shows: synonymous vs non-synonymous count
   - Removes: synonymous variants

5. **Gene Symbol Filter**
   - Shows: variants with/without gene names
   - Keeps: only variants with gene symbols

6. **Driver Gene Analysis**
   - Shows: which variants are in PAAD driver genes (IntOGen)
   - Lists: all driver genes found

7. **Drug Match Analysis**
   - Shows: which variants have drug recommendations
   - Lists: all variants with actual drugs (not "None")

## Output Files

After running, you'll get:

1. **`filter_work.txt`** - Complete log with all statistics
2. **`<job_id>_filtered.csv`** - All variants that passed filters
3. **`<job_id>_with_drugs.csv`** - Only variants with drug recommendations

## Example Output in filter_work.txt:

```
================================================================================
FILTER 1: POPULATION FREQUENCY (Rare Variants)
================================================================================
Threshold: AF < 0.01 (rare variants)
Missing AF (kept): 156234
AF < 0.01 (PASS): 45123
AF >= 0.01 (FAIL - too common): 32456
After frequency filter: 201357 / 233813 (86.1%)

================================================================================
FILTER 2: CANONICAL TRANSCRIPT
================================================================================
Canonical (PASS): 45678
Non-canonical (FAIL): 155679
After canonical filter: 45678 / 201357 (22.7%)

================================================================================
FILTER 3: IMPACT SEVERITY
================================================================================
Impact distribution:
  MODIFIER: 23456 (FAIL)
  HIGH: 8901 (PASS)
  MODERATE: 12345 (PASS)
  LOW: 976 (FAIL)
After impact filter: 21246 / 45678 (46.5%)

...and so on for each filter
```

## Troubleshooting

**Q: Error "No VEP response files found"**  
A: Make sure you've run the pipeline at least once. VEP response files are saved to `vep_work/` directory.

**Q: Where is filter_work.txt?**  
A: In the project root: `c:\Users\madhu\Downloads\vibeathon\filter_work.txt`

**Q: I want to analyze a different VEP file**  
A: Pass it as an argument: `python analyze_vep_filters.py vep_work/your_file.json`
