"""SigV4-signed OpenSearch client and the candidate search the turn uses.

The domain's access policy trusts the account, but each caller still needs IAM
permission (``es:ESHttpGet``, ``es:ESHttpPost`` and so on). Requests are signed
with whatever credentials boto3 finds: a teammate's profile on a laptop, or the
Fargate task role in AWS.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from urllib.parse import urlparse

from runtime_config import AWS_REGION, OPENSEARCH_URL
from search.query import build_query

log = logging.getLogger(__name__)

SCHOOLS_INDEX = "schools"
PROGRAMS_INDEX = "programs"


def enabled() -> bool:
    return bool(OPENSEARCH_URL)


@lru_cache(maxsize=1)
def client():
    import boto3
    from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

    url = OPENSEARCH_URL if "://" in OPENSEARCH_URL else f"https://{OPENSEARCH_URL}"
    parsed = urlparse(url)
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, AWS_REGION, "es")
    return OpenSearch(
        hosts=[{"host": parsed.hostname, "port": parsed.port or 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=10,
        pool_maxsize=10,
    )


def query_body(criteria: list, query_text: str, vector: list[float] | None, size: int = 500) -> dict:
    """The query sent to the domain.

    Hard filters (city, level, type) come from ``build_query``, so the domain and
    the local engine agree on what is filtered. The free-text part is a keyword
    match plus, when a query vector exists, a k-NN clause on ``embedding``. Need
    boosts are applied in code after the search, where evidence is computed.
    """
    filters = build_query(criteria, "", size=size)["query"].get("bool", {}).get("filter", [])
    should: list[dict] = []
    if query_text.strip():
        should.append({"multi_match": {"query": query_text, "fields": ["search_text^2", "name^3"], "type": "best_fields"}})
        if vector:
            should.append({"knn": {"embedding": {"vector": vector, "k": min(size, 100)}}})
    bool_query: dict = {}
    if filters:
        bool_query["filter"] = filters
    if should:
        bool_query["should"] = should
        bool_query["minimum_should_match"] = 0
    query = {"bool": bool_query} if bool_query else {"match_all": {}}
    return {"size": size, "_source": False, "query": query}


def search_candidates(criteria: list, query_text: str) -> tuple[dict[str, float] | None, dict]:
    """Return ``({school_id: score}, info)``. Scores are None when the domain is off or fails.

    ``info`` is what goes in the request log: the query (vectors trimmed), and
    whether the domain answered.
    """
    from observability import trim_vectors

    if not enabled():
        return None, {"opensearch": "off", "query": build_query(criteria, query_text)}
    vector = None
    if query_text.strip():
        from catalog import models
        from mapping.embedder import embed_texts

        vector = embed_texts([query_text], int(models().get("embed_dimension", 256)))[0]
    body = query_body(criteria, query_text, vector)
    info: dict = {"opensearch": "on", "query": trim_vectors(body)}
    started = time.perf_counter()
    try:
        response = client().search(index=SCHOOLS_INDEX, body=body)
    except Exception as exc:  # The local engine still answers; the log says why.
        log.warning("opensearch search failed: %s", exc)
        info.update(opensearch="error", error=str(exc)[:300])
        return None, info
    hits = response.get("hits", {}).get("hits", [])
    info.update(took_ms=round((time.perf_counter() - started) * 1000, 1), hits=len(hits))
    return {hit["_id"]: float(hit.get("_score") or 0.0) for hit in hits}, info
