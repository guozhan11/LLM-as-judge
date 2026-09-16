"""Context-parity sensitivity check for the Round 1 human comments.

Statt and Gemini comments were generated from agency-level personas with no specific docket, so the
evaluator saw only an agency name (e.g. "Policy ID: EPA") and no rule summary. Round 1 human comments
were scored with their exact docket ID and rule summary. This script rescores the same 298 human
comments (and the 633 AI comments) and writes them to separate files (the original outputs are untouched):

  agency_only    - policy ID = agency name, no summary (same information the AI comments received)
  full_context   - original setup, rerun as a test-retest control for evaluator noise
  ai_same_day    - Statt and Gemini comments rescored with their original inputs, so every source in the
                   comparison is scored in the same run (the evaluator drifted between runs)
  ai_agency_only - Statt and Gemini comments rescored with only the agency name from their source file
                   (the original Statt inputs sometimes carried a docket-like ID taken from the letter)

Round 2 human comments (the ~3,000 downloaded CSV comments) are also rescored under agency_only.

Usage: python rescore_context_sensitivity.py
"""
import json
import os
import re
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from jsonschema import Draft7Validator
from openai import OpenAI

BASE_DIR = Path(__file__).parent
OUTPUT_JSONL = BASE_DIR / "comment_scores_context_sensitivity.jsonl"
OUTPUT_CSV = BASE_DIR / "comment_scores_context_sensitivity.csv"
MODEL = "gpt-5.4-mini"
TEMPERATURE = 0.2
MAX_TOKENS = 1000
WORKERS = 8

# Same rubric, schema, and prompt as comment_evaluator.ipynb.
RUBRIC = {
    "relevance": "How directly the comment addresses the docket topic and requested issues.",
    "reasoning": "Logical coherence and clarity of arguments.",
    "evidence": "Use of facts, data, citations, or concrete examples.",
    "impact": "Specificity and plausibility of claimed impacts.",
    "actionability": "Provides clear, feasible recommendations or requests.",
    "structure_formatting": "Organization, readability, and professional formatting.",
    "overall": "Holistic quality across all criteria.",
}
_fields = {k: {"type": "integer", "minimum": 1, "maximum": 5} for k in RUBRIC}
VALIDATOR = Draft7Validator({
    "type": "object",
    "properties": {
        "scores": {"type": "object", "properties": _fields, "required": list(RUBRIC)},
        "rationales": {"type": "object", "properties": {k: {"type": "string"} for k in RUBRIC}, "required": list(RUBRIC)},
        "overall_summary": {"type": "string"},
    },
    "required": ["scores", "rationales", "overall_summary"],
})


def build_prompt(comment_text, policy_id=None, policy_context=None):
    rubric_lines = "\n".join([f"- {k}: {v}" for k, v in RUBRIC.items()])
    policy_block = ""
    if policy_id or policy_context:
        policy_block = textwrap.dedent(
            f"""
            Policy context:
            - Policy ID: {policy_id or "unknown"}
            - Summary: {policy_context or "(no summary provided)"}
            """
        )
    return textwrap.dedent(
        f"""
        You are evaluating a public comment letter. Score each criterion from 1 (poor) to 5 (excellent).
        Provide a short rationale per criterion and a brief overall summary.

        Criteria:
        {rubric_lines}

        {policy_block}
        Return ONLY valid JSON with this structure:
        {{
          "scores": {{"relevance": 1-5, "reasoning": 1-5, "evidence": 1-5, "impact": 1-5,
                      "actionability": 1-5, "structure_formatting": 1-5, "overall": 1-5}},
          "rationales": {{"relevance": "...", "reasoning": "...", "evidence": "...", "impact": "...",
                         "actionability": "...", "structure_formatting": "...", "overall": "..."}},
          "overall_summary": "..."
        }}

        Comment:
        """ + comment_text.strip()
    )


def extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in response")
        return json.loads(match.group(0))


