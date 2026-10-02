"""
filter_retrieval_reviews.py

What this script does (in plain words):
Reads the raw Play Store reviews and keeps ONLY the ones that are evidence of
RETRIEVAL FAILURE - a user saying they cannot find / search for / get back to a
specific photo or video they know they have.

It deliberately throws away reviews about storage limits, pricing, crashes,
backup failures, editing tools, and generic praise, because those are not
evidence of the retrieval problem this project is about.

HOW THE FILTER WORKS (three layers, all must agree):
  Layer 1 - RETRIEVAL SIGNAL: the review says something like "can't find",
            "search doesn't work", "where did my photos go", "forgot when I
            took it". Note that "old photos" alone does NOT qualify a review,
            because that phrase is just as common in praise; it is only recorded
            as extra context once a real signal has matched.
  Layer 2 - PHOTO OBJECT: the thing being looked for is actually a photo, video,
            album, or memory. This is what stops false positives like
            "can't get into my spades games" or "can't delete anything to get
            storage back" from sneaking in.
  Layer 3 - NOT DISQUALIFIED: the review isn't really about storage/pricing/
            crashes/backup/editing, and isn't praise ("search works great").

HOW TO RUN THIS:
    python3 scripts/filter_retrieval_reviews.py

Input:  data/raw_data/google_photos_playstore_reviews.csv
Output: data/filtered_data/google_photos_retrieval_failure_reviews.csv
        (same columns as the input, plus a "match_reason" column telling you
         WHICH rule caught each review, so you can audit the filter by eye)
"""

import csv
import os
import re

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------

# The project folder, worked out from where THIS file sits. Everything is
# located relative to that, so the script works no matter which folder you run
# it from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FILE = os.path.join(PROJECT_ROOT, "data", "raw_data", "google_photos_playstore_reviews.csv")
OUTPUT_FILE = os.path.join(
    PROJECT_ROOT, "data", "filtered_data", "google_photos_retrieval_failure_reviews.csv"
)

# Reviews shorter than this are things like "good" / "bad" - no usable evidence.
MIN_TEXT_LENGTH = 15


# ---------------------------------------------------------------------------
# LAYER 2: words that mean "a photo I am looking for"
# ---------------------------------------------------------------------------
PHOTO_OBJECT = re.compile(
    r"\b(photo|photos|pic|pics|picture|pictures|image|images|video|videos|"
    r"album|albums|memory|memories|screenshot|screenshots|gallery|"
    r"folder|folders|file|files|past event|past events|moment|moments)\b",
    re.I,
)

# "can't find the magic eraser / the app / that button" is a UI complaint, not a
# failure to retrieve a photo, even though it reads like one.
FIND_NON_PHOTO_TARGET = re.compile(
    r"\b(can'?t|cannot|can not|couldn'?t|could not|unable to)\s+"
    r"(even\s+|really\s+)?(find|locate)\s+"
    r"(the|a|an|my|any|that|this)?\s*(\w+\s+){0,2}?"
    r"\b(app|eraser|tool|tools|button|option|options|feature|icon|menu|"
    r"setting|settings|coupon|coupons|deal|deals|word|words|download|downloads)\b",
    re.I,
)

# Two cases where we accept a review even though it never says "photo":
# 1. It complains about THE SEARCH FEATURE itself ("search is broken"). In a
#    Google Photos review, searching means searching photos.
# 2. It says the user can't find ANYTHING / NOTHING - same meaning, no noun.
SEARCH_FEATURE_COMPLAINT = re.compile(
    r"\bsearch(ing)?\b[^.!?]{0,40}?"
    r"\b(broken|useless|terrible|awful|horrible|garbage|trash|rubbish|worthless|"
    r"unusable|ruined|sucks|pointless|hopeless|doesn'?t work|does not work|"
    r"not work|never works|worse|worst|failed|fails|no longer works)\b"
    r"|\b(broken|useless|terrible|awful|garbage|trash|worthless|unusable|ruined)\b"
    r"[^.!?]{0,25}?\bsearch\b",
    re.I,
)

# ...but NOT when "search" means Google/web search (Gemini reviews mention this).
WEB_SEARCH = re.compile(r"\b(web|google|internet|browser|engine)\s+search\b", re.I)

