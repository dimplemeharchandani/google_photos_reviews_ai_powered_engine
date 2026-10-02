"""
filter_attribute_search_failures.py

Finds, across ALL four raw sources, the cases at the heart of this project:
someone searched for a photo using what they could REMEMBER about it - an
object, a place, a person, an event, roughly when it was - and the search
failed them.

This is the pattern being looked for:

    "I was looking for a picture of a medicine prescription from when I was
     sick in Goa. I searched 'medicine Goa' and 'sick' but got zero results...
     I had to scroll through 4,000 photos for 45 minutes to find it."

Three things must appear close together for a row to be kept:

  1. A SEARCH ATTEMPT   - searched / typed / looked up / query
  2. A REMEMBERED ATTRIBUTE - the kind of thing a person actually recalls:
                          an object, a colour, a place, a person, an event,
                          a rough date, or text seen in the picture
  3. A FAILURE          - no results, wrong results, couldn't find it, gave
                          up, or had to scroll through everything by hand

Successes are deliberately excluded: this is about retrieval breaking down.
Note that a mixed review still counts - "search is great for 'cat' but useless
when my memory is vague" contains a failure, so it is kept.

The output records WHICH attributes were searched on and, where the reviewer
quoted them, the actual words they typed - which is the most direct evidence
available of how people phrase a half-remembered photo.

HOW TO RUN THIS:
    python3 backend/scripts/filter_attribute_search_failures.py

Input:  all four files in data/raw_data/
Output: data/filtered_data/google_photos_vague_memory_search_failures.csv
"""

import csv
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw_data")
OUTPUT_FILE = os.path.join(
    PROJECT_ROOT, "data", "filtered_data",
    "google_photos_vague_memory_search_failures.csv",
)

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

SOURCES = [
    {"name": "Google Play Store", "file": "google_photos_playstore_reviews.csv",
     "text": ["text"], "date": "date", "url": "url", "rating": "rating", "engagement": None},
    {"name": "Reddit", "file": "reddit_googlephotos_formatted.csv",
     "text": ["text"], "date": "date", "url": "url", "rating": None, "engagement": "score"},
    {"name": "YouTube", "file": "youtube_comments_all.csv",
     "text": ["text"], "date": "date", "url": "url", "rating": None, "engagement": "likes"},
    {"name": "Google Photos Community", "file": "reviews - Google Photos Community_Support Forum.csv",
     "text": ["Post Title", "Full text"], "date": "Date", "url": "URL",
     "rating": None, "engagement": None},
]

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
SENTENCE_WINDOW = 3          # these stories run over a few sentences

