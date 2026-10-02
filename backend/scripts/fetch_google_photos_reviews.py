"""
fetch_google_photos_reviews.py

What this script does (in plain words):
1. Downloads real user reviews of the "Google Photos" app from the Google Play Store.
2. Puts them into a common format (source, date, rating, text, url), so other
   review sources can be added later using the same columns and combined in
   your master research sheet.
3. Saves them to data/raw_data/google_photos_playstore_reviews.csv (ALL fetched reviews).

Re-running this script ADDS to that file rather than replacing it. It remembers
which reviews it already has (by their review ID) and only appends new ones, so
you can safely run it again whenever you want to top up your data.

Apple App Store reviews used to be fetched here too, via Apple's public RSS feed,
but that feed no longer returns any review entries, so the code was removed.

This script only FETCHES. Narrowing those reviews down to the ones relevant to
the project (retrieval of vaguely-remembered photos) is done by a separate
filtering script, which reads from data/raw_data/ and writes into
data/filtered_data/.

HOW TO RUN THIS (step by step, for a fresher):
1. Install Python 3 on your laptop if you don't already have it (python.org).
2. Open Terminal and install ONE required library by running:
       pip3 install google-play-scraper
3. Save this file as fetch_google_photos_reviews.py
4. In the terminal, navigate to the folder where you saved it, then run:
       python3 scripts/fetch_google_photos_reviews.py
5. Wait a minute or two - it will print progress messages as it fetches reviews.
6. Once done, you'll find the CSV file inside the data/raw_data/ folder. Open it
   directly in Excel/Google Sheets.

No API keys or logins are needed.
"""

import csv
import os
import re
import time

# ---------------------------------------------------------------------------
# SETTINGS - change these if you want more/fewer reviews, or a different app
# ---------------------------------------------------------------------------

PLAY_STORE_REVIEW_COUNT = 20000

# How many reviews to try for in each extra "pass" (see FETCH_PASSES below).
EXTRA_PASS_COUNT = 3000

# The Play Store will not simply hand over every review it has. Asking for the
# NEWEST ones twice just returns the same newest ones again. To collect MORE
# reviews we have to ask in different ways - by "most relevant", and star by
# star - because each way opens a different slice of the pile. Anything we have
# already collected is skipped, so re-running this is always safe.
FETCH_PASSES = [
    ("most relevant, all ratings", "MOST_RELEVANT", None),
    ("most relevant, 1 star", "MOST_RELEVANT", 1),
    ("most relevant, 2 star", "MOST_RELEVANT", 2),
    ("most relevant, 3 star", "MOST_RELEVANT", 3),
    ("most relevant, 4 star", "MOST_RELEVANT", 4),
    ("most relevant, 5 star", "MOST_RELEVANT", 5),
    ("newest, 1 star", "NEWEST", 1),
    ("newest, 2 star", "NEWEST", 2),
    ("newest, 3 star", "NEWEST", 3),
]

# Folder where the untouched, freshly-fetched CSVs are saved. Filtering is done
# separately, by its own script, which reads from here and writes to
# data/filtered_data/.
# The project folder, worked out from where THIS file sits. Everything is
# located relative to that, so the script works no matter which folder you run
# it from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw_data")

# Google Play package name for Google Photos (found in its Play Store URL)
PLAY_STORE_APP_ID = "com.google.android.apps.photos"


# ---------------------------------------------------------------------------
# STEP 1: Fetch Google Play Store reviews
# ---------------------------------------------------------------------------
def fetch_play_store_reviews(app_id, count, sort_name="NEWEST", star_rating=None, seen_ids=None):
    """Fetches one 'pass' of reviews and returns them in our common format.

    sort_name   - "NEWEST" or "MOST_RELEVANT" (a different way of asking)
    star_rating - None for all reviews, or 1-5 to ask for only that star rating
    seen_ids    - reviewIds we already have; anything in here is skipped
    """
    from google_play_scraper import reviews, Sort

    sort_option = Sort.NEWEST if sort_name == "NEWEST" else Sort.MOST_RELEVANT
    seen_ids = seen_ids if seen_ids is not None else set()

    collected = []
    continuation_token = None
    batch_size = 200

    while len(collected) < count:
        try:
            result, continuation_token = reviews(
                app_id,
                lang="en",
                country="us",
                sort=sort_option,
                count=batch_size,
                filter_score_with=star_rating,
                continuation_token=continuation_token,
            )
        except Exception as e:
            print(f"  ...stopped early (error: {e})")
            break

        if not result:
            break

        # Only keep reviews we have never seen before, in any pass or any
        # previous run of this script.
        for r in result:
            review_id = r.get("reviewId")
            if review_id in seen_ids:
                continue
            seen_ids.add(review_id)
            collected.append({
                "source": "Google Play Store",
                "date": r.get("at"),
                "rating": r.get("score"),
                "text": r.get("content", "").replace("\n", " ").strip(),
                "url": f"https://play.google.com/store/apps/details?id={app_id}&reviewId={review_id}",
            })

        print(f"  ...{len(collected)} new so far")

        if continuation_token is None:
            break
        time.sleep(1)

    return collected


def load_existing(filename):
    """Reads the reviews already saved, so a re-run adds to them instead of
    wiping them. Returns (rows, set_of_reviewIds)."""
    if not os.path.exists(filename):
        return [], set()

    with open(filename, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    ids = set()
    for row in rows:
        match = re.search(r"reviewId=(.+)$", row.get("url", ""))
        if match:
            ids.add(match.group(1))

    print(f"Found {len(rows)} reviews already saved - these will be kept.\n")
    return rows, ids


# ---------------------------------------------------------------------------
# STEP 2: Save to CSV
# ---------------------------------------------------------------------------
def save_to_csv(review_list, filename):
    fieldnames = ["source", "date", "rating", "text", "url"]
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(review_list)
    print(f"Saved {len(review_list)} rows to {filename}")


# ---------------------------------------------------------------------------
# MAIN - runs everything in order
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    output_file = os.path.join(RAW_DATA_DIR, "google_photos_playstore_reviews.csv")

    # Whatever we collected on earlier runs is kept and added to.
    all_rows, seen_ids = load_existing(output_file)
    starting_total = len(all_rows)

    # Pass 1: the newest reviews (this is the original behaviour).
    print(f"PASS: newest, all ratings (up to {PLAY_STORE_REVIEW_COUNT})")
    new_rows = fetch_play_store_reviews(
        PLAY_STORE_APP_ID, PLAY_STORE_REVIEW_COUNT, "NEWEST", None, seen_ids
    )
    all_rows.extend(new_rows)
    print(f"  -> added {len(new_rows)}\n")

    # Extra passes: different ways of asking, to reach reviews the "newest"
    # list will never show us.
    for description, sort_name, star_rating in FETCH_PASSES:
        print(f"PASS: {description} (up to {EXTRA_PASS_COUNT})")
        new_rows = fetch_play_store_reviews(
            PLAY_STORE_APP_ID, EXTRA_PASS_COUNT, sort_name, star_rating, seen_ids
        )
        all_rows.extend(new_rows)
        print(f"  -> added {len(new_rows)}\n")

    save_to_csv(all_rows, output_file)

    print("\nAll done!")
    print(f"Reviews before this run: {starting_total}")
    print(f"New reviews added:       {len(all_rows) - starting_total}")
    print(f"Total reviews now:       {len(all_rows)}")
