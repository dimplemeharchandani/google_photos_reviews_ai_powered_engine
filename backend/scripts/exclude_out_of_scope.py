"""
exclude_out_of_scope.py

Splits the labelled master file into the rows that belong to this research
project and the rows that do not.

WHY:
The project is about people SEARCHING for a photo they remember having. A large
share of the collected feedback is really about something else: photos that
vanished, were deleted, or were lost by a sync problem, where the person never
describes looking for anything. That is data loss, not retrieval failure.
Mixing the two makes the findings wrong - answers end up blaming search for
problems that search never caused.

HOW A ROW IS JUDGED:
By the AI label "failure_type". A row is out of scope when it is labelled
"photos missing (no search attempted)". That label is produced by
ai_label_reviews.py, which is explicitly asked "did this person try to FIND a
photo?" - a judgement keyword rules cannot make reliably, because "I can't find
my photos" can mean either "I searched and got nothing" or "they are gone".

NOTHING IS DELETED. The excluded rows are written to their own file so they can
be counted, reported, or put back.

HOW TO RUN THIS:
    python3 backend/scripts/exclude_out_of_scope.py

Input:  data/final_filtered_data/master_filtered_reviews_ai_labelled.csv
Output: data/final_filtered_data/master_search_scope.csv      (used from here on)
        data/final_filtered_data/master_excluded_data_loss.csv (kept for the record)
"""

import csv
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL_DIR = os.path.join(PROJECT_ROOT, "data", "final_filtered_data")

INPUT_FILE = os.path.join(FINAL_DIR, "master_filtered_reviews_ai_labelled.csv")
IN_SCOPE_FILE = os.path.join(FINAL_DIR, "master_search_scope.csv")
EXCLUDED_FILE = os.path.join(FINAL_DIR, "master_excluded_data_loss.csv")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# The label that means "this is data loss, not a search failure".
OUT_OF_SCOPE_LABEL = "photos missing (no search attempted)"


def main():
    if not os.path.exists(INPUT_FILE):
        raise SystemExit(
            f"No {os.path.basename(INPUT_FILE)} found.\n"
            "Run ai_label_reviews.py first - this script sorts rows using its labels."
        )

    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        rows = list(reader)

    if "failure_type" not in (columns or []):
        raise SystemExit("That file has no failure_type column - nothing to sort by.")

    labels = {row.get("failure_type", "") for row in rows}
    if OUT_OF_SCOPE_LABEL not in labels:
        print("WARNING: no row carries the label")
        print(f'         "{OUT_OF_SCOPE_LABEL}"')
        print("         This file was probably labelled BEFORE that category existed.")
        print("         Re-run ai_label_reviews.py, or nothing will be excluded.\n")

    in_scope = [r for r in rows if r.get("failure_type") != OUT_OF_SCOPE_LABEL]
    excluded = [r for r in rows if r.get("failure_type") == OUT_OF_SCOPE_LABEL]

    for path, subset in ((IN_SCOPE_FILE, in_scope), (EXCLUDED_FILE, excluded)):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(subset)

    total = len(rows)
    print(f"Read {total} labelled rows\n")
    print(f"  IN SCOPE (search/retrieval) : {len(in_scope):>5}  "
          f"({len(in_scope)/total*100:.1f}%)  -> {os.path.basename(IN_SCOPE_FILE)}")
    print(f"  EXCLUDED (data loss)        : {len(excluded):>5}  "
          f"({len(excluded)/total*100:.1f}%)  -> {os.path.basename(EXCLUDED_FILE)}")

    if excluded:
        print("\nExcluded rows by source:")
        counts = {}
        for row in excluded:
            counts[row["source"]] = counts.get(row["source"], 0) + 1
        for source, count in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  {source:<28} {count:>5}")

    print("\nWhat remains, by failure type:")
    counts = {}
    for row in in_scope:
        counts[row["failure_type"]] = counts.get(row["failure_type"], 0) + 1
    for label, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {label:<38} {count:>5}")

    print("\nNext: rebuild the model from the in-scope rows with")
    print("  python3 backend/scripts/step1_ingest.py")
    print("  python3 backend/scripts/step2_embed.py")


if __name__ == "__main__":
    main()
