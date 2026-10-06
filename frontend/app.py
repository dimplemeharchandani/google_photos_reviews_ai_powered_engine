"""
app.py - the web interface for the Google Photos review engine.

This is only a FRONT END. All the thinking happens in
backend/scripts/step3_query.py - this file imports that script's
ask_question() function and calls it, so there is exactly one copy of the
search-and-answer logic and the two can never disagree.

THE LAYOUT:
    left sidebar - Photos Review Engine, navigation, and recent chats
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
import time
import uuid
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
        box-sizing: border-box !important;
        width: 312px !important;
        min-width: 312px !important;
        max-width: 312px !important;
        height: 100vh !important;
        min-height: 100vh !important;
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
      [data-testid="stColumn"]:has(.refs-card),
      [data-testid="stColumn"]:has(.refs-anchor) {
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
        padding: 14px;
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
      [data-testid="stSidebarContent"] {
        padding: 11px 16px 0 !important;
      }
      [data-testid="stSidebarUserContent"] {
        padding-left: 0 !important;
        padding-right: 0 !important;
      }

      [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0 !important; }
      [data-testid="stSidebar"] [data-testid="stElementContainer"],
      [data-testid="stSidebar"] [data-testid="stButton"] {
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        /* Don't let a short sidebar squash these rows on top of each other. */
        flex: 0 0 auto !important;
        min-height: unset !important;
        height: auto !important;
      }
      [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.side-kicker) {
        margin: 28px 0 8px !important;
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
      [data-testid="stSidebar"] .st-key-nav-flow button[kind="primary"],
      [data-testid="stSidebar"] [class*="st-key-chat-"] button[kind="primary"] {
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

      [data-testid="stSidebar"] [class*="st-key-chat-"] button {
        min-height: 40px !important;
      }
      [data-testid="stSidebar"] [class*="st-key-chat-"] button p {
        font-weight: 400 !important;
        white-space: nowrap !important;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      /* Same dark tip as New chat and Repository. Fixed so the recents
         scroller does not clip it or let it cover the next row. */
      [class*="st-key-chat-"] {
        position: relative;
        overflow: visible !important;
        height: 40px !important;
        min-height: 40px !important;
        max-height: 40px !important;
        flex: 0 0 40px !important;
      }
      [class*="st-key-chat-"]::after,
      [class*="st-key-chat-"]::before {
        display: none;
        pointer-events: none;
      }
      [class*="st-key-chat-"]::after {
        position: fixed;
        left: 320px;
        top: var(--tip-y, -9999px);
        transform: translateY(-50%);
        z-index: 80;
        width: max-content;
        max-width: 260px;
        padding: 7px 10px;
        border-radius: 8px;
        background: #1f1f1f;
        color: #fff;
        font-size: 13px;
        font-weight: 400;
        line-height: 1.35;
        white-space: normal;
        box-shadow: 0 6px 18px rgba(32, 33, 36, .18);
      }
      [class*="st-key-chat-"]::before {
        content: "";
        position: fixed;
        left: 314px;
        top: var(--tip-y, -9999px);
        transform: translateY(-50%);
        z-index: 81;
        border: 6px solid transparent;
        border-right-color: #1f1f1f;
      }
      [class*="st-key-chat-"]:hover::after,
      [class*="st-key-chat-"]:hover::before { display: block; }
      [data-testid="stSidebarUserContent"],
      [data-testid="stSidebarUserContent"] > div,
      [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {
        height: 100% !important;
        max-height: 100vh !important;
        min-height: 0 !important;
      }
      [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {
        display: flex !important;
        flex-direction: column !important;
      }
      /* Streamlit wraps the chat list in stLayoutWrapper, not the button
         itself. That wrapper was growing with every chat, so nothing scrolled. */
      [data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(.st-key-recents) {
        flex: 1 1 0 !important;
        min-height: 0 !important;
        overflow: hidden !important;
        display: flex !important;
        flex-direction: column !important;
      }
      .st-key-recents {
        flex: 1 1 auto !important;
        min-height: 0 !important;
        height: 100% !important;
        max-height: 100% !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;
      }
      .st-key-recents [data-testid="stVerticalBlockBorderWrapper"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
      }
      .st-key-recents [data-testid="stElementContainer"] {
        height: 40px !important;
        min-height: 40px !important;
        max-height: 40px !important;
        flex: 0 0 40px !important;
        overflow: visible !important;
      }
      [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(iframe) {
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        flex: 0 0 0 !important;
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
        margin: 0 10px;
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
      .side-note {
        display: block;
        margin: 12px;
        padding: 0;
        font-size: 12px;
        line-height: 1.45;
        color: #80868b;
      }
      /* Pinned to the bottom of the sidebar, the way the question box is pinned
         under the conversation. Chats scroll behind it. */
      [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.side-note) {
        position: fixed !important;
        left: 0 !important;
        bottom: 0 !important;
        width: 312px !important;
        margin: 0 !important;
        padding: 12px 16px 12px !important;
        box-sizing: border-box !important;
        background: #fff !important;
        border-right: 1px solid #eceff1;
        z-index: 40 !important;
        flex: none !important;
      }
      .st-key-recents {
        padding-bottom: 78px !important;
        box-sizing: border-box !important;
      }
      /* The sidebar markdown wrapper collapses to 0 height, so the label
         was painting on top of the first chat. Give these their own height. */
      [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.side-kicker),
      [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.side-empty),
      [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.side-note),
      [data-testid="stSidebar"] [data-testid="stMarkdown"]:has(.side-kicker),
      [data-testid="stSidebar"] [data-testid="stMarkdown"]:has(.side-empty),
      [data-testid="stSidebar"] [data-testid="stMarkdown"]:has(.side-note),
      [data-testid="stSidebar"] [data-testid="stMarkdown"]:has(.side-kicker) > div,
      [data-testid="stSidebar"] [data-testid="stMarkdown"]:has(.side-empty) > div,
      [data-testid="stSidebar"] [data-testid="stMarkdown"]:has(.side-note) > div {
        height: auto !important;
        max-height: none !important;
      }
      [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.side-kicker) {
        min-height: 20px !important;
      }
      [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.side-empty) {
        min-height: 22px !important;
      }
      [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.side-note) {
        min-height: 40px !important;
      }
      [data-testid="stSidebar"] [data-testid="stMarkdown"]:has(.side-kicker) > div,
      [data-testid="stSidebar"] [data-testid="stMarkdown"]:has(.side-empty) > div,
      [data-testid="stSidebar"] [data-testid="stMarkdown"]:has(.side-note) > div {
        display: block !important;
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

      .row-right { display: flex; justify-content: flex-end; margin: 0; }
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
        padding: 0;
        margin: 0;
        width: 100%;
        max-width: 100%;
      }
      [data-testid="stChatMessageAvatarAssistant"],
      [data-testid="stChatMessageAvatarUser"] { display: none !important; }

      .thinking {
        display: flex;
        align-items: center;
        gap: 10px;
        min-height: 1.6rem;
        padding: .15rem 0 .1rem;
      }
      .thinking-label {
        font-size: .95rem;
        font-weight: 500;
        letter-spacing: -0.01em;
        background: linear-gradient(90deg, #9aa0a6 0%, #3c4043 45%, #9aa0a6 90%);
        background-size: 220% 100%;
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        animation: thinking-shimmer 1.5s linear infinite;
      }
      .thinking-dots { display: inline-flex; gap: 4px; align-items: center; }
      .thinking-dots span {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #1a73e8;
        animation: thinking-bounce 1.05s infinite ease-in-out;
      }
      .thinking-dots span:nth-child(2) { animation-delay: .15s; }
      .thinking-dots span:nth-child(3) { animation-delay: .3s; }
      @keyframes thinking-shimmer {
        0% { background-position: 100% 0; }
        100% { background-position: -100% 0; }
      }
      @keyframes thinking-bounce {
        0%, 70%, 100% { opacity: .3; transform: translateY(0); }
        35% { opacity: 1; transform: translateY(-3px); }
      }
      @keyframes caret-blink {
        0%, 45% { opacity: 1; }
        50%, 100% { opacity: 0; }
      }
      [data-testid="stChatMessage"]:has(.typing-now):not(:has(.thinking))
        [data-testid="stMarkdownContainer"]:last-of-type > *:last-child::after {
        content: "▍";
        display: inline-block;
        margin-left: 1px;
        color: #1a73e8;
        font-weight: 400;
        animation: caret-blink 1s steps(1) infinite;
      }
      .st-key-chatscroll [data-testid="stElementContainer"]:has(iframe),
      [data-testid="stMain"] [data-testid="stElementContainer"]:has(iframe) {
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
      }

      .stApp,
      [data-testid="stAppViewContainer"],
      [data-testid="stMain"],
      [data-testid="stMain"] .block-container {
        transform: none !important;
      }
      [data-testid="stElementContainer"]:has(.chat-dock) { display: none !important; }
      .st-key-chatscroll { gap: 4px !important; }
      .st-key-chatscroll [data-testid="stElementContainer"],
      .st-key-chatscroll [data-testid="stMarkdown"],
      .st-key-chatscroll [data-testid="stMarkdownContainer"] {
        margin: 0 !important;
        padding: 0 !important;
      }
      .st-key-chatscroll [data-testid="stElementContainer"]:has(.row-right) {
        margin-bottom: 8px !important;
      }
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
      [data-testid="stForm"] [data-testid="InputInstructions"],
      [data-testid="stForm"] :has(> [data-testid="InputInstructions"]) {
        display: none !important;
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
      @keyframes src-in {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
      }
      .src-card-in { animation: src-in .24s ease; }
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

      [data-testid="stMain"] .block-container:has(.flow),
      [data-testid="stMain"] .block-container:has(.st-key-library) { padding-right: 2rem; }
      [data-testid="stAppViewContainer"]:has(.flow) .refs-card,
      [data-testid="stAppViewContainer"]:has(.st-key-library) .refs-card { display: none !important; }

      .flow { max-width: 1080px; margin: .2rem auto 2.5rem; }
      .flow-head { text-align: center; max-width: 640px; margin: .15rem auto 2rem; }
      .flow-title {
        font-size: 1.7rem;
        font-weight: 500;
        letter-spacing: -0.03em;
        color: #202124;
        margin: 0;
      }
      .flow-lead {
        margin: .65rem auto 0;
        color: var(--muted);
        font-size: .98rem;
        line-height: 1.5;
      }
      .flow-sec { margin-top: 2.15rem; }
      .kicker {
        margin: 0 0 .28rem;
        font-size: .7rem;
        font-weight: 600;
        letter-spacing: .07em;
        text-transform: uppercase;
        color: #1a73e8;
      }
      .flow-h {
        margin: 0;
        font-size: 1.22rem;
        font-weight: 500;
        letter-spacing: -0.02em;
        color: #202124;
      }
      .flow-sub {
        margin: .35rem 0 .95rem;
        max-width: 42rem;
        color: var(--muted);
        font-size: .92rem;
        line-height: 1.45;
      }
      .steps {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 22px minmax(0, 1fr) 22px minmax(0, 1fr) 22px minmax(0, 1fr);
        align-items: stretch;
        gap: 8px;
      }
      .step {
        background: #fff;
        border: 1px solid #e3e6ea;
        border-top: 3px solid var(--c, #4285F4);
        border-radius: 14px;
        padding: 14px 14px 16px;
        box-shadow: 0 1px 2px rgba(32, 33, 36, .04);
      }
      .step-done {
        background: #f3faf5;
        border-color: #ceead6;
      }
      .step-ico {
        width: 28px;
        height: 28px;
        border-radius: 8px;
        background: var(--soft, #e8f0fe);
        color: var(--c, #4285F4);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 12px;
      }
      .step-ico svg { width: 16px; height: 16px; display: block; }
      .step-label {
        font-size: .68rem;
        font-weight: 600;
        letter-spacing: .05em;
        text-transform: uppercase;
        color: var(--c, #4285F4);
      }
      .step b {
        display: block;
        margin-top: 3px;
        font-size: .92rem;
        font-weight: 600;
        color: #202124;
        line-height: 1.3;
      }
      .step span {
        display: block;
        margin-top: 6px;
        color: var(--muted);
        font-size: .8rem;
        line-height: 1.42;
      }
      .s-blue { --c: #4285F4; --soft: #e8f0fe; }
      .s-red { --c: #EA4335; --soft: #fce8e6; }
      .s-yellow { --c: #F9AB00; --soft: #fef7e0; }
      .s-green { --c: #34A853; --soft: #e6f4ea; }
      .arrow {
        align-self: center;
        height: 2px;
        background: #dadce0;
        position: relative;
      }
      .arrow::after {
        content: "";
        position: absolute;
        right: -1px;
        top: 50%;
        width: 7px;
        height: 7px;
        border-top: 2px solid #9aa0a6;
        border-right: 2px solid #9aa0a6;
        transform: translateY(-50%) rotate(45deg);
      }
      .flow-note {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        margin-top: 12px;
        padding: 12px 14px;
        background: #f8f9fa;
        border: 1px solid #eceff1;
        border-radius: 12px;
        color: #5f6368;
        font-size: .84rem;
        line-height: 1.45;
      }
      .flow-note svg { flex: 0 0 16px; margin-top: 2px; color: #1a73e8; }
      .rules {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      }
      .rule {
        display: flex;
        gap: 12px;
        align-items: flex-start;
        background: #fff;
        border: 1px solid #e3e6ea;
        border-radius: 14px;
        padding: 14px 16px 15px;
      }
      .rule-ico {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: var(--soft, #e8f0fe);
        color: var(--c, #4285F4);
        display: flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 28px;
      }
      .rule-ico svg { width: 15px; height: 15px; display: block; }
      .rule b {
        display: block;
        font-size: .9rem;
        font-weight: 600;
        color: #202124;
        line-height: 1.3;
      }
      .rule span {
        display: block;
        margin-top: 3px;
        color: var(--muted);
        font-size: .8rem;
        line-height: 1.42;
      }
      @media (max-width: 1180px) {
        .steps { grid-template-columns: 1fr 1fr; }
        .arrow { display: none; }
      }
      @media (max-width: 720px) {
        .steps, .rules { grid-template-columns: 1fr; }
      }

      .st-key-library { max-width: 820px; }
      .st-key-library [data-testid="stTextInputRootElement"],
      .st-key-library .react-aria-ComboBox > div {
        background: #fff !important;
        border: 1.5px solid #80868b !important;
        border-radius: 12px !important;
        min-height: 44px;
      }
      .st-key-library [data-testid="stTextInput"] input {
        border: none !important;
        background: transparent !important;
        font-size: 15px !important;
        min-height: 42px;
      }
      .lib-count {
        color: var(--muted);
        font-size: .84rem;
        margin: .35rem 0 .85rem;
      }
      .lib-empty {
        color: var(--muted);
        font-size: .95rem;
        padding: 1.2rem 0 1.6rem;
      }
      .review-card {
        background: #fff;
        border: 1.5px solid #80868b;
        border-radius: 16px;
        padding: 16px 18px 14px;
        margin-bottom: 14px;
      }
      .review-top {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 8px;
      }
      .review-source {
        font-size: .84rem;
        font-weight: 600;
        color: var(--ink);
      }
      .review-when { font-size: .78rem; color: var(--muted); white-space: nowrap; }
      .review-text { color: var(--ink); font-size: .95rem; line-height: 1.5; }
      .review-tags { margin-top: 10px; }
      .review-card .src-url { display: inline-block; margin-top: 10px; }
      .tag {
        display: inline-block;
        margin: 0 .35rem .3rem 0;
        background: #f1f3f4;
        color: #3c4043;
        border-radius: 999px;
        padding: .14rem .5rem;
        font-size: .72rem;
        font-weight: 500;
      }
      .lib-page {
        color: var(--muted);
        font-size: .84rem;
        text-align: center;
        padding-top: .55rem;
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


# How fast a finished answer is revealed. 112 characters a second is 40%
# faster than the first pass. Three-character slices keep the pace even,
# so a long word does not pop in after a pause. time.sleep runs slightly
# long, so the pause is trimmed to land on that rate.
REVEAL_CHARS_PER_SEC = 112
REVEAL_SLICE = 3
# How long each new reference card stays alone before the next one arrives.
REF_TILE_PAUSE = 0.28


def reveal_answer(text):
    """Yield the answer in small even slices so it reads as continuous typing."""
    text = text or ""
    if not text:
        yield ""
        return
    delay = max(0.0, REVEAL_SLICE / REVEAL_CHARS_PER_SEC - 0.004)
    for start in range(0, len(text), REVEAL_SLICE):
        yield text[start:start + REVEAL_SLICE]
        if start + REVEAL_SLICE < len(text):
            time.sleep(delay)


def thinking_status(question):
    """The live status shown while a reply is being prepared.

    Greetings never search the library, so they must not say that they do.
    """
    label = "Writing a reply" if small_talk_reply(question) else "Searching reviews"
    return (
        "<div class='thinking' role='status' aria-live='polite'>"
        f"<span class='thinking-label'>{html.escape(label)}</span>"
        "<span class='thinking-dots' aria-hidden='true'>"
        "<span></span><span></span><span></span>"
        "</span></div>"
    )


def follow_latest_message():
    """Keep the conversation pinned to the newest line while text is arriving."""
    token = str(time.time())
    components.html(
        f"""
        <script>
        const token = {token!r};
        const doc = window.parent.document;
        const box = doc.querySelector(
          '.st-key-chatscroll [data-testid="stVerticalBlockBorderWrapper"]'
        ) || doc.querySelector('.st-key-chatscroll');
        if (!box) return;
        const jump = () => {{ box.scrollTop = box.scrollHeight; }};
        jump();
        if (box.dataset.followToken !== token) {{
          box.dataset.followToken = token;
          const pause = () => {{
            const gap = box.scrollHeight - box.scrollTop - box.clientHeight;
            box.dataset.pauseFollow = gap > 160 ? "1" : "0";
          }};
          box.addEventListener("wheel", pause, {{passive: true}});
          box.addEventListener("touchmove", pause, {{passive: true}});
          new MutationObserver(() => {{
            if (box.dataset.pauseFollow === "1") return;
            jump();
          }}).observe(box, {{
            childList: true, subtree: true, characterData: true
          }});
        }}
        setTimeout(jump, 60);
        setTimeout(jump, 240);
        </script>
        """,
        height=0,
        width=0,
    )


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


def reference_key(source):
    """Identity of a cited review, so the same link is not shown twice."""
    return source.get("url") or source_line(source)


def chat_references(turns):
    """Unique reviews cited in this conversation, newest answer first."""
    seen = set()
    ordered = []
    for turn in reversed(turns):
        if not turn.get("used"):
            continue
        for source in turn.get("sources") or []:
            key = reference_key(source)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(source)
    return ordered


def show_reference(index, source, arriving=False):
    color = source_color(source.get("source", ""))
    klass = "src-card src-card-in" if arriving else "src-card"
    return (
        f"<div class='{klass}' style='--accent:{color}'>"
        f"<div class='src-top'>"
        f"<div class='src-head'>{index}. {html.escape(source_line(source))}</div>"
        f"<span class='score'>{source['similarity']:.3f}</span>"
        f"</div>"
        f"<a class='src-url' href='{html.escape(source['url'])}' target='_blank'>"
        f"{html.escape(source['url'])}</a>"
        f"</div>"
    )


def references_markup(turns, sources=None, arriving_key=None):
    """The references card. Pass sources to show a growing subset, one new tile at a time."""
    cited = chat_references(turns) if sources is None else sources
    latest = turns[-1] if turns else {}
    if cited:
        period = (
            f"<div class='muted'><b>Limited to {html.escape(latest['period'])}</b></div>"
            if latest.get("period") else ""
        )
        cards = "".join(
            show_reference(
                i,
                source,
                arriving=arriving_key is not None and reference_key(source) == arriving_key,
            )
            for i, source in enumerate(cited, start=1)
        )
        body = (
            f"<div class='muted'>Used in this chat — {len(cited)} "
            f"{'review' if len(cited) == 1 else 'reviews'}.</div>"
            + period
            + cards
        )
        open_attr = "open"
    elif turns and latest.get("smalltalk"):
        body = (
            "<div class='muted'>No references for that message. It was a greeting, "
            "so no reviews were searched.</div>"
        )
        open_attr = ""
    elif turns and not latest.get("used"):
        body = (
            "<div class='muted'>No references. Nothing in the library was close enough "
            "to answer from.</div>"
        )
        open_attr = ""
    else:
        body = (
            "<div class='muted'>Reviews used in this chat will show up here, "
            "with a similarity score and a link back to the original.</div>"
        )
        open_attr = ""
    return (
        f"<details class='refs-card' {open_attr}>"
        "<summary class='refs-heading'>"
        "<span>References</span>"
        "<span class='refs-chevron'></span>"
        "</summary>"
        f"<div class='refs-body'>{body}</div>"
        "</details>"
    )


def reveal_new_references(slot, turns, previous_keys):
    """Add each new reference card on its own, then leave the rest in place."""
    final = chat_references(turns)
    fresh = [source for source in final if reference_key(source) not in previous_keys]
    if not fresh:
        slot.markdown(references_markup(turns), unsafe_allow_html=True)
        return
    # The card list is replaced on every tile, so watch the page for the one
    # that is arriving and keep it inside the references panel.
    components.html(
        """
        <script>
        const doc = window.parent.document;
        if (doc.body.dataset.refWatch === "1") return;
        doc.body.dataset.refWatch = "1";
        const watch = () => {
          const card = doc.querySelector(".src-card-in");
          if (card) card.scrollIntoView({block: "nearest", inline: "nearest"});
        };
        new MutationObserver(watch).observe(doc.body, {
          childList: true, subtree: true
        });
        watch();
        setTimeout(watch, 80);
        setTimeout(watch, 240);
        </script>
        """,
        height=0,
        width=0,
    )
    revealed = set()
    for source in fresh:
        key = reference_key(source)
        revealed.add(key)
        shown = [
            item for item in final
            if reference_key(item) in previous_keys or reference_key(item) in revealed
        ]
        slot.markdown(
            references_markup(turns, sources=shown, arriving_key=key),
            unsafe_allow_html=True,
        )
        time.sleep(REF_TILE_PAUSE)


def open_chat(question=None):
    """Switch back to the open conversation. Optionally queue a question."""
    go_to("chat")
    if question:
        active_chat()["pending"] = question
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
# Chats live in this browser session only. New chat keeps the previous thread
# in the list and opens a blank one. Nothing is written to disk.
def blank_chat():
    return {"id": uuid.uuid4().hex, "turns": [], "pending": None}


def css_string(text):
    """A single line safe to drop into a CSS content value."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) > 220:
        cleaned = cleaned[:217].rstrip() + "…"
    return (
        cleaned.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("<", "")
    )


