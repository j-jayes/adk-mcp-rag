from __future__ import annotations

from uuid import uuid4
from typing import List, Optional, Sequence, Dict, Any, Union
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm


class VectorDB(BaseModel):
    """
    Qdrant-backed vector store (FastEmbed path) with:
      - add(): hybrid-ready ingestion via client.add(documents=..., metadata=..., ids=...)
      - query(): dense (and hybrid if sparse model is set) text query
      - scroll_all(): correct pagination using next_page_offset
      - ensure_payload_indexes(): create keyword/range indexes for faster filtering
    """
    memory_location: str = "http://localhost:6333"
    embeddings_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    sparse_embeddings_model_name: str = "Qdrant/bm25"  # optional hybrid
    collection_name: str = "default_collection"
    client: Optional[QdrantClient] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._initialize_client()

    # -----------------------------
    # Client / collection setup
    # -----------------------------
    def _initialize_client(self) -> None:
        try:
            self.client = QdrantClient(url=self.memory_location)
            # FastEmbed models for add/query
            self.client.set_model(self.embeddings_model_name)
            # If sparse model available, enables hybrid by default.
            try:
                if self.sparse_embeddings_model_name:
                    self.client.set_sparse_model(self.sparse_embeddings_model_name)
            except Exception:
                # Sparse is optional; skip if not supported in your install.
                pass
        except Exception as e:
            print(
                f"Error initializing Qdrant client: {e}\n"
                f"Check Qdrant is reachable at '{self.memory_location}'."
            )
            self.client = None

    def check_collection_existence(self) -> bool:
        try:
            return bool(self.client.get_collection(self.collection_name))
        except Exception as e:
            print(f"Collection does not exist: {e}")
            return False

    # -----------------------------
    # Ingestion
    # -----------------------------
    def add(
        self,
        documents: Sequence[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[Sequence[Union[str, int]]] = None,
    ) -> List[Union[str, int]]:
        """
        Add chunks to Qdrant using the FastEmbed path.

        - We mirror text into BOTH 'document' (Qdrant default) and 'page_content'
          so downstream consumers that expect either key will work.
        - You can pass full 'metadatas' per chunk (preferred). If omitted, minimal
          metadata is created.
        """
        if not documents:
            print("No documents to add.")
            return []

        # Prepare IDs
        if ids is None:
            ids = [str(uuid4()) for _ in range(len(documents))]

        # Prepare metadata list and mirror page_content
        now_iso = datetime.utcnow().isoformat() + "Z"
        md_list: List[Dict[str, Any]] = []
        if metadatas is None:
            md_list = [{"ingested_at": now_iso} for _ in range(len(documents))]
        else:
            if len(metadatas) != len(documents):
                raise ValueError("len(metadatas) must match len(documents)")
            # shallow copy to avoid side effects
            md_list = [dict(m) if m is not None else {"ingested_at": now_iso} for m in metadatas]
            for m in md_list:
                m.setdefault("ingested_at", now_iso)

        # Ensure helpful fields exist and mirror content keys
        for i, text in enumerate(documents):
            m = md_list[i]
            # Stable-ish identifiers if caller didn't set them
            m.setdefault("chunk_id", m.get("id") or m.get("source_id") or str(uuid4()))
            m.setdefault("doc_id", m.get("source") or m.get("doc_path") or None)
            m.setdefault("chunk_index", m.get("chunk_index") or m.get("page", 0))
            m.setdefault("text_length", len(text))
            # Mirror into page_content to satisfy non-Qdrant wrappers
            # Qdrant will also store the text under 'document' automatically.
            m["page_content"] = text

        # Perform add (embeds + auto collection creation)
        try:
            out_ids = self.client.add(
                collection_name=self.collection_name,
                documents=list(documents),
                metadata=md_list,
                ids=list(ids),
            )
            return out_ids
        except Exception as e:
            print(f"Error adding documents: {e}")
            return []

    # Backwards-compatible wrapper for older call sites
    def add_to_vectordb(self, documents, source_ids):
        # Convert source_ids into metadatas and forward to add()
        metadatas = [{"source_id": sid} for sid in source_ids]
        return self.add(documents=documents, metadatas=metadatas)

    # -----------------------------
    # Retrieval
    # -----------------------------
    def query(
        self,
        query_text: str,
        limit: int = 5,
        score_threshold: Optional[float] = None,
        query_filter: Optional[qm.Filter] = None,
    ) -> List[Dict[str, Any]]:
        """
        Text query using FastEmbed path. If a sparse model is set, Qdrant will
        fuse dense+sparse (RRF) under the hood.

        Returns a list of dicts with id, score, page_content, and metadata.
        """
        try:
            kwargs: Dict[str, Any] = {"limit": limit}
            if score_threshold is not None:
                kwargs["score_threshold"] = score_threshold
            if query_filter is not None:
                kwargs["query_filter"] = query_filter

            results = self.client.query(
                collection_name=self.collection_name,
                query_text=query_text,
                **kwargs,
            )

            normalized = []
            for r in results:
                # r.metadata contains payload incl. 'document' (and our 'page_content')
                payload = dict(r.metadata or {})
                text = payload.get("page_content") or payload.get("document") or ""
                normalized.append(
                    {
                        "id": r.id,
                        "score": getattr(r, "score", None),
                        "page_content": text,
                        "metadata": payload,
                    }
                )
            return normalized
        except Exception as e:
            print(f"Error using query(): {e}")
            return []

    def scroll_all(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """
        Read the entire collection with proper scrolling.

        Uses the 'next_page_offset' returned by Qdrant, not a naive integer step.
        """
        all_docs: List[Dict[str, Any]] = []
        next_offset: Optional[Union[int, str]] = None

        try:
            while True:
                points, next_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=batch_size,
                    offset=next_offset,        # <-- correct paging token
                    with_payload=True,
                    with_vectors=False,
                )
                if not points:
                    break

                for p in points:
                    payload = dict(p.payload or {})
                    text = payload.get("page_content") or payload.get("document") or ""
                    meta = {k: v for k, v in payload.items()}
                    all_docs.append(
                        {"id": p.id, "page_content": text, "metadata": meta}
                    )

                if next_offset is None:
                    break

            return all_docs
        except Exception as e:
            print(f"Error retrieving documents: {e}")
            return []

    # -----------------------------
    # Indexing helpers (optional)
    # -----------------------------
    def ensure_payload_indexes(self) -> None:
        """
        Create payload indexes for the most common fields we’ll filter by.
        Safe to call multiple times; Qdrant will ignore existing indexes.
        """
        index_specs = [
            ("source", "keyword"),
            ("source_id", "keyword"),
            ("doc_id", "keyword"),
            ("chunk_id", "keyword"),
            ("chunk_index", "integer"),
            ("page", "integer"),
            ("ext", "keyword"),
            ("lang", "keyword"),
            ("year", "integer"),
        ]
        for field_name, schema in index_specs:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception:
                # Ignore "already exists" or unused fields
                pass