# The thing being remembered has to be a photo or video.
PHOTO_OBJECT = re.compile(
    r"\b(photo|photos|foto|fotos|pic|pics|picture|pictures|image|images|"
    r"video|videos|vid|vids|clip|clips|album|albums|memory|memories|"
    r"screenshot|screenshots|gallery|library|shot|shots|footage)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# 1. Did they actually search?
# ---------------------------------------------------------------------------
SEARCH_ATTEMPT = re.compile(
    r"\b(search(?:ed|es|ing)?|typed?|typing|look(?:ed|ing)?\s+up|queried|query|"
    r"put\s+in|enter(?:ed)?)\b"
    r"|\bsearch\s+(?:bar|box|function|feature|term|word)\b"
    r"|\bphoto finder\b"
    # Hunting for a photo counts even when the word "search" is never used -
    # plenty of people write "I was looking for the photo of..." instead.
    r"|\b(?:look(?:ing|ed)?|hunt(?:ing)?|dig(?:ging)?|scroll(?:ing|ed)?)\s+"
    r"(?:for|through|around)\b"
    r"|\b(?:trying|tried|want(?:ed)?|need(?:ed)?|attempt(?:ing|ed)?)\s+to\s+"
    r"(?:find|locate|retrieve|get (?:to|back)|pull up|track down)\b",
    re.I,
)

# The exact words they typed, when they quoted them: searched "medicine Goa"
QUOTED_TERMS = re.compile(
    r"(?:search(?:ed|ing)?|typed?|look(?:ed)?\s+up|query|for)\s*"
    r"(?:for\s+)?[\"'“‘]([^\"'”’]{2,60})[\"'”’]",
    re.I,
)


# ---------------------------------------------------------------------------
# 2. What did they remember about the photo?
# ---------------------------------------------------------------------------
ATTRIBUTES = [
    ("object", re.compile(
        r"\b(bottle|receipt|prescription|document|card|ticket|book|sign|poster|"
        r"plate|number ?plate|licence|license|car|bike|dog|cat|pet|bird|flower|"
        r"plant|tree|food|meal|recipe|dress|shoes|shirt|furniture|chair|table|"
        r"cabinet|armoire|screenshot|whiteboard|menu|label|box|bag|watch|ring)\b",
        re.I)),
    ("colour/appearance", re.compile(
        r"\b(red|blue|green|white|black|yellow|orange|purple|pink|brown|grey|gray|"
        r"wooden|metal|plastic|striped|dimly lit|dark|bright|small|tiny|big|huge|"
        r"cozy|cosy)\s+\w+", re.I)),
    ("place", re.compile(
        r"\b(beach|park|mall|garage|hotel|restaurant|cafe|café|coffee ?shop|"
        r"museum|zoo|airport|station|office|school|church|temple|street|city|"
        r"country|abroad|place|location|where i was|geotag|geo ?location)\b", re.I)),
    ("person", re.compile(
        r"\b(face|faces|people|person|friend|friends|family|mum|mom|dad|"
        r"mother|father|kid|kids|child|children|baby|grandma|grandpa|"
        r"someone|somebody|my wife|my husband|my son|my daughter)\b", re.I)),
    ("event", re.compile(
        r"\b(wedding|birthday|party|concert|festival|graduation|holiday|vacation|"
        r"trip|honeymoon|funeral|christmas|diwali|eid|thanksgiving|anniversary|"
        r"event|occasion)\b", re.I)),
    ("time/date", re.compile(
        r"\b(last (?:year|month|week|summer|winter)|years? ago|months? ago|"
        r"(?:19|20)\d{2}|january|february|march|april|may|june|july|august|"
        r"september|october|november|december|by date|the date|exact date)\b", re.I)),
    ("text in image", re.compile(
        r"\b(ocr|text in (?:the )?(?:image|photo|picture)|words in|written|"
        r"handwriting|handwritten|number|caption|scan(?:ned)?|serial number|"
        r"index(?:ed|ing)? the text|parse)\b", re.I)),
    # Photographed paperwork - people search for these by what they were FOR,
    # not by anything the app has indexed.
    ("document/screenshot", re.compile(
        r"\b(screenshot|screenshots|receipt|receipts|bill|invoice|prescription|"
        r"vaccination card|vaccine card|insurance|policy|passport|licence|license|"
        r"wifi password|password|serial|router|note|notes|napkin|recipe|"
        r"article|address|boarding pass|certificate|form)\b", re.I)),
    ("clothing/appearance of a person", re.compile(
        r"\b(dress|hat|shirt|jacket|coat|suit|uniform|costume|wearing|wore)\b", re.I)),
    # The hardest case: remembering the feeling or circumstances of a moment
    # rather than anything visible in the frame.
    ("event context/emotion", re.compile(
        r"\b(it rained|raining|power (?:went )?out|outage|storm|snowed|"
        r"the night (?:we|it|i)|the day (?:we|it|i)|felt|emotion|emotions|"
        r"mood|atmosphere|context)\b", re.I)),
    # "the photo right before we flew to Tokyo", "taken within 2 hours of"
    ("relative time / nearby photos", re.compile(
        r"\b(right before|just before|just after|right after|around the time|"
        r"within \d+ (?:hours?|minutes?|days?) of|next to|co-?occurrence|"
        r"taken near|same trip|same day as)\b", re.I)),
]

# ---------------------------------------------------------------------------
# REQUIRED: the person could not fully remember what they were looking for
# ---------------------------------------------------------------------------
# This is the point of the whole project. Without it a review is just an
# ordinary "search is broken" complaint, with no evidence about memory.
MEMORY_STRUGGLE = re.compile(
    r"\b(?:don'?t|do not|cannot|can'?t|couldn'?t|could not|never|hardly|barely)\s+"
    r"(?:remember|recall)\b"
    r"|\b(?:vaguely|barely|faintly|half|sort of|kinda|only)\s+(?:remember|recall)\b"
    r"|\bforgot(?:ten)?\b(?!\s+to\b)"
    r"|\bno idea\s+(?:when|where|which|what|who|how)\b"
    # "don't know WHAT I'm gonna do" is not a memory problem, so bare "what"
    # is not enough - it has to be a detail OF THE PHOTO that escapes them.
    r"|\bdon'?t know\s+(?:the\s+)?(?:exact(?:ly)?|when|where|which|"
    r"the date|the name|the year|the month|what it was called|what to search)\b"
    r"|\bnot sure\s+(?:exactly\s+)?(?:when|where|which)\s+(?:i|we|it|the photo|the pic)\b"
    r"|\bi know i (?:have|had|took|saved|uploaded)\b"
    r"|\bcan'?t (?:think of|describe|put into words|remember what)\b"
    r"|\bhard to describe\b|\bmemory is (?:vague|fuzzy|hazy|bad)\b"
    r"|\bvague (?:memory|recollection|idea)\b|\bhalf[- ]remember\w*\b"
    # Note: "something like" is deliberately NOT here. It nearly always
    # introduces an example ("a folder or something like that"), not a hazy
    # recollection, and it flooded the results with irrelevant reviews.
    r"|\broughly (?:when|where|around)\b"
    r"|\bcan'?t remember (?:what|which|when|where|the)\b",
    re.I,
)

# Uncertainty about the APP, not about a remembered photo. "Not sure why it
# does this", "I don't know what Google changed" - these are complaints, not
# evidence that someone half-remembers a picture.
UNCERTAIN_ABOUT_THE_APP = re.compile(
    r"\b(?:not sure|don'?t know|no idea)\s+"
    r"(?:why|how (?:to|it|they)|what (?:google|they|the app|happened|changed|"
    r"is going on|to do)|when it (?:began|started)|if (?:it|this|they))\b"
    r"|\bhaven'?t (?:totally )?figured (?:out|it)\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Reviews about EDITING photos are a different subject entirely
# ---------------------------------------------------------------------------
ABOUT_EDITING = re.compile(
    r"\b(edit|edits|edited|editing|editor|crop|cropping|cropped|filter|filters|"
    r"magic eraser|eraser|unblur|retouch|adjust(?:ment)?s?|brightness|contrast|"
    r"saturation|exposure|collage|markup|annotate|rotate|resize|enhance|"
    r"blur tool|preset|vignette)\b",
    re.I,
)


# People describing HOW human memory works, as opposed to how the app indexes.
# These posts are directly about the research problem even when no single
# search term is quoted.
MEMORY_CONCEPT = re.compile(
    r"\bmemory (?:trigger|triggers|is vague|works)\b"
    r"|\b(?:contextual|visual|relative|human|episodic) memory\b"
    r"|\bremember (?:events?|emotions?|context|the feeling)\b"
    r"|\bnot metadata\b|\bmulti-?dimensional\b"
    r"|\bmemory is (?:vague|fuzzy|hazy)\b"
    r"|\bsearch by (?:intent|memory|context|feeling)\b"
    r"|\bhalf[- ]remember\w*\b|\bvague (?:memory|recollection)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# 3. Did it fail?
# ---------------------------------------------------------------------------
FAILURE = re.compile(
    # nothing came back
    r"\b(?:zero|0|no|nothing|none)\s+(?:results?|photos?|pictures?|images?|matches|hits)\b"
    r"|\bgot\s+(?:zero|0|nothing)\b|\breturn(?:ed|s)?\s+(?:zero|0)\b"
    r"|\b(?:came|come)s? up empty|\breturns? nothing\b|\bnothing (?:came|shows?|showed|appears?) up\b"
    r"|\bdoesn'?t (?:find|return|show)\b|\bwon'?t (?:find|show)\b|\bnever finds?\b"
    # wrong or useless results
    r"|\b(?:wrong|irrelevant|unrelated|random|useless|inaccurate|garbage|nonsense)\b"
    r"[^.!?]{0,30}\b(?:results?|photos?|pictures?|images?|stuff)\b"
    r"|\bsearch(?:ing)?\b[^.!?]{0,40}\b(?:useless|broken|terrible|awful|garbage|"
    r"rubbish|worthless|unusable|inaccurate|doesn'?t work|does not work|fails?|failed)\b"
    # couldn't find it / gave up / brute force
    r"|\b(?:can'?t|cannot|couldn'?t|could not|unable to|impossible to)\s+"
    r"(?:\w+\s+){0,3}?(?:find|locate|retrieve)\b"
    r"|\bgave up\b|\bhad to scroll\b|\bscroll(?:ed|ing)?\b[^.!?]{0,40}"
    r"\b(?:manually|thousands|hundreds|\d{3,}|for (?:hours|ages|\d+ minutes))\b"
    # returned the wrong thing instead of what was asked for
    r"|\b(?:returned|showed|shows|brought up|gives?|yield(?:ed|s)?)\b[^.!?]{0,40}"
    r"\b(?:instead|random|everything|every (?:year|dress|photo)|unrelated|nothing)\b"
    # the app never indexed what they were searching on
    r"|\b(?:isn'?t|is not|wasn'?t|was not|doesn'?t|does not|didn'?t|did not)\s+"
    r"(?:properly\s+|correctly\s+)?(?:index\w*|parse\w*|tag\w*|recognis\w*|recogniz\w*|read)\b"
    r"|\bno way to search\b|\bcan'?t (?:combine|filter) (?:by|person|people)\b"
    r"|\bnot filtered by\b|\bdoesn'?t combine\b"
    # spent real time on it
    r"|\b(?:spent|took me|wasted)\b[^.!?]{0,25}\b(?:hour|hours|minutes|ages|forever)\b",
    re.I,
)

# Keeps out complaints that mention searching but are really about something
# else (storage, billing, crashes) and Google/web search rather than photos.
OFF_TOPIC = re.compile(
    r"\b(?:web|google|internet|browser|play store|app store)\s+search\b"
    r"|\bsearch\s+engine\b",
    re.I,
)

# The photo is GONE, not merely hard to find. That is data loss - a different
# problem from search failing - so those rows are dropped.
#
# Note the care around "lost": "I lost my physical vaccination card and needed
# the photo of it" is about a lost CARD, and the photo is still there to be
# searched for. Only loss of the photo/video itself disqualifies a row.
PHOTO_IS_GONE = re.compile(
    # "my photos disappeared / are missing / were deleted"
    r"\b(?:photos?|pics?|pictures?|images?|videos?|albums?|memories)\b"
    r"[^.!?]{0,40}?\b(?:disappear\w*|vanish\w*|are gone|is gone|went missing|"
    r"gone missing|missing|deleted|erased|wiped|removed|lost forever|"
    r"no longer (?:there|exist\w*)|not (?:there|showing up)|won'?t show up)\b"
    # "deleted / lost all my photos"
    r"|\b(?:deleted|delete|erased|wiped|lost|losing|removed)\b[^.!?]{0,25}?"
    r"\b(?:my|all|the|every|thousands of)\s+(?:\w+\s+){0,2}?"
    r"(?:photos?|pics?|pictures?|images?|videos?|albums?|memories)\b"
    r"|\bfree up space\b[^.!?]{0,40}\bdelet\w*",
    re.I,
)

# ...but these mean something physical was lost, not the photo.
LOST_A_REAL_OBJECT = re.compile(
    # Allow a few words in between: "lost my physical vaccination card".
    r"\blost\s+(?:my|the|his|her|our)?\s*(?:\w+\s+){0,3}?"
    r"(?:card|wallet|phone|passport|licence|license|documents?|receipt|keys?|bag)\b",
    re.I,
)

# "that functionality is missing", "the button disappeared" - a FEATURE is
# gone, not the photos. Those are still search/UI complaints, so they stay.
A_FEATURE_IS_GONE = re.compile(
    r"\b(functionality|feature|function|option|button|setting|menu|tab|toggle|"
    r"edit function|search bar)\b",
    re.I,
)


# Unmistakable data-loss language, checked against the WHOLE review rather
# than one passage - because the person often describes the search in one
# sentence and only reveals the photos are actually gone several lines later.
WHOLE_REVIEW_IS_ABOUT_LOSS = re.compile(
    r"\brecover(?:ing)?\s+(?:them|those|my|the|deleted)\b"
    r"|\brestore\s+(?:them|those|my)\s*(?:photos?|pictures?|videos?)?\b"
    r"|\b(?:they|those|photos?|pictures?|videos?)\s+(?:are|were|is)\s+"
    r"(?:just\s+|all\s+|permanently\s+|now\s+)?gone\b"
    r"|\bpermanently deleted\b|\bgone forever\b|\blost forever\b"
    r"|\bfrom (?:the )?trash\b|\bin the bin\b|\b60 days\b"
    r"|\blost (?:all|a lot of|a bunch of|thousands of|most of) (?:my )?"
    r"(?:photos?|pictures?|videos?|memories)\b",
    re.I,
)


def photo_is_gone(window):
    """True when the PHOTO itself is missing - as opposed to a feature being
    missing, or a physical object being lost."""
    match = PHOTO_IS_GONE.search(window)
    if not match:
        return False
    if LOST_A_REAL_OBJECT.search(window):
        return False
    # If the thing described as missing is a feature, this is not data loss.
    if A_FEATURE_IS_GONE.search(match.group(0)):
        return False
    return True


# ---------------------------------------------------------------------------
# Happy 5-star reviews
# ---------------------------------------------------------------------------
# A 5-star review that reports a real difficulty is still useful evidence
# ("love this app, but I can never find old photos"). One that is simply
# delighted is not. So we look for any sign of a complaint before deciding.
COMPLAINT_SIGNAL = re.compile(
    r"\b(can'?t|cannot|couldn'?t|won'?t|doesn'?t|don'?t|didn'?t|isn'?t|aren'?t|"
    r"hard|harder|difficult|struggle|struggling|annoying|annoyed|frustrat\w*|"
    r"useless|broken|terrible|awful|awkward|confusing|confused|"
    r"issue|issues|problem|problems|bug|bugs|glitch|fix|fails?|failed|"
    r"wish|should be|needs? to|would be better|but |however|unfortunately|"
    r"hate|dislike|worse|worst|complaint|disappoint\w*|"
    r"takes (?:too )?long|forever|no way to|lacking|missing)\b",
    re.I,
)


# Phrases that LOOK like complaints but are praise: "can't think of anything
# negative", "no complaints", "nothing bad to say". These are stripped out
# before deciding whether a review is genuinely happy.
PRAISE_IN_DISGUISE = re.compile(
    r"\b(?:can'?t|cannot|couldn'?t)\s+think\s+of\s+(?:anything|a\s+\w+\s+reason|"
    r"any\s+\w+|nothing)[^.!?]*"
    r"|\bno\s+(?:complaints?|issues?|problems?|downsides?)\b"
    r"|\bnothing\s+(?:negative|bad|wrong)\b"
    r"|\bcan'?t\s+fault\b|\bno\s+reason\s+not\s+to\b",
    re.I,
)


def is_happy_five_star(rating, text):
    """True for a 5-star review with nothing negative in it at all."""
    if str(rating).strip() not in ("5", "5.0"):
        return False
    # Remove praise that is phrased negatively, then look for real complaints.
    without_disguised_praise = PRAISE_IN_DISGUISE.sub(" ", text)
    return not COMPLAINT_SIGNAL.search(without_disguised_praise)


def best_passage(text, pattern):
    """The sentence (plus its neighbour) where a pattern appears - used to
    quote the relevant bit of a long review rather than the whole thing."""
    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s and s.strip()]
    for i, sentence in enumerate(sentences):
        if pattern.search(sentence):
            return " ".join(" ".join(sentences[i:i + 2]).split())
    return " ".join(text.split())[:400]


def analyse(text):
    """Keeps a review when the writer (a) could not fully remember what they
    wanted, (b) is talking about a photo or video, and (c) was trying to find
    it.

    Judged across the WHOLE review, not one passage: people often say what
    they couldn't remember in one sentence and what happened several
    sentences later, and it is all one person's story either way.

    A failure is NOT required - "I couldn't remember the date so I just
    scrolled" is evidence of the problem even without a complaint. Whether a
    failure was mentioned is recorded in its own column instead.
    """
    # Uncertainty about the app ("not sure why it does that") is not memory.
    without_app_talk = UNCERTAIN_ABOUT_THE_APP.sub(" ", text)
    memory = MEMORY_STRUGGLE.search(without_app_talk)
    if not memory:
        return None

    if not PHOTO_OBJECT.search(text):
        return None

    if not SEARCH_ATTEMPT.search(text):
        return None

    # The photo is gone - data loss, not a memory problem.
    if WHOLE_REVIEW_IS_ABOUT_LOSS.search(text) and not LOST_A_REAL_OBJECT.search(text):
        return None

    passage = best_passage(without_app_talk, MEMORY_STRUGGLE)

    # Only drop the review if the memory bit itself is about editing.
    if ABOUT_EDITING.search(passage):
        return None

    if photo_is_gone(passage):
        return None

    found = [name for name, pattern in ATTRIBUTES if pattern.search(text)]
    if MEMORY_CONCEPT.search(text):
        found.append("describes how memory works")

    quoted = [
        q.strip() for q in QUOTED_TERMS.findall(text)
        if 0 < len(q.split()) <= 5 and not q.strip().endswith(("doesn", "don", "isn", "won"))
    ]

    return {
        "matched_text": passage,
        "attributes_searched": "; ".join(found) or "not stated",
        "searched_terms": "; ".join(dict.fromkeys(quoted)),
        "search_failed": "yes" if FAILURE.search(text) else "no",
        "forgot": " ".join(memory.group(0).split()),
    }


def _old_analyse(text):
    """Returns details of the first passage that shows an attribute-based
    search that failed, or None."""
    # If the review as a whole is the story of losing photos, it belongs to
    # the data-loss problem, not the search problem - whatever any individual
    # sentence looks like.
    if WHOLE_REVIEW_IS_ABOUT_LOSS.search(text) and not LOST_A_REAL_OBJECT.search(text):
        return None

    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s and s.strip()]

    for i in range(len(sentences)):
        window = " ".join(sentences[i:i + SENTENCE_WINDOW])

        if not SEARCH_ATTEMPT.search(window):
            continue
        if not FAILURE.search(window):
            continue
        if OFF_TOPIC.search(window):
            continue

        # THE POINT OF THIS FILTER: they could not fully remember what they
        # were looking for. A plain "can't find my photos" has no evidence of
        # a memory problem, so it is not what this file is for.
        # Take out phrases that are uncertainty about the APP ("not sure why
        # it does this"), then see whether any genuine memory struggle is
        # still left. If not, this is a complaint, not a memory problem.
        without_app_talk = UNCERTAIN_ABOUT_THE_APP.sub(" ", window)
        if not MEMORY_STRUGGLE.search(without_app_talk):
            continue

        # Editing is a different subject.
        if ABOUT_EDITING.search(window):
            continue

        # Drop rows where the photo itself is gone - that is data loss, not a
        # search that failed.
        if photo_is_gone(window):
            continue

        found = [name for name, pattern in ATTRIBUTES if pattern.search(window)]

        # Someone explaining that human memory does not match how the app
        # indexes photos is describing this exact problem, even if they never
        # name a concrete object or place.
        if MEMORY_CONCEPT.search(window):
            found.append("describes how memory works")

        if not found:
            continue

        # Quotes are also used for emphasis ("Search" doesn't work), so a
        # capture can accidentally run from one quote mark to the next across
        # a whole clause. A real search term is a few words, so anything
        # longer than that is discarded rather than reported as a query.
        quoted = [
            q.strip() for q in QUOTED_TERMS.findall(window)
            if 0 < len(q.split()) <= 5 and not q.strip().endswith(("doesn", "don", "isn", "won"))
        ]

        return {
            "matched_text": " ".join(window.split()),
            "attributes_searched": "; ".join(found),
            "searched_terms": "; ".join(dict.fromkeys(quoted)),
        }

    return None


def get(row, key):
    return (row.get(key) or "").strip() if key else ""


def main():
    kept = []
    per_source = {}

    for source in SOURCES:
        path = os.path.join(RAW_DIR, source["file"])
        if not os.path.exists(path):
            print(f"SKIPPED (not found): {source['file']}")
            continue

        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))

        count = 0
        for row in rows:
            text = " ".join(get(row, c) for c in source["text"]).strip()
            if len(text) < 25:
                continue

            # A wholly positive 5-star review is not evidence of a problem.
            if is_happy_five_star(get(row, source["rating"]), text):
                continue

            result = analyse(text)
            if not result:
                continue

            kept.append({
                "source": source["name"],
                "date": get(row, source["date"])[:10],
                "rating": get(row, source["rating"]),
                "engagement": get(row, source["engagement"]),
                "text": text,
                "url": get(row, source["url"]),
                "attributes_searched": result["attributes_searched"],
                "searched_terms": result["searched_terms"],
                "search_failed": result["search_failed"],
                "forgot": result["forgot"],
                "matched_text": result["matched_text"],
            })
            count += 1

        per_source[source["name"]] = (count, len(rows))

    columns = ["source", "date", "rating", "engagement", "text", "url",
               "attributes_searched", "searched_terms", "search_failed",
               "forgot", "matched_text"]

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(kept)

    print("Attribute-based searches that FAILED:\n")
    for name, (count, total) in per_source.items():
        print(f"  {name:<26} {count:>4} of {total:>6}")
    print(f"  {'-'*26} {'-'*4}")
    print(f"  {'TOTAL':<26} {len(kept):>4}")
    print(f"\nSaved to data/filtered_data/{os.path.basename(OUTPUT_FILE)}\n")

    print("What people were searching ON (a row can use several):")
    counts = {}
    for row in kept:
        for attribute in row["attributes_searched"].split("; "):
            counts[attribute] = counts.get(attribute, 0) + 1
    for attribute, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {attribute:<20} {count:>4}")

    quoted = [r for r in kept if r["searched_terms"]]
    failed = [r for r in kept if r["search_failed"] == "yes"]
    print(f"\nRows where the person quoted the words they typed: {len(quoted)}")
    print(f"Rows that also describe the search failing:         {len(failed)}"
          f"  (the strongest cases)")


if __name__ == "__main__":
    main()