def place_chat_tips():
    """Line each chat tip up with its row, even while the list scrolls."""
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const place = (row) => {
          const box = row.getBoundingClientRect();
          row.style.setProperty("--tip-y", (box.top + box.height / 2) + "px");
        };
        if (!doc.documentElement.dataset.chatTips) {
          doc.documentElement.dataset.chatTips = "1";
          doc.addEventListener("mouseover", (event) => {
            const row = event.target.closest("[class*='st-key-chat-']");
            if (row) place(row);
          });
          doc.addEventListener("scroll", (event) => {
            const scroller = event.target;
            if (!scroller || !scroller.querySelector) return;
            const row = scroller.querySelector("[class*='st-key-chat-']:hover");
            if (row) place(row);
          }, true);
        }
        </script>
        """,
        height=0,
    )


def chat_title(chat):
    """The sidebar label: the first question in that thread."""
    for turn in chat["turns"]:
        question = (turn.get("question") or "").strip()
        if question:
            break
    else:
        question = (chat.get("pending") or "").strip()
    if not question:
        return "New chat"
    return question if len(question) <= 32 else question[:31] + "…"


# Each section has its own address, so a refresh stays where you were.
# Changing section updates that address without loading the app again.
VIEW_SLUGS = {
    "chat": "chat",
    "library": "library",
    "workflow": "how-it-works",
}
SLUG_VIEWS = {slug: view for view, slug in VIEW_SLUGS.items()}


def go_to(view):
    """Show a section and keep that choice in the address bar."""
    st.session_state.view = view
    slug = VIEW_SLUGS[view]
    if st.query_params.get("view") != slug:
        st.query_params["view"] = slug


def view_in_url():
    """The section named in the address bar, if it is one we know."""
    return SLUG_VIEWS.get(st.query_params.get("view", ""))


if "view" not in st.session_state:
    st.session_state.view = view_in_url() or "chat"
# The address bar wins on refresh and when the back button is used.
# A click below replaces it in this same run, then the script starts again.
if view_in_url():
    st.session_state.view = view_in_url()
else:
    go_to(st.session_state.view)
if "library_page" not in st.session_state:
    st.session_state.library_page = 0
if "chats" not in st.session_state:
    first = blank_chat()
    # A session that already had one thread keeps it as the first chat.
    if st.session_state.get("turns"):
        first["turns"] = list(st.session_state.turns)
    if st.session_state.get("pending"):
        first["pending"] = st.session_state.pending
    st.session_state.chats = [first]
    st.session_state.active_chat_id = first["id"]


def active_chat():
    """The thread currently on screen."""
    for chat in st.session_state.chats:
        if chat["id"] == st.session_state.active_chat_id:
            return chat
    chat = st.session_state.chats[-1]
    st.session_state.active_chat_id = chat["id"]
    return chat


def start_new_chat():
    """Open a blank thread. An already blank thread is left as it is."""
    current = active_chat()
    go_to("chat")
    if not current["turns"] and not current["pending"]:
        return
    chat = blank_chat()
    st.session_state.chats.append(chat)
    st.session_state.active_chat_id = chat["id"]


def open_saved_chat(chat_id):
    """Show a thread already in this session. Does not ask again."""
    st.session_state.active_chat_id = chat_id
    go_to("chat")
    st.session_state.scroll_chat = True
    st.rerun()


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
        go_to("chat")
        st.rerun()
    if st.button("New chat", key="nav-new", use_container_width=True):
        start_new_chat()
        st.rerun()
    if st.button(
        "Reviews library",
        key="nav-library",
        type="primary" if view == "library" else "secondary",
        use_container_width=True,
    ):
        go_to("library")
        st.rerun()
    if st.button(
        "How it works",
        key="nav-flow",
        type="primary" if view == "workflow" else "secondary",
        use_container_width=True,
    ):
        go_to("workflow")
        st.rerun()
    st.markdown(
        f"<a class='nav-item' href='{GITHUB_URL}' target='_blank' rel='noopener'>"
        f"<span class='nav-ico'>{ICON_REPO}</span>"
        "<span class='nav-text'>Repository</span>"
        "<span class='tip'>Open this project on GitHub.</span></a>",
        unsafe_allow_html=True,
    )
    saved_chats = [
        chat for chat in reversed(st.session_state.chats)
        if chat["turns"] or chat["pending"]
    ]
    st.markdown("<div class='side-kicker'>Recents</div>", unsafe_allow_html=True)
    tip_rules = []
    open_id = st.session_state.active_chat_id
    with st.container(border=False, key="recents"):
        if not saved_chats:
            st.markdown(
                "<div class='side-empty'>Chats you start show up here.</div>",
                unsafe_allow_html=True,
            )
        for chat in saved_chats:
            title = chat_title(chat)
            full = next(
                (
                    (turn.get("question") or "").strip()
                    for turn in chat["turns"]
                    if (turn.get("question") or "").strip()
                ),
                chat.get("pending") or title,
            )
            tip_rules.append(
                f'.st-key-chat-{chat["id"]}::after{{content:"{css_string(full)}"}}'
            )
            if st.button(
                title,
                key=f"chat-{chat['id']}",
                type="primary" if chat["id"] == open_id else "secondary",
                use_container_width=True,
            ):
                open_saved_chat(chat["id"])
    if tip_rules:
        st.markdown("<style>" + " ".join(tip_rules) + "</style>", unsafe_allow_html=True)
        place_chat_tips()
    st.markdown(
        "<div class='side-note'>Note - Chats are limited to this browser session. "
        "Refreshing the page clears them.</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Centre and references
# ---------------------------------------------------------------------------
main, refs = st.columns([2.7, 1], gap="large")
pending_slot = None
refs_slot = None
view = st.session_state.view

with main:
    if view == "library":
        with st.container(key="library"):
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
                f"<div class='lib-count'>{total} reviews</div>",
                unsafe_allow_html=True,
            )
            if total == 0:
                st.markdown(
                    "<div class='lib-empty'>Nothing in the library matches that.</div>",
                    unsafe_allow_html=True,
                )
            for _, row in page.iterrows():
                text = str(row["text"]).strip()
                if len(text) > 320:
                    text = text[:317].rstrip() + "…"
                when = []
                date = str(row["date"]).strip()
                if date:
                    when.append(date[:10])
                rating = str(row["rating"]).strip()
                if rating and rating.lower() not in ("nan", "none"):
                    if rating.endswith(".0"):
                        rating = rating[:-2]
                    when.append(f"{rating}★")
                when_html = (
                    f"<span class='review-when'>{html.escape(' · '.join(when))}</span>"
                    if when else ""
                )
                tags = []
                for label, column in (
                    ("Failure", "failure_type"),
                    ("Memory", "memory_detail"),
                    ("Photo age", "photo_age"),
                ):
                    value = str(row.get(column, "")).strip()
                    if value and value.lower() not in ("not specified", "not mentioned", "nan"):
                        tags.append(f"{label}: {value}")
                tag_html = (
                    "<div class='review-tags'>"
                    + "".join(f"<span class='tag'>{html.escape(tag)}</span>" for tag in tags)
                    + "</div>"
                    if tags else ""
                )
                url = str(row["url"]).strip()
                link = (
                    f"<a class='src-url' href='{html.escape(url)}' target='_blank'>Open original</a>"
                    if url else ""
                )
                st.markdown(
                    f"<div class='review-card'>"
                    f"<div class='review-top'>"
                    f"<span class='review-source'>{html.escape(str(row['source']))}</span>"
                    f"{when_html}</div>"
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
                    f"<div class='lib-page'>Page {st.session_state.library_page + 1} of {pages}</div>",
                    unsafe_allow_html=True,
                )
            with next_col:
                if st.button("Next", disabled=st.session_state.library_page >= pages - 1, key="lib-next"):
                    st.session_state.library_page += 1
                    st.rerun()

    elif view == "workflow":
        st.markdown(
            """
            <div class="flow">
              <div class="flow-head">
                <div class="flow-title">How it works</div>
                <p class="flow-lead">People already wrote about failing to find something in Google Photos. Those stories are prepared once. After that, each question looks for stories about the same idea, and the reply is written only from what turned up. When the match is weak, you get a plain note that there is not enough evidence.</p>
              </div>

              <section class="flow-sec">
                <p class="kicker">Prepared once, before any question</p>
                <div class="flow-h">Getting the library ready</div>
                <p class="flow-sub">Reviews and posts are collected, trimmed down to search problems, and stored so a later question can find them quickly. This runs again only when the library itself changes.</p>
                <div class="steps">
                  <div class="step s-blue">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16v12H4z"/><path d="M4 10h16"/><path d="M8 6v12"/></svg></div>
                    <div class="step-label">Step 1</div>
                    <b>Four places, one list</b>
                    <span>Play Store reviews, Reddit posts, YouTube comments, and Google Photos forum threads are pulled together, with the same details kept for each.</span>
                  </div>
                  <div class="arrow"></div>
                  <div class="step s-red">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16l-6 7v6l-4 2v-8z"/></svg></div>
                    <div class="step-label">Step 2</div>
                    <b>Search failures only</b>
                    <span>A story stays if someone tried to look for a photo or video and the search failed, returned the wrong things, or dragged on. Praise and unrelated complaints drop out.</span>
                  </div>
                  <div class="arrow"></div>
                  <div class="step s-yellow">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13l-7 7-9-9V4h7z"/><circle cx="7.5" cy="7.5" r="1" fill="currentColor" stroke="none"/></svg></div>
                    <div class="step-label">Step 3</div>
                    <b>Notes taken from the words</b>
                    <span>Where the text is clear, we note what went wrong, how much they remember, how old the photo seems, and how long they searched. A long post is split into overlapping pieces so one sentence can still match.</span>
                  </div>
                  <div class="arrow"></div>
                  <div class="step s-green">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg></div>
                    <div class="step-label">Step 4</div>
                    <b>Stored by the idea</b>
                    <span>Each piece becomes a vector, a row of numbers that stands in for the idea, not the exact wording. The link to the original page stays attached.</span>
                  </div>
                </div>
              </section>

              <section class="flow-sec">
                <p class="kicker">Each time you ask</p>
                <div class="flow-h">Matching your question to those stories</div>
                <p class="flow-sub">You do not need the same words the reviewer used. The search ranks stories by how close the idea is, then holds a small set for the reply.</p>
                <div class="steps">
                  <div class="step s-blue">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 6h14v9H8l-3 3z"/></svg></div>
                    <div class="step-label">Step 1</div>
                    <b>Ask in your own words</b>
                    <span>Anything about how people fail to find photos works, including a follow-up such as "what about on iPhone?".</span>
                  </div>
                  <div class="arrow"></div>
                  <div class="step s-red">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 7H4v4"/><path d="M4 11a8 8 0 1 0 2-5"/></svg></div>
                    <div class="step-label">Step 2</div>
                    <b>Follow-ups get filled in</b>
                    <span>If this chat already has earlier turns, they are joined to the latest message, so "that" still points at the right topic. A period you mention, like "last year", is picked up at the same time.</span>
                  </div>
                  <div class="arrow"></div>
                  <div class="step s-yellow">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="6"/><path d="M20 20l-4.3-4.3"/></svg></div>
                    <div class="step-label">Step 3</div>
                    <b>Ideas are lined up</b>
                    <span>The question is converted the same way the stories were, then scored against the whole library.</span>
                  </div>
                  <div class="arrow"></div>
                  <div class="step s-green">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 7h12"/><path d="M8 12h12"/><path d="M8 17h12"/><path d="M4 7h.01"/><path d="M4 12h.01"/><path d="M4 17h.01"/></svg></div>
                    <div class="step-label">Step 4</div>
                    <b>A fair short list</b>
                    <span>The closest pieces stay. Reddit, YouTube, and the forum also add a few of their own best matches, because Play Store reviews would otherwise take almost every slot.</span>
                  </div>
                </div>
                <div class="flow-note">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></svg>
                  <span>Name a year or a stretch of time, and only feedback written then remains. That lookup runs on this computer. A model on the internet is called only when it is time to write the reply.</span>
                </div>
              </section>

              <section class="flow-sec">
                <p class="kicker">The reply, if the match is good enough</p>
                <div class="flow-h">Written from those stories, or not at all</div>
                <p class="flow-sub">The writer only sees the short list. If nothing is close, or that time period is empty, the model is never called.</p>
                <div class="steps">
                  <div class="step s-blue">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><path d="M9 9l6 6"/><path d="M15 9l-6 6"/></svg></div>
                    <div class="step-label">Step 1</div>
                    <b>Poor fits are refused</b>
                    <span>The closest story can still be a stretch. In that case, or when nothing was posted in the period you asked about, the app says there is not enough evidence.</span>
                  </div>
                  <div class="arrow"></div>
                  <div class="step s-red">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/><path d="M10 13h5"/><path d="M10 17h3"/></svg></div>
                    <div class="step-label">Step 2</div>
                    <b>Only the short list is opened</b>
                    <span>Past that check, the model reads the stories that made the cut. Earlier answers in the chat explain your wording. They are not proof.</span>
                  </div>
                  <div class="arrow"></div>
                  <div class="step s-yellow">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h8"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4z"/></svg></div>
                    <div class="step-label">Step 3</div>
                    <b>A brief reply</b>
                    <span>It restates what people reported, says when a pattern rests on only one or two stories, and turns down questions that are not about Google Photos search.</span>
                  </div>
                  <div class="arrow"></div>
                  <div class="step s-green step-done">
                    <div class="step-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/></svg></div>
                    <div class="step-label">Step 4</div>
                    <b>Links stay in view</b>
                    <span>The stories used for the reply show up on the right, each pointing at the original page, so a claim can be checked.</span>
                  </div>
                </div>
              </section>

              <section class="flow-sec">
                <p class="kicker">The guardrails</p>
                <div class="flow-h">How a reply stays tied to the evidence</div>
                <p class="flow-sub">These limits keep a fluent answer from wandering off the reviews that were actually found.</p>
                <div class="rules">
                  <div class="rule s-blue">
                    <div class="rule-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/></svg></div>
                    <div>
                      <b>Nothing from outside the short list</b>
                      <span>If the stories do not support a claim, the reply says so. It does not fill the gap from general knowledge.</span>
                    </div>
                  </div>
                  <div class="rule s-red">
                    <div class="rule-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 7H5v6c0 2 1.2 3 3 3"/><path d="M19 7h-3v6c0 2 1.2 3 3 3"/></svg></div>
                    <div>
                      <b>No made-up quotations</b>
                      <span>Wording is restated, not presented as a direct quote. Pieces cut from one long post still belong to one person.</span>
                    </div>
                  </div>
                  <div class="rule s-yellow">
                    <div class="rule-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 7H4v4"/><path d="M4 11a8 8 0 1 0 2-5"/><path d="M12 12v4"/><path d="M12 8h.01"/></svg></div>
                    <div>
                      <b>Chat history is for context</b>
                      <span>Earlier messages clarify what you are asking now. They are not extra evidence, and a previous reply is left alone unless you ask for it.</span>
                    </div>
                  </div>
                  <div class="rule s-green">
                    <div class="rule-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><path d="M12 8v5l3 2"/></svg></div>
                    <div>
                      <b>The time you named is the frame</b>
                      <span>If you asked about a period, the reply stays inside it. Answers are kept short and finish on a full sentence.</span>
                    </div>
                  </div>
                </div>
              </section>
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:
        chat = active_chat()
        with st.container(height=PANEL_HEIGHT, border=False, key="chatscroll"):
            if not chat["turns"] and not chat["pending"]:
                st.markdown(
                    "<div class='hero'><h1>Ask what people say about finding photos</h1>"
                    "<p>Answers come only from Play Store reviews, Reddit, YouTube, "
                    "and the Google Photos forum. References sit on the right.</p></div>",
                    unsafe_allow_html=True,
                )
            else:
                for turn in chat["turns"]:
                    st.markdown(
                        f"<div class='row-right'><div class='bubble-user'>"
                        f"{html.escape(turn['question'])}</div></div>",
                        unsafe_allow_html=True,
                    )
                    with st.chat_message("assistant"):
                        st.write(turn["answer"])
                if chat["pending"]:
                    st.markdown(
                        f"<div class='row-right'><div class='bubble-user'>"
                        f"{html.escape(chat['pending'])}</div></div>",
                        unsafe_allow_html=True,
                    )
                    with st.chat_message("assistant"):
                        st.markdown(
                            "<div class='typing-now'></div>",
                            unsafe_allow_html=True,
                        )
                        pending_slot = st.empty()
                        with pending_slot:
                            st.markdown(
                                thinking_status(chat["pending"]),
                                unsafe_allow_html=True,
                            )
            if chat["pending"] or st.session_state.get("scroll_chat"):
                follow_latest_message()
                st.session_state.scroll_chat = False

        if not chat["turns"] and not chat["pending"] and backend_ready:
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
                disabled=not backend_ready or bool(chat["pending"]),
            )
            sent = st.form_submit_button(
                "Send",
                disabled=not backend_ready or bool(chat["pending"]),
            )
        if sent and asked and asked.strip() and backend_ready:
            active_chat()["pending"] = asked.strip()
            go_to("chat")
            st.rerun()

