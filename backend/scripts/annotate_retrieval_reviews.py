"""
annotate_retrieval_reviews.py

What this script does (in plain words):
Reads the filtered retrieval-failure reviews and adds FOUR new columns that
describe what each review actually says:

  1. failure_type          - what specifically went wrong with the search
  2. memory_detail         - how much the user seems to remember about the photo
  3. photo_age             - how old the photo/video seems to be
  4. time_spent_searching  - the exact phrase, if they said how long they spent

IMPORTANT - how honest this is:
This reads the words in each review; it does not "understand" them. When a
review does not clearly say something, the column is filled with "not specified"
(or "not mentioned") rather than a guess. Expect a LOT of "not specified" - most
reviews simply do not describe their search in that much detail, and a blank
answer is more useful to your research than an invented one.

A note on time_spent_searching: most time phrases in these reviews are NOT about
time spent searching. "10 years ago" is the age of the photo, "60 days" is the
trash retention period. So a duration only counts here when it sits next to a
searching word (searching, looking, scrolling, digging...).

HOW TO RUN THIS:
    python3 scripts/annotate_retrieval_reviews.py

Input:  data/filtered_data/google_photos_retrieval_failure_reviews.csv
Output: data/filtered_data/google_photos_retrieval_failure_reviews_annotated.csv
        (the original file is left untouched)
"""

import csv
import os
import re

# The project folder, worked out from where THIS file sits. Everything is
# located relative to that, so the script works no matter which folder you run
# it from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FILE = os.path.join(
    PROJECT_ROOT, "data", "filtered_data", "google_photos_retrieval_failure_reviews.csv"
)
OUTPUT_FILE = os.path.join(
    PROJECT_ROOT, "data", "filtered_data",
    "google_photos_retrieval_failure_reviews_annotated.csv",
)


# ---------------------------------------------------------------------------
# COLUMN 1: failure_type - what went wrong with the search
# ---------------------------------------------------------------------------
# Checked in this order; the FIRST one that matches wins. The order matters:
# "I searched for ages and gave up" should be recorded as giving up, which is a
# stronger statement than simply struggling.
FAILURE_TYPE_RULES = [
    (
        "gave up searching",
        re.compile(
            r"\b(gave up|give up|given up|stopped (?:trying|looking|searching)|"
            r"not worth (?:the|it)|forget it|no point (?:in )?(?:trying|looking|searching)|"
            r"had to give up)\b",
            re.I,
        ),
    ),
    (
        "found after long struggle",
        re.compile(
            r"\b(finally|eventually|in the end|at last)\b[^.!?]{0,50}?"
            r"\b(found|find|located|managed)\b"
            r"|\b(found|find|located)\b[^.!?]{0,30}?"
            r"\b(after (?:hours|ages|a while|a long time|much|a lot of)|eventually|finally)\b"
            r"|\btook me\b[^.!?]{0,40}?\b(to find|to locate|of digging|searching|looking)\b",
            re.I,
        ),
    ),
    (
        "no results found",
        re.compile(
            r"\b(no results?|zero results?|nothing (?:comes|came|show|shows|showed|appears|appeared)"
            r"|comes? up (?:empty|blank|with nothing)|returns? nothing|finds? nothing"
            r"|doesn'?t (?:find|return|show) any|shows? nothing|empty results?"
            r"|not (?:a )?single (?:result|photo|picture)|never (?:finds|shows) (?:it|them|anything))\b",
            re.I,
        ),
    ),
    (
        "too many irrelevant results",
        re.compile(
            r"\b(too many|thousands of|hundreds of|endless|floods? of|swamped|buried)\b"
            r"[^.!?]{0,40}?\b(results?|photos?|pictures?|images?|junk|stuff)\b"
            r"|\b(results?|search)\b[^.!?]{0,30}?\b(cluttered|overwhelming|flooded)\b",
            re.I,
        ),
    ),
    (
        "wrong results shown",
        re.compile(
            r"\b(wrong|irrelevant|unrelated|random|nonsense|garbage|junk|rubbish|useless)\b"
            r"[^.!?]{0,30}?\b(results?|photos?|pictures?|images?|stuff|things)\b"
            r"|\b(search|searching|results?)\b[^.!?]{0,40}?"
            r"\b(wrong|irrelevant|unrelated|random|nothing to do with|not what i|"
            r"all kinds of|anything but)\b"
            r"|\bshows?\b[^.!?]{0,25}?\b(wrong|random|irrelevant|unrelated)\b",
            re.I,
        ),
    ),
    (
        "feature missing/unclear",
        re.compile(
            r"\b(no (?:search|filter|sort) (?:option|function|feature|bar|button)|"
            r"search (?:bar|button|option|feature)\b[^.!?]{0,25}?\b(gone|missing|removed|disappeared|"
            r"hidden|not (?:there|available)|can'?t (?:be )?find)|"
            r"(?:removed|took away|got rid of)\b[^.!?]{0,25}?\bsearch|"
            r"where(?:'s| is) the search|can'?t find the search|"
            r"no way to (?:search|filter|sort)|"
            r"(?:don'?t|doesn'?t) know how to (?:search|find))\b",
            re.I,
        ),
    ),
]


