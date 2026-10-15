# LLM-eval

Evaluate public comment letters with OpenAI and export structured scores.

## Published report

The project's findings were published on Georgetown University's McCourt School of Public Policy website on **October 3, 2026**:

**[Fine-Tuning Works: What Specialized AI Can Teach Us About Regulatory Comments](https://mccourt.georgetown.edu/research-centers/fine-tuning-works-what-specialized-ai-can-teach-us-about-regulatory-comments/)** — Nora Guo Zhan, Tech & Public Policy.

Local materials: [evaluation memo (PDF)](reports/LLM-Evaluation%20Memo.pdf) and [editable memo (Word)](reports/LLM-Evaluation%20Memo.docx).

## Project layout

```text
LLM-eval/
├── README.md
├── requirements.txt
├── notebooks/          # Transformation, evaluation, and analysis notebooks
├── scripts/            # Context-sensitivity rescoring script
├── data/
│   ├── context/        # Policy summaries and downloaded policy HTML
│   ├── results/        # Original and context-sensitivity scores (CSV/JSONL)
│   └── samples/        # Frozen balanced sample and theme audit
├── comments/           # Evaluator-ready comments
├── comments_original/  # Original Regulations.gov bulk downloads
├── images/             # Analysis figures
└── reports/            # Evaluation memo (PDF and Word)
```

The comment directories retain their existing locations to preserve file identifiers used by saved scores and frozen samples. Existing data and notebook outputs are retained.

## What this does
- Loads comment JSON files and CSV files from the `comments/` folder.
- Converts bulk-downloaded Regulations.gov CSV files from `comments_original/` into evaluator-ready CSVs.
- Optionally loads policy context from `data/context/policy_contexts.json` and/or downloaded policy HTML files.
- Sends each comment text to the OpenAI API for scoring.
- Scores criteria: relevance, reasoning, evidence, impact, actionability, structure/formatting, overall.
- Writes results to JSONL and CSV in `data/results/`.

## Setup
Use Python 3.12.3 and install dependencies from the project root:

```bash
python -m pip install -r requirements.txt
```

1. Create a `.env` file in this folder with your API key:
   
   OPENAI_API_KEY=your_key_here

2. If using downloaded Regulations.gov bulk CSVs, run `notebooks/transform_comments_original.ipynb`.
3. Open and run `notebooks/comment_evaluator.ipynb`.
4. For analysis, open and run `notebooks/comment_analysis.ipynb`.

Start Jupyter from the project root or `notebooks/`, and run notebook cells in order. Notebooks locate the project root automatically; `.env` stays at the root and figures are saved to `images/`.

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
3. Run `notebooks/transform_comments_original.ipynb`.

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

1. `data/context/policy_contexts.json`

   Add summaries keyed by policy ID:

   ```json
   {
     "FDA-2024-C-1085": "Policy summary here.",
     "EPA-HQ-OW-2025-2929": "Policy summary here.",
     "FMCSA-2023-0257": "Policy summary here."
   }
   ```

2. `data/context/policy_context_html/`

   Put downloaded policy HTML pages in this folder. The filename must contain the policy ID, for example:

   ```text
   data/context/policy_context_html/FDA-2024-C-1085-0003_content.html
   ```

The evaluator reads `data/context/policy_contexts.json` first. If a policy has no JSON context, it looks for matching HTML files and extracts plain text from them. Long HTML-derived context is truncated before it is added to the prompt.

The OpenAI API receives the policy ID, optional policy context, and comment text. It does not receive `source_label`, `display_name`, filenames, or whether a comment is human/Gemini/Statt.

## Evaluation Limits
`notebooks/comment_evaluator.ipynb` currently has:

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
- `data/results/comment_scores.jsonl` (one JSON per comment)
- `data/results/comment_scores.csv` (flat table for analysis)

## Context-Parity Rescoring
Statt and Gemini comments were generated from agency-level personas with no specific docket, so the evaluator only saw an agency name for them, while Round 1 human comments were originally scored with their exact docket and rule summary. `scripts/rescore_context_sensitivity.py` rescores:
- the 298 Round 1 human comments with agency-only information (`agency_only`) and with the original setup (`full_context`, a test-retest control);
- all Statt and Gemini comments with their original inputs (`ai_same_day`), so Round 1 sources come from one run;
- all Statt and Gemini comments with only the agency name from their source file (`ai_agency_only`). The original inputs sent 188 Statt comments a docket-like ID taken from the letter text;
- the 2,997 Round 2 human comments with agency-only information (`agency_only`).

Results are written to `data/results/comment_scores_context_sensitivity.jsonl` / `.csv`. `notebooks/comment_analysis.ipynb` uses the `agency_only` + `ai_agency_only` scores by default (`USE_CONTEXT_PARITY_SCORES`), so every comment is scored with only its agency name, and compares all scenarios in its final section.

Run rescoring from the project root (requires an API key and may incur API charges):

```bash
python scripts/rescore_context_sensitivity.py
```

## Reproducibility
- `requirements.txt` pins the library versions used for the published numbers (Python 3.12.3).
- `data/samples/balanced_sample_files.csv` freezes the 894-comment agency-balanced sample (file list and order) used by every regression and topic model. Delete it only if you intend to draw a new sample.
- `data/samples/topic_theme_audit_sample.csv` holds a 150-clause spot check of the v2 theme assignments (10 per theme). The current `fits_theme` labels are a first pass by Claude and still need human verification; the notebook reports precision from this file.

## Analysis
- `notebooks/comment_analysis.ipynb` compares scores by `source_label` and runs BERTopic per rationale field.
- The "Topic Modeling v2" section is the recommended topic analysis. Human, Statt, and Gemini comments cover different dockets, so the earlier document-level topics mostly separate dockets. v2 splits evaluator rationales into clauses, masks docket-specific words, separates praise from criticism, fits BERTopic on the agency-balanced Round 1 sample, and writes `images/topic_modeling_evaluator_themes.png`.
- It reads `data/results/comment_scores.csv` and `data/results/comment_scores.jsonl`.
- The analysis notebook infers missing `policy_id` values (especially for human labels) using docket ID patterns.

## Notes
- The notebook uses `RESUME = True` to skip files already scored in the JSONL output.
- `MAX_FILES` is still available as a global cap for small test runs.
- If changing caps or contexts and you want a fully fresh run, rename or delete `data/results/comment_scores.jsonl` and `data/results/comment_scores.csv` before rerunning the evaluator.
- `.env` is ignored by git for safety.
