"""
step3_query.py

Step 3 of the retrieval pipeline - asking questions of the review data.

What this script does (in plain words):
1. Opens the Chroma database built in step 2 (it does NOT rebuild it).
2. Loads the same "all-MiniLM-L6-v2" model, because a question has to be turned
   into numbers the SAME way the reviews were, or the comparison is meaningless.
3. ask_question(question) then:
   a. Turns the question into a vector.
   b. Pulls the 8 most similar review chunks out of the database.
   c. GUARDRAIL: if even the best match is weak (below MIN_SIMILARITY), it does
      not call the AI at all. Nothing relevant was found, so there is nothing
      honest to say - and this is what stops the tool inventing an answer.
   d. Otherwise it builds a strict prompt telling the AI to use ONLY those
      reviews, never to invent quotes, and to decline off-topic questions.
   e. Sends it to Google's Gemini model and returns the answer.
   f. Always prints the source review URLs and their similarity scores, so
      every claim can be traced back to real evidence.
4. Runs four test questions, then hands over to you: type your own questions
   for as long as you like, and type 'quit' when you're finished.

A NOTE ON THE API KEY:
The key is NOT stored in this file. It is read from an environment variable
called GEMINI_API_KEY, so the key never sits in your code where it could be
shared, copied or uploaded by accident.

HOW TO RUN THIS:
    pip3 install google-genai
    export GEMINI_API_KEY="your-key-here"
    python3 scripts/step3_query.py

Input: vector_db/chroma_db/  (built by step2_embed.py)
"""

import os
import re
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

# The project folder, worked out from where THIS file sits. Everything is
# located relative to that, so the script works no matter which folder you run
# it from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_FOLDER = os.path.join(PROJECT_ROOT, "vector_db", "chroma_db")
COLLECTION_NAME = "google_photos_reviews"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# How many chunks to retrieve overall, before balancing by source.
TOP_K = 8

# 85% of the collection is Play Store reviews, which are short and repetitive.
# Without help, they crowd out the richer Reddit and forum posts. So after the
# overall search we also take the best few from each of these sources.
SOURCES_TO_BALANCE = ["Reddit", "Google Photos Community", "YouTube"]
PER_SOURCE_K = 2

# ...but only if they are genuinely relevant. A source with nothing useful to
# say about the question should stay out, not pad the answer with noise.
PER_SOURCE_MIN_SIMILARITY = 0.45

# The most chunks the AI is ever given for one question.
MAX_EVIDENCE = 12

# When a question asks about a particular period, we search this many chunks
# before filtering by date. It has to be wide: the best matches overall may all
# fall outside the period, leaving nothing if we only looked at the top few.
WIDE_NET = 400

# Said when a period was asked for but nothing was written in it.
NO_FEEDBACK_IN_PERIOD = (
    "I don't have any feedback from {period} in the review data, so I can't "
    "answer that for this time frame."
)

# Google's free tier allows only about 5 requests per minute, so we pause
# between questions to stay under it.
SECONDS_BETWEEN_QUESTIONS = 15

# The guardrail. Similarity runs from -1 (opposite) to 1 (identical meaning).
# If the best chunk we can find scores below this, we refuse to answer.
MIN_SIMILARITY = 0.4

NOT_ENOUGH_EVIDENCE = (
    "I don't have enough evidence in the review data to answer this confidently."
)

# Gemini model to use. "gemini-1.5-flash" has been retired by Google, so we try
# the current Flash models in order and use the first one that is available.
# Listing several means this script keeps working when model names change.
# "flash-lite" is a lighter model that tends to be less congested, so it is far
# less likely to answer with "503 - high demand" than the bigger Flash models.
#
# Google retires model names regularly (gemini-1.5-flash and gemini-2.5-flash-lite
# have both been retired during this project), so we keep a list. If the model we
# ask for has been retired, the script automatically moves on to the next one
# rather than failing.
MODEL_NAME = "gemini-3.5-flash-lite"
MODEL_CANDIDATES = [
    MODEL_NAME,
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-2.5-flash",
]