# ---------------------------------------------------------------------------
# COLUMN 2: memory_detail - how much the user remembers about the photo
# ---------------------------------------------------------------------------
# Checked most-specific first: if they name an exact date or keyword, that beats
# a rough "sometime last year".
MEMORY_SPECIFIC = re.compile(
    r"\b(exact(?:ly)? (?:date|day|name|word|photo|picture)|by name|"
    r"the exact|specific (?:photo|picture|image|date|keyword|word|name)|"
    r"i know the (?:date|name|day)|typed? in (?:the )?(?:name|date|keyword)|"
    r"searched (?:for )?(?:the )?(?:exact|specific)|know exactly (?:when|what|where))\b"
    r"|\b(?:from|on|in) (?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december) \d{1,2}\b"
    r"|\bsearch(?:ed|ing)? (?:for|by) [\"'][^\"']{2,30}[\"']",
    re.I,
)

MEMORY_PARTIAL = re.compile(
    r"\b(some ?time (?:in|around|last|back)|around (?:19|20)\d{2}|"
    r"(?:last|that) (?:year|summer|winter|spring|autumn|fall|month|week)|"
    r"(?:a )?few (?:years|months|weeks) (?:ago|back)|"
    r"(?:when|while) i was (?:in|at|on)|"
    r"on (?:my|our) (?:trip|holiday|vacation|wedding)|"
    r"roughly|approximately|more or less when|i think it was)\b"
    r"|\b(?:19|20)\d{2}\b",
    re.I,
)

MEMORY_VAGUE = re.compile(
    r"\b(i know i (?:have|had|took|saved)|i'?m sure i (?:have|had|took)|"
    r"pretty sure (?:i|it)|i remember (?:taking|seeing|having|the)|"
    r"remember (?:having|taking|seeing) (?:a|an|that|the|some)|"
    r"(?:a|some) photo of|(?:a|some) picture of|somewhere in (?:my|the)|"
    r"i don'?t remember (?:when|where|which|what)|can'?t remember (?:when|where|which|what)|"
    r"(?:forgot|forgotten) (?:when|where|which|what)|no idea (?:when|where|which))\b",
    re.I,
)


# ---------------------------------------------------------------------------
# COLUMN 3: photo_age - how old the sought photo/video seems to be
# ---------------------------------------------------------------------------
PHOTO_AGE_OLD = re.compile(
    r"\b(years? ago|decades? ago|long time ago|way back|back in (?:19|20)\d{2}|"
    r"from (?:19|20)(?:0\d|1\d|2[0-3])|old (?:photo|photos|picture|pictures|video|videos|"
    r"image|images|memory|memories)|older (?:photo|photos|picture|pictures)|"
    r"oldest (?:photo|picture|image)|childhood|from my childhood|"
    r"since (?:19|20)\d{2}|over the years)\b",
    re.I,
)

PHOTO_AGE_RECENT = re.compile(
    r"\b(yesterday|today|this morning|last night|just (?:took|taken|shot|saved|uploaded)|"
    r"(?:a )?few (?:minutes|hours|days) ago|last (?:week|month)|this (?:week|month)|"
    r"recent (?:photo|photos|picture|pictures|video|videos)|recently (?:took|taken|saved|uploaded)|"
    r"(?:weeks|days) ago|new (?:photo|photos|picture|pictures))\b",
    re.I,
)


# ---------------------------------------------------------------------------
# COLUMN 4: time_spent_searching - only counts near a "searching" word
# ---------------------------------------------------------------------------
DURATION = re.compile(
    r"\b(\d+\s*(?:-|to|\+)?\s*\d*\s*"
    r"(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?)"
    r"|(?:half|an|a|several|many|countless|multiple)\s+(?:hour|hours|day|days|minute|minutes)"
    r"|hours (?:and hours|on end)|forever|ages|all (?:day|night|morning|afternoon)"
    r"|(?:so|too) long)\b",
    re.I,
)