def load_policy_contexts():
    contexts = json.loads((BASE_DIR / "policy_contexts.json").read_text(encoding="utf-8"))
    for html_path in sorted((BASE_DIR / "policy_context_html").glob("*.html")):
        policy_id = re.search(r"\bFDA-\d{4}-[A-Z]-\d{4}\b|\bEPA-[A-Z]{2}-[A-Z]{2}-\d{4}-\d{4}\b|\bFMCSA-\d{4}-\d{4}\b", html_path.name)
        if policy_id and not contexts.get(policy_id.group(0)):
            raw = html_path.read_text(encoding="utf-8", errors="ignore")
            text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.I | re.S)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"[ \t]+", " ", re.sub(r"\r\n?", "\n", text))
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if len(text) > 12000:  # same truncation rule as the evaluator notebook
                cut = text[:12000]
                last_break = max(cut.rfind("\n\n"), cut.rfind(". "))
                cut = cut[:last_break + 1] if last_break > 12000 * 0.65 else cut
                text = cut.strip() + "\n\n[Context truncated for prompt length.]"
            contexts[policy_id.group(0)] = text
    return contexts


def main():
    load_dotenv(BASE_DIR / ".env")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    contexts = load_policy_contexts()

    scores = pd.read_csv(BASE_DIR / "comment_scores.csv")
    round1_human = scores[
        scores["source_label"].str.lower().eq("human") & ~scores["file"].str.startswith("csv:", na=False)
    ]
    # The CSV collapses line breaks; the JSONL keeps the exact text that was originally sent.
    raw_text = {}
    for line in (BASE_DIR / "comment_scores.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("comment_text"):
            raw_text[rec["file"]] = rec["comment_text"]
    jobs = []
    for row in round1_human.itertuples():
        agency = row.policy_id.split("-")[0].upper()
        text = raw_text[row.file]
        jobs.append((row.file, "agency_only", text, agency, None))
        jobs.append((row.file, "full_context", text, row.policy_id, contexts.get(row.policy_id, "")))

    round2_human = scores[
        scores["source_label"].str.lower().eq("human") & scores["file"].str.startswith("csv:", na=False)
    ]
    for row in round2_human.itertuples():
        jobs.append((row.file, "agency_only", raw_text[row.file], row.policy_id.split("-")[0].upper(), None))

    ai_rows = scores[scores["source_label"].str.lower().isin(["statt", "gemini"])]
    for row in ai_rows.itertuples():
        text = raw_text[row.file]
        jobs.append((row.file, "ai_same_day", text, row.policy_id, contexts.get(row.policy_id, "")))
        # Parity condition: 188 Statt rows were originally sent a docket-like ID inferred from the letter text,
        # so send every AI comment the agency name from its source file, like Gemini and the human rescoring.
        agency = re.match(r"csv:([a-z]+)_", row.file).group(1).upper()
        jobs.append((row.file, "ai_agency_only", text, agency, None))

    done = set()
    if OUTPUT_JSONL.exists():
        for line in OUTPUT_JSONL.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if "scores" in rec:
                done.add((rec["file"], rec["condition"]))
    jobs = [j for j in jobs if (j[0], j[1]) not in done]
    print(f"{len(round1_human)} Round 1 human + {len(round2_human)} Round 2 human + {len(ai_rows)} AI comments; {len(jobs)} evaluations to run")

    def run(job):
        file, condition, text, policy_id, context = job
        response = client.responses.create(
            model=MODEL, input=build_prompt(text, policy_id, context),
            temperature=TEMPERATURE, max_output_tokens=MAX_TOKENS,
        )
        data = extract_json(response.output_text)
        errors = list(VALIDATOR.iter_errors(data))
        if errors:
            raise ValueError("; ".join(e.message for e in errors))
        return {"file": file, "condition": condition, "policy_id_sent": policy_id, **data}

    failures = 0
    with OUTPUT_JSONL.open("a", encoding="utf-8") as out, ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(run, job): job for job in jobs}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                out.write(json.dumps(future.result(), ensure_ascii=False) + "\n")
                out.flush()
            except Exception as exc:
                failures += 1
                print("FAILED", futures[future][:2], exc)
            if i % 250 == 0:
                print(f"{i}/{len(jobs)} done")
    print(f"finished; failures: {failures}")

    rows = []
    for line in OUTPUT_JSONL.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        flat = {"file": rec["file"], "condition": rec["condition"], "policy_id_sent": rec["policy_id_sent"],
                "overall_summary": rec["overall_summary"]}
        flat.update({f"score_{k}": v for k, v in rec["scores"].items()})
        flat.update({f"rationale_{k}": " ".join(v.split()) for k, v in rec["rationales"].items()})
        rows.append(flat)
    pd.DataFrame(rows).to_csv(OUTPUT_CSV, index=False)


if __name__ == "__main__":
    main()