# How long to wait between retries when the server is busy, in seconds. Each
# retry waits longer than the last ("exponential backoff"), which gives an
# overloaded model time to recover instead of hammering it.
RETRY_WAITS = [5, 15, 30, 60]

# One first try, plus one retry for each wait above = 5 attempts in total.
MAX_ATTEMPTS = len(RETRY_WAITS) + 1

def get_api_key():
    """Reads the Gemini API key from the environment. The key is deliberately
    NOT written in this file - anyone who can read the file could otherwise
    use your key."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit(
            "\nNo GEMINI_API_KEY found.\n\n"
            "Set it in Terminal with:\n"
            '    export GEMINI_API_KEY="your-key-here"\n\n'
            "To make it stick every time you open Terminal, run:\n"
            '    echo \'export GEMINI_API_KEY="your-key-here"\' >> ~/.zshrc\n'
            "    source ~/.zshrc\n"
        )
    return key

PROMPT_TEMPLATE = """You are analyzing real user feedback about Google Photos search and retrieval problems. The feedback comes from four places: Google Play Store reviews, Reddit posts, YouTube comments, and the Google Photos community support forum. Each item below says which one it came from.

Follow these rules strictly:
- Only use information from the user feedback provided below. Do not use any outside knowledge.
- Do not invent or fabricate exact quotes - paraphrase what people say instead.
- If the feedback doesn't clearly support an answer, say so honestly instead of guessing.
- If the question is unrelated to Google Photos search/retrieval (e.g. general knowledge, unrelated topics), politely decline to answer and say this tool only analyzes Google Photos user feedback.
- Mention patterns across multiple items where relevant, and note if a pattern is based on only 1-2 items vs. many.
- Where it matters, say which source a pattern comes from (for example, whether it appears mainly in Reddit posts or in Play Store reviews).
- Some long posts were split into parts, marked "part 2 of 3". Treat those as excerpts from one longer post, not as separate people.

User feedback:
{reviews}

