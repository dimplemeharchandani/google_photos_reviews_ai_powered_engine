"""
app.py - the web interface for the Google Photos review engine.

This is only a FRONT END. All the thinking happens in
backend/scripts/step3_query.py - this file imports that script's
ask_question() function and calls it, so there is exactly one copy of the
search-and-answer logic and the two can never disagree.

THE LAYOUT:
    left sidebar - Photos Review Engine, navigation, and recent questions
    centre       - the conversation, the review library, or how the pipeline works
    right        - references used in this chat

HOW TO RUN IT:
    export GEMINI_API_KEY="your-key-here"
    streamlit run app.py
"""

import html
import importlib.util
import os
import re
from urllib.parse import quote

import pandas as pd
import streamlit as st

# This file lives in frontend/, so the project folder is one level up - that
# is where backend/ sits alongside it.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEP3_PATH = os.path.join(PROJECT_ROOT, "backend", "scripts", "step3_query.py")
LIBRARY_PATH = os.path.join(
    PROJECT_ROOT,
    "backend",
    "data",
    "final_filtered_data",
    "master_filtered_reviews_ai_labelled.csv",
)
GITHUB_URL = (
    "https://github.com/dimplemeharchandani/google_photos_reviews_ai_powered_engine"
)

# How tall the conversation and the references card are. They scroll inside
# themselves so the page as a whole stays put.
PANEL_HEIGHT = 560
LIBRARY_PAGE_SIZE = 8

EXAMPLE_QUESTIONS = [
    "Why do people fail to find an old photo?",
    "Do users say the search returns wrong results?",
    "What do people remember about photos they look for?",
]

# The four semicircles of the Google Photos mark: yellow, red, green, blue.
PHOTOS_LOGO = """
<svg class="photos-logo" viewBox="0 0 256 256" role="img" aria-label="Google Photos">
  <path fill="#34A853" d="M58.222 192C58.222 156.672 86.894 128 122.222 128H128V250.222C128 253.44 125.367 256 122.222 256C86.894 256 58.222 227.328 58.222 192Z"/>
  <path fill="#FBBC04" d="M64 58.222C99.328 58.222 128 86.894 128 122.222V128H5.778C2.56 128 0 125.367 0 122.222C0 86.894 28.672 58.222 64 58.222Z"/>
  <path fill="#EA4335" d="M197.778 64C197.778 99.328 169.106 128 133.778 128H128V5.778C128 2.56 130.633 0 133.778 0C169.106 0 197.778 28.672 197.778 64Z"/>
  <path fill="#4285F4" d="M192 197.778C156.672 197.778 128 169.106 128 133.778V128H250.222C253.44 128 256 130.633 256 133.778C256 169.106 227.328 197.778 192 197.778Z"/>
</svg>
"""

