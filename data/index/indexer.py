"""Build search_text and embeddings. Push to OpenSearch only when OPENSEARCH_URL is set."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from runtime_config import INDEX_DIR, OPENSEARCH_URL
from search.corpus import clear_corpus_cache, load_programs, load_schools
from search.engine import search_text_for
from mapping.embedder import embed_hash


def documents() -> list[dict]:
    clear_corpus_cache()
    rows = []
    for school in load_schools():
        text = search_text_for(school)
        rows.append({"index": "schools", "id": school["id"], "search_text": text, "embedding": embed_hash(text)})
    for program in load_programs():
        text = " ".join(
            [
                str(program.get("name") or ""),
                str(program.get("description") or ""),
                " ".join(program.get("tag_names") or []),
                str(program.get("city") or ""),
            ]
        )
        rows.append({"index": "programs", "id": program.get("id"), "search_text": text, "embedding": embed_hash(text)})
    return rows


def main() -> None:
    rows = documents()
    out = INDEX_DIR / "documents.jsonl"
    with out.open("w") as handle:
        for row in rows:
            handle.write(json.dumps({"id": row["id"], "index": row["index"], "search_text": row["search_text"]}) + "\n")
    print(f"wrote {len(rows)} documents to {out}")
    if not OPENSEARCH_URL:
        print("OPENSEARCH_URL is not set; skipped the cluster.")
        return
    from opensearchpy import OpenSearch

    client = OpenSearch(OPENSEARCH_URL)
    mappings = json.loads((INDEX_DIR / "mappings.json").read_text())
    for name, body in mappings.items():
        if client.indices.exists(index=name):
            client.indices.delete(index=name)
        client.indices.create(index=name, body=body)
    for row in rows:
        client.index(index=row["index"], id=row["id"], body={"id": row["id"], "search_text": row["search_text"], "embedding": row["embedding"]})
    print("indexed into OpenSearch")


if __name__ == "__main__":
    main()
