"""
ai_label_reviews.py

Re-labels the master file using Gemini instead of keyword rules.

WHY THIS EXISTS:
The keyword-based labels left failure_type as "not specified" for 93% of rows
and memory_detail for about 90%. That is not a bug - most people simply do not
spell out HOW their search failed - but it means the analysis columns are
mostly empty. Recognising that "I know I took it at some barbecue but no idea
when" is a vague memory needs reading comprehension, not pattern matching.
So this script asks Gemini to read each row and label it.

WHAT IT PRODUCES:
A copy of the master file with four columns replaced by AI labels, plus the
originals kept alongside (suffix "_rules") so you can compare the two methods -
useful evidence for a write-up.

HOW IT AVOIDS WASTING YOUR FREE QUOTA:
- Rows are sent in BATCHES (many rows per request), so 1,536 rows cost about
  100 requests rather than 1,536.
- Progress is SAVED AFTER EVERY BATCH. If it stops - crash, rate limit, closed
  laptop - just run it again and it carries on from where it left off instead
  of paying for the same rows twice.

HOW TO RUN THIS:
    export GEMINI_API_KEY="your-key-here"
    python3 scripts/ai_label_reviews.py

    # try a small run first to check label quality:
    python3 scripts/ai_label_reviews.py --limit 50

Input:  data/final_filtered_data/master_filtered_reviews.csv
Output: data/final_filtered_data/master_filtered_reviews_ai_labelled.csv
        data/final_filtered_data/.ai_label_cache.json   (progress, safe to delete)
"""

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
FINAL_DIR = os.path.join(PROJECT_ROOT, "data", "final_filtered_data")

OUTPUT_FILE = os.path.join(FINAL_DIR, "master_filtered_reviews_ai_labelled.csv")

# Normally the plain master (built by combine_all_sources.py) is the input.
# Only one master file is kept now, so if the plain one is not there we read
# the labelled master instead - it holds the same reviews, and re-running
# simply refreshes the labels on them.
_PLAIN_MASTER = os.path.join(FINAL_DIR, "master_filtered_reviews.csv")
INPUT_FILE = _PLAIN_MASTER if os.path.exists(_PLAIN_MASTER) else OUTPUT_FILE
CACHE_FILE = os.path.join(FINAL_DIR, ".ai_label_cache.json")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# How many rows to put in one request. Bigger = fewer requests = less waiting,
# but too big and the model starts losing track of which answer belongs to
# which row. 15 is a safe middle.
BATCH_SIZE = 15

# Seconds to wait between requests, to stay inside the free tier's limit.
SECONDS_BETWEEN_BATCHES = 13

# Very long posts are trimmed before sending, to keep requests small. The
# opening of a post almost always contains the complaint.
MAX_CHARS_PER_ROW = 1200

# The only answers the AI is allowed to give.
ALLOWED = {
    "failure_type": [
        "no results found",
        "wrong results shown",
        "too many irrelevant results",
        "gave up searching",
        "found after long struggle",
        "feature missing/unclear",
        # For the very common case of "my photos vanished" - which is data
        # loss, NOT a search failure. Keeping it as its own answer stops it
        # being mislabelled as "no results found", which happened on the
        # first pass and made the whole column untrustworthy.
        "photos missing (no search attempted)",
        "not specified",
    ],
    "memory_detail": [
        "vague memory (event/feeling only)",
        "partial memory (rough time or place)",
        "specific memory (exact date/keyword/person)",
        "not specified",
    ],
    "photo_age": [
        "old (years ago)",
        "recent (weeks/months)",
        "not specified",
    ],
}

LABEL_COLUMNS = ["failure_type", "memory_detail", "photo_age", "time_spent_searching"]