FIND_ANYTHING = re.compile(
    r"\b(can'?t|cannot|can not|couldn'?t|could not|unable to)\s+"
    r"(really\s+|even\s+|ever\s+)?(find|locate|search for)\s+"
    r"(anything|nothing|any of|a thing)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# LAYER 1: the retrieval-failure signals, grouped so we can label each match
# ---------------------------------------------------------------------------
# Each entry is (label, regex). The label ends up in the match_reason column.
RETRIEVAL_SIGNALS = [
    # "can't find my photos", "unable to locate that picture"
    (
        "cannot_find",
        re.compile(
            r"(can'?t|cannot|can not|couldn'?t|could not|unable to|"
            r"impossible to|hard to|difficult to|struggle to|no way to|"
            r"never able to|takes forever to)"
            r"[^.!?]{0,40}?"
            r"\b(find|finding|locate|locating|search|searching|retrieve|"
            r"get back to|track down|pull up)\b",
            re.I,
        ),
    ),
    # "the search doesn't work", "search is useless/broken/terrible"
    (
        "search_broken",
        re.compile(
            r"\bsearch(ing)?\b[^.!?]{0,40}?"
            r"\b(doesn'?t|does not|don'?t|do not|won'?t|will not|never|no longer)\b"
            r"[^.!?]{0,20}?\b(work|working|works|find|show|return|bring)\b"
            r"|\bsearch(ing)?\s+(function|feature|bar|tool|option|results?)?\s*"
            r"\b(is|are|has become|became|got|now)\b[^.!?]{0,25}?"
            r"\b(broken|useless|terrible|awful|horrible|garbage|trash|"
            r"rubbish|worthless|hopeless|bad|poor|weak|worse|worst|unusable|"
            r"ruined|sucks|pointless)\b"
            r"|\b(broken|useless|terrible|awful|horrible|garbage|trash|"
            r"worthless|poor|weak|unusable|ruined|no good)\b\s+search"
            r"|\bsearch\s+(is|was)\s+(now\s+)?(broken|useless|terrible|awful|"
            r"garbage|trash|worthless|unusable|ruined)\b",
            re.I,
        ),
    ),
    # "where did my photos go?", "where are my pictures"
    (
        "where_did_they_go",
        re.compile(
            r"\bwhere\s+(did|have|are|is|do|does|has)\b[^.!?]{0,40}?"
            r"\b(go|goes|gone|went|disappear|disappeared|end up|hiding|hidden|"
            r"kept|store[d]?|save[d]?)\b"
            r"|\bwhere\s+(is|are|did|do)\s+(my|the|all)\b",
            re.I,
        ),
    ),
    # "my photos disappeared / vanished / are missing / are gone"
    (
        "photos_missing",
        re.compile(
            r"\b(disappear|disappeared|disappearing|vanish|vanished|vanishing|"
            r"missing|gone missing|nowhere to be found|lost|losing|lost track of)\b",
            re.I,
        ),
    ),
    # the vague-memory case: "I forgot when I took it", "I don't remember which
    # album I put it in" - the user knows the photo exists but not its details
    (
        "forgot_details",
        re.compile(
            r"\b(remember|recall|forgot|forgotten|forget|don'?t know|no idea)\b"
            r"[^.!?]{0,40}?"
            r"\b(when|where|which|what date|the date|the name|the title|"
            r"took it|taken|saved it|put it|album)\b",
            re.I,
        ),
    ),
    # scrolling forever because retrieval failed
    (
        "endless_scrolling",
        re.compile(
            r"\b(scroll|scrolling|swipe|swiping)\b[^.!?]{0,30}?"
            r"\b(forever|for hours|for ages|endlessly|thousands|manually|"
            r"all the way|through everything)\b"
            r"|\bhave to scroll\b",
            re.I,
        ),
    ),
]


# A SUPPORTING signal, not a qualifying one. "old photos" / "years ago" shows up
# constantly in praise ("excellent to view my old pictures"), so on its own it is
# not evidence of anything. It is recorded in match_reason only when one of the
# real signals above has already qualified the review, because it tells you the
# user was after OLD content specifically - the vaguely-remembered case.
OLD_CONTENT = re.compile(
    r"\b(years? ago|months? ago|long time ago|way back|back in \d{4}|from \d{4}|"
    r"old photo|old photos|old picture|old pictures|old video|old videos|"
    r"older photos|older pictures)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# LAYER 3a: topics that mean the review is NOT about retrieval
# ---------------------------------------------------------------------------
# These only disqualify a review when it has no strong retrieval wording,
# so a review like "storage is full AND I can't find my old photos" is kept.
OFF_TOPIC = re.compile(
    r"\b(storage (space|limit|full|plan)|out of storage|free up space|"
    r"buy more storage|subscription|subscribe|price|pricing|paid plan|"
    r"expensive|refund|billing|payment|"
    r"crash|crashes|crashing|freeze|freezes|freezing|force clos|"
    r"won'?t open|keeps stopping|not responding|lag|laggy|battery|"
    r"backup fail|back up fail|won'?t back up|not backing up|sync fail|"
    r"edit|editing|editor|filter|crop|collage|magic eraser)\b",
    re.I,
)

# LAYER 3b: praise about search - mentions search but reports no failure
PRAISE = re.compile(
    r"\b(search|find|finds|finding)\b[^.!?]{0,40}?"
    r"\b(great|amazing|awesome|excellent|perfect|love|works well|"
    r"works great|so smart|so good|easy|brilliant|fantastic|impressive)\b"
    r"|\b(love|great|amazing|excellent|perfect|brilliant|fantastic)\b"
    r"[^.!?]{0,30}?\bsearch\b"
    # "makes it easy/easier to find", "helps me find", "simple way of finding"
    r"|\b(easy|easier|simple|quick|quicker|effortless|no trouble|helps? me|"
    r"helping me|able)\b[^.!?]{0,20}?\b(to )?(find|finding|locate|search)\b"
    r"|\b(find|finding)\b[^.!?]{0,20}?\b(is|are)\s+(so\s+)?(easy|simple|quick)\b",
    re.I,
)

# Strong wording that keeps a review even if an off-topic word is present.
STRONG_RETRIEVAL = re.compile(
    r"(can'?t|cannot|couldn'?t|unable to|impossible to)"
    r"[^.!?]{0,40}?\b(find|locate|search)\b"
    r"|\bsearch(ing)?\b[^.!?]{0,30}?\b(useless|broken|doesn'?t work|does not work|"
    r"never works|garbage|trash|terrible|awful|worthless|unusable)\b"
    r"|\bwhere\s+(did|are|is)\s+(my|all)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# The filter itself
# ---------------------------------------------------------------------------
def classify(text):
    """Returns a list of matched rule labels, or [] if the review is not
    evidence of retrieval failure."""
    if len(text.strip()) < MIN_TEXT_LENGTH:
        return []

    # Layer 2: it has to be about photos at all - unless it's an explicit
    # complaint about the search feature, or a flat "can't find anything".
    search_complaint = bool(SEARCH_FEATURE_COMPLAINT.search(text)) and not WEB_SEARCH.search(text)
    if not PHOTO_OBJECT.search(text) and not search_complaint and not FIND_ANYTHING.search(text):
        return []

    # Layer 1: collect every retrieval signal present.
    reasons = [label for label, pattern in RETRIEVAL_SIGNALS if pattern.search(text)]
    if not reasons:
        return []

    strong = bool(STRONG_RETRIEVAL.search(text))

    # A UI complaint dressed up as "can't find", with nothing else to back it up.
    if FIND_NON_PHOTO_TARGET.search(text) and (
        reasons == ["cannot_find"] or not PHOTO_OBJECT.search(text)
    ):
        return []

    # Layer 3b: drop praise, unless it also contains a strong complaint.
    if PRAISE.search(text) and not strong:
        return []

    # Layer 3a: drop off-topic complaints, unless strongly about retrieval.
    if OFF_TOPIC.search(text) and not strong:
        return []

    # "missing/lost" on its own is weak (e.g. "lost my subscription"), so it
    # only counts when paired with another signal or strong retrieval wording.
    if reasons == ["photos_missing"] and not strong:
        return []

    if OLD_CONTENT.search(text):
        reasons.append("about_old_content")

    return reasons


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"Read {len(rows)} reviews from {INPUT_FILE}")

    kept = []
    for row in rows:
        reasons = classify(row.get("text", ""))
        if reasons:
            row["match_reason"] = "; ".join(reasons)
            kept.append(row)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    fieldnames = ["source", "date", "rating", "text", "url", "match_reason"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"Kept {len(kept)} retrieval-failure reviews ({len(kept) / len(rows) * 100:.1f}% of the raw set)")
    print(f"Saved to {OUTPUT_FILE}\n")

    print("Breakdown by rule (a review can match more than one):")
    counts = {}
    for row in kept:
        for reason in row["match_reason"].split("; "):
            counts[reason] = counts.get(reason, 0) + 1
    for reason, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {reason:<22} {n}")

    print("\nBreakdown by star rating:")
    stars = {}
    for row in kept:
        stars[row["rating"]] = stars.get(row["rating"], 0) + 1
    for rating in sorted(stars):
        print(f"  {rating} star: {stars[rating]}")


if __name__ == "__main__":
    main()
