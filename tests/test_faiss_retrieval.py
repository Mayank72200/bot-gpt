import os
import tempfile

import numpy as np
from langchain_core.embeddings import Embeddings

from app.vector_store.faiss_index import FaissIndexManager


class TestEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        if text == "beta":
            return [0.0, 1.0, 0.0, 0.0]
        if text == "alpha":
            return [1.0, 0.0, 0.0, 0.0]
        return [0.0, 0.0, 1.0, 0.0]


def test_faiss_retrieval_returns_expected_chunk() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        index_path = os.path.join(temp_dir, "index.faiss")

        manager = FaissIndexManager(index_path=index_path, dim=4, embedding_provider=TestEmbeddings())
        manager.initialize()

        vectors = [
            np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32),
            np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32),
        ]
        manager.add_text_embeddings(
            texts=["alpha", "beta", "gamma"],
            embeddings=vectors,
            metadatas=[{"user_id": "u1"}, {"user_id": "u1"}, {"user_id": "u2"}],
            ids=["101", "102", "103"],
        )

        query = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        results = manager.search_by_vector(query_vector=query, top_k=1, metadata_filter={"user_id": "u1"})

        assert len(results) == 1
        assert results[0] == "beta"