PROMPT_TEMPLATE = """You are labelling real user feedback about Google Photos search and retrieval problems, for academic research into how people look for photos they only half-remember.

For EACH numbered item below, decide four things. Use ONLY what the text actually says - never guess or infer beyond the words. When the text does not make something clear, say "not specified". A high number of "not specified" answers is expected and correct; inventing labels would ruin the research.

1. failure_type - what specifically went wrong. Exactly one of:
{failure_types}

   CRITICAL RULE for failure_type. Only use a SEARCH failure type (no results found / wrong results shown / too many irrelevant results / gave up searching / found after long struggle) when the text shows the person ACTUALLY TRIED TO LOOK for something - they searched, typed a keyword, browsed, scrolled looking for it, or used the search bar.

   - If photos simply vanished, were deleted, or are missing, and the person never describes looking for them, use "photos missing (no search attempted)". Do NOT call that "no results found". "No results found" means a search was run and came back empty.
   - If the complaint is about a button, menu, setting or feature being hard to find or missing - not about finding a PHOTO - use "feature missing/unclear".
   - If the text is praise, or a general complaint with no search and no missing photos, use "not specified".

   Ask yourself: "did this person try to FIND a photo?" If you cannot tell from the words, the answer is "not specified".

2. memory_detail - how much the person seems to remember about the photo or video they wanted. Exactly one of:
{memory_details}

3. photo_age - how old the wanted photo/video seems to be. Exactly one of:
{photo_ages}

4. time_spent_searching - if they say how long they spent LOOKING for it (e.g. "20 minutes", "hours", "forever"), copy that phrase exactly as written. Careful: a duration about something else - how old a photo is ("10 years ago"), how long a backup took, how long until deletion - is NOT time spent searching. If they do not say, write "not mentioned".

Reply with ONLY a JSON array, one object per item, in the same order, like:
[{{"id": 1, "failure_type": "...", "memory_detail": "...", "photo_age": "...", "time_spent_searching": "..."}}]

No explanation, no markdown fences - just the JSON array.

ITEMS:
{items}"""


