"""
filter_vague_memory_reviews.py

Pulls out the Play Store reviews where someone describes having only a PARTIAL
or VAGUE memory of a photo or video they are trying to get back to - they know
it exists, but not the date, the place, the album, or what they called it.

This is the heart of the research question, so the filter is deliberately
strict. Three things must all appear close together in the same sentence (or
the next one):

  1. MEMORY UNCERTAINTY - "can't remember", "forgot", "vaguely remember",
     "no idea when/where", "I know I have..."
  2. A PHOTO - photo, picture, video, album, screenshot...
  3. LOOKING FOR IT - find, search, locate, hunt, scroll...

All three matter. Without (3) the matches are mostly people fondly reminiscing
about the Memories feature; without (1) it is just an ordinary "can't find my
photos" complaint, with no evidence about what they remembered.

Known noise that is screened out: "no idea what Google changed", "long
forgotten memories", "forgot to back up" - these read like memory but are about
the app, not about recalling a photo.

Because this is a small, hand-checkable set, the output includes a
"matched_text" column showing the exact sentence that caused each match, so you
can confirm or discard each row quickly.

HOW TO RUN THIS:
    python3 backend/scripts/filter_vague_memory_reviews.py

Input:  data/raw_data/google_photos_playstore_reviews.csv
Output: data/filtered_data/google_photos_play_store_reviews_2409.csv
"""

import csv
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(
    PROJECT_ROOT, "data", "raw_data", "google_photos_playstore_reviews.csv"
)
OUTPUT_FILE = os.path.join(
    PROJECT_ROOT, "data", "filtered_data", "google_photos_play_store_reviews_2409.csv"
)

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# Judge a sentence together with the one after it, so "I took a photo of my car.
# I can't remember when." still reads as one thought.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
SENTENCE_WINDOW = 2

# 1. The memory is incomplete. Note "forgot(?!\s+to)": "forgot TO back up" is
#    forgetting an action, not failing to recall a photo.
MEMORY_UNCERTAIN = re.compile(
    r"\b(?:don'?t|do not|cannot|can'?t|couldn'?t|could not|never|hardly|barely)\s+"
    r"(?:remember|recall)\b"
    r"|\b(?:vaguely|barely|faintly|half|sort of|kinda)\s+(?:remember|recall)\b"
    r"|\bforgot(?:ten)?\b(?!\s+to\b)"
    r"|\bno idea\s+(?:when|where|which|what|who)\b"
    r"|\bi know i (?:have|had|took|saved|uploaded)\b"
    r"|\bcan'?t think of (?:the|its|what)\b",
    re.I,
)

# 2. It is a photo or video they are thinking of.
PHOTO_OBJECT = re.compile(
    r"\b(photo|photos|pic|pics|picture|pictures|image|images|video|videos|"
    r"album|albums|shot|shots|screenshot|screenshots)\b",
    re.I,
)

# 3. They are trying to get to it.
LOOKING_FOR = re.compile(
    r"\b(find|finding|found|locate|locating|search|searching|searched|"
    r"look for|looking for|looked for|retriev\w+|track down|pull up|"
    r"scroll|scrolling|scrolled|hunt|hunting|dig through|go through)\b",
    re.I,
)

# Wording that reads like memory but is really about the app itself.
NOT_ABOUT_A_PHOTO = re.compile(
    r"no idea what (?:google|they|the app|happened|to click)"
    r"|remember (?:how i|what i did|the steps)"
    r"|(?:long |newly )?forgotten memories"
    r"|reminds me|memories feature|this day last year|remember when\b",
    re.I,
)

# The detail they cannot recall - recorded so you can see WHAT was forgotten.
FORGOTTEN_DETAIL = [
    ("when it was taken", re.compile(r"\b(when|date|day|year|month|time)\b", re.I)),
    ("where it was taken", re.compile(r"\b(where|place|location|city|country)\b", re.I)),
    ("which album/folder", re.compile(r"\b(which|album|folder|which one)\b", re.I)),
    ("its name/keyword", re.compile(r"\b(name|title|called|keyword|word)\b", re.I)),
    ("who is in it", re.compile(r"\b(who|whose|person|people|face)\b", re.I)),
]


def find_evidence(text):
    """Returns (matched sentence, what was forgotten) or (None, None)."""
    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s and s.strip()]

    for i in range(len(sentences)):
        window = " ".join(sentences[i:i + SENTENCE_WINDOW])

        match = MEMORY_UNCERTAIN.search(window)
        if not match:
            continue
        if not PHOTO_OBJECT.search(window):
            continue
        if not LOOKING_FOR.search(window):
            continue
        if NOT_ABOUT_A_PHOTO.search(window):
            continue

        # What exactly could they not remember? Look just after the phrase.
        tail = window[match.end():match.end() + 80]
        forgotten = [name for name, pattern in FORGOTTEN_DETAIL if pattern.search(tail)]

        return " ".join(window.split()), "; ".join(forgotten) or "not stated"

    return None, None


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        rows = list(reader)

    print(f"Read {len(rows)} reviews from {os.path.basename(INPUT_FILE)}")

    kept = []
    for row in rows:
        evidence, forgotten = find_evidence(row.get("text", ""))
        if evidence:
            record = dict(row)
            record["matched_text"] = evidence
            record["forgotten_detail"] = forgotten
            kept.append(record)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(columns) + ["matched_text", "forgotten_detail"])
        writer.writeheader()
        writer.writerows(kept)

    print(f"Kept {len(kept)} reviews mentioning a vague or partial memory "
          f"({len(kept) / len(rows) * 100:.3f}% of the raw set)")
    print(f"Saved to data/filtered_data/{os.path.basename(OUTPUT_FILE)}\n")

    print("What people said they could not remember:")
    counts = {}
    for row in kept:
        for detail in row["forgotten_detail"].split("; "):
            counts[detail] = counts.get(detail, 0) + 1
    for detail, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {detail:<22} {count:>3}")

    print("\nBy star rating:")
    stars = {}
    for row in kept:
        stars[row["rating"]] = stars.get(row["rating"], 0) + 1
    for rating in sorted(stars):
        print(f"  {rating} star: {stars[rating]}")


if __name__ == "__main__":
    main()
