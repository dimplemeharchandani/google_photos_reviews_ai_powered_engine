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
        --refs-rail: 372px;
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

      .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background: #ffffff;
      }
      [data-testid="stAppViewContainer"]::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        z-index: 200;
        pointer-events: none;
        background: linear-gradient(90deg, #FBBC04, #EA4335, #4285F4, #34A853);
      }
      [data-testid="stMain"] .block-container {
        padding-top: 1.1rem;
        padding-bottom: .6rem;
        padding-left: 1.4rem;
        padding-right: var(--refs-rail);
        max-width: 100%;
      }
      [data-testid="stColumn"]:has(.refs-card) {
        width: 0 !important;
        min-width: 0 !important;
        max-width: 0 !important;
        flex: 0 0 0px !important;
        overflow: visible !important;
        padding: 0 !important;
      }
      .refs-card {
        position: fixed;
        top: 16px;
        right: 16px;
        width: 340px;
        background: #fff;
        border: 1px solid #e6e8ee;
        border-radius: 14px;
        box-shadow: 0 1px 2px rgba(32, 33, 36, .04), 0 10px 28px rgba(32, 33, 36, .08);
        z-index: 80;
        overflow: hidden;
      }
      .refs-heading {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: 0;
        padding: 14px 16px;
        font-size: 16px;
        font-weight: 600;
        letter-spacing: -0.01em;
        color: #1f1f1f;
        cursor: pointer;
        list-style: none;
      }
      .refs-heading::-webkit-details-marker { display: none; }
      .refs-chevron {
        width: 8px;
        height: 8px;
        border-right: 2px solid #1f1f1f;
        border-bottom: 2px solid #1f1f1f;
        transform: rotate(-45deg);
        margin-right: 2px;
      }
      .refs-card[open] .refs-chevron {
        transform: rotate(45deg);
        margin-top: -4px;
      }
      .refs-body {
        max-height: min(62vh, 520px);
        overflow: auto;
        padding: 0 14px 14px;
        border-top: 1px solid #eee;
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

      [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0 !important; }
      [data-testid="stSidebar"] [data-testid="stElementContainer"],
      [data-testid="stSidebar"] [data-testid="stButton"] {
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
      }
      [data-testid="stSidebar"] button {
        width: 100% !important;
        min-height: 40px !important;
        height: 40px !important;
        margin: 0 !important;
        padding: 0 10px !important;
        gap: 12px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        border-radius: 10px !important;
        box-shadow: none !important;
        outline: none !important;
        color: #3c4043 !important;
        font-size: 17px !important;
        font-weight: 500 !important;
        text-align: left !important;
        line-height: 1.2 !important;
      }
      [data-testid="stSidebar"] button > div,
      [data-testid="stSidebar"] button p {
        margin: 0 !important;
        width: auto !important;
        flex: 0 1 auto !important;
        justify-content: flex-start !important;
        background: transparent !important;
        font-size: 17px !important;
        font-weight: 500 !important;
        line-height: 1.2 !important;
        text-align: left !important;
        color: #3c4043 !important;
      }
      [data-testid="stSidebar"] button > div {
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
      }
      [data-testid="stSidebar"] button:hover {
        background: #f1f3f4 !important;
        background-color: #f1f3f4 !important;
        border: none !important;
        color: #3c4043 !important;
      }
      [data-testid="stSidebar"] .st-key-nav-library button[kind="primary"],
      [data-testid="stSidebar"] .st-key-nav-flow button[kind="primary"] {
        background: #e8eaed !important;
        background-color: #e8eaed !important;
      }
      .st-key-brand button {
        min-height: 56px !important;
        height: 56px !important;
        margin-bottom: 8px !important;
      }
      .st-key-brand button p {
        font-size: 22px !important;
        font-weight: 600 !important;
        letter-spacing: -0.03em;
        color: #1f1f1f !important;
      }
      .st-key-brand button::before,
      .st-key-nav-new button::before,
      .st-key-nav-library button::before,
      .st-key-nav-flow button::before {
        content: "";
        width: 22px;
        height: 22px;
        flex: 0 0 22px;
        background: center / 22px 22px no-repeat;
      }
      .st-key-brand button::before {
        width: 29px;
        height: 29px;
        flex-basis: 29px;
        background-size: 29px 29px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 256 256'%3E%3Cpath fill='%2334A853' d='M58.2 192C58.2 156.7 86.9 128 122.2 128H128v122.2c0 3.2-2.6 5.8-5.8 5.8C86.9 256 58.2 227.3 58.2 192z'/%3E%3Cpath fill='%23FBBC04' d='M64 58.2C99.3 58.2 128 86.9 128 122.2V128H5.8C2.6 128 0 125.4 0 122.2 0 86.9 28.7 58.2 64 58.2z'/%3E%3Cpath fill='%23EA4335' d='M197.8 64c0 35.3-28.7 64-64 64H128V5.8C128 2.6 130.6 0 133.8 0 169.1 0 197.8 28.7 197.8 64z'/%3E%3Cpath fill='%234285F4' d='M192 197.8c-35.3 0-64-28.7-64-64V128h122.2c3.2 0 5.8 2.6 5.8 5.8 0 35.3-28.7 64-64 64z'/%3E%3C/svg%3E");
      }
      .st-key-nav-new button::before {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%233c4043' stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 20h9'/%3E%3Cpath d='M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z'/%3E%3C/svg%3E");
      }
      .st-key-nav-library button::before {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%233c4043' stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 19.5A2.5 2.5 0 0 1 6.5 17H20'/%3E%3Cpath d='M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'/%3E%3C/svg%3E");
      }
      .st-key-nav-flow button::before {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%233c4043' stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='9' y='2' width='6' height='5' rx='1'/%3E%3Crect x='3' y='17' width='6' height='5' rx='1'/%3E%3Crect x='15' y='17' width='6' height='5' rx='1'/%3E%3Cpath d='M12 7v3M12 10H8a2 2 0 0 0-2 2v5M12 10h4a2 2 0 0 1 2 2v5'/%3E%3C/svg%3E");
      }
      .st-key-brand,
      .st-key-nav-new,
      .st-key-nav-library,
      .st-key-nav-flow {
        position: relative;
        overflow: visible !important;
      }
      .st-key-brand::after,
      .st-key-nav-new::after,
      .st-key-nav-library::after,
      .st-key-nav-flow::after,
      .st-key-brand::before,
      .st-key-nav-new::before,
      .st-key-nav-library::before,
      .st-key-nav-flow::before {
        display: none;
        pointer-events: none;
      }
      .st-key-brand::after,
      .st-key-nav-new::after,
      .st-key-nav-library::after,
      .st-key-nav-flow::after {
        position: absolute;
        left: calc(100% + 8px);
        top: 50%;
        transform: translateY(-50%);
        z-index: 40;
        width: max-content;
        padding: 7px 10px;
        border-radius: 8px;
        background: #1f1f1f;
        color: #fff;
        font-size: 13px;
        font-weight: 400;
        line-height: 1.35;
        white-space: nowrap;
        box-shadow: 0 6px 18px rgba(32, 33, 36, .18);
      }
      .st-key-brand::before,
      .st-key-nav-new::before,
      .st-key-nav-library::before,
      .st-key-nav-flow::before {
        content: "";
        position: absolute;
        left: calc(100% + 2px);
        top: 50%;
        transform: translateY(-50%);
        z-index: 41;
        border: 6px solid transparent;
        border-right-color: #1f1f1f;
      }
      .st-key-brand:hover::after,
      .st-key-nav-new:hover::after,
      .st-key-nav-library:hover::after,
      .st-key-nav-flow:hover::after,
      .st-key-brand:hover::before,
      .st-key-nav-new:hover::before,
      .st-key-nav-library:hover::before,
      .st-key-nav-flow:hover::before { display: block; }
      .st-key-brand::after { content: "Return to this conversation."; }
      .st-key-nav-new::after { content: "Start a fresh conversation."; }
      .st-key-nav-library::after { content: "Browse the reviews this engine searches."; }
      .st-key-nav-flow::after { content: "See how a question becomes an answer."; }

      [data-testid="stSidebar"] [class*="st-key-hist"] button {
        min-height: 40px !important;
      }
      [data-testid="stSidebar"] [class*="st-key-hist"] button p {
        font-weight: 400 !important;
        white-space: nowrap !important;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .st-key-prompts {
        position: fixed !important;
        left: calc(312px + 1.4rem) !important;
        bottom: 132px !important;
        width: min(760px, calc(100vw - 312px - var(--refs-rail) - 1.4rem - 8px)) !important;
        z-index: 50 !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        height: auto !important;
        overflow: visible !important;
      }
      .st-key-prompts [data-testid="stVerticalBlock"] { gap: 4px !important; }
      .st-key-prompts [data-testid="stElementContainer"] { margin: 0 !important; padding: 0 !important; }
      .st-key-prompts [data-testid="stButton"] { width: fit-content !important; }
      .st-key-prompts button {
        width: auto !important;
        min-height: 0 !important;
        font-style: italic !important;
        font-size: 16px !important;
        font-weight: 400 !important;
        color: #80868b !important;
        background: #fff !important;
        border: 1px solid #e3e6ea !important;
        border-radius: 999px !important;
        padding: 8px 16px !important;
        margin: 0 !important;
      }
      .st-key-prompts button:hover {
        color: #3c4043 !important;
        border-color: #dadce0 !important;
        background: #f8f9fa !important;
      }
      .st-key-prompts button p {
        font-style: italic !important;
        font-size: 16px !important;
        font-weight: 400 !important;
      }

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
      .nav-item { min-height: 40px; height: 40px; }
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
        display: block;
        margin: 16px 10px 0;
        padding: 0;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: .06em;
        text-transform: uppercase;
        line-height: 1.2;
        color: #80868b;
      }
      .side-empty {
        display: block;
        margin: 8px 10px 0;
        padding: 0;
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

      .stApp,
      [data-testid="stAppViewContainer"],
      [data-testid="stMain"],
      [data-testid="stMain"] .block-container {
        transform: none !important;
      }
      [data-testid="stElementContainer"]:has(.chat-dock) { display: none !important; }
      .st-key-chatscroll,
      .st-key-chatscroll [data-testid="stVerticalBlockBorderWrapper"] {
        width: min(760px, calc(100vw - 312px - var(--refs-rail) - 1.4rem - 8px)) !important;
        height: calc(100vh - 150px) !important;
        min-height: calc(100vh - 150px) !important;
        max-height: none !important;
        box-sizing: border-box !important;
        padding-right: 22px !important;
        overflow: auto !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
      }
      [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stForm"]) {
        height: auto !important;
        max-height: none !important;
        overflow: visible !important;
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
      }
      .prompt-stack {
        position: fixed;
        left: calc(312px + 1.4rem);
        bottom: 132px;
        width: min(760px, calc(100vw - 312px - var(--refs-rail) - 1.4rem - 8px));
        max-width: none;
        z-index: 50;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
        padding-left: 0;
        box-sizing: border-box;
      }
      .prompt, .prompt:visited {
        display: inline-block;
        font-style: italic;
        font-size: 16px;
        font-weight: 400;
        line-height: 1.35;
        color: #80868b !important;
        text-decoration: none !important;
        background: #fff;
        border: 1px solid #e3e6ea;
        border-radius: 999px;
        padding: 8px 16px;
      }
      .prompt:hover {
        color: #3c4043 !important;
        border-color: #dadce0;
        background: #f8f9fa;
      }
      [data-testid="stElementContainer"]:has(.prompt-stack) {
        height: 0 !important;
        margin: 0 !important;
        overflow: visible !important;
      }

      [data-testid="stForm"] {
        position: fixed !important;
        bottom: 48px !important;
        left: calc(312px + 1.4rem) !important;
        width: min(760px, calc(100vw - 312px - var(--refs-rail) - 1.4rem - 8px)) !important;
        max-width: none !important;
        height: auto !important;
        max-height: 64px !important;
        z-index: 50 !important;
        margin: 0 !important;
        background: #fff;
        border: 1px solid #e3e6ea;
        border-radius: 999px;
        box-shadow: 0 1px 2px rgba(32, 33, 36, .06), 0 8px 20px rgba(32, 33, 36, .10);
        padding: .25rem .35rem .25rem .9rem;
      }
      [data-testid="stForm"] [data-testid="stVerticalBlock"] {
        flex-direction: row !important;
        align-items: center !important;
        height: auto !important;
        min-height: 0 !important;
        gap: .35rem;
      }
      [data-testid="stForm"] [data-testid="stElementContainer"] {
        margin-bottom: 0 !important;
      }
      [data-testid="stForm"] [data-testid="stElementContainer"]:first-child { flex: 1 1 auto; }
      [data-testid="stForm"] [data-testid="stTextInput"] div,
      [data-testid="stForm"] [data-testid="stTextInput"] input {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        font-size: 17px !important;
      }
      [data-testid="stForm"] [data-testid="stFormSubmitButton"] {
        width: 42px !important;
        height: 42px !important;
        flex: 0 0 42px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
      }
      [data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
        position: relative;
        width: 42px !important;
        height: 42px !important;
        min-width: 42px !important;
        min-height: 42px !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
        border-radius: 50% !important;
        box-shadow: none !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        background:
          radial-gradient(circle at center, #fff 0 15px, transparent 16px),
          conic-gradient(#FBBC04 0 90deg, #EA4335 90deg 180deg, #4285F4 180deg 270deg, #34A853 270deg 360deg) !important;
      }
      [data-testid="stForm"] [data-testid="stFormSubmitButton"] button p,
      [data-testid="stForm"] [data-testid="stFormSubmitButton"] [data-testid="stIconMaterial"] {
        display: none !important;
      }
      [data-testid="stForm"] [data-testid="stFormSubmitButton"] button::after {
        content: "";
        position: absolute;
        left: 50%;
        top: 50%;
        width: 20px;
        height: 20px;
        transform: translate(-50%, -50%);
        background: center / 19px 19px no-repeat url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='%23000' stroke='%23000' stroke-width='1.35' stroke-linejoin='round' stroke-linecap='round' d='M13 19V7.83l4.88 4.88c.39.39 1.03.39 1.42 0a.996.996 0 000-1.41l-6.59-6.59a.996.996 0 00-1.41 0l-6.6 6.58a.996.996 0 101.41 1.41L11 7.83V19c0 .55.45 1 1 1s1-.45 1-1z'/%3E%3C/svg%3E");
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
    return (
        f"<div class='src-card' style='--accent:{color}'>"
        f"<div class='src-top'>"
        f"<div class='src-head'>{index}. {html.escape(source_line(source))}</div>"
        f"<span class='score'>{source['similarity']:.3f}</span>"
        f"</div>"
        f"<a class='src-url' href='{html.escape(source['url'])}' target='_blank'>"
        f"{html.escape(source['url'])}</a>"
        f"</div>"
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


ICON_REPO = _icon(
    '<polyline points="16 18 22 12 16 6"/>'
    '<polyline points="8 6 2 12 8 18"/>'
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
# Sidebar. Buttons stay on this page. Only Repository opens a new tab.
# ---------------------------------------------------------------------------
view = st.session_state.view
with st.sidebar:
    if st.button("Photos Review Engine", key="brand", use_container_width=True):
        st.session_state.view = "chat"
        st.rerun()
    if st.button("New chat", key="nav-new", use_container_width=True):
        st.session_state.turns = []
        st.session_state.pending = None
        st.session_state.view = "chat"
        st.rerun()
    if st.button(
        "Reviews library",
        key="nav-library",
        type="primary" if view == "library" else "secondary",
        use_container_width=True,
    ):
        st.session_state.view = "library"
        st.rerun()
    if st.button(
        "How it works",
        key="nav-flow",
        type="primary" if view == "workflow" else "secondary",
        use_container_width=True,
    ):
        st.session_state.view = "workflow"
        st.rerun()
    st.markdown(
        f"<a class='nav-item' href='{GITHUB_URL}' target='_blank' rel='noopener'>"
        f"<span class='nav-ico'>{ICON_REPO}</span>"
        "<span class='nav-text'>Repository</span>"
        "<span class='tip'>Open this project on GitHub.</span></a>",
        unsafe_allow_html=True,
    )
    if not st.session_state.turns:
        st.markdown(
            "<div class='side-kicker'>Recents</div>"
            "<div class='side-empty'>Questions you ask show up here.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div class='side-kicker'>Recents</div>", unsafe_allow_html=True)
        for i, turn in enumerate(reversed(st.session_state.turns)):
            number = len(st.session_state.turns) - 1 - i
            label = turn["question"] if len(turn["question"]) <= 32 else turn["question"][:31] + "…"
            if st.button(label, key=f"hist{number}", help=turn["question"], use_container_width=True):
                open_chat(turn["question"])


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
        with st.container(height=PANEL_HEIGHT, border=False, key="chatscroll"):
            if not st.session_state.turns and not st.session_state.pending:
                st.markdown(
                    "<div class='hero'><h1>Ask what people say about finding photos</h1>"
                    "<p>Answers come only from Play Store reviews, Reddit, YouTube, "
                    "and the Google Photos forum. References sit on the right.</p></div>",
                    unsafe_allow_html=True,
                )
            else:
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

        if not st.session_state.turns and not st.session_state.pending and backend_ready:
            with st.container(key="prompts"):
                for i, example in enumerate(EXAMPLE_QUESTIONS):
                    if st.button(example, key=f"prompt{i}"):
                        open_chat(example)
        st.markdown("<div class='chat-dock'></div>", unsafe_allow_html=True)
        with st.form("composer", clear_on_submit=True, border=False):
            asked = st.text_input(
                "Ask",
                placeholder="Ask about Google Photos reviews" if backend_ready else "Backend not available",
                label_visibility="collapsed",
                disabled=not backend_ready,
            )
            sent = st.form_submit_button("Send")
        if sent and asked and asked.strip() and backend_ready:
            st.session_state.pending = asked.strip()
            st.session_state.view = "chat"
            st.rerun()

with refs:
    cited = chat_references(st.session_state.turns)
    if cited:
        latest = st.session_state.turns[-1] if st.session_state.turns else {}
        period = (
            f"<div class='muted'><b>Limited to {html.escape(latest['period'])}</b></div>"
            if latest.get("period") else ""
        )
        body = (
            f"<div class='muted'>Used in this chat — {len(cited)} "
            f"{'review' if len(cited) == 1 else 'reviews'}.</div>"
            + period
            + "".join(show_reference(i, source) for i, source in enumerate(cited, start=1))
        )
    elif st.session_state.turns and st.session_state.turns[-1].get("smalltalk"):
        body = (
            "<div class='muted'>No references for that message. It was a greeting, "
            "so no reviews were searched.</div>"
        )
    elif st.session_state.turns and not st.session_state.turns[-1].get("used"):
        body = (
            "<div class='muted'>No references. Nothing in the library was close enough "
            "to answer from.</div>"
        )
    else:
        body = (
            "<div class='muted'>Reviews used in this chat will show up here, "
            "with a similarity score and a link back to the original.</div>"
        )
    open_attr = "open" if cited else ""
    st.markdown(
        f"<details class='refs-card' {open_attr}>"
        "<summary class='refs-heading'>"
        "<span>References</span>"
        "<span class='refs-chevron'></span>"
        "</summary>"
        f"<div class='refs-body'>{body}</div>"
        "</details>",
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