Question: {question}"""


# ---------------------------------------------------------------------------
# Set-up: done once, then reused for every question
# ---------------------------------------------------------------------------
def load_everything():
    """Opens the existing database and loads the models. Returns a tuple of
    (chroma collection, embedding model, gemini model)."""
    import chromadb
    from google import genai
    from sentence_transformers import SentenceTransformer

    if not os.path.exists(DB_FOLDER):
        raise SystemExit(
            f"No '{DB_FOLDER}' folder found. Run step2_embed.py first."
        )

    client = chromadb.PersistentClient(path=DB_FOLDER)
    collection = client.get_collection(COLLECTION_NAME)
    print(f"Opened existing database '{COLLECTION_NAME}' with {collection.count()} chunks")

    embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    print(f"Loaded embedding model '{EMBED_MODEL_NAME}'")

    client = genai.Client(api_key=get_api_key())

    # Ask Google which models this key can actually use. We check the LIST
    # rather than sending a test message, because the free tier only allows a
    # few messages per minute and we don't want to waste one on a test.
    chosen = MODEL_NAME
    try:
        available = {
            model.name.replace("models/", "")
            for model in client.models.list()
            if model.supported_actions and "generateContent" in model.supported_actions
        }
        chosen = next((name for name in MODEL_CANDIDATES if name in available), MODEL_NAME)
    except Exception as e:
        # Not fatal: we can still try the default model and report any real
        # error when the first question is asked.
        print(f"(Could not list models: {type(e).__name__}. Trying '{MODEL_NAME}' anyway.)")

    gemini_model = GeminiRunner(client, chosen)
    print(f"Using Gemini model '{chosen}'\n")

    return collection, embed_model, gemini_model


class GeminiRunner:
    """A thin wrapper around the google-genai client, so the rest of the script
    just calls .generate(prompt) and doesn't care about SDK details.

    If Google has retired the model we asked for, it says so with a 404. Rather
    than failing, we move down the list of backup models and try the next one.
    """

    def __init__(self, client, model_name):
        self.client = client
        self.model_name = model_name

        # The models we may fall back to, starting after the chosen one.
        remaining = [n for n in MODEL_CANDIDATES if n != model_name]
        self.backups = remaining

    def generate(self, prompt):
        while True:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                message = str(e)
                model_retired = "404" in message and (
                    "no longer available" in message
                    or "not found" in message.lower()
                    or "NOT_FOUND" in message
                )

                if not model_retired or not self.backups:
                    raise

                # Google often names the replacement model in the error text.
                # Prefer that, since it is the most accurate answer available.
                suggested = re.search(r"use\s+models/([A-Za-z0-9.\-]+)", message)
                if suggested and suggested.group(1) != self.model_name:
                    next_model = suggested.group(1)
                else:
                    next_model = self.backups[0]

                if next_model in self.backups:
                    self.backups.remove(next_model)

                print(f"   ('{self.model_name}' has been retired - "
                      f"switching to '{next_model}')")
                self.model_name = next_model


def generate_with_retry(gemini_model, prompt, attempts=MAX_ATTEMPTS):
    """Calls Gemini, waiting and trying again when the problem is temporary.

    Two temporary problems are worth retrying:
      429 - too many requests too quickly (the free tier's rate limit)
      503 - the model is busy right now ("high demand")

    Both usually clear up on their own within a minute or two, so we wait a bit
    longer before each retry (5s, 15s, 30s, 60s) rather than giving up. Any
    other error - a bad key, say - is NOT retried, because waiting will not fix
    it and there is no point making you sit through four pointless pauses.
    """
    import re
    import time

    for attempt in range(1, attempts + 1):
        try:
            return gemini_model.generate(prompt).strip()
        except Exception as e:
            message = str(e)
            error_name = type(e).__name__

            is_rate_limit = (
                "429" in message
                or "RESOURCE_EXHAUSTED" in message
                or "ResourceExhausted" in error_name
            )
            is_busy = (
                "503" in message
                or "UNAVAILABLE" in message.upper()
                or "overloaded" in message.lower()
                or "high demand" in message.lower()
            )

            if not (is_rate_limit or is_busy) or attempt == attempts:
                return f"(The Gemini API call failed: {error_name} - {message[:200]})"

            # For a rate limit, Google usually tells us exactly how long to
            # wait - trust that. Otherwise use our growing backoff waits.
            match = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)", message)
            if is_rate_limit and match:
                wait_seconds = int(match.group(1)) + 2
            else:
                wait_seconds = RETRY_WAITS[min(attempt - 1, len(RETRY_WAITS) - 1)]

            reason = "rate limit (429)" if is_rate_limit else "model busy (503)"
            print(f"   ({reason} - waiting {wait_seconds}s before retry "
                  f"{attempt + 1} of {attempts}...)")
            time.sleep(wait_seconds)

    return "(The Gemini API call failed after several retries.)"


# ---------------------------------------------------------------------------
# The main function
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Reading a time period out of the question
# ---------------------------------------------------------------------------
# People often want an answer about a particular stretch of time - "reviews
# from Jan'26 to Sep'26", "what changed in 2025", "since 2023". When they do,
# the answer must come ONLY from feedback written in that period, or the dates
# in the citations will not match what was asked for.
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

# How many days each month has (February is treated as 29 - being a day out at
# the very end of a range does not matter for this kind of question).
MONTH_LAST_DAY = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# A year written as '26 or 26 means 2026, not 1926.
def _full_year(text):
    number = int(text)
    return number if number > 100 else 2000 + number


def _month_of(text):
    return MONTHS.get(text.lower().strip(". ")) if text else None


def _start_of(year, month):
    return f"{year:04d}-{(month or 1):02d}-01"


def _end_of(year, month):
    month = month or 12
    return f"{year:04d}-{month:02d}-{MONTH_LAST_DAY[month]:02d}"


# "Jan'26", "January 2026", "09/2026", or just "2026"
_POINT = r"(?:(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|" \
         r"jul(?:y)?|aug(?:ust)?|sep(?:t)?(?:ember)?|oct(?:ober)?|nov(?:ember)?|" \
         r"dec(?:ember)?)[\s,'’]*)?'?(\d{4}|\d{2})"

RANGE_PATTERNS = [
    # "from Jan'26 to Sep'26", "Jan 2026 - Sep 2026", "between 2024 and 2025"
    re.compile(rf"(?:from|between)?\s*{_POINT}\s*(?:-|–|—|to|till|until|through|and)\s*{_POINT}", re.I),
]

SINGLE_PATTERNS = [
    ("since", re.compile(rf"\b(?:since|after|from)\s+{_POINT}", re.I)),
    ("until", re.compile(rf"\b(?:before|until|till|up\s+to|prior\s+to)\s+{_POINT}", re.I)),
    ("in", re.compile(rf"\b(?:in|during|for|of)\s+{_POINT}", re.I)),
]

RELATIVE = re.compile(
    r"\b(?:last|past|previous)\s+(\d{1,2})?\s*(day|week|month|year)s?\b", re.I
)


def parse_date_range(question):
    """Finds a time period in the question.

    Returns (start, end, description) as YYYY-MM-DD strings, or
    (None, None, None) when no period was asked for. Either end can be None,
    meaning "no limit in that direction".
    """
    text = question.strip()

    # "last 6 months", "past year"
    relative = RELATIVE.search(text)
    if relative:
        amount = int(relative.group(1) or 1)
        unit = relative.group(2).lower()
        days = {"day": 1, "week": 7, "month": 30, "year": 365}[unit] * amount
        today = datetime.now()
        start = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        return start, end, f"the last {amount} {unit}{'s' if amount > 1 else ''}"

    # "Jan'26 - Sep'26"
    for pattern in RANGE_PATTERNS:
        found = pattern.search(text)
        if found:
            m1, y1, m2, y2 = found.groups()
            month1, month2 = _month_of(m1), _month_of(m2)
            year1, year2 = _full_year(y1), _full_year(y2)
            # Ignore nonsense like "top 5 to 10" that happens to match.
            if 2000 <= year1 <= 2100 and 2000 <= year2 <= 2100 and year1 <= year2:
                start = _start_of(year1, month1)
                end = _end_of(year2, month2)
                return start, end, f"{_describe(month1, year1)} to {_describe(month2, year2)}"

    for kind, pattern in SINGLE_PATTERNS:
        found = pattern.search(text)
        if found:
            month, year = _month_of(found.group(1)), _full_year(found.group(2))
            if not 2000 <= year <= 2100:
                continue
            if kind == "since":
                return _start_of(year, month), None, f"since {_describe(month, year)}"
            if kind == "until":
                return None, _end_of(year, month), f"up to {_describe(month, year)}"
            return (_start_of(year, month), _end_of(year, month),
                    _describe(month, year))

    return None, None, None


def _describe(month, year):
    return f"{MONTH_NAMES[month]} {year}" if month else str(year)


def in_range(metadata, start, end):
    """True if this piece of feedback was written inside the wanted period."""
    date = (metadata.get("date") or "")[:10]
    if len(date) != 10:
        return False          # undated - safer to leave out of a dated answer
    if start and date < start:
        return False
    if end and date > end:
        return False
    return True


def query_chroma(collection, vector, n_results, source=None):
    """Runs one search, optionally restricted to a single source.
    Returns a list of (document, metadata, similarity)."""
    kwargs = {"query_embeddings": [vector], "n_results": n_results}
    if source:
        kwargs["where"] = {"source": source}

    try:
        results = collection.query(**kwargs)
    except Exception:
        return []

    return [
        (document, metadata, 1 - distance)
        for document, metadata, distance in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
    ]


def retrieve(collection, vector, start=None, end=None):
    """Gathers the evidence to hand to the AI.

    Plain "top 8 overall" is dominated by Play Store reviews, simply because
    there are far more of them - so the richer Reddit and forum posts can be
    crowded out even when they are more relevant. To avoid that, we ALSO take
    the best few from each source separately, and merge everything together.

    Weak per-source matches are ignored, so a source with nothing useful to say
    about this question stays out rather than padding the answer with noise.

    When start/end are given, only feedback written in that period is used. We
    search a much wider net first and then keep what falls inside the dates,
    because the closest matches overall may all sit outside the period asked
    about - and returning those would answer the wrong question.
    """
    if start or end:
        # Cast a wide net, then keep only what falls in the period.
        wide = query_chroma(collection, vector, WIDE_NET)
        gathered = [item for item in wide if in_range(item[1], start, end)]

        for source in SOURCES_TO_BALANCE:
            for item in query_chroma(collection, vector, WIDE_NET, source=source):
                if item[2] >= PER_SOURCE_MIN_SIMILARITY and in_range(item[1], start, end):
                    gathered.append(item)
    else:
        gathered = query_chroma(collection, vector, TOP_K)

        for source in SOURCES_TO_BALANCE:
            for item in query_chroma(collection, vector, PER_SOURCE_K, source=source):
                if item[2] >= PER_SOURCE_MIN_SIMILARITY:
                    gathered.append(item)

    # The same chunk can arrive twice (once overall, once per-source).
    unique = {}
    for document, metadata, similarity in gathered:
        key = (metadata.get("url", ""), metadata.get("part", ""), document[:60])
        if key not in unique or similarity > unique[key][2]:
            unique[key] = (document, metadata, similarity)

    best_first = sorted(unique.values(), key=lambda item: -item[2])[:MAX_EVIDENCE]

    documents = [item[0] for item in best_first]
    metadatas = [item[1] for item in best_first]
    similarities = [item[2] for item in best_first]
    return documents, metadatas, similarities


def ask_question(question, collection, embed_model, gemini_model,
                 quiet=False, return_details=False):
    """Answers a question using only the review data.

    quiet          - don't print anything (used by the web app, which displays
                     the result itself instead of writing to the terminal)
    return_details - return a dictionary with the answer AND the sources behind
                     it, instead of just the answer text. The web app needs the
                     sources to show its "View sources" panel.

    Default behaviour is unchanged: print everything, return the answer text.
    """
    def say(*args):
        if not quiet:
            print(*args)

    say("=" * 78)
    say(f"QUESTION: {question}")
    say("=" * 78)

    # a. Did the question ask about a particular stretch of time?
    start, end, period = parse_date_range(question)
    if period:
        say(f"\n(time period detected: {period} -> {start or 'any'} .. {end or 'any'})")

    # b. Embed the question and fetch the most similar chunks.
    question_vector = embed_model.encode([question])[0].tolist()
    documents, metadatas, similarities = retrieve(collection, question_vector, start, end)

    best_similarity = max(similarities) if similarities else 0.0

    def package(answer, used):
        """Bundles the answer with the evidence behind it, for the web app."""
        if not return_details:
            return answer
        return {
            "answer": answer,
            "best_similarity": best_similarity,
            "used": used,
            "period": period,
            "period_start": start,
            "period_end": end,
            "sources": [
                {
                    "url": metadata.get("url", ""),
                    "source": metadata.get("source", ""),
                    "date": metadata.get("date", "")[:10],
                    "rating": metadata.get("rating", ""),
                    "engagement": metadata.get("engagement", ""),
                    "part": metadata.get("part", "1/1"),
                    "similarity": similarity,
                    "text": document,
                }
                for document, metadata, similarity in zip(documents, metadatas, similarities)
            ],
        }

    # c1. A period was asked for, but nothing was written in it. Saying so is
    #     the only honest answer - anything else would quote the wrong dates.
    if period and not documents:
        message = NO_FEEDBACK_IN_PERIOD.format(period=period)
        say(f"\nNo feedback found in that period.\n\nANSWER:\n{message}\n")
        return package(message, used=False)

    # c2. The guardrail: nothing relevant found, so do not call the AI at all.
    if best_similarity < MIN_SIMILARITY:
        say(f"\nGUARDRAIL TRIGGERED - best match only {best_similarity:.3f}, "
            f"below the {MIN_SIMILARITY} threshold.")
        say("The AI was NOT called, so it had no chance to invent an answer.\n")
        say(f"ANSWER:\n{NOT_ENOUGH_EVIDENCE}\n")
        if not quiet:
            print_sources(metadatas, similarities, used=False)
        return package(NOT_ENOUGH_EVIDENCE, used=False)

    # d. Build the strict prompt from the retrieved reviews.
    numbered_reviews = "\n".join(
        f"{i}. {document}" for i, document in enumerate(documents, start=1)
    )
    prompt = PROMPT_TEMPLATE.format(reviews=numbered_reviews, question=question)

    if period:
        # Every item below is already inside the period, but say so explicitly
        # so the answer is framed as being about that time and nothing else.
        prompt += (
            f"\n\nIMPORTANT: this question is about {period}. Every item above was "
            f"written in that period and the answer must describe only that period. "
            f"Do not generalise beyond it, and mention the time frame in your answer."
        )

    # e. Ask Gemini.
    say(f"\n(best match {best_similarity:.3f} - above threshold, so the AI was called)")
    answer = generate_with_retry(gemini_model, prompt)
    say(f"\nANSWER:\n{answer}\n")

    # f. Always show the evidence behind the answer.
    if not quiet:
        print_sources(metadatas, similarities, used=True)
    return package(answer, used=True)


def describe(metadata):
    """One readable line about where a chunk came from. Play Store rows have a
    star rating; Reddit and YouTube have upvotes/likes instead; the forum has
    neither - so we only show what actually exists."""
    bits = [metadata.get("source", "?"), metadata.get("date", "")[:10]]
    if metadata.get("rating"):
        bits.append(f"{metadata['rating']} stars")
    if metadata.get("engagement"):
        bits.append(f"{metadata['engagement']} upvotes/likes")
    if metadata.get("part", "1/1") != "1/1":
        bits.append(f"part {metadata['part']}")
    return " | ".join(b for b in bits if b)


def print_sources(metadatas, similarities, used):
    """Prints every retrieved item with its score, so answers are traceable."""
    heading = "SOURCES GIVEN TO THE AI" if used else "CLOSEST MATCHES FOUND (all too weak to use)"
    print(f"{heading}:")
    print("-" * 78)
    for i, (metadata, similarity) in enumerate(zip(metadatas, similarities), start=1):
        print(f"{i}. similarity {similarity:.3f} | {describe(metadata)}")
        print(f"   {metadata['url']}")
    print()


# ---------------------------------------------------------------------------
# Ask your own questions, over and over, until you type 'quit'
# ---------------------------------------------------------------------------
QUIT_WORDS = {"quit", "exit", "q", "stop"}


def interactive_loop(collection, embed_model, gemini_model):
    print("\n" + "#" * 78)
    print("# The test questions are done. Now it's your turn.")
    print("#" * 78)

    while True:
        print("\nAsk your own question (or type 'quit' to stop):")

        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl-C or Ctrl-D should stop cleanly, not crash with a red error.
            print("\nStopped. Bye!")
            return

        if question.lower() in QUIT_WORDS:
            print("Bye!")
            return

        if not question:
            print("(Nothing typed - try asking something about the reviews.)")
            continue

        ask_question(question, collection, embed_model, gemini_model)


# ---------------------------------------------------------------------------
# Run the four test questions
# ---------------------------------------------------------------------------
TEST_QUESTIONS = [
    "What are the most common reasons users fail to find an old photo?",
    "Do users mention giving up on their search? What do they do instead?",
    "What specific information do users say they remember about a photo they're trying to find?",
    "What's the capital of France?",
]


def main():
    import time

    collection, embed_model, gemini_model = load_everything()

    for i, question in enumerate(TEST_QUESTIONS):
        # The free tier allows only about 5 requests a minute, so we space the
        # questions out rather than firing them off back to back.
        if i > 0:
            time.sleep(SECONDS_BETWEEN_QUESTIONS)
        ask_question(question, collection, embed_model, gemini_model)
        print()

    interactive_loop(collection, embed_model, gemini_model)


if __name__ == "__main__":
    main()
