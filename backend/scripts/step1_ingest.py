"""
step1_ingest.py

Step 1 of the retrieval pipeline.

What this script does (in plain words):
1. Reads the MASTER file with pandas - all four sources in one place
   (Google Play Store reviews, Reddit posts, YouTube comments, and posts from
   the Google Photos community forum).
2. Turns each row into one or more "documents" (chunks) - readable text that
   combines what the person wrote with its failure_type, memory_detail and
   photo_age labels. Any label whose value is "not specified" is left out, so
   chunks only carry real information.
3. SPLITS LONG POSTS. The embedding model in step 2 only reads roughly the
   first 1,000 characters of any text. Most reviews are far shorter than that,
   but Reddit posts often are not - so a long post is cut into overlapping
   pieces. Every piece keeps the same url/date/source, so a quote from halfway
   down a long post is still traceable to the original.
4. Keeps url, source, date, rating and engagement alongside each chunk as
   "metadata", so later steps can show a proper citation.
5. Saves the whole list to vector_db/chunks.pkl using pickle, ready for step 2.

HOW TO RUN THIS:
    pip3 install pandas
    python3 scripts/step1_ingest.py

Input:  data/final_filtered_data/master_filtered_reviews.csv
Output: vector_db/chunks.pkl
"""

import os
import pickle
import re

import pandas as pd

# The project folder, worked out from where THIS file sits. Everything is
# located relative to that, so the script works no matter which folder you run
# it from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FILE = os.path.join(
    PROJECT_ROOT, "data", "final_filtered_data", "master_filtered_reviews.csv"
)
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "vector_db", "chunks.pkl")

# Which file to build the model from. The first one that exists wins:
#   1. master_search_scope.csv  - data-loss rows already removed (best)
#   2. master_filtered_reviews_ai_labelled.csv - AI labels, all rows
#   3. master_filtered_reviews.csv - keyword labels only
PREFERRED_FILES = [
    os.path.join(PROJECT_ROOT, "data", "final_filtered_data", "master_search_scope.csv"),
    os.path.join(
        PROJECT_ROOT, "data", "final_filtered_data",
        "master_filtered_reviews_ai_labelled.csv",
    ),
]

# How big one chunk may get, in characters, and how much neighbouring chunks
# overlap. The overlap matters: without it, a sentence split across the join
# would be lost to the search.
MAX_CHUNK_CHARS = 900
OVERLAP_CHARS = 150

# What to call the writer of each source, so the text reads naturally and the
# AI in step 3 knows where a quote came from.
SOURCE_LABEL = {
    "Google Play Store": "Google Play Store review",
    "Reddit": "Reddit post",
    "YouTube": "YouTube comment",
    "Google Photos Community": "Google Photos Community forum post",
}

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def tidy_number(value):
    """pandas reads a column with blanks as decimals, so a 1-star rating
    arrives as "1.0". Show it as "1"."""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return "" if text.lower() in ("nan", "none") else text


def split_long_text(text):
    """Splits text into overlapping pieces of at most MAX_CHUNK_CHARS.

    It tries to break at the end of a sentence so each piece still reads as
    proper English, and only cuts mid-sentence when a single sentence is
    itself longer than the limit.
    """
    text = text.strip()
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    sentences = SENTENCE_END.split(text)

    pieces = []
    current = ""
    for sentence in sentences:
        # A single enormous sentence has to be cut by length.
        while len(sentence) > MAX_CHUNK_CHARS:
            if current:
                pieces.append(current.strip())
                current = ""
            pieces.append(sentence[:MAX_CHUNK_CHARS].strip())
            sentence = sentence[MAX_CHUNK_CHARS - OVERLAP_CHARS:]

        if len(current) + len(sentence) + 1 <= MAX_CHUNK_CHARS:
            current = f"{current} {sentence}".strip()
        else:
            pieces.append(current.strip())
            # Start the next piece with the tail of this one, so nothing is
            # lost at the seam between two chunks.
            tail = current[-OVERLAP_CHARS:]
            current = f"{tail} {sentence}".strip()

    if current.strip():
        pieces.append(current.strip())

    return [p for p in pieces if p]


def build_chunk_text(piece, row, part_number, total_parts):
    """Combines one piece of text with its labels into a readable chunk.

    Labels that say "not specified" are left out completely. They carry no
    information, and because most rows are unlabelled, repeating that same
    phrase on nearly every chunk would make all the chunks look more alike
    than they really are - which makes the meaning-based search less accurate.
    """
    label = SOURCE_LABEL.get(str(row["source"]).strip(), "User review")

    if total_parts > 1:
        opening = f"{label} (part {part_number} of {total_parts}): {piece}"
    else:
        opening = f"{label}: {piece}"

    parts = [opening.rstrip(".") + "."]

    tags = [
        ("Failure type", row.get("failure_type", "")),
        ("Memory detail", row.get("memory_detail", "")),
        ("Photo age", row.get("photo_age", "")),
        ("Time spent searching", row.get("time_spent_searching", "")),
    ]
    for name, value in tags:
        value = str(value).strip()
        if value and value.lower() not in ("not specified", "not mentioned"):
            parts.append(f"{name}: {value}.")

    return " ".join(parts)


def main():
    # Use the best available version of the master file.
    input_file = next((p for p in PREFERRED_FILES if os.path.exists(p)), INPUT_FILE)

    df = pd.read_csv(input_file, encoding="utf-8-sig")
    print(f"Read {len(df)} rows from {os.path.basename(input_file)}")
    if input_file.endswith("master_search_scope.csv"):
        print("  (data-loss rows already excluded - search/retrieval only)")
    elif input_file.endswith("_ai_labelled.csv"):
        print("  (AI-labelled version - richer labels, but data-loss rows still included)")

    # Blank cells come back from pandas as NaN, which would print as "nan" in
    # the middle of a sentence. Turn them into plain text instead.
    df = df.fillna("")

    chunks = []
    split_rows = 0

    for _, row in df.iterrows():
        text = str(row["text"]).strip()
        if not text:
            continue

        pieces = split_long_text(text)
        if len(pieces) > 1:
            split_rows += 1

        for number, piece in enumerate(pieces, start=1):
            chunks.append(
                {
                    "chunk_text": build_chunk_text(piece, row, number, len(pieces)),
                    "metadata": {
                        "url": str(row["url"]),
                        "source": str(row["source"]),
                        "date": str(row["date"]),
                        "rating": tidy_number(row.get("rating", "")),
                        "engagement": tidy_number(row.get("engagement", "")),
                        # Which piece of a long post this is (1 of 1 for short ones).
                        "part": f"{number}/{len(pieces)}",
                    },
                }
            )

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "wb") as f:
        pickle.dump(chunks, f)

    print(f"Created {len(chunks)} chunks from {len(df)} rows")
    print(f"  ({split_rows} long posts were split into several chunks)")
    print(f"Saved them to {OUTPUT_FILE}\n")

    print("Chunks per source:")
    counts = {}
    for chunk in chunks:
        source = chunk["metadata"]["source"]
        counts[source] = counts.get(source, 0) + 1
    for source, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {source:<28} {count:>5}")

    print("\nPreview of the first 2 chunks:")
    print("=" * 72)
    for i, chunk in enumerate(chunks[:2], start=1):
        print(f"\nCHUNK {i}")
        print("-" * 72)
        print("chunk_text:")
        print(f"  {chunk['chunk_text'][:400]}")
        print("metadata:")
        for key, value in chunk["metadata"].items():
            print(f"  {key:<11} {value}")
    print("=" * 72)


if __name__ == "__main__":
    main()
