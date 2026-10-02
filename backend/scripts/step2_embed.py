"""
step2_embed.py

Step 2 of the retrieval pipeline.

What this script does (in plain words):
1. Loads the 1,390 chunks that step1_ingest.py saved into vector_db/chunks.pkl.
2. Loads a free embedding model called "all-MiniLM-L6-v2". An embedding model
   turns a piece of text into a list of numbers (a "vector") that represents
   its MEANING. Texts that mean similar things get similar numbers. This model
   runs on your own laptop - no API key, no internet account needed.
3. Converts every chunk into one of those vectors.
4. Creates a local Chroma database in a folder called chroma_db. Chroma is a
   "vector database": it stores those vectors and can very quickly find which
   ones are closest in meaning to a question you ask.
5. Stores every chunk's vector, its text, and its metadata (url, source, date,
   rating) so later steps can quote reviews and cite where they came from.
6. Runs one test search at the end to prove the search works.

The important idea: this is SEMANTIC search, not keyword search. A review that
says "photos from my wedding in 2015 have vanished" can be found by the query
"old pictures I lost", even though they share almost no words.

HOW TO RUN THIS:
    pip3 install sentence-transformers chromadb
    python3 scripts/step2_embed.py

Input:  vector_db/chunks.pkl
Output: vector_db/chroma_db/  (a folder holding the database)
"""

import pickle
import shutil
import os

# The project folder, worked out from where THIS file sits. Everything is
# located relative to that, so the script works no matter which folder you run
# it from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHUNKS_FILE = os.path.join(PROJECT_ROOT, "vector_db", "chunks.pkl")
DB_FOLDER = os.path.join(PROJECT_ROOT, "vector_db", "chroma_db")
COLLECTION_NAME = "google_photos_reviews"
MODEL_NAME = "all-MiniLM-L6-v2"

# How many chunks to embed at a time, and how often to report progress.
BATCH_SIZE = 200

TEST_QUERIES = [
    "can't find an old photo I remember taking years ago",
    "scrolling endlessly through thousands of images",
]

# How many results to show for each test search.
TOP_N = 3


def main():
    # -----------------------------------------------------------------------
    # 1. Load the chunks from step 1
    # -----------------------------------------------------------------------
    with open(CHUNKS_FILE, "rb") as f:
        chunks = pickle.load(f)
    print(f"Loaded {len(chunks)} chunks from {CHUNKS_FILE}\n")

    # -----------------------------------------------------------------------
    # 2. Load the embedding model (downloads once, ~90 MB, then cached)
    # -----------------------------------------------------------------------
    from sentence_transformers import SentenceTransformer

    print(f"Loading embedding model '{MODEL_NAME}'...")
    print("(first run downloads it - about 90 MB - afterwards it is instant)")
    model = SentenceTransformer(MODEL_NAME)
    print("Model loaded.\n")

    # -----------------------------------------------------------------------
    # 3. Create a fresh local Chroma database
    # -----------------------------------------------------------------------
    import chromadb

    # Start clean so re-running this script never leaves duplicates behind.
    if os.path.exists(DB_FOLDER):
        print(f"Removing the previous {DB_FOLDER}/ so we start fresh...")
        shutil.rmtree(DB_FOLDER)

    client = chromadb.PersistentClient(path=DB_FOLDER)
    collection = client.create_collection(
        name=COLLECTION_NAME,
        # Cosine similarity is the usual choice for sentence embeddings.
        metadata={"hnsw:space": "cosine"},
    )
    print(f"Created Chroma database in {DB_FOLDER}/\n")

    # -----------------------------------------------------------------------
    # 4. Embed the chunks and add them to the database, in batches
    # -----------------------------------------------------------------------
    print(f"Embedding {len(chunks)} chunks (progress every {BATCH_SIZE})...")

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]

        texts = [chunk["chunk_text"] for chunk in batch]
        metadatas = [chunk["metadata"] for chunk in batch]
        ids = [f"chunk-{start + offset}" for offset in range(len(batch))]

        # Turn this batch of texts into vectors.
        embeddings = model.encode(texts, show_progress_bar=False)

        collection.add(
            ids=ids,
            documents=texts,
            embeddings=[vector.tolist() for vector in embeddings],
            metadatas=metadatas,
        )

        print(f"  ...{min(start + BATCH_SIZE, len(chunks))} of {len(chunks)} chunks processed")

    print(f"\nDone. The database now holds {collection.count()} chunks.\n")

    # -----------------------------------------------------------------------
    # 5. Test search - does semantic search actually work?
    # -----------------------------------------------------------------------
    for query in TEST_QUERIES:
        print("=" * 72)
        print(f'TEST SEARCH: "{query}"')
        print("=" * 72)

        query_vector = model.encode([query])[0].tolist()
        results = collection.query(query_embeddings=[query_vector], n_results=TOP_N)

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for rank, (document, metadata, distance) in enumerate(
            zip(documents, metadatas, distances), start=1
        ):
            # With cosine distance, 0 means identical meaning and 2 means
            # opposite. Flipping it into a similarity score is easier to read.
            similarity = 1 - distance
            print(f"\nRESULT {rank}  (similarity {similarity:.3f})")
            print("-" * 72)
            print(document[:400])
            # Play Store rows have a star rating; Reddit and YouTube have
            # upvotes/likes instead; the forum has neither. Show what exists.
            bits = [metadata.get("source", "?"), metadata.get("date", "")[:10]]
            if metadata.get("rating"):
                bits.append(f"{metadata['rating']} stars")
            if metadata.get("engagement"):
                bits.append(f"{metadata['engagement']} upvotes/likes")
            print(f"  {' | '.join(b for b in bits if b)}")
            print(f"  url    : {metadata['url'][:95]}")

        print()


if __name__ == "__main__":
    main()
