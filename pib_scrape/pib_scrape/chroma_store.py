from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

from .chunking import TextChunk


def get_client(persist_dir: str | Path):
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
    except ImportError as e:
        raise ImportError("Install chromadb: pip install chromadb") from e

    persist_dir = Path(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(persist_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_collection(persist_dir: str | Path, collection_name: str, embedding_fn: Any = None):
    client = get_client(persist_dir)
    kwargs: dict[str, Any] = {"name": collection_name}
    if embedding_fn is not None:
        kwargs["embedding_function"] = embedding_fn
    return client.get_or_create_collection(**kwargs)


def existing_prids(
    persist_dir: str | Path,
    collection_name: str,
    prids: Iterable[str],
) -> set[str]:
    """Return subset of prids that already have at least one chunk stored."""
    wanted = {p for p in prids if p}
    if not wanted:
        return set()
    collection = get_collection(persist_dir, collection_name)
    found: set[str] = set()
    # Probe by deterministic first-chunk id (pib-{prid}-0)
    ids = [f"pib-{p}-0" for p in wanted]
    # Chroma get is fine in batches
    batch = 100
    for i in range(0, len(ids), batch):
        chunk = ids[i : i + batch]
        got = collection.get(ids=chunk)
        for cid in got.get("ids") or []:
            # pib-2338083-0 → 2338083
            parts = cid.split("-")
            if len(parts) >= 3 and parts[0] == "pib":
                found.add(parts[1])
    return found


def upsert_chunks(
    chunks: Sequence[TextChunk],
    *,
    persist_dir: str | Path,
    collection_name: str,
    embedding_fn: Any = None,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Upsert chunks by stable chunk_id (idempotent re-runs)."""
    if not chunks:
        collection = get_collection(persist_dir, collection_name, embedding_fn)
        return {
            "persist_dir": str(persist_dir),
            "collection": collection_name,
            "count_before": collection.count(),
            "count_after": collection.count(),
            "upserted": 0,
        }

    collection = get_collection(persist_dir, collection_name, embedding_fn)
    count_before = collection.count()
    ids = [c.chunk_id for c in chunks]
    documents = [c.document for c in chunks]
    metadatas = [c.metadata for c in chunks]

    for i in range(0, len(ids), batch_size):
        collection.upsert(
            ids=ids[i : i + batch_size],
            documents=documents[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )
    count_after = collection.count()
    return {
        "persist_dir": str(persist_dir),
        "collection": collection_name,
        "count_before": count_before,
        "count_after": count_after,
        "upserted": len(ids),
    }
