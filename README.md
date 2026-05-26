# LLM-eval

Evaluate public comment letters with OpenAI and export structured scores.

## What this does
- Loads comment JSON files and CSV files from the `comments/` folder.
- Converts bulk-downloaded Regulations.gov CSV files from `comments_original/` into evaluator-ready CSVs.
- Optionally loads policy context from `policy_contexts.json` and/or downloaded policy HTML files.
- Sends each comment text to the OpenAI API for scoring.
- Scores criteria: relevance, reasoning, evidence, impact, actionability, structure/formatting, overall.
- Writes results to JSONL and CSV in this folder.

## Setup
1. Create a `.env` file in this folder with your API key:
   
   OPENAI_API_KEY=your_key_here

2. If using downloaded Regulations.gov bulk CSVs, run `transform_comments_original.ipynb`.
3. Open and run `comment_evaluator.ipynb`.
4. For analysis, open and run `comment_analysis.ipynb`.

## Inputs
- Place comment JSON files under `comments/` (per-comment JSON).
- CSV files are also supported in `comments/`:
   - Statt format: `comment_text` contains a JSON string with a `draft` key.
   - Gemini format: `Comment Letter` or `comment_letter` contains plain text.
   - Human/downloaded format: `source`, `source_label`, `policy_id`, `display_name`, `comment_text`.
- The JSON extractor prefers `text.fullText` but also checks common fields like `comment_text` or `body`.
- Optional: add `source_label` (e.g., `human`, `ai`). This label is saved to outputs but is not sent to the API.
- Optional: add `policy_id`. If missing, the evaluator tries to infer it from the text or filename.

## Downloaded Regulations.gov comments
1. Download bulk comment CSVs from Regulations.gov.
2. Put the downloaded files in `comments_original/`.
3. Run `transform_comments_original.ipynb`.

The transform notebook writes one cleaned CSV per policy into `comments/`, currently:
- `comments/fda_comments_human.csv`
- `comments/epa_comments_human.csv`
- `comments/fmcsa_comments_human.csv`

The generated CSVs are intentionally minimal and evaluator-ready:

```text
source, source_label, policy_id, display_name, comment_text
```

Downloaded comments are labeled as:

```text
source_label = human
```

## Policy Context
Policy context is optional. Comments can still be evaluated when no context exists.

There are two supported context sources:

1. `policy_contexts.json`

   Add summaries keyed by policy ID:

   ```json
   {
     "FDA-2024-C-1085": "Policy summary here.",
     "EPA-HQ-OW-2025-2929": "Policy summary here.",
     "FMCSA-2023-0257": "Policy summary here."
   }
   ```

2. `policy_context_html/`

   Put downloaded policy HTML pages in this folder. The filename must contain the policy ID, for example:

   ```text
   policy_context_html/FDA-2024-C-1085-0003_content.html
   ```

The evaluator reads `policy_contexts.json` first. If a policy has no JSON context, it looks for matching HTML files and extracts plain text from them. Long HTML-derived context is truncated before it is added to the prompt.

The OpenAI API receives the policy ID, optional policy context, and comment text. It does not receive `source_label`, `display_name`, filenames, or whether a comment is human/Gemini/Statt.

## Evaluation Limits
`comment_evaluator.ipynb` currently has:

```python
MAX_RECORDS_PER_POLICY = 1000
CAP_SOURCE_LABELS = {"human"}
```

This means the evaluator processes up to 1000 downloaded human comments per policy. Gemini and Statt comments are not capped by this setting.

To evaluate all human comments, set:

```python
MAX_RECORDS_PER_POLICY = None
```

To apply the cap to every source label, set:

```python
CAP_SOURCE_LABELS = None
```

## Outputs
- `comment_scores.jsonl` (one JSON per comment)
- `comment_scores.csv` (flat table for analysis)

## Analysis
- `comment_analysis.ipynb` compares scores by `source_label` and runs BERTopic per rationale field.
- It expects `comment_scores.csv` and `comment_scores.jsonl` in this folder.
- The analysis notebook infers missing `policy_id` values (especially for human labels) using docket ID patterns.

## Notes
- The notebook uses `RESUME = True` to skip files already scored in the JSONL output.
- `MAX_FILES` is still available as a global cap for small test runs.
- If changing caps or contexts and you want a fully fresh run, rename or delete `comment_scores.jsonl` and `comment_scores.csv` before rerunning the evaluator.
- `.env` is ignored by git for safety.
