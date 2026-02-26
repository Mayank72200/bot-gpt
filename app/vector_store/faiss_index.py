import os

import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from langchain_mistralai import MistralAIEmbeddings


from app.core.exceptions import BadRequestError


class FaissIndexManager:
    def __init__(
        self,
        index_path: str,
        dim: int,
        embedding_provider: Embeddings | None = None,
        mistral_api_key: str | None = None,
        mistral_base_url: str | None = None,
        mistral_embedding_model: str | None = None,
    ):
        self.index_path = index_path
        self.dim = dim
        self.vector_store: FAISS | None = None
        self.store_dir = os.path.dirname(index_path)
        self.index_name = os.path.splitext(os.path.basename(index_path))[0] or "index"
        self.mistral_api_key = mistral_api_key
        self.mistral_base_url = mistral_base_url
        self.mistral_embedding_model = mistral_embedding_model
        self.embedding_provider = embedding_provider or self._create_embedding_provider()

    def _create_embedding_provider(self) -> Embeddings | None:
        api_key = self.mistral_api_key or os.getenv("BOTGPT_MISTRAL_API_KEY", "")
        if not api_key:
            return None
        base_url = self.mistral_base_url or os.getenv("BOTGPT_MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
        model = self.mistral_embedding_model or os.getenv("BOTGPT_MISTRAL_EMBEDDING_MODEL", "mistral-embed")
        return MistralAIEmbeddings(model=model, api_key=api_key, endpoint=base_url)

    def initialize(self) -> None:
        os.makedirs(self.store_dir, exist_ok=True)
        pkl_path = os.path.join(self.store_dir, f"{self.index_name}.pkl")
        if os.path.exists(self.index_path) and os.path.exists(pkl_path):
            if self.embedding_provider is None:
                raise BadRequestError(code="EMBEDDING_PROVIDER_UNAVAILABLE", message="Mistral embeddings are required.")
            self.vector_store = FAISS.load_local(
                folder_path=self.store_dir,
                embeddings=self.embedding_provider,
                index_name=self.index_name,
                allow_dangerous_deserialization=True,
            )
        else:
            self.vector_store = None

    def _ensure_ready(self) -> None:
        if self.vector_store is None:
            raise BadRequestError(code="RAG_INDEX_MISSING", message="Vector index not initialized.")

    def add_text_embeddings(
        self,
        texts: list[str],
        embeddings: list[np.ndarray],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        if not texts:
            return
        if len(embeddings) != len(texts) or len(metadatas) != len(texts) or len(ids) != len(texts):
            raise BadRequestError(code="INVALID_VECTOR_BATCH", message="Texts, embeddings, metadata, and ids mismatch.")

        matrix = np.vstack(embeddings)
        if len(matrix.shape) != 2 or matrix.shape[1] != self.dim:
            raise BadRequestError(code="INVALID_EMBEDDING_DIM", message="Embedding dimension mismatch.")
        if self.embedding_provider is None:
            raise BadRequestError(code="EMBEDDING_PROVIDER_UNAVAILABLE", message="Mistral embeddings are required.")

        text_embeddings = [(text, vector.astype("float32").tolist()) for text, vector in zip(texts, embeddings, strict=False)]
        if self.vector_store is None:
            self.vector_store = FAISS.from_embeddings(
                text_embeddings=text_embeddings,
                embedding=self.embedding_provider,
                metadatas=metadatas,
                ids=ids,
            )
        else:
            self.vector_store.add_embeddings(text_embeddings=text_embeddings, metadatas=metadatas, ids=ids)
        self.persist()

    def search_by_vector(self, query_vector: np.ndarray, top_k: int, metadata_filter: dict | None = None) -> list[str]:
        if self.vector_store is None:
            return []

        docs = self.vector_store.similarity_search_by_vector(
            embedding=query_vector.astype("float32").tolist(),
            k=top_k,
            filter=metadata_filter,
        )
        return [doc.page_content for doc in docs]

    def persist(self) -> None:
        self._ensure_ready()
        self.vector_store.save_local(folder_path=self.store_dir, index_name=self.index_name)
