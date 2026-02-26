import numpy as np

from app.services.llm_service import LLMService


class EmbeddingService:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def embed_text(self, text: str) -> np.ndarray:
        vector = await self.llm_service.generate_embedding(text)
        return np.array(vector, dtype=np.float32)
