"""
filter_other_sources.py

Filters the NON-Play-Store sources (Reddit, YouTube, Google Photos community
forum) down to only the posts/comments that are evidence of RETRIEVAL FAILURE -
someone saying they cannot find, search for, or get back to a photo or video
they know they have, including the case where they only half-remember it.

It deliberately throws away posts about storage limits, pricing, crashes,
backup failures, editing tools, and generic praise.

HOW THE FILTER WORKS (three layers, all must agree):
  Layer 1 - RETRIEVAL SIGNAL: the text says something like "can't find",
            "search doesn't work", "where did my photos go", "forgot when I
            took it", or uses any looking-for word (find, locate, look for,
            hunt for, seek out, browse, discover, view...) with difficulty.
  Layer 2 - PHOTO OBJECT: the thing being looked for is actually a photo,
            video, album or memory. This stops false positives like "can't
            find Google Photos in the app store".
  Layer 3 - NOT DISQUALIFIED: the text isn't really about storage/pricing/
            crashes/backup/editing, and isn't praise.

Each source keeps its ORIGINAL columns exactly as they are. Only whole rows
are removed; nothing is renamed, added or restructured.

HOW TO RUN THIS:
    python3 scripts/filter_other_sources.py

Input:  data/raw_data/<each source>.csv
Output: data/filtered_data/<same name>_filtered.csv
"""

import csv
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw_data")
OUT_DIR = os.path.join(PROJECT_ROOT, "data", "filtered_data")

# Some of these posts are long, so allow big CSV fields.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# Which file, and which column(s) hold the words people actually wrote.
SOURCES = [
    {
        "name": "Reddit",
        "file": "reddit_googlephotos_formatted.csv",
        "text_columns": ["text"],
    },
    {
        "name": "YouTube",
        "file": "youtube_comments_all.csv",
        "text_columns": ["text"],
    },
    {
        "name": "Community/Support Forum",
        "file": "reviews - Google Photos Community_Support Forum.csv",
        "text_columns": ["Post Title", "Full text"],
    },
]

# Text shorter than this is things like "nice video" - no usable evidence.
MIN_TEXT_LENGTH = 15

# Used only as a quick "is this worth examining at all?" check.
SEARCH_WORD = re.compile(r"\bsearch\w*\b|\bphoto finder\b", re.I)


# ---------------------------------------------------------------------------
# LAYER 2: words that mean "a photo I am looking for"
# ---------------------------------------------------------------------------
PHOTO_OBJECT = re.compile(
    r"\b(photo|photos|foto|fotos|pic|pics|picture|pictures|image|images|"
    r"video|videos|vid|vids|clip|clips|album|albums|memory|memories|"
    r"screenshot|screenshots|gallery|library|folder|folders|file|files|"
    r"past event|past events|moment|moments|shot|shots|footage)\b",
    re.I,
)

# Every way people say "look for". The user asked for these synonyms explicitly.
# Note "find(?!\s+out)": "find out" means discover a fact, not locate a photo,
# so it must not count as looking for something.
LOOKING_VERB = (
    r"find(?!\s+out)|finding|locate|locating|search|searches|searched|searching|"
    r"look for|looking for|looked for|hunt for|hunting for|hunt down|"
    r"seek out|seeking|track down|tracking down|dig up|digging for|"
    r"browse|browsing|discover|discovering|retrieve|retrieving|"
    r"pull up|get back to|view|viewing"
)

# Words that mean it went badly.
DIFFICULTY = (
    r"can'?t|cannot|can not|couldn'?t|could not|unable to|impossible to|"
    r"hard to|difficult to|struggle to|struggling to|no way to|"
    r"never able to|takes forever to|takes ages to|trying to|tried to|"
    r"gave up|give up|failed to|fails to|no luck"
)

# A TIGHTER set, used only for deciding whether a passage is strong enough to
# survive an off-topic word. "trying to find X" is not a complaint - everyone
# writes it - so it must not be able to override the exclusions.
STRONG_DIFFICULTY = (
    r"can'?t|cannot|can not|couldn'?t|could not|unable to|impossible to|"
    r"never able to|gave up|failed to"
)

