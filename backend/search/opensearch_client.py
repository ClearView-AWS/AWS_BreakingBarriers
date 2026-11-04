"""SigV4 OpenSearch client. Used by the indexer and the live search path."""

from __future__ import annotations

import logging
from functools import lru_cache
from urllib.parse import urlparse

from runtime_config import AWS_REGION, OPENSEARCH_URL

log = logging.getLogger(__name__)


def opensearch_configured() -> bool:
    return bool(OPENSEARCH_URL)


@lru_cache(maxsize=1)
def get_client():
    if not OPENSEARCH_URL:
        raise RuntimeError("OPENSEARCH_URL is not set")
    import boto3
    from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

    parsed = urlparse(OPENSEARCH_URL if "://" in OPENSEARCH_URL else f"https://{OPENSEARCH_URL}")
    host = parsed.hostname or OPENSEARCH_URL
    auth = AWSV4SignerAuth(boto3.Session().get_credentials(), AWS_REGION, "es")
    return OpenSearch(
        hosts=[{"host": host, "port": parsed.port or 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )


def search_school_ids(body: dict, *, index: str = "schools") -> list[str]:
    """Run a search and return hit ids in rank order. Raises on transport errors."""
    client = get_client()
    response = client.search(index=index, body=body)
    hits = response.get("hits", {}).get("hits", [])
    ids: list[str] = []
    for hit in hits:
        doc_id = hit.get("_id") or (hit.get("_source") or {}).get("id")
        if doc_id:
            ids.append(str(doc_id))
    return ids
