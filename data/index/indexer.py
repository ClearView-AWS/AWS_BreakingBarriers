"""Build search_text and embeddings, and push them to OpenSearch when OPENSEARCH_URL is set.

    python data/index/indexer.py            # create missing indexes and load them
    python data/index/indexer.py --recreate # drop and rebuild both indexes

Requests are SigV4-signed with the caller's AWS credentials (a teammate's
profile, or the Fargate task role when the API builds the index at startup).
Embeddings use Bedrock when BEDROCK_ENABLED=1, otherwise the hash embedder. The
API must embed queries the same way, so index with the same BEDROCK_ENABLED
value the API runs with.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from catalog import models  # noqa: E402
from mapping.embedder import embed_texts  # noqa: E402
from runtime_config import BEDROCK_ENABLED, INDEX_DIR, OPENSEARCH_URL  # noqa: E402
from search.corpus import clear_corpus_cache, load_programs, load_schools  # noqa: E402
from search.engine import search_text_for  # noqa: E402

BATCH = 50


def _school_doc(school: dict) -> dict:
    return {
        "id": school["id"],
        "name": school.get("name"),
        "city": school.get("city"),
        "city_untokenized": str(school.get("city") or "").casefold().replace(" ", ""),
        "state": school.get("state"),
        "entity_type": school.get("entity_type"),
        "level_codes": school.get("level_codes") or [],
        "summary_rating": school.get("summary_rating") if isinstance(school.get("summary_rating"), int) else None,
        "search_text": search_text_for(school),
        "synthetic": bool(school.get("_synthetic")),
    }


def _program_doc(program: dict) -> dict:
    text = " ".join(
        [
            str(program.get("name") or ""),
            str(program.get("description") or ""),
            " ".join(program.get("tag_names") or []),
            str(program.get("city") or ""),
        ]
    )
    return {"id": str(program.get("id")), "name": program.get("name"), "city": program.get("city"), "search_text": text}


def documents(with_vectors: bool = False) -> list[dict]:
    clear_corpus_cache()
    rows = [{"index": "schools", **_school_doc(s)} for s in load_schools()]
    rows += [{"index": "programs", **_program_doc(p)} for p in load_programs()]
    if with_vectors:
        dimension = int(models().get("embed_dimension", 256))
        for start in range(0, len(rows), BATCH):
            chunk = rows[start : start + BATCH]
            for row, vector in zip(chunk, embed_texts([r["search_text"] for r in chunk], dimension)):
                row["embedding"] = vector
    return rows


def _mappings() -> dict:
    mappings = json.loads((INDEX_DIR / "mappings.json").read_text())
    dimension = int(models().get("embed_dimension", 256))
    for body in mappings.values():
        body["mappings"]["properties"]["embedding"]["dimension"] = dimension
    return mappings


def ensure_indexes(recreate: bool = False) -> dict:
    """Create and load the indexes if they are missing (or always, with recreate)."""
    from opensearchpy import helpers

    from search.opensearch_client import client

    os_client = client()
    mappings = _mappings()
    todo = []
    for name, body in mappings.items():
        exists = os_client.indices.exists(index=name)
        if exists and recreate:
            os_client.indices.delete(index=name)
            exists = False
        if not exists:
            os_client.indices.create(index=name, body=body)
            todo.append(name)
    if not todo:
        counts = {name: os_client.count(index=name)["count"] for name in mappings}
        return {"created": [], "counts": counts}
    rows = [row for row in documents(with_vectors=True) if row["index"] in todo]
    actions = (
        {"_index": row["index"], "_id": row["id"], "_source": {k: v for k, v in row.items() if k != "index"}}
        for row in rows
    )
    ok, errors = helpers.bulk(os_client, actions, chunk_size=200, raise_on_error=False)
    for name in todo:
        os_client.indices.refresh(index=name)
    counts = {name: os_client.count(index=name)["count"] for name in mappings}
    return {"created": todo, "indexed": ok, "errors": len(errors), "counts": counts, "bedrock_embeddings": BEDROCK_ENABLED}


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
    print(json.dumps(ensure_indexes(recreate="--recreate" in sys.argv), indent=2))


if __name__ == "__main__":
    main()