# Words that mean the duration is about LOOKING for something.
SEARCH_CONTEXT = re.compile(
    r"\b(search|searches|searched|searching|look|looked|looking|find|finding|"
    r"locate|locating|scroll|scrolled|scrolling|dig|digging|hunt|hunted|hunting|"
    r"browse|browsing|trawl|sift|sifting|wade|wading|trying to find|to find)\b",
    re.I,
)

# Other things a duration is commonly attached to in these reviews. If one of
# these sits CLOSER to the duration than any searching word does, the duration
# belongs to that activity instead - "takes ages to delete a photo" is not time
# spent searching, and neither is "waiting 15 minutes for one photo to back up".
OTHER_ACTIVITY = re.compile(
    r"\b(load|loads|loading|delete|deletes|deleting|deleted|back ?up|backing ?up|"
    r"backed ?up|upload|uploads|uploading|uploaded|download|downloading|"
    r"sync|syncing|transfer|transferring|wait|waiting|waited|create|creating|"
    r"share|sharing|gone|disappear|disappears|disappeared|vanish|vanished|"
    r"lost forever|forever gone)\b",
    re.I,
)

# How far away (in characters) the searching word may sit from the duration.
CONTEXT_WINDOW = 70


def find_time_spent(text):
    """Returns the duration phrase exactly as written, but only when it is
    clearly about time spent searching. Otherwise 'not mentioned'."""
    for match in DURATION.finditer(text):
        start = max(0, match.start() - CONTEXT_WINDOW)
        end = min(len(text), match.end() + CONTEXT_WINDOW)
        window = text[start:end]

        # The phrase "X years ago" is the age of the photo, never a search time.
        trailing = text[match.end():match.end() + 6].lower()
        if trailing.strip().startswith("ago"):
            continue

        # Distance from the duration to the nearest searching word, and to the
        # nearest other-activity word. Whichever is closer, wins.
        def nearest(pattern):
            best = None
            for found in pattern.finditer(window):
                # how far this word sits from the duration inside the window
                distance = min(
                    abs(found.start() - (match.start() - start)),
                    abs(found.start() - (match.end() - start)),
                )
                if best is None or distance < best:
                    best = distance
            return best

        search_distance = nearest(SEARCH_CONTEXT)
        if search_distance is None:
            continue

        other_distance = nearest(OTHER_ACTIVITY)
        if other_distance is not None and other_distance < search_distance:
            continue

        return match.group(0).strip()

    return "not mentioned"


def classify_failure_type(text):
    for label, pattern in FAILURE_TYPE_RULES:
        if pattern.search(text):
            return label
    return "not specified"


def classify_memory_detail(text):
    if MEMORY_SPECIFIC.search(text):
        return "specific memory (exact date/keyword/person)"
    if MEMORY_PARTIAL.search(text):
        return "partial memory (rough time or place)"
    if MEMORY_VAGUE.search(text):
        return "vague memory (event/feeling only)"
    return "not specified"


def classify_photo_age(text):
    old = PHOTO_AGE_OLD.search(text)
    recent = PHOTO_AGE_RECENT.search(text)

    # If both appear, trust whichever is mentioned first.
    if old and recent:
        return "old (years ago)" if old.start() < recent.start() else "recent (weeks/months)"
    if old:
        return "old (years ago)"
    if recent:
        return "recent (weeks/months)"
    return "not specified"


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        original_columns = list(rows[0].keys()) if rows else []

    print(f"Read {len(rows)} reviews from {INPUT_FILE}\n")

    for row in rows:
        text = row.get("text", "")
        row["failure_type"] = classify_failure_type(text)
        row["memory_detail"] = classify_memory_detail(text)
        row["photo_age"] = classify_photo_age(text)
        row["time_spent_searching"] = find_time_spent(text)

    new_columns = ["failure_type", "memory_detail", "photo_age", "time_spent_searching"]

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=original_columns + new_columns)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} annotated reviews to {OUTPUT_FILE}\n")

    # A breakdown, so you can see at a glance what the data says.
    for column in new_columns:
        print(f"{column}:")
        counts = {}
        for row in rows:
            value = row[column]
            if column == "time_spent_searching" and value != "not mentioned":
                value = "(a duration was found)"
            counts[value] = counts.get(value, 0) + 1
        for value, n in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  {value:<46} {n:>5}  ({n / len(rows) * 100:.0f}%)")
        print()


if __name__ == "__main__":
    main()
