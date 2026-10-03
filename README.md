# Google Photos Review Engine

Ask how people fail to find photos in Google Photos. The app answers from real reviews and posts, and shows the sources it used. If nothing in the library is close enough, it says so.

The feedback is from the Google Play Store, Reddit, YouTube, and the Google Photos community forum. It is about search: someone tried to find a photo and the search failed, returned the wrong things, or took a long time.

## Quick start

You need Python 3.11 or newer and a free [Gemini API key](https://aistudio.google.com/apikey).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export GEMINI_API_KEY="your-key-here"
streamlit run frontend/app.py
```

Open the address Streamlit prints, usually `http://localhost:8501`.

The sidebar has a chat, a review library you can browse, and a short “how it works” page. Chats last only for that browser session.

The same answers are available in the terminal. Type `quit` to stop.

```bash
python3 backend/scripts/step3_query.py
```

## How it works

1. Reviews are split into short pieces and stored in a local search database.
2. Your question and those pieces are turned into numbers with `all-MiniLM-L6-v2`, which runs on your computer. Closeness is by meaning, so the words do not have to match.
3. The closest reviews are sent to Gemini (`gemini-3.5-flash-lite`). It may use only those reviews.
4. If the best match scores below **0.40**, Gemini is not called.

The website calls `ask_question()` in `backend/scripts/step3_query.py`. The search index is already built in `backend/vector_db/`. Gemini is the only step that needs `GEMINI_API_KEY`. The key stays in the environment, not in the code.

## Stack

| Piece | Role |
| --- | --- |
| Python 3.11, pandas, Streamlit | App and data files |
| sentence-transformers, Chroma | Local search. Collection: `google_photos_reviews` |
| Google Gemini (`google-genai`) | Writes answers and labels reviews |
| google-play-scraper | Downloads Play Store reviews |

## Layout

```text
frontend/app.py          Chat, library, and how-it-works page
backend/scripts/         Fetch, filter, label, and query
backend/data/            Raw files, filtered files, and the labelled master file
backend/vector_db/       chunks.pkl and the Chroma database
requirements.txt
```

## Data pipeline

Run these only when you are updating the reviews. The app does not need them.

| Step | Script | Result |
| --- | --- | --- |
| Download | `fetch_google_photos_reviews.py` | Play Store reviews in `data/raw_data/` |
| Keep search failures | `filter_retrieval_reviews.py`, `filter_other_sources.py` | Rows about failing to find a photo or video |
| Combine | `combine_all_sources.py` | One master file, same columns for every source |
| Label | `ai_label_reviews.py` | Gemini fills failure type, memory detail, photo age, and time spent searching |
| Drop out-of-scope rows | `exclude_out_of_scope.py` | Rows labelled `photos missing (no search attempted)` go to their own file |
| Rebuild the index | `step1_ingest.py`, then `step2_embed.py` | `chunks.pkl`, then `chroma_db/` |

```bash
python3 backend/scripts/step1_ingest.py
python3 backend/scripts/step2_embed.py
```

Step 1 uses `master_search_scope.csv` if it exists, otherwise `master_filtered_reviews_ai_labelled.csv`. A label stays `not specified` when the text does not say.

Other scripts in `backend/scripts/` are narrower research filters (vague memory, attribute search) and a merge back into the master file.
