"""
merge_vague_memory_into_master.py

Adds the vague-memory reviews (the ones where somebody could only half-recall
the photo they wanted) into the master file, skipping any that are already
there.

WHY A SEPARATE STEP:
Those reviews were found by a different, much narrower filter than the one
that built the master file, so some of them were never picked up. This brings
the two together without disturbing anything already in the master.

WHAT IT DOES NOT DO:
- It does not touch existing rows.
- It does not add rows that are already present (matched on their URL).
- It takes a backup of the master first, so the merge can be undone.

A NOTE ON THE LABELS:
The rows being added have not been through the Gemini labelling run, so their
failure_type / memory_detail / photo_age / time_spent_searching are worked out
with the keyword rules from annotate_retrieval_reviews.py. Their match_reason
is set to "vague_memory_search" so you can always tell which rows arrived this
way, and re-label them later if you want.

HOW TO RUN THIS:
    python3 backend/scripts/merge_vague_memory_into_master.py

Input:  data/filtered_data/google_photos_vague_memory_search_failures.csv
        data/final_filtered_data/master_filtered_reviews_ai_labelled.csv
Output: the master file, updated (a .backup copy is written first)
"""

import csv
import importlib.util
import os
import shutil
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")

VAGUE_FILE = os.path.join(
    PROJECT_ROOT, "data", "filtered_data",
    "google_photos_vague_memory_search_failures.csv",
)
MASTER_FILE = os.path.join(
    PROJECT_ROOT, "data", "final_filtered_data",
    "master_filtered_reviews_ai_labelled.csv",
)
BACKUP_FILE = MASTER_FILE.replace(".csv", "_before_vague_merge.csv")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def load_annotator():
    """Reuses the keyword labelling rules rather than copying them."""
    path = os.path.join(SCRIPTS_DIR, "annotate_retrieval_reviews.py")
    spec = importlib.util.spec_from_file_location("annotate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    annotate = load_annotator()

    with open(MASTER_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        master = list(reader)

    with open(VAGUE_FILE, newline="", encoding="utf-8-sig") as f:
        vague = list(csv.DictReader(f))

    print(f"master: {len(master)} rows")
    print(f"vague-memory file: {len(vague)} rows")

    # Match on URL, falling back to the text itself for anything without one.
    seen_urls = {r["url"].strip() for r in master if r.get("url", "").strip()}
    seen_texts = {" ".join(r["text"].split())[:120] for r in master}

    added = []
    for row in vague:
        url = row.get("url", "").strip()
        key = " ".join(row.get("text", "").split())[:120]

        if (url and url in seen_urls) or key in seen_texts:
            continue

        text = row.get("text", "")
        record = {column: "" for column in columns}
        record.update({
            "source": row.get("source", ""),
            "date": row.get("date", ""),
            "rating": row.get("rating", ""),
            "engagement": row.get("engagement", ""),
            "text": text,
            "url": url,
            # Where this row came from, so it can always be told apart.
            "match_reason": "vague_memory_search",
        })

        # Keyword labels, since these rows never went through the AI run.
        labels = {
            "failure_type": annotate.classify_failure_type(text),
            "memory_detail": annotate.classify_memory_detail(text),
            "photo_age": annotate.classify_photo_age(text),
            "time_spent_searching": annotate.find_time_spent(text),
        }
        for name, value in labels.items():
            if name in record:
                record[name] = value
            rules_column = f"{name}_rules"
            if rules_column in record:
                record[rules_column] = value

        added.append(record)
        if url:
            seen_urls.add(url)
        seen_texts.add(key)

    if not added:
        print("\nNothing new to add - every row is already in the master.")
        return

    shutil.copyfile(MASTER_FILE, BACKUP_FILE)
    print(f"\nBacked up the master to {os.path.basename(BACKUP_FILE)}")

    with open(MASTER_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(master + added)

    print(f"Added {len(added)} new rows -> master now has {len(master) + len(added)}")
    print(f"Skipped {len(vague) - len(added)} that were already there\n")

    print("Added rows by source:")
    counts = {}
    for row in added:
        counts[row["source"]] = counts.get(row["source"], 0) + 1
    for name, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {name:<28} {count:>3}")


if __name__ == "__main__":
    main()
