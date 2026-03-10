# Logging Guide

## Output Files

All console logs are now automatically saved to:

📄 **`filter_work.txt`** (in the project root directory)

This file contains:
- Timestamps for every log entry
- Component names (e.g., `[pipeline]`, `[vep_client]`, `[filter_and_match]`)
- All step-by-step progress messages
- Error messages and stack traces
- Filtering statistics
- Matching results

## How It Works

1. **When you start the server** (`uvicorn main:app --reload`):
   - The log file `filter_work.txt` is cleared
   - A "New session started" message is logged

2. **During pipeline execution**:
   - Every log message appears in BOTH:
     - Terminal/console (stderr)
     - `filter_work.txt` file

3. **After a job completes**:
   - Open `filter_work.txt` to review the complete log
   - Each job's logs include the job_id for easy filtering

## Example Log File Contents

```
[2026-02-13 14:35:22] [logger] === New session started ===
[2026-02-13 14:35:22] [main] FastAPI server started - all logs will be saved to filter_work.txt
[2026-02-13 14:36:10] [main] Upload request: test_sample.vcf
[2026-02-13 14:36:10] [main fc8e14f8-b504-406f-9403-b2d6bd0a6189] Saved 1024 bytes -> uploads/fc8e14f8-b504-406f-9403-b2d6bd0a6189.vcf
[2026-02-13 14:36:10] [main fc8e14f8-b504-406f-9403-b2d6bd0a6189] Job created: fc8e14f8-b504-406f-9403-b2d6bd0a6189
[2026-02-13 14:36:12] [main fc8e14f8-b504-406f-9403-b2d6bd0a6189] POST /run job_id=fc8e14f8-b504-406f-9403-b2d6bd0a6189
[2026-02-13 14:36:12] [main fc8e14f8-b504-406f-9403-b2d6bd0a6189] Background job started (local VEP pipeline)
[2026-02-13 14:36:12] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] Step 1/5: Parsing VCF...
[2026-02-13 14:36:12] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] Parsed 3 variants, sample_id=SAMPLE_001
[2026-02-13 14:36:12] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] Step 2/5: Annotating with Ensembl VEP...
[2026-02-13 14:36:12] [vep_client] Starting VEP for 3 variant(s) in 1 batch(es), batch_size=200, delay=0.5s
[2026-02-13 14:36:12] [vep_client] Batch 1/1: variants 1-3 of 3
[2026-02-13 14:36:12] [vep_client] POST https://rest.ensembl.org/vep/homo_sapiens/region (batch size 3)
[2026-02-13 14:36:45] [vep_client] VEP batch OK: received 3 result(s)
[2026-02-13 14:36:45] [vep_client] VEP complete: 3 total result(s)
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] VEP returned 3 annotation(s) for 3 variant(s).
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] VEP REST response saved to vep_work/fc8e14f8-b504-406f-9403-b2d6bd0a6189_vep_rest_response.json
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] Step 3/5: Filtering variants...
[2026-02-13 14:36:45] [filter_and_match] Filtering 3 VEP result(s): max_af=0.01, missing_af_policy=pass
[2026-02-13 14:36:45] [filter_and_match] Filter results: 2 passed, 1 synonymous, 0 AF>=0.01, 0 no transcript, 0 not canonical, 0 no gene, 0 missing AF excluded
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] After filtering: 2 variant(s).
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] Step 4/5: Matching to knowledge base...
[2026-02-13 14:36:45] [filter_and_match] Matching 2 filtered variant(s) to knowledge base...
[2026-02-13 14:36:45] [filter_and_match] Match results: 1 exact matches (gene+HGVS), 1 gene-only matches, 0 no matches, 1 with actual drugs (not 'None')
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] After matching: 2 variant(s) (including those without drugs).
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] Filtered to 1 variant(s) WITH drug recommendations.
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] After deduplication: 1 unique variant(s) with drugs.
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] Step 5/5: Generating PDF report...
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] PDF written to reports/fc8e14f8-b504-406f-9403-b2d6bd0a6189.pdf
[2026-02-13 14:36:45] [pipeline fc8e14f8-b504-406f-9403-b2d6bd0a6189] Pipeline completed successfully.
[2026-02-13 14:36:45] [main fc8e14f8-b504-406f-9403-b2d6bd0a6189] Job completed: variant_count=1
```

## Finding Specific Job Logs

Since logs include job IDs, you can:

1. **Open `filter_work.txt`** in any text editor
2. **Search** (Ctrl+F) for your job_id (from the upload response)
3. **Review** all steps for that specific job

## Log File Location

```
c:\Users\madhu\Downloads\vibeathon\filter_work.txt
```

The file is automatically created when you run the server. If it doesn't exist, check:
- Permissions on the `vibeathon` folder
- That the server started successfully

## Troubleshooting

**Q: I don't see `filter_work.txt`**  
A: Start the server (`uvicorn main:app --reload`) - it will be created on first log

**Q: The file is empty**  
A: Make sure you've run at least one job through the pipeline

**Q: I want to clear old logs**  
A: Just delete `filter_work.txt` and restart the server, or let it restart automatically (it clears on startup)
