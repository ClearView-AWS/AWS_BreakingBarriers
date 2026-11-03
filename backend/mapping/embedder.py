"""Stable hashing embedder, with an optional Bedrock embedder behind the same shape.

The mapper and the index both call `embed`. Hashing keeps tests and local search
repeatable without a model. Set BEDROCK_ENABLED=1 to embed with the configured
Titan (or other) model instead.
"""

from __future__ import annotations

import hashlib
import math
import re

from runtime_config import BEDROCK_ENABLED

_TOKEN = re.compile(r"[a-z0-9]+")


def _bucket(text: str, modulo: int) -> int:
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_hash(text: str, dimension: int = 256) -> list[float]:
    vec = [0.0] * dimension
    lowered = text.casefold()
    for token in _TOKEN.findall(lowered):
        vec[_bucket(token, dimension)] += 1.0
        vec[_bucket(token + "#2", dimension)] += 0.4
    padded = f" {lowered} "
    for i in range(len(padded) - 2):
        vec[_bucket(padded[i : i + 3], dimension)] += 0.25
    return _normalize(vec)


def embed_texts(texts: list[str], dimension: int = 256) -> list[list[float]]:
    if BEDROCK_ENABLED:
        from observability import append

        try:
            vectors = _embed_bedrock(texts, dimension)
            append("bedrock", {"purpose": "embed", "ok": True, "texts": len(texts)})
            return vectors
        except Exception as exc:
            append("bedrock", {"purpose": "embed", "ok": False, "error": str(exc)[:300]})
    return [embed_hash(text, dimension) for text in texts]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _embed_bedrock(texts: list[str], dimension: int) -> list[list[float]]:
    import json

    import boto3

    from catalog import models

    cfg = models()
    client = boto3.client("bedrock-runtime", region_name=cfg.get("region", "us-east-1"))
    model_id = cfg.get("embed_model")
    vectors: list[list[float]] = []
    for text in texts:
        body = json.dumps({"inputText": text, "dimensions": dimension, "normalize": True})
        response = client.invoke_model(modelId=model_id, body=body)
        payload = json.loads(response["body"].read())
        vectors.append(payload["embedding"])
    return vectors
