"""
app.py - the web interface for the Google Photos discovery engine.

This is only a FRONT END. All the thinking happens in
backend/scripts/step3_query.py - this file imports that script's
ask_question() function and calls it, so there is exactly one copy of the
search-and-answer logic and the two can never disagree.

THE LAYOUT (three panels, each scrolling on its own):
    left   - what this project is, and the history of questions asked
    centre - the conversation, with the question box at its foot
    right  - the reviews each answer was based on, with their scores

On a phone the three panels stack into one column.

HOW TO RUN IT:
    export GEMINI_API_KEY="your-key-here"
    streamlit run app.py
"""

import html
import importlib.util
import os
import re

import streamlit as st

# This file lives in frontend/, so the project folder is one level up - that
# is where backend/ sits alongside it.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEP3_PATH = os.path.join(PROJECT_ROOT, "backend", "scripts", "step3_query.py")

# How tall the three panels are. They scroll inside themselves, so the page
# as a whole never needs a scrollbar.
PANEL_HEIGHT = 430

GREETING = "Hello! 👋 How can I help you today?"

EXAMPLE_QUESTIONS = [
    "Why do people fail to find an old photo?",
    "Do users say the search returns wrong results?",
    "What do people remember about photos they look for?",
]

st.set_page_config(
    page_title="Google Photos Search - Discovery Engine",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      /* Tighten the page so all three panels fit on one screen without the
         whole window scrolling - each panel scrolls on its own instead. */
      .block-container { padding-top: 1.2rem; padding-bottom: 0.5rem; }
      [data-testid="stAppViewContainer"] > .main { overflow: hidden; }
      #MainMenu, footer { visibility: hidden; }

      h1 { font-size: 1.9rem !important; margin-bottom: .2rem; }

      /* The subtitle, given real emphasis rather than small grey caption text */
      .tagline {
        background: linear-gradient(90deg, rgba(66,133,244,.10), rgba(52,168,83,.08));
        border-left: 4px solid #4285F4;
        border-radius: 8px;
        padding: .55rem .9rem;
        font-size: .95rem;
        line-height: 1.45;
        margin-bottom: .9rem;
        /* Keep it on one line on a normal screen... */
        white-space: nowrap;
        overflow-x: auto;
      }
      /* ...but let it wrap on narrow screens rather than run off the edge. */
      @media (max-width: 1200px) {
        .tagline { white-space: normal; }
      }

      .panel-title { font-weight: 600; margin-bottom: .35rem; }
      .muted { opacity: .72; font-size: .86rem; }

      /* Chat bubbles - the person asking appears on the right, like a
         messaging app; the answer appears on the left. */
      .row-right { display: flex; justify-content: flex-end; margin: .35rem 0; }
      .bubble-user {
        background: #DDEBFF; color: #10508f;
        padding: .5rem .85rem; border-radius: 16px 16px 4px 16px;
        max-width: 85%; font-size: .94rem; word-wrap: break-word;
      }

      .src-card {
        border: 1px solid rgba(128,128,128,.25); border-radius: 10px;
        padding: .55rem .7rem; margin-bottom: .5rem; font-size: .85rem;
      }
      .src-head { font-weight: 600; margin-bottom: .15rem; }
      /* Full URLs are long, so let them wrap instead of overflowing the panel */
      .src-url {
        display: inline-block; margin-top: .25rem;
        font-size: .78rem; line-height: 1.3;
        word-break: break-all; overflow-wrap: anywhere;
      }

      /* Phones: let the panels stack and breathe instead of becoming three
         unreadable slivers. */
      @media (max-width: 900px) {
        [data-testid="stAppViewContainer"] > .main { overflow: auto; }
        .block-container { padding-left: .8rem; padding-right: .8rem; }
        h1 { font-size: 1.45rem !important; }
        .tagline { font-size: .94rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Load the backend once, and keep it loaded between questions
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def load_backend(backend_version):
    """Imports step3_query.py and opens the database + models.

    st.cache_resource means this runs ONCE, not on every interaction - loading
    the embedding model takes several seconds.

    backend_version is the "last modified" time of step3_query.py. It is not
    used inside the function; its only job is to be part of the cache key, so
    that EDITING step3_query.py automatically reloads it. Without this the app
    would happily keep running the old code until the server was restarted -
    which silently hides any backend change you make.
    """
    spec = importlib.util.spec_from_file_location("step3_query", STEP3_PATH)
    step3 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(step3)
    collection, embed_model, gemini_model = step3.load_everything()
    return step3, collection, embed_model, gemini_model


def backend_version():
    """When step3_query.py was last changed."""
    try:
        return os.path.getmtime(STEP3_PATH)
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# Small talk
# ---------------------------------------------------------------------------
# "Hello" is not a research question. Sending it to the search engine returns
# "I don't have enough evidence...", which is technically true but a rude way
# to answer a greeting. These are handled here in the interface instead, so no
# search is run and no AI request is spent on them.
SMALL_TALK = [
    (r"^(hi|hey|hello|hiya|yo|hola|namaste|greetings|"
     r"good\s*(morning|afternoon|evening|day))"
     r"(\s+(there|all|everyone|folks|guys|bot|again))?$",
     "Hello! 👋 Ask me anything about how people struggle to find their photos or "
     "videos in Google Photos — for example *“why do people fail to find an old photo?”*"),
    (r"^(thanks|thank\s*you|thx|ty|cheers|great|nice|cool|awesome|perfect|ok|okay|"
     r"got\s*it|understood)"
     r"(\s+(a\s*lot|so\s*much|very\s*much|mate|buddy))?$",
     "You're welcome! 🙂 Ask me another question whenever you like."),
    (r"^(bye|goodbye|see\s*you|good\s*night|cya)$",
     "Goodbye! 👋 Come back any time you want to dig into the reviews."),
    (r"^(who\s*are\s*you|what\s*are\s*you|what\s*can\s*you\s*do|help|what\s*is\s*this)\??$",
     "I answer questions using real user feedback about Google Photos — Play Store "
     "reviews, Reddit posts, YouTube comments and community forum posts. I only use "
     "what people actually wrote, and I show you the sources behind every answer.\n\n"
     "Try asking *“do users say the search returns wrong results?”*"),
    (r"^(how\s*are\s*you|how'?s\s*it\s*going)\??$",
     "Doing well, thank you! 🙂 What would you like to know about how people search "
     "for their photos?"),
]


def small_talk_reply(text):
    """Returns a friendly reply if the message is a greeting or pleasantry,
    otherwise None so it is treated as a real question.

    Only SHORT messages are considered, so "hello, why can't I find my photos?"
    is still answered properly from the reviews.
    """
    cleaned = re.sub(r"[^\w\s']", " ", text.lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    if len(cleaned.split()) > 4:
        return None

    for pattern, reply in SMALL_TALK:
        if re.fullmatch(pattern, cleaned, re.I):
            return reply
    return None


def source_line(source):
    """One line describing where a piece of evidence came from."""
    bits = [source["source"]]
    if source.get("date"):
        bits.append(source["date"])
    if source.get("rating"):
        bits.append(f"{source['rating']}★")
    if source.get("engagement"):
        bits.append(f"{source['engagement']} upvotes/likes")
    if source.get("part", "1/1") != "1/1":
        bits.append(f"part {source['part']}")
    return " · ".join(bits)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("# 🔍 Google Photos Search - Discovery Engine")
st.markdown(
    "<div class='tagline'>Explore why people struggle to find their photos/videos — answered "
    "only from real Play Store, Reddit, YouTube &amp; forum feedback, with sources.</div>",
    unsafe_allow_html=True,
)

# Conversation so far. Each turn is {"question", "answer", "sources", "used"}
if "turns" not in st.session_state:
    st.session_state.turns = []

# A question queued by clicking an example or a history entry.
if "pending" not in st.session_state:
    st.session_state.pending = None


# ---------------------------------------------------------------------------
# Start the backend (and fail helpfully if the API key is missing)
# ---------------------------------------------------------------------------
backend_ready = False
try:
    with st.spinner("Starting up - loading the review database..."):
        step3, collection, embed_model, gemini_model = load_backend(backend_version())
    backend_ready = True
except SystemExit as e:
    st.error(str(e) or "Could not start the backend.")
except Exception as e:  # noqa: BLE001 - show the user what went wrong
    st.error(f"Could not start the backend: {type(e).__name__} - {e}")


# ---------------------------------------------------------------------------
# The three panels
# ---------------------------------------------------------------------------
left, centre, right = st.columns([1.05, 2.3, 1.2], gap="medium")

# ----- LEFT: about the project, and the history of questions ---------------
with left:
    st.markdown("<div class='panel-title'>🕘 History</div>", unsafe_allow_html=True)
    with st.container(height=PANEL_HEIGHT, border=True):
        if not st.session_state.turns:
            st.markdown("<div class='muted'>Your previous questions will appear here.</div>",
                        unsafe_allow_html=True)
        else:
            # Newest first - that is what you want to click back to.
            for i, turn in enumerate(reversed(st.session_state.turns)):
                number = len(st.session_state.turns) - i
                if st.button(f"{number}. {turn['question'][:55]}",
                             key=f"hist{number}", use_container_width=True):
                    st.session_state.pending = turn["question"]
                    st.rerun()

            if st.button("🗑 Clear conversation", use_container_width=True):
                st.session_state.turns = []
                st.rerun()

# ----- CENTRE: the conversation, with the question box at its foot ---------
with centre:
    st.markdown("<div class='panel-title'>💬 Conversation</div>", unsafe_allow_html=True)

    with st.container(height=PANEL_HEIGHT, border=False):
        # A greeting, so the panel is never empty.
        with st.chat_message("assistant"):
            st.write(GREETING)

        for turn in st.session_state.turns:
            # The question, on the RIGHT like a messaging app.
            st.markdown(
                f"<div class='row-right'><div class='bubble-user'>"
                f"{html.escape(turn['question'])}</div></div>",
                unsafe_allow_html=True,
            )
            # The answer, on the LEFT. No source list here - sources live in
            # the right-hand panel so the conversation stays readable.
            with st.chat_message("assistant"):
                st.write(turn["answer"])

        # A question that has been asked but not answered yet. Showing it here
        # - with "Searching reviews..." underneath - means you see your question
        # land immediately, instead of the screen sitting still until the whole
        # answer is ready.
        if st.session_state.pending:
            st.markdown(
                f"<div class='row-right'><div class='bubble-user'>"
                f"{html.escape(st.session_state.pending)}</div></div>",
                unsafe_allow_html=True,
            )
            with st.chat_message("assistant"):
                # The answer is worked out below, once this has been drawn.
                st.markdown("_🔎 Searching reviews..._")

    # The example questions sit at the foot of the conversation, and disappear
    # once the conversation has started.
    if not st.session_state.turns and not st.session_state.pending:
        st.markdown("<div class='muted'>Try one of these:</div>", unsafe_allow_html=True)
        for i, example in enumerate(EXAMPLE_QUESTIONS):
            if st.button(example, key=f"eg{i}", use_container_width=True,
                         disabled=not backend_ready):
                st.session_state.pending = example
                st.rerun()

    # The question box, inside the centre panel rather than across the page.
    typed = st.chat_input(
        "Ask a question about finding photos/videos..." if backend_ready
        else "Backend not available",
        disabled=not backend_ready,
    )

# ----- RIGHT: the evidence behind the latest answer ------------------------
with right:
    st.markdown("<div class='panel-title'>🔗 Sources</div>", unsafe_allow_html=True)
    with st.container(height=PANEL_HEIGHT, border=True):
        if st.session_state.turns:
            latest = st.session_state.turns[-1]
            used = latest.get("used", True)

            def show_sources(sources):
                with st.expander("View sources", expanded=True):
                    for i, source in enumerate(sources, start=1):
                        st.markdown(
                            f"<div class='src-card'>"
                            f"<div class='src-head'>{i}. {html.escape(source_line(source))}</div>"
                            f"<div class='muted'>similarity {source['similarity']:.3f}</div>"
                            f"<a class='src-url' href='{html.escape(source['url'])}' "
                            f"target='_blank'>{html.escape(source['url'])}</a>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

            if used and latest["sources"]:
                period_note = ""
                if latest.get("period"):
                    # Make it obvious the date filter was applied, and to what.
                    period_note = (
                        f"<br><b>Limited to {html.escape(latest['period'])}</b>"
                    )
                st.markdown(
                    f"<div class='muted'>Evidence behind the latest answer — "
                    f"{len(latest['sources'])} items.{period_note}</div>",
                    unsafe_allow_html=True,
                )
                show_sources(latest["sources"])
            else:
                # Either a greeting (nothing was searched) or an off-topic
                # question (only weak matches, which would mislead if shown).
                # Either way we say plainly that there are none, then fall back
                # to the last answer that DID have sources.
                if latest.get("smalltalk"):
                    st.markdown(
                        "<div class='muted'>No sources needed — that was a greeting, "
                        "so no reviews were searched.</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown("**No sources found**")

                previous = next(
                    (t for t in reversed(st.session_state.turns[:-1])
                     if t.get("used") and t["sources"]),
                    None,
                )
                if previous:
                    st.markdown(
                        f"<div class='muted' style='margin-top:.6rem'>Sources for "
                        f"previous answer — {len(previous['sources'])} items.</div>",
                        unsafe_allow_html=True,
                    )
                    show_sources(previous["sources"])
        else:
            st.markdown(
                "<div class='muted'>Sources for each answer will appear here, with a "
                "similarity score showing how closely each review matched your question."
                "</div>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Handle a new question
# ---------------------------------------------------------------------------
# Step 1 of asking: remember the question and redraw straight away, so it
# appears in the conversation with "Searching reviews..." underneath. Nothing
# is worked out yet.
if typed and backend_ready:
    st.session_state.pending = typed
    st.rerun()

# Step 2: the question has now been drawn on screen (above), so it is safe to
# take our time working out the answer.
question = st.session_state.pending

if question and backend_ready:
    # A greeting or a thank-you is answered here and now - no search, no AI
    # request, no "not enough evidence" for someone just saying hello.
    chat_reply = small_talk_reply(question)

    if chat_reply:
        st.session_state.turns.append(
            {
                "question": question,
                "answer": chat_reply,
                "sources": [],
                "used": False,
                "smalltalk": True,
            }
        )
    else:
        result = step3.ask_question(
            question, collection, embed_model, gemini_model,
            quiet=True, return_details=True,
        )

        st.session_state.turns.append(
            {
                "question": question,
                "answer": result["answer"],
                "sources": result["sources"],
                "used": result["used"],
                "smalltalk": False,
                "period": result.get("period"),
            }
        )

    # The question has been answered, so it is no longer pending.
    st.session_state.pending = None
    st.rerun()
