"""Build search_text and embeddings. Push to OpenSearch only when OPENSEARCH_URL is set."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from runtime_config import AWS_REGION, INDEX_DIR, OPENSEARCH_URL
from search.corpus import clear_corpus_cache, load_programs, load_schools
from search.engine import search_text_for
from mapping.embedder import embed_hash


def _city_key(city: str | None) -> str:
    return str(city or "").casefold().replace(" ", "")


def documents() -> list[dict]:
    clear_corpus_cache()
    rows = []
    for school in load_schools():
        text = search_text_for(school)
        city = school.get("city")
        rows.append(
            {
                "index": "schools",
                "id": school["id"],
                "body": {
                    "id": school["id"],
                    "name": school.get("name"),
                    "city": city,
                    "city_untokenized": _city_key(city),
                    "state": school.get("state"),
                    "entity_type": school.get("entity_type"),
                    "level_codes": school.get("level_codes") or [],
                    "summary_rating": school.get("summary_rating"),
                    "search_text": text,
                    "embedding": embed_hash(text),
                },
            }
        )
    for program in load_programs():
        text = " ".join(
            [
                str(program.get("name") or ""),
                str(program.get("description") or ""),
                " ".join(program.get("tag_names") or []),
                str(program.get("city") or ""),
            ]
        )
        rows.append(
            {
                "index": "programs",
                "id": program.get("id"),
                "body": {
                    "id": program.get("id"),
                    "name": program.get("name"),
                    "city": program.get("city"),
                    "search_text": text,
                    "embedding": embed_hash(text),
                },
            }
        )
    return rows


def main() -> None:
    rows = documents()
    out = INDEX_DIR / "documents.jsonl"
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with out.open("w") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "id": row["id"],
                        "index": row["index"],
                        "search_text": row["body"].get("search_text"),
                        "city_untokenized": row["body"].get("city_untokenized"),
                        "entity_type": row["body"].get("entity_type"),
                        "level_codes": row["body"].get("level_codes"),
                    }
                )
                + "\n"
            )
    print(f"wrote {len(rows)} documents to {out}")
    if not OPENSEARCH_URL:
        print("OPENSEARCH_URL is not set; skipped the cluster.")
        return
    import boto3
    from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

    auth = AWSV4SignerAuth(boto3.Session().get_credentials(), AWS_REGION, "es")
    client = OpenSearch(
        hosts=[OPENSEARCH_URL],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )
    mappings = json.loads((INDEX_DIR / "mappings.json").read_text())
    for name, body in mappings.items():
        if client.indices.exists(index=name):
            client.indices.delete(index=name)
        client.indices.create(index=name, body=body)
    for row in rows:
        client.index(index=row["index"], id=row["id"], body=row["body"])
    print("indexed into OpenSearch")


if __name__ == "__main__":
    main()
