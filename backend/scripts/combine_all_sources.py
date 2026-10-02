"""
combine_all_sources.py

Combines the four filtered sources (Play Store, Reddit, YouTube, Google Photos
community forum) into ONE master file where every row has the same columns,
no matter which website it came from.

THE MASTER COLUMNS:
    source        "Google Play Store" / "Reddit" / "YouTube" /
                  "Google Photos Community"
    date          normalised to YYYY-MM-DD so the column can be sorted
    rating        STAR RATING only (1-5). Play Store rows only; blank elsewhere,
                  because Reddit and YouTube have no star ratings.
    engagement    Reddit upvotes / YouTube likes. Kept SEPARATE from rating on
                  purpose: "40 likes" and "1 star" are completely different
                  things and must not be mixed into one column.
    text          what the person actually wrote. For the forum, the post title
                  and body are joined together.
    url           link back to the original post, so anything can be checked.

    match_reason        which retrieval rule caught this row
    failure_type        what specifically went wrong with the search
    memory_detail       how much the person remembered about the photo
    photo_age           how old the wanted photo seems to be
    time_spent_searching  how long they said they searched, in their words

The last five columns are worked out for EVERY row using the same rules that
were used on the Play Store reviews, so the whole master file is labelled
consistently rather than only one quarter of it.

HOW TO RUN THIS:
    python3 scripts/combine_all_sources.py

Output: data/final_filtered_data/master_filtered_reviews.csv
"""

import csv
import importlib.util
import os
import re
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
FILTERED_DIR = os.path.join(PROJECT_ROOT, "data", "filtered_data")

# The finished, combined file lives in its own folder, so it is easy to find
# and never mixed up with the per-source filtered files it was built from.
FINAL_DIR = os.path.join(PROJECT_ROOT, "data", "final_filtered_data")
OUTPUT_FILE = os.path.join(FINAL_DIR, "master_filtered_reviews.csv")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

MASTER_COLUMNS = [
    "source",
    "date",
    "rating",
    "engagement",
    "text",
    "url",
    "match_reason",
    "failure_type",
    "memory_detail",
    "photo_age",
    "time_spent_searching",
]


def load_script(filename):
    """Imports one of our other scripts so we can reuse its rules instead of
    copying and pasting them (which would let the two drift apart)."""
    path = os.path.join(SCRIPTS_DIR, filename)
    spec = importlib.util.spec_from_file_location(filename[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


annotate = load_script("annotate_retrieval_reviews.py")
other_filter = load_script("filter_other_sources.py")


# ---------------------------------------------------------------------------
# Dates arrive in four different shapes. Turn them all into YYYY-MM-DD.
# ---------------------------------------------------------------------------
DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",      # Play Store: 2026-09-19 06:10:36
    "%Y-%m-%dT%H:%M:%SZ",     # YouTube:    2021-07-01T21:26:53Z
    "%b %d, %Y",              # Forum:      Aug 26, 2026
    "%B %d, %Y",              # Forum:      August 26, 2026
    "%b %d, %y",              # Forum:      Dec 10, 25
    "%d-%b-%Y",               # Forum:      13-Jan-2025
    "%d-%B-%Y",               # Forum:      13-January-2025
    "%d-%b-%y",               # Forum:      13-Jan-25
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
]


def normalise_date(raw):
    """Returns the date as YYYY-MM-DD, or the original text if it cannot be
    understood (better to keep something than to silently lose it)."""
    if not raw:
        return ""

    text = str(raw).strip()

    # Reddit style: 2026-05-20T16:57:44.598000+0000 - Python needs the
    # timezone written as +00:00, and cannot handle 6-digit microseconds here.
    iso = re.sub(r"(\+\d{2})(\d{2})$", r"\1:\2", text)
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d")
    except ValueError:
        pass

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Last resort: if it simply starts with a date, take that.
    match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)

    return text


def join_title_and_body(title, body):
    """Joins a post title and its body, the same way the Reddit export does."""
    title = (title or "").strip()
    body = (body or "").strip()
    if title and body:
        # Don't repeat the title if the body already opens with it.
        if body.lower().startswith(title.lower()[:40]):
            return body
        return f"{title} - {body}"
    return title or body


# ---------------------------------------------------------------------------
# Each source, and how to read one of its rows into the master shape
# ---------------------------------------------------------------------------
def from_play_store(row):
    return {
        "source": "Google Play Store",
        "date": normalise_date(row.get("date")),
        "rating": row.get("rating", ""),
        "engagement": "",
        "text": (row.get("text") or "").strip(),
        "url": row.get("url", ""),
        # This source was already labelled, so keep the existing labels.
        "match_reason": row.get("match_reason", ""),
        "failure_type": row.get("failure_type", ""),
        "memory_detail": row.get("memory_detail", ""),
        "photo_age": row.get("photo_age", ""),
        "time_spent_searching": row.get("time_spent_searching", ""),
    }


def from_reddit(row):
    # Reddit's "text" already holds "title - body" from the export.
    return {
        "source": "Reddit",
        "date": normalise_date(row.get("date")),
        "rating": "",
        "engagement": row.get("score", ""),
        "text": (row.get("text") or "").strip(),
        "url": row.get("url", ""),
    }


def from_youtube(row):
    return {
        "source": "YouTube",
        "date": normalise_date(row.get("date")),
        "rating": "",
        "engagement": row.get("likes", ""),
        "text": (row.get("text") or "").strip(),
        "url": row.get("url", ""),
    }


def from_forum(row):
    return {
        "source": "Google Photos Community",
        "date": normalise_date(row.get("Date")),
        "rating": "",
        "engagement": "",
        "text": join_title_and_body(row.get("Post Title"), row.get("Full text")),
        "url": row.get("URL", ""),
    }


SOURCES = [
    ("google_photos_retrieval_failure_reviews_annotated.csv", from_play_store, True),
    ("reddit_googlephotos_formatted_filtered.csv", from_reddit, False),
    ("youtube_comments_all_filtered.csv", from_youtube, False),
    ("reviews - Google Photos Community_Support Forum_filtered.csv", from_forum, False),
]


def add_labels(record):
    """Works out the five label columns for a row that doesn't have them yet,
    using exactly the same rules applied to the Play Store reviews."""
    text = record["text"]

    reasons = other_filter.classify(text)
    record["match_reason"] = "; ".join(reasons)
    record["failure_type"] = annotate.classify_failure_type(text)
    record["memory_detail"] = annotate.classify_memory_detail(text)
    record["photo_age"] = annotate.classify_photo_age(text)
    record["time_spent_searching"] = annotate.find_time_spent(text)
    return record


def main():
    all_rows = []
    counts = {}

    for filename, convert, already_labelled in SOURCES:
        path = os.path.join(FILTERED_DIR, filename)
        if not os.path.exists(path):
            print(f"SKIPPED (not found): {filename}")
            continue

        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))

        converted = []
        for row in rows:
            record = convert(row)
            if not record["text"]:
                continue  # nothing was written, so there is nothing to study
            if not already_labelled:
                record = add_labels(record)
            converted.append(record)

        all_rows.extend(converted)
        counts[converted[0]["source"] if converted else filename] = len(converted)

    os.makedirs(FINAL_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=MASTER_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    print("Rows contributed by each source:")
    for source, count in counts.items():
        print(f"  {source:<28} {count:>5}")
    print(f"  {'-' * 28} {'-' * 5}")
    print(f"  {'TOTAL':<28} {len(all_rows):>5}")
    print(f"\nSaved to data/final_filtered_data/{os.path.basename(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()
