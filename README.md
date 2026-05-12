# LLM-eval

Evaluate public comment letters with OpenAI and export structured scores.

## What this does
- Loads comment JSON files and CSV files from the `comments/` folder.
- Sends each comment text to the OpenAI API for scoring.
- Scores criteria: relevance, reasoning, evidence, impact, actionability, structure/formatting, overall.
- Writes results to JSONL and CSV in this folder.

## Setup
1. Create a `.env` file in this folder with your API key:
   
   OPENAI_API_KEY=your_key_here

2. Open and run `comment_evaluator.ipynb`.
3. For analysis, open and run `comment_analysis.ipynb`.

## Inputs
- Place comment JSON files under `comments/` (per-comment JSON).
- CSV files are also supported in `comments/`:
   - Statt format: `comment_text` contains a JSON string with a `draft` key.
   - Gemini format: `Comment Letter` or `comment_letter` contains plain text.
- The JSON extractor prefers `text.fullText` but also checks common fields like `comment_text` or `body`.
- Optional: add `source_label` (e.g., `human`, `ai`). This label is saved to outputs but is not sent to the API.
- Optional: add `policy_id`. If missing, the evaluator tries to infer it from the text or filename.
- Optional: add `policy_contexts.json` in this folder with policy summaries keyed by `policy_id`.

## Outputs
- `comment_scores.jsonl` (one JSON per comment)
- `comment_scores.csv` (flat table for analysis)

## Analysis
- `comment_analysis.ipynb` compares scores by `source_label` and runs BERTopic per rationale field.
- It expects `comment_scores.csv` and `comment_scores.jsonl` in this folder.
- The analysis notebook infers missing `policy_id` values (especially for human labels) using docket ID patterns.

## Notes
- The notebook uses `RESUME = True` to skip files already scored in the JSONL output.
- Set `MAX_FILES = None` to process all comments.
- `.env` is ignored by git for safety.
