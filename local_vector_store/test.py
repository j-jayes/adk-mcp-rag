#!/usr/bin/env python3
"""
Minimal Qdrant query tester.

Usage examples:
  python test_queries.py "banana bread"
  python test_queries.py "chicken gochujang" --limit 10 --threshold 0.2
  python test_queries.py --loop      # interactive mode

Assumes your VectorDB class is importable from vector_db.py and that
your collection already contains data.
"""

import argparse
import sys
from vector_db import VectorDB

def make_db(url: str, collection: str, embed_model: str, sparse_model: str | None) -> VectorDB:
    db = VectorDB(
        memory_location=url,
        embeddings_model_name=embed_model,
        sparse_embeddings_model_name=sparse_model,
        collection_name=collection,
    )
    return db

def run_one(db: VectorDB, query: str, limit: int, threshold: float | None):
    results = db.query(query_text=query, limit=limit, score_threshold=threshold)
    n = len(results)
    print(f"\n🔎 Query: {query!r}")
    print(f"✅ Returned {n} chunk(s).")
    for i, r in enumerate(results, 1):
        score = r.get("score")
        text = r.get("page_content") or ""
        meta = r.get("metadata", {})
        sid = meta.get("source_id") or meta.get("id") or r.get("id")
        print(f"\n— Result {i} | score={score} | id={sid}")
        print(f"  Snippet: {text}{'…' if len((r.get('page_content') or '')) > 200 else ''}")

def main():
    p = argparse.ArgumentParser(description="Minimal Qdrant query tester")
    p.add_argument("query", nargs="?", help="Text query (omit with --loop for interactive mode)")
    p.add_argument("--limit", type=int, default=5, help="Max results (default: 5)")
    p.add_argument("--threshold", type=float, default=None, help="Score threshold (optional)")
    p.add_argument("--url", default="http://localhost:6333", help="Qdrant URL (default: http://localhost:6333)")
    p.add_argument("--collection", default="default_collection", help="Collection name")
    p.add_argument("--embed-model", default="sentence-transformers/all-MiniLM-L6-v2",
                   help="Dense embeddings model name")
    p.add_argument("--sparse-model", default="Qdrant/bm25",
                   help="Sparse model name for hybrid (set to '' to disable)")
    p.add_argument("--loop", action="store_true", help="Interactive loop mode")
    args = p.parse_args()

    sparse_model = args.sparse_model if args.sparse_model.strip() else None
    db = make_db(args.url, args.collection, args.embed_model, sparse_model)

    if args.loop and args.query:
        print("Note: --loop ignores the single query and enters interactive mode.\n")

    if args.loop:
        try:
            while True:
                q = input("\nEnter query (empty to exit): ").strip()
                if not q:
                    break
                run_one(db, q, args.limit, args.threshold)
        except (EOFError, KeyboardInterrupt):
            print()
        return

    if not args.query:
        print("Error: provide a query or use --loop for interactive mode.", file=sys.stderr)
        sys.exit(2)

    run_one(db, args.query, args.limit, args.threshold)

if __name__ == "__main__":
    main()