st.set_page_config(
    page_title="Photos Review Engine",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Styling — a light sidebar, a soft blue canvas, a slim references card
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      :root {
        --ink: #1f1f1f;
        --muted: #5f6368;
        --line: #e6e8ee;
        --blue: #1a73e8;
        --blue-soft: #e8f0fe;
        --pill: #f0f4f9;
      }

      header[data-testid="stHeader"], #MainMenu, footer { display: none; }
      [data-testid="stSidebarHeader"],
      [data-testid="stSidebarCollapseButton"],
      [data-testid="stSidebarCollapsedControl"],
      [data-testid="collapsedControl"] { display: none !important; }

      [data-testid="stSidebar"] {
        background: #ffffff !important;
        border-right: 1px solid #eceff1;
        width: 312px !important;
        min-width: 312px !important;
        max-width: 312px !important;
        /* Streamlit slides a collapsed sidebar off-screen. Keep it in place. */
        transform: none !important;
      }

      [data-testid="stMain"] {
        background: radial-gradient(980px 620px at 46% 36%, #d7e9ff 0%, #eef5ff 46%, #f7f9fc 74%);
      }
      [data-testid="stMain"] .block-container {
        padding-top: 1.1rem;
        padding-bottom: .6rem;
        padding-left: 1.4rem;
        padding-right: 1.1rem;
        max-width: 100%;
      }
      [data-testid="stAppViewContainer"] > .main { overflow: auto; }

      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div,
      [data-testid="stSidebarContent"],
      [data-testid="stSidebarUserContent"] {
        overflow: visible !important;
      }
      [data-testid="stSidebar"] { z-index: 100; }
      [data-testid="stSidebarContent"] { padding-top: 11px !important; }

      .side { padding: 0 .4rem .5rem; }
      .brand-link, .nav-item, .recent-item {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 12px;
        width: 100%;
        box-sizing: border-box;
        min-height: 47px;
        padding: 0 10px;
        border-radius: 10px;
        color: #3c4043 !important;
        text-decoration: none !important;
        font-size: 17px;
        font-weight: 500;
        line-height: 1;
        letter-spacing: 0;
      }
      .brand-link {
        gap: 12px;
        min-height: 56px;
        margin-bottom: 9px;
      }
      .brand-link:hover, .nav-item:hover, .recent-item:hover { background: #f1f3f4; }
      .nav-item.is-on { background: #e8eaed; color: var(--ink) !important; }
      .photos-logo { width: 29px; height: 29px; display: block; flex: 0 0 29px; }
      .brand-name {
        font-size: 22px;
        font-weight: 600;
        letter-spacing: -0.03em;
        color: var(--ink);
        line-height: 1.15;
      }
      .nav-ico {
        width: 22px;
        height: 22px;
        flex: 0 0 22px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #3c4043;
      }
      .nav-ico svg { width: 22px; height: 22px; display: block; }
      .nav-text, .recent-text {
        font-size: 17px;
        font-weight: 500;
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .recent-text { font-weight: 400; color: #3c4043; }
      .side-kicker {
        margin: 14px 10px 4px;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: .06em;
        text-transform: uppercase;
        color: #80868b;
      }
      .side-empty {
        margin: 0 10px;
        font-size: 14px;
        line-height: 1.4;
        color: var(--muted);
      }
      .tip {
        display: none;
        position: absolute;
        left: calc(100% + 8px);
        top: 50%;
        transform: translateY(-50%);
        z-index: 40;
        width: max-content;
        max-width: 280px;
        padding: 7px 10px;
        border-radius: 8px;
        background: #1f1f1f;
        color: #fff;
        font-size: 13px;
        font-weight: 400;
        line-height: 1.35;
        letter-spacing: 0;
        white-space: nowrap;
        pointer-events: none;
        box-shadow: 0 6px 18px rgba(32, 33, 36, .18);
      }
      .tip::before {
        content: "";
        position: absolute;
        right: 100%;
        top: 50%;
        transform: translateY(-50%);
        border: 6px solid transparent;
        border-right-color: #1f1f1f;
      }
      .brand-link:hover .tip,
      .nav-item:hover .tip,
      .recent-item:hover .tip { display: block; }
      .recent-item .tip { white-space: normal; }

      .hero {
        text-align: center;
        padding: 11vh 1rem 1.2rem;
      }
      .hero h1 {
        font-size: 2.05rem;
        font-weight: 500;
        letter-spacing: -0.03em;
        color: #202124;
        margin: 0;
      }
      .hero p {
        margin: .7rem auto 0;
        max-width: 36rem;
        color: var(--muted);
        font-size: .98rem;
        line-height: 1.45;
      }

      .page-title {
        font-size: 1.55rem;
        font-weight: 500;
        letter-spacing: -0.02em;
        color: var(--ink);
        margin: .2rem 0 .25rem;
      }
      .page-lead { color: var(--muted); font-size: .95rem; margin-bottom: .9rem; line-height: 1.45; }

      .row-right { display: flex; justify-content: flex-end; margin: .55rem 0; }
      .bubble-user {
        background: var(--pill);
        color: var(--ink);
        padding: .6rem .9rem;
        border-radius: 18px;
        max-width: 80%;
        font-size: .96rem;
        line-height: 1.45;
      }
      [data-testid="stChatMessage"] {
        background: transparent;
        border: none;
        padding: .15rem 0;
        margin: .15rem 0;
        width: 100%;
        max-width: 100%;
      }
      [data-testid="stChatMessageAvatarAssistant"],
      [data-testid="stChatMessageAvatarUser"] { display: none !important; }

      [data-testid="stChatInput"] { padding-bottom: .35rem; }
      [data-testid="stChatInput"] > div {
        border-radius: 28px !important;
        border: 1px solid #e3e6ea !important;
        background: #fff !important;
        box-shadow: 0 8px 28px rgba(26, 115, 232, .08);
      }

      [data-testid="stForm"] {
        max-width: 680px;
        margin: .4rem auto 0;
        background: #fff;
        border: 1px solid #e3e6ea;
        border-radius: 999px;
        box-shadow: 0 8px 28px rgba(26, 115, 232, .1);
        padding: .2rem .35rem .2rem .85rem;
      }
      [data-testid="stForm"] [data-testid="stVerticalBlock"] {
        flex-direction: row !important;
        align-items: center !important;
        gap: .35rem;
      }
      [data-testid="stForm"] [data-testid="stElementContainer"]:first-child { flex: 1 1 auto; }
      [data-testid="stForm"] [data-testid="stTextInput"] div,
      [data-testid="stForm"] [data-testid="stTextInput"] input {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
      }
      [data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
        border-radius: 999px !important;
        background: var(--blue) !important;
        color: #fff !important;
        border: none !important;
        padding: .4rem .9rem !important;
        min-height: 0 !important;
      }

      .refs-card-title {
        font-size: .95rem;
        font-weight: 600;
        color: var(--ink);
        margin-bottom: .15rem;
      }
      .muted { color: var(--muted); font-size: .84rem; line-height: 1.45; }
      .src-card {
        border: 1px solid var(--line);
        border-left: 3px solid var(--accent, var(--blue));
        border-radius: 12px;
        padding: .55rem .65rem;
        margin: .45rem 0;
        background: #fff;
      }
      .src-top { display: flex; justify-content: space-between; gap: .4rem; align-items: flex-start; }
      .src-head { font-weight: 600; color: var(--ink); font-size: .8rem; line-height: 1.35; }
      .score {
        flex: 0 0 auto;
        font-size: .7rem;
        font-weight: 600;
        color: #174ea6;
        background: var(--blue-soft);
        border-radius: 999px;
        padding: .08rem .4rem;
      }
      .src-url {
        display: inline-block;
        margin-top: .3rem;
        font-size: .75rem;
        line-height: 1.35;
        color: var(--blue);
        word-break: break-all;
        text-decoration: none;
      }
      .src-url:hover { text-decoration: underline; }

      .flow { max-width: 640px; margin-top: .4rem; }
      .flow-sources, .flow-split { display: flex; flex-wrap: wrap; gap: .45rem; }
      .pill {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: .35rem .75rem;
        font-size: .86rem;
        color: var(--ink);
      }
      .step {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: .75rem .9rem;
        box-shadow: 0 1px 2px rgba(32, 33, 36, .04);
      }
      .step strong { display: block; margin-bottom: .15rem; color: var(--ink); }
      .step span { color: var(--muted); font-size: .9rem; line-height: 1.4; }
      .arrow { color: #9aa0a6; padding: .28rem 0 .28rem .9rem; font-size: .9rem; }

      .review-card {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: .75rem .85rem;
        margin-bottom: .55rem;
      }
      .review-meta { font-size: .78rem; color: var(--muted); margin-bottom: .3rem; }
      .review-text { color: var(--ink); font-size: .92rem; line-height: 1.45; }
      .review-card .src-url { display: block; margin-top: .45rem; }
      .tag {
        display: inline-block;
        margin-top: .4rem;
        margin-right: .3rem;
        background: var(--blue-soft);
        color: #174ea6;
        border-radius: 999px;
        padding: .05rem .45rem;
        font-size: .72rem;
        font-weight: 600;
      }

      [data-testid="stMain"] div[data-testid="stButton"] > button {
        border-radius: 999px;
        background: #fff;
        border: 1px solid var(--line);
        color: var(--ink);
        font-weight: 500;
        box-shadow: none;
      }
      [data-testid="stMain"] div[data-testid="stButton"] > button:hover {
        background: var(--blue-soft);
        border-color: #c6dafc;
        color: #174ea6;
      }
      [data-testid="stMain"] div[data-testid="stButton"] p { white-space: normal !important; }

      @media (max-width: 900px) {
        [data-testid="stAppViewContainer"] > .main { overflow: auto; }
        [data-testid="stSidebar"] { min-width: 0; max-width: none; }
        .hero { padding-top: 2.5rem; }
        .hero h1 { font-size: 1.55rem; }
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


@st.cache_data(show_spinner=False)
def load_library():
    """The filtered reviews the engine was built from."""
    frame = pd.read_csv(LIBRARY_PATH, encoding="utf-8-sig").fillna("")
    return frame


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
     "Hello! Ask me anything about how people struggle to find their photos or "
     "videos in Google Photos — for example *“why do people fail to find an old photo?”*"),
    (r"^(thanks|thank\s*you|thx|ty|cheers|great|nice|cool|awesome|perfect|ok|okay|"
     r"got\s*it|understood)"
     r"(\s+(a\s*lot|so\s*much|very\s*much|mate|buddy))?$",
     "You're welcome. Ask me another question whenever you like."),
    (r"^(bye|goodbye|see\s*you|good\s*night|cya)$",
     "Goodbye. Come back any time you want to dig into the reviews."),
    (r"^(who\s*are\s*you|what\s*are\s*you|what\s*can\s*you\s*do|help|what\s*is\s*this)\??$",
     "I answer questions using real user feedback about Google Photos — Play Store "
     "reviews, Reddit posts, YouTube comments and community forum posts. I only use "
     "what people actually wrote, and I show you the references behind every answer.\n\n"
     "Try asking *“do users say the search returns wrong results?”*"),
    (r"^(how\s*are\s*you|how'?s\s*it\s*going)\??$",
     "Doing well, thank you. What would you like to know about how people search "
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
        bits.append(str(source["date"])[:10])
    if source.get("rating"):
        bits.append(f"{source['rating']}★")
    if source.get("engagement"):
        bits.append(f"{source['engagement']} upvotes/likes")
    if source.get("part", "1/1") != "1/1":
        bits.append(f"part {source['part']}")
    return " · ".join(bits)


def source_color(name):
    """A stable accent for each place the feedback came from."""
    if name == "Reddit":
        return "#E85D04"
    if name == "YouTube":
        return "#EA4335"
    if name == "Google Photos Community":
        return "#1A73E8"
    return "#34A853"


def chat_references(turns):
    """Unique reviews cited in this conversation, newest answer first."""
    seen = set()
    ordered = []
    for turn in reversed(turns):
        if not turn.get("used"):
            continue
        for source in turn.get("sources") or []:
            key = source.get("url") or source_line(source)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(source)
    return ordered


def show_reference(index, source):
    color = source_color(source.get("source", ""))
    st.markdown(
        f"<div class='src-card' style='--accent:{color}'>"
        f"<div class='src-top'>"
        f"<div class='src-head'>{index}. {html.escape(source_line(source))}</div>"
        f"<span class='score'>{source['similarity']:.3f}</span>"
        f"</div>"
        f"<a class='src-url' href='{html.escape(source['url'])}' target='_blank'>"
        f"{html.escape(source['url'])}</a>"
        f"</div>",
        unsafe_allow_html=True,
    )


def open_chat(question=None):
    """Switch back to the conversation. Optionally queue a question."""
    st.session_state.view = "chat"
    if question:
        st.session_state.pending = question
    st.rerun()


def _icon(path):
    """A 18px line icon. Every sidebar icon uses this same box."""
    return (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
        f"{path}</svg>"
    )


ICON_NEW = _icon('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>')
ICON_LIBRARY = _icon(
    '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
    '<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>'
)
ICON_FLOW = _icon(
    '<rect x="9" y="2" width="6" height="5" rx="1"/>'
    '<rect x="3" y="17" width="6" height="5" rx="1"/>'
    '<rect x="15" y="17" width="6" height="5" rx="1"/>'
    '<path d="M12 7v3M12 10H8a2 2 0 0 0-2 2v5M12 10h4a2 2 0 0 1 2 2v5"/>'
)
ICON_REPO = _icon(
    '<polyline points="16 18 22 12 16 6"/>'
    '<polyline points="8 6 2 12 8 18"/>'
)


def side_link(href, label, tip, icon, active=False, external=False, kind="nav"):
    """One sidebar row: same icon box, same type size, left aligned, with a hover line."""
    cls = f"{kind}-item" + (" is-on" if active else "")
    target = ' target="_blank" rel="noopener"' if external else ' target="_self"'
    icon_html = f"<span class='nav-ico'>{icon}</span>" if icon else ""
    text_cls = "recent-text" if kind == "recent" else "nav-text"
    return (
        f"<a class='{cls}' href='{href}'{target}>"
        f"{icon_html}<span class='{text_cls}'>{html.escape(label)}</span>"
        f"<span class='tip'>{html.escape(tip)}</span></a>"
    )


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
if "turns" not in st.session_state:
    st.session_state.turns = []
if "pending" not in st.session_state:
    st.session_state.pending = None
if "view" not in st.session_state:
    st.session_state.view = "chat"
if "library_page" not in st.session_state:
    st.session_state.library_page = 0


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
# Sidebar navigation via query params, so every row is the same HTML
# ---------------------------------------------------------------------------
nav_request = st.query_params.get("nav")
ask_request = st.query_params.get("ask")
if nav_request == "new":
    st.session_state.turns = []
    st.session_state.pending = None
    st.session_state.view = "chat"
    st.query_params.clear()
    st.rerun()
elif nav_request in ("chat", "library", "workflow"):
    st.session_state.view = "library" if nav_request == "library" else (
        "workflow" if nav_request == "workflow" else "chat"
    )
    st.query_params.clear()
    st.rerun()
elif ask_request:
    st.session_state.pending = ask_request
    st.session_state.view = "chat"
    st.query_params.clear()
    st.rerun()

view = st.session_state.view
rows = [
    side_link("?nav=new", "New chat", "Start a fresh conversation.", ICON_NEW),
    side_link(
        "?nav=library", "Reviews library", "Browse the reviews this engine searches.",
        ICON_LIBRARY, active=view == "library",
    ),
    side_link(
        "?nav=workflow", "How it works", "See how a question becomes an answer.",
        ICON_FLOW, active=view == "workflow",
    ),
    side_link(
        GITHUB_URL, "Repository", "Open this project on GitHub.",
        ICON_REPO, external=True,
    ),
]
if st.session_state.turns:
    recent_html = "".join(
        side_link(
            f"?ask={quote(turn['question'])}",
            turn["question"] if len(turn["question"]) <= 32 else turn["question"][:31] + "…",
            turn["question"],
            icon="",
            kind="recent",
        )
        for turn in reversed(st.session_state.turns)
    )
else:
    recent_html = "<div class='side-empty'>Questions you ask show up here.</div>"

st.sidebar.markdown(
    "<div class='side'>"
    "<a class='brand-link' href='?nav=chat' target='_self'>"
    f"{PHOTOS_LOGO}"
    "<span class='brand-name'>Photos Review Engine</span>"
    "<span class='tip'>Return to this conversation.</span></a>"
    + "".join(rows)
    + "<div class='side-kicker'>Recents</div>"
    + recent_html
    + "</div>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Centre and references
# ---------------------------------------------------------------------------
main, refs = st.columns([2.7, 1], gap="large")
typed = None
view = st.session_state.view

with main:
    if view == "library":
        st.markdown("<div class='page-title'>Reviews library</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='page-lead'>The reviews this engine can search. "
            "Play Store, Reddit, YouTube, and the Google Photos community forum.</div>",
            unsafe_allow_html=True,
        )
        frame = load_library()
        sources = ["All sources"] + sorted(frame["source"].astype(str).unique())
        pick, query_col = st.columns([1, 2])
        with pick:
            chosen = st.selectbox("Source", sources, label_visibility="collapsed")
        with query_col:
            query = st.text_input(
                "Search reviews",
                placeholder="Search the library",
                label_visibility="collapsed",
            )
        filtered = frame
        if chosen != "All sources":
            filtered = filtered[filtered["source"].astype(str) == chosen]
        if query.strip():
            needle = query.strip().lower()
            filtered = filtered[filtered["text"].astype(str).str.lower().str.contains(needle, regex=False)]

        signature = (chosen, query.strip())
        if st.session_state.get("library_sig") != signature:
            st.session_state.library_sig = signature
            st.session_state.library_page = 0
        total = len(filtered)
        pages = max(1, (total + LIBRARY_PAGE_SIZE - 1) // LIBRARY_PAGE_SIZE)
        st.session_state.library_page = min(st.session_state.library_page, pages - 1)
        start = st.session_state.library_page * LIBRARY_PAGE_SIZE
        page = filtered.iloc[start:start + LIBRARY_PAGE_SIZE]

        st.markdown(
            f"<div class='muted'>{total} reviews</div>",
            unsafe_allow_html=True,
        )
        for _, row in page.iterrows():
            text = str(row["text"]).strip()
            if len(text) > 320:
                text = text[:317].rstrip() + "…"
            bits = [str(row["source"])]
            date = str(row["date"]).strip()
            if date:
                bits.append(date[:10])
            rating = str(row["rating"]).strip()
            if rating and rating.lower() not in ("nan", "none"):
                if rating.endswith(".0"):
                    rating = rating[:-2]
                bits.append(f"{rating}★")
            tags = []
            for label, column in (
                ("Failure", "failure_type"),
                ("Memory", "memory_detail"),
                ("Photo age", "photo_age"),
            ):
                value = str(row.get(column, "")).strip()
                if value and value.lower() not in ("not specified", "not mentioned", "nan"):
                    tags.append(f"{label}: {value}")
            tag_html = "".join(f"<span class='tag'>{html.escape(tag)}</span>" for tag in tags)
            url = str(row["url"]).strip()
            link = (
                f"<a class='src-url' href='{html.escape(url)}' target='_blank'>Open original</a>"
                if url else ""
            )
            st.markdown(
                f"<div class='review-card'>"
                f"<div class='review-meta'>{html.escape(' · '.join(bits))}</div>"
                f"<div class='review-text'>{html.escape(text)}</div>"
                f"{tag_html}{link}</div>",
                unsafe_allow_html=True,
            )
        prev_col, page_col, next_col = st.columns([1, 2, 1])
        with prev_col:
            if st.button("Previous", disabled=st.session_state.library_page <= 0, key="lib-prev"):
                st.session_state.library_page -= 1
                st.rerun()
        with page_col:
            st.markdown(
                f"<div class='muted' style='text-align:center;padding-top:.45rem'>"
                f"Page {st.session_state.library_page + 1} of {pages}</div>",
                unsafe_allow_html=True,
            )
        with next_col:
            if st.button("Next", disabled=st.session_state.library_page >= pages - 1, key="lib-next"):
                st.session_state.library_page += 1
                st.rerun()

    elif view == "workflow":
        st.markdown("<div class='page-title'>How it works</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='page-lead'>A question is answered only from real Google Photos "
            "reviews. If nothing in the library is close enough, the engine says so "
            "instead of guessing.</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="flow">
              <div class="flow-sources">
                <span class="pill">Play Store reviews</span>
                <span class="pill">Reddit posts</span>
                <span class="pill">YouTube comments</span>
                <span class="pill">Community forum</span>
              </div>
              <div class="arrow">↓</div>
              <div class="step"><strong>1 · Filter and label</strong>
                <span>Keep feedback about failing to find a photo or video. Label the failure, what the person remembers, and how old the photo is.</span></div>
              <div class="arrow">↓</div>
              <div class="step"><strong>2 · Split into chunks</strong>
                <span>Long posts are cut into overlapping pieces so a sentence in the middle can still be found. Each piece keeps its link.</span></div>
              <div class="arrow">↓</div>
              <div class="step"><strong>3 · Embed into a local database</strong>
                <span>Each chunk is turned into numbers with all-MiniLM-L6-v2 and stored in Chroma. Similar meanings land near each other, even when the words differ.</span></div>
              <div class="arrow">↓</div>
              <div class="flow-split">
                <div class="step" style="flex:1"><strong>4 · Your question</strong>
                  <span>The question is embedded the same way, then the closest reviews are retrieved.</span></div>
                <div class="step" style="flex:1"><strong>5 · Gemini</strong>
                  <span>The model may use only those reviews. It does not invent quotes.</span></div>
              </div>
              <div class="arrow">↓</div>
              <div class="step"><strong>6 · Answer and references</strong>
                <span>The reply stays in the conversation. The reviews it used appear in the references card, with a similarity score and a link.</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:
        if not st.session_state.turns and not st.session_state.pending:
            st.markdown(
                "<div class='hero'><h1>Ask what people say about finding photos</h1>"
                "<p>Answers come only from Play Store reviews, Reddit, YouTube, "
                "and the Google Photos forum. References sit on the right.</p></div>",
                unsafe_allow_html=True,
            )
            chips = st.columns(3, gap="small")
            for i, example in enumerate(EXAMPLE_QUESTIONS):
                with chips[i]:
                    if st.button(example, key=f"eg{i}", use_container_width=True, disabled=not backend_ready):
                        open_chat(example)
            with st.form("composer", clear_on_submit=True, border=False):
                asked = st.text_input(
                    "Ask",
                    placeholder="Ask about Google Photos reviews",
                    label_visibility="collapsed",
                    disabled=not backend_ready,
                )
                sent = st.form_submit_button("Send")
            if sent and asked and asked.strip() and backend_ready:
                st.session_state.pending = asked.strip()
                st.session_state.view = "chat"
                st.rerun()
        else:
            with st.container(height=PANEL_HEIGHT, border=False):
                for turn in st.session_state.turns:
                    st.markdown(
                        f"<div class='row-right'><div class='bubble-user'>"
                        f"{html.escape(turn['question'])}</div></div>",
                        unsafe_allow_html=True,
                    )
                    with st.chat_message("assistant"):
                        st.write(turn["answer"])
                if st.session_state.pending:
                    st.markdown(
                        f"<div class='row-right'><div class='bubble-user'>"
                        f"{html.escape(st.session_state.pending)}</div></div>",
                        unsafe_allow_html=True,
                    )
                    with st.chat_message("assistant"):
                        st.markdown("_Searching reviews…_")
            typed = st.chat_input(
                "Ask about Google Photos reviews" if backend_ready else "Backend not available",
                disabled=not backend_ready,
            )

with refs:
    st.markdown("<div class='refs-card-title'>References</div>", unsafe_allow_html=True)
    cited = chat_references(st.session_state.turns)
    with st.container(height=PANEL_HEIGHT if cited else 168, border=True):
        if cited:
            st.markdown(
                f"<div class='muted'>Used in this chat — {len(cited)} "
                f"{'review' if len(cited) == 1 else 'reviews'}.</div>",
                unsafe_allow_html=True,
            )
            latest = st.session_state.turns[-1] if st.session_state.turns else {}
            if latest.get("period"):
                st.markdown(
                    f"<div class='muted'><b>Limited to {html.escape(latest['period'])}</b></div>",
                    unsafe_allow_html=True,
                )
            for i, source in enumerate(cited, start=1):
                show_reference(i, source)
        elif st.session_state.turns and st.session_state.turns[-1].get("smalltalk"):
            st.markdown(
                "<div class='muted'>No references for that message. It was a greeting, "
                "so no reviews were searched.</div>",
                unsafe_allow_html=True,
            )
        elif st.session_state.turns and not st.session_state.turns[-1].get("used"):
            st.markdown(
                "<div class='muted'>No references. Nothing in the library was close enough "
                "to answer from.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='muted'>Reviews used in this chat will show up here, "
                "with a similarity score and a link back to the original.</div>",
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
    st.session_state.view = "chat"
    st.rerun()

# Step 2: the question has now been drawn on screen (above), so it is safe to
# take our time working out the answer.
question = st.session_state.pending

if question and backend_ready:
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

    st.session_state.pending = None
    st.rerun()