# "I searched Google / this subreddit / YouTube" is not searching your photos.
NON_PHOTO_SEARCH = re.compile(
    r"\b(search|searching|searched|google)\s+(on\s+|in\s+|through\s+)?"
    r"(google|the web|online|the internet|reddit|this sub|the sub|subreddit|"
    r"youtube|the forum|forums?|stack\w*)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# LAYER 1: the retrieval-failure signals, grouped so we can label each match
# ---------------------------------------------------------------------------
RETRIEVAL_SIGNALS = [
    # "can't find my photos", "struggling to locate that video"
    (
        "cannot_find",
        re.compile(
            rf"({DIFFICULTY})[^.!?]{{0,45}}?\b({LOOKING_VERB})\b",
            re.I,
        ),
    ),
    # "the search doesn't work", "search is useless/broken"
    (
        "search_broken",
        re.compile(
            r"\bsearch(ing)?\b[^.!?]{0,45}?"
            r"\b(doesn'?t|does not|don'?t|do not|won'?t|will not|never|no longer|"
            r"stopped)\b[^.!?]{0,25}?\b(work|working|works|find|finding|show|"
            r"showing|return|returning|bring|match)\b"
            r"|\bsearch(ing)?\s*(function|feature|bar|tool|option|results?)?\s*"
            r"\b(is|are|has become|became|got|now|seems)\b[^.!?]{0,25}?"
            r"\b(broken|useless|terrible|awful|horrible|garbage|trash|rubbish|"
            r"worthless|hopeless|bad|poor|weak|worse|worst|unusable|ruined|"
            r"sucks|pointless|unreliable|inaccurate)\b"
            r"|\b(broken|useless|terrible|awful|horrible|garbage|trash|worthless|"
            r"poor|weak|unusable|ruined|no good|crappy)\b\s+search"
            r"|\bphoto finder\b",
            re.I,
        ),
    ),
    # "where did my photos go?", "where are my pictures"
    (
        "where_did_they_go",
        re.compile(
            r"\bwhere\s+(did|have|are|is|do|does|has|the hell|the heck)\b"
            r"[^.!?]{0,45}?\b(go|goes|gone|went|disappear|disappeared|vanish|"
            r"vanished|end up|ended up|hiding|hidden|kept|store[d]?|save[d]?)\b"
            r"|\bwhere\s+(is|are|did|do|can i find)\s+(my|the|all)\b",
            re.I,
        ),
    ),
    # "my photos disappeared / are missing / are gone"
    (
        "photos_missing",
        re.compile(
            r"\b(disappear|disappeared|disappearing|vanish|vanished|vanishing|"
            r"missing|gone missing|nowhere to be found|lost|losing|lost track of|"
            r"wiped|no longer there|not showing up|won'?t show up)\b",
            re.I,
        ),
    ),
    # the vague-memory case: "I know I took it but can't remember when"
    (
        "vague_memory",
        re.compile(
            r"\b(remember|recall|forgot|forgotten|forget|don'?t know|no idea|"
            r"not sure|can'?t recall|somewhere)\b[^.!?]{0,45}?"
            r"\b(when|where|which|what date|the date|the name|the title|"
            r"took it|taken|saved it|put it|album|year|month|it was)\b"
            r"|\bi know i (have|had|took|saved|uploaded)\b"
            r"|\b(pretty sure|certain) i (have|had|took|saved)\b"
            r"|\bsomewhere in (my|the)\b",
            re.I,
        ),
    ),
    # scrolling forever because retrieval failed
    (
        "endless_scrolling",
        re.compile(
            r"\b(scroll|scrolling|scrolled|swipe|swiping|sift|sifting|wade|wading)\b"
            r"[^.!?]{0,35}?\b(forever|for hours|for ages|endlessly|thousands|"
            r"manually|all the way|through everything|back years|years back)\b"
            r"|\bhave to scroll\b|\bendless scroll\w*\b",
            re.I,
        ),
    ),
]


# ---------------------------------------------------------------------------
# LAYER 3a: topics that mean the text is NOT about retrieval
# ---------------------------------------------------------------------------
OFF_TOPIC = re.compile(
    r"\b(storage (space|limit|full|plan|quota)|out of storage|free up space|"
    r"buy more storage|subscription|subscribe|price|pricing|paid plan|"
    r"per month|expensive|refund|billing|payment|google one\b|"
    r"crash|crashes|crashing|freeze|freezes|freezing|force clos|"
    r"keeps stopping|not responding|lag|laggy|battery|"
    r"backup fail|back up fail|won'?t back up|not backing up|sync fail|"
    r"edit|editing|editor|filter|crop|collage|magic eraser|unblur)\b",
    re.I,
)

# LAYER 3b: praise - mentions finding but reports no failure
PRAISE = re.compile(
    r"\b(search|find|finds|finding)\b[^.!?]{0,40}?"
    r"\b(great|amazing|awesome|excellent|perfect|love it|works well|works great|"
    r"so smart|so good|brilliant|fantastic|impressive|flawless)\b"
    r"|\b(love|great|amazing|excellent|perfect|brilliant|fantastic)\b"
    r"[^.!?]{0,30}?\bsearch\b"
    r"|\b(easy|easier|simple|quick|quicker|effortless|instantly|no trouble|"
    r"helps? me|helping me)\b[^.!?]{0,20}?\b(to )?(find|finding|locate|search)\b",
    re.I,
)

# Strong wording that keeps a row even if an off-topic word is also present
# (long Reddit posts often mention storage in passing).
STRONG_RETRIEVAL = re.compile(
    rf"({STRONG_DIFFICULTY})[^.!?]{{0,35}}?\b(find(?!\s+out)|locate|search|retrieve)\b"
    r"|\bsearch(ing)?\b[^.!?]{0,30}?\b(useless|broken|doesn'?t work|does not work|"
    r"no longer works|never works|garbage|trash|terrible|awful|worthless|unusable)\b"
    r"|\bwhere\s+(did|are|is)\s+(my|all)\b"
    r"|\bphoto finder\b",
    re.I,
)

# "can't find the app / the button / the setting" is a UI complaint, not a
# failure to retrieve a photo.
FIND_NON_PHOTO_TARGET = re.compile(
    rf"({DIFFICULTY})\s+(even\s+|really\s+|seem to\s+)?(find|locate)\s+"
    r"(the|a|an|my|any|that|this)?\s*(\w+\s+){0,2}?"
    r"\b(app|application|eraser|tool|tools|button|option|options|feature|icon|"
    r"menu|setting|settings|tab|link|page|website|subscription|plan|"
    r"word|words|download|downloads|answer|answers|solution|information|info|"
    r"method|way|ways|post|posts|thread|threads|anyone|anybody|documentation|"
    r"reason|explanation|help|"
    # editing / UI features - wanting a tool back is not a lost photo
    r"crop|slideshow|flip|layout|collage|widget|shortcut|toggle|filter|"
    r"eraser|theme|checkbox|slider)\b",
    re.I,
)

# Sentences are the unit we judge. In a long Reddit post, "can't find" in one
# paragraph and "photos" three paragraphs later do NOT mean the person was
# looking for a photo - they are separate thoughts. So a row only qualifies
# when a SINGLE sentence contains both the difficulty and the photo.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?\n])\s+|\n+")

# A window of neighbouring sentences is also checked, because people often
# write "I took a photo of my car. Now I can't find it."
SENTENCE_WINDOW = 2


def classify_passage(passage):
    """Judges ONE sentence (or small group of sentences). Returns the rule
    labels it matched, or [] if this passage is not retrieval evidence."""
    reasons = [label for label, pattern in RETRIEVAL_SIGNALS if pattern.search(passage)]
    if not reasons:
        return []

    # An explicit complaint about the search feature counts even without the
    # word "photo" - in a Google Photos discussion, search means photo search.
    about_photos = bool(PHOTO_OBJECT.search(passage))
    if not about_photos and "search_broken" not in reasons:
        return []

    strong = bool(STRONG_RETRIEVAL.search(passage))

    # "can't find the app / any information / the crop tool" is not a lost
    # photo, no matter how strongly it is worded.
    if FIND_NON_PHOTO_TARGET.search(passage):
        return []

    # "I searched Google and this subreddit" is not searching your photos.
    if NON_PHOTO_SEARCH.search(passage) and reasons == ["cannot_find"]:
        return []

    if PRAISE.search(passage) and not strong:
        return []

    if OFF_TOPIC.search(passage) and not strong:
        return []

    # "missing/lost" alone is weak ("lost my subscription"), and a bare
    # vague-memory phrase alone isn't a retrieval failure either.
    if reasons in (["photos_missing"], ["vague_memory"]) and not strong:
        return []

    return reasons


def classify(text):
    """Returns a list of matched rule labels, or [] if this row is not
    evidence of retrieval failure.

    The text is examined sentence by sentence, so the complaint and the photo
    have to belong to the same thought - not merely appear in the same post.
    """
    if len(text.strip()) < MIN_TEXT_LENGTH:
        return []

    # Cheap early exit: nothing photo-related anywhere means nothing to find.
    if not PHOTO_OBJECT.search(text) and not SEARCH_WORD.search(text):
        return []

    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s and s.strip()]
    if not sentences:
        return []

    found = []
    for i in range(len(sentences)):
        # Look at this sentence together with the next one or two, so a photo
        # mentioned just before the complaint still counts.
        passage = " ".join(sentences[i:i + SENTENCE_WINDOW])
        found.extend(classify_passage(passage))

    # Remove duplicates but keep the order they were found in.
    return list(dict.fromkeys(found))


def get_text(row, text_columns):
    """Joins the columns that hold what the person actually wrote."""
    return " ".join((row.get(column) or "") for column in text_columns).strip()


def filter_source(source):
    in_path = os.path.join(RAW_DIR, source["file"])
    stem, extension = os.path.splitext(source["file"])
    out_path = os.path.join(OUT_DIR, f"{stem}_filtered{extension}")

    if not os.path.exists(in_path):
        print(f"{source['name']}: SKIPPED - no file at {in_path}\n")
        return

    with open(in_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    kept = [row for row in rows if classify(get_text(row, source["text_columns"]))]

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        # Same columns, same order, nothing added or renamed.
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    percent = (len(kept) / len(rows) * 100) if rows else 0
    print(f"{source['name']}")
    print(f"  matched {len(kept)} of {len(rows)} rows ({percent:.1f}%)")
    print(f"  saved to data/filtered_data/{os.path.basename(out_path)}\n")


def main():
    for source in SOURCES:
        filter_source(source)


if __name__ == "__main__":
    main()