with refs:
    refs_slot = st.empty()
    if view == "chat":
        refs_slot.markdown(
            references_markup(active_chat()["turns"]),
            unsafe_allow_html=True,
        )
    else:
        # The column stays collapsed. The card itself is only for chat.
        refs_slot.markdown("<div class='refs-anchor'></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Handle a new question
# ---------------------------------------------------------------------------
# The question is already on screen, with a live status in pending_slot.
# Finding the answer happens below. When it is ready, that same spot types
# the reply out, and each new reference card follows on its own.
chat = active_chat()
question = chat["pending"]

if question and backend_ready:
    already_cited = {
        reference_key(source)
        for source in chat_references(chat["turns"])
    }
    try:
        chat_reply = small_talk_reply(question)
        if chat_reply:
            turn = {
                "question": question,
                "answer": chat_reply,
                "sources": [],
                "used": False,
                "smalltalk": True,
            }
        else:
            result = step3.ask_question(
                question, collection, embed_model, gemini_model,
                quiet=True, return_details=True,
                history=[
                    {
                        "question": earlier["question"],
                        "answer": earlier["answer"],
                        "smalltalk": earlier.get("smalltalk", False),
                    }
                    for earlier in chat["turns"]
                ],
            )
            turn = {
                "question": question,
                "answer": result["answer"],
                "sources": result["sources"],
                "used": result["used"],
                "smalltalk": False,
                "period": result.get("period"),
                "resolved_question": result.get("resolved_question", question),
            }
    except Exception as error:  # noqa: BLE001 - keep the chat usable
        turn = {
            "question": question,
            "answer": (
                "I couldn't finish that search. "
                f"{type(error).__name__}: {error}"
            ),
            "sources": [],
            "used": False,
            "smalltalk": False,
        }

    turn["answer"] = step3.cap_answer(turn["answer"])
    chat["turns"].append(turn)
    chat["pending"] = None
    if pending_slot is not None:
        with pending_slot:
            st.write_stream(reveal_answer(turn["answer"]))
        st.session_state.scroll_chat = True
    if refs_slot is not None:
        reveal_new_references(refs_slot, chat["turns"], already_cited)
    st.rerun()