def load_step3():
    """Reuses the API set-up, model fallback and retry logic already written
    and tested in step3_query.py, instead of writing it a second time."""
    path = os.path.join(SCRIPTS_DIR, "step3_query.py")
    spec = importlib.util.spec_from_file_location("step3_query", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row_key(row):
    """A stable id for a row, so we can remember which ones are already done."""
    raw = f"{row.get('url','')}|{row.get('text','')[:120]}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            print("(progress file unreadable - starting fresh)")
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def build_prompt(batch):
    items = []
    for number, row in enumerate(batch, start=1):
        text = " ".join(str(row.get("text", "")).split())[:MAX_CHARS_PER_ROW]
        items.append(f"{number}. [{row.get('source','')}] {text}")

    return PROMPT_TEMPLATE.format(
        failure_types="\n".join(f"   - {v}" for v in ALLOWED["failure_type"]),
        memory_details="\n".join(f"   - {v}" for v in ALLOWED["memory_detail"]),
        photo_ages="\n".join(f"   - {v}" for v in ALLOWED["photo_age"]),
        items="\n\n".join(items),
    )


def parse_reply(reply, expected_count):
    """Turns the AI's reply into a list of label dictionaries.

    Anything the AI gets wrong - missing rows, invented categories, wrapping the
    JSON in markdown - is corrected here rather than being written into your
    data. A row we cannot read a valid answer for stays "not specified".
    """
    blank = {
        "failure_type": "not specified",
        "memory_detail": "not specified",
        "photo_age": "not specified",
        "time_spent_searching": "not mentioned",
    }
    results = [dict(blank) for _ in range(expected_count)]

    match = re.search(r"\[.*\]", reply or "", re.S)
    if not match:
        return results, False

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return results, False

    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        try:
            index = int(entry.get("id", 0)) - 1
        except (TypeError, ValueError):
            continue
        if not 0 <= index < expected_count:
            continue

        for column in ("failure_type", "memory_detail", "photo_age"):
            value = str(entry.get(column, "")).strip()
            # Only accept one of the allowed answers.
            if value in ALLOWED[column]:
                results[index][column] = value

        spent = str(entry.get("time_spent_searching", "")).strip()
        results[index]["time_spent_searching"] = spent or "not mentioned"

    return results, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="only label the first N rows (for a cheap trial run)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        original_columns = reader.fieldnames
        rows = list(reader)

    if args.limit:
        rows = rows[:args.limit]
    print(f"Read {len(rows)} rows from {os.path.basename(INPUT_FILE)}")

    cache = load_cache()
    todo = [row for row in rows if row_key(row) not in cache]
    print(f"Already labelled in a previous run: {len(rows) - len(todo)}")
    print(f"Still to do: {len(todo)}")

    if todo:
        step3 = load_step3()
        from google import genai

        client = genai.Client(api_key=step3.get_api_key())
        runner = step3.GeminiRunner(client, step3.MODEL_NAME)
        print(f"Using Gemini model '{step3.MODEL_NAME}'")

        batches = [todo[i:i + args.batch_size] for i in range(0, len(todo), args.batch_size)]
        estimate = len(batches) * SECONDS_BETWEEN_BATCHES / 60
        print(f"{len(batches)} requests to make - roughly {estimate:.0f} minutes\n")

        failures = 0
        for number, batch in enumerate(batches, start=1):
            reply = step3.generate_with_retry(runner, build_prompt(batch))
            labels, ok = parse_reply(reply, len(batch))

            if not ok:
                failures += 1
                print(f"  batch {number}/{len(batches)}: could not read the reply "
                      f"- these {len(batch)} rows stay unlabelled")
            else:
                for row, label in zip(batch, labels):
                    cache[row_key(row)] = label
                labelled = sum(1 for l in labels if l["failure_type"] != "not specified")
                print(f"  batch {number}/{len(batches)}: done "
                      f"({labelled}/{len(batch)} had a clear failure type)")

            save_cache(cache)  # never lose more than one batch of work

            if number < len(batches):
                time.sleep(SECONDS_BETWEEN_BATCHES)

        if failures:
            print(f"\n{failures} batch(es) could not be read. Re-run to retry just those.")

    # ---------------------------------------------------------------------
    # Write the output: AI labels in the main columns, rule labels kept too
    # ---------------------------------------------------------------------
    new_columns = list(original_columns)
    for column in LABEL_COLUMNS:
        rules_column = f"{column}_rules"
        if rules_column not in new_columns:
            new_columns.insert(new_columns.index(column) + 1, rules_column)

    written = []
    for row in rows:
        record = dict(row)
        labels = cache.get(row_key(row))
        for column in LABEL_COLUMNS:
            record[f"{column}_rules"] = row.get(column, "")
            if labels:
                record[column] = labels[column]
        written.append(record)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=new_columns)
        writer.writeheader()
        writer.writerows(written)

    print(f"\nSaved {len(written)} rows to "
          f"data/final_filtered_data/{os.path.basename(OUTPUT_FILE)}")

    # A before/after comparison, which is the interesting part.
    print("\nHow much the AI labelled, compared with the keyword rules:")
    for column in ("failure_type", "memory_detail", "photo_age"):
        ai = sum(1 for r in written if r[column] not in ("not specified", ""))
        rules = sum(1 for r in written if r[f"{column}_rules"] not in ("not specified", ""))
        print(f"  {column:<16} rules: {rules:>5}   AI: {ai:>5}   (of {len(written)})")

    ai_time = sum(1 for r in written if r["time_spent_searching"] not in ("not mentioned", ""))
    rules_time = sum(1 for r in written if r["time_spent_searching_rules"] not in ("not mentioned", ""))
    print(f"  {'time_spent':<16} rules: {rules_time:>5}   AI: {ai_time:>5}   (of {len(written)})")


if __name__ == "__main__":
    main()
