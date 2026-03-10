# Critical Fixes Applied - VCF Report Pipeline

## 📄 **NEW: All Logs Saved to `filter_work.txt`**
Every console log message (with timestamps) is now automatically saved to:
- **File**: `filter_work.txt` (in project root)
- **Also shown in**: Terminal/console (as before)
- **Auto-cleared**: On server startup
- **Contains**: All step-by-step progress, filtering stats, errors, and results

See `LOGGING_GUIDE.md` for details.

---

## Problem 1: VEP REST Response Not Visible ✅ FIXED
**Issue**: When using Ensembl REST API, you couldn't see what VEP was returning.

**Solution**: 
- VEP REST responses are now dumped to: `vep_work/<job_id>_vep_rest_response.json`
- Local VEP output is copied to: `vep_work/<job_id>_vep_local_output.tsv`
- Both files are saved automatically for inspection

## Problem 2: 450-Page Report (Wrong Filtering) ✅ FIXED
**Issue**: The REST pipeline was including ALL filtered variants in the report, even those without drug recommendations. Your knowledge base has many entries with `Associated Drug(s) = None`, which should NOT appear in the final report.

**Root Cause**:
- The local VEP pipeline (`pipeline_vep_tab.py`) correctly filtered to only drug-matched variants
- The REST pipeline (`pipeline.py`) was including all variants, even those matched to KB entries with "None" drugs

**Solution**:
In `pipeline.py` (REST pipeline):
1. After matching to knowledge base, filter to keep ONLY variants where:
   - `associated_drugs` is not empty
   - `associated_drugs` is not "None"
   - `associated_drugs` is not missing
2. Added logging: "Filtered to N variant(s) WITH drug recommendations"
3. If zero variants have drugs, the pipeline stops with a clear error message

**Expected Result**: Report will now contain ONLY variants with actual drug recommendations, matching the behavior of the local VEP pipeline.

## Additional Improvements

### Enhanced Logging
1. **Filtering step** now shows:
   - How many variants passed
   - How many were filtered out for each reason:
     - Synonymous variants
     - AF >= 0.01 (too common)
     - Not canonical
     - No gene symbol
     - Missing AF (if policy is "exclude")

2. **Matching step** now shows:
   - Exact matches (gene + HGVS)
   - Gene-only fallback matches
   - No matches
   - Total with actual drugs (not "None")

3. **Pipeline progress** shows:
   - Step X/5 for each major step
   - Variant counts after each step
   - Clear error messages when steps fail

### Example Server Console Output
```
[pipeline <job_id>] Step 1/5: Parsing VCF...
[pipeline <job_id>] Parsed 150 variants, sample_id=SAMPLE_001
[pipeline <job_id>] Step 2/5: Annotating with Ensembl VEP...
[vep_client] Starting VEP for 150 variant(s) in 1 batch(es)...
[vep_client] Batch 1/1: variants 1-150 of 150
[vep_client] POST https://rest.ensembl.org/vep/homo_sapiens/region (batch size 150)
[vep_client] VEP batch OK: received 150 result(s)
[vep_client] VEP complete: 150 total result(s)
[pipeline <job_id>] VEP returned 150 annotation(s)
[pipeline <job_id>] VEP REST response saved to vep_work/<job_id>_vep_rest_response.json
[pipeline <job_id>] Step 3/5: Filtering variants...
[filter_and_match] Filtering 150 VEP result(s): max_af=0.01...
[filter_and_match] Filter results: 12 passed, 85 synonymous, 45 AF>=0.01, 8 no gene
[pipeline <job_id>] After filtering: 12 variant(s).
[pipeline <job_id>] Step 4/5: Matching to knowledge base...
[filter_and_match] Matching 12 filtered variant(s) to knowledge base...
[filter_and_match] Match results: 8 exact matches, 2 gene-only, 2 no matches, 5 with actual drugs
[pipeline <job_id>] After matching: 12 variant(s) (including those without drugs).
[pipeline <job_id>] Filtered to 5 variant(s) WITH drug recommendations.
[pipeline <job_id>] After deduplication: 5 unique variant(s) with drugs.
[pipeline <job_id>] Step 5/5: Generating PDF report...
[pipeline <job_id>] PDF written to reports/<job_id>.pdf
[pipeline <job_id>] Pipeline completed successfully.
```

## Testing the Fix

1. **Run the pipeline** with your VCF file
2. **Check the server console** - you'll see step-by-step progress and counts
3. **Check these files**:
   - `vep_work/<job_id>_vep_rest_response.json` (REST API) or
   - `vep_work/<job_id>_vep_local_output.tsv` (local VEP)
4. **Check the PDF** - should now contain ONLY variants with drug recommendations (not "None")
5. **Expected page count** - should be dramatically smaller (5-10 pages instead of 450)

## Knowledge Base Structure
Your KB has entries like:
- `KRAS, c.35G>A, p.Gly12Asp, PDAC, Investigational KRAS G12D inhibitors, Tier II` ✅ INCLUDED
- `TP53, c.818G>A, p.Arg273His, PDAC, None, Tier IV` ❌ EXCLUDED
- `SMAD4, c.1244_1247del, p.Glu415fs, PDAC, None, Tier IV` ❌ EXCLUDED

Only variants with actual drugs (not "None") will appear in the final report.

## If You Still See Issues

1. Check server console logs - they show every step and count
2. Check browser console (F12) - shows frontend polling and errors
3. Inspect the VEP output files in `vep_work/` folder
4. Look for these key log lines:
   - "Filtered to N variant(s) WITH drug recommendations" (should be small number)
   - "After deduplication: N unique variant(s) with drugs"
   - "Match results: ... with actual drugs (not 'None')"
