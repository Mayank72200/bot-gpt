import logging
import time
import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.chat_client: ChatMistralAI | None = None
        self.embedding_client: MistralAIEmbeddings | None = None
        if settings.mistral_api_key:
            self.chat_client = ChatMistralAI(
                model=settings.mistral_chat_model,
                api_key=settings.mistral_api_key,
                endpoint=settings.mistral_base_url,
                temperature=0.2,
            )
            self.embedding_client = MistralAIEmbeddings(
                model=settings.mistral_embedding_model,
                api_key=settings.mistral_api_key,
                endpoint=settings.mistral_base_url,
            )

    @staticmethod
    def _to_langchain_messages(messages: list[dict]) -> list[SystemMessage | HumanMessage | AIMessage]:
        converted: list[SystemMessage | HumanMessage | AIMessage] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                converted.append(SystemMessage(content=content))
            elif role == "assistant":
                converted.append(AIMessage(content=content))
            else:
                converted.append(HumanMessage(content=content))
        return converted

    @retry(
        retry=retry_if_exception_type((ExternalServiceError, Exception)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def generate_chat(self, messages: list[dict]) -> dict:
        if not self.settings.mistral_api_key:
            content = "[Mocked response] Set BOTGPT_MISTRAL_API_KEY for live model calls."
            return {"content": content, "token_estimate": max(1, int(len(content.split()) * 1.3))}

        lc_messages = self._to_langchain_messages(messages)

        started = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                self.chat_client.ainvoke(lc_messages), timeout=self.settings.mistral_timeout_seconds
            )
        except TimeoutError as exc:
            raise ExternalServiceError(code="MISTRAL_TIMEOUT", message="Mistral request timed out.", status_code=504) from exc
        except Exception as exc:
            raise ExternalServiceError(code="MISTRAL_REQUEST_FAILED", message="Mistral request failed.", status_code=502) from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        content = str(response.content)
        token_estimate = max(1, int(len(content.split()) * 1.3))

        self.logger.info("llm_chat_completed", extra={"latency_ms": elapsed_ms, "token_estimate": token_estimate})
        return {"content": content, "token_estimate": token_estimate}

    @retry(
        retry=retry_if_exception_type((ExternalServiceError, Exception)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def generate_embedding(self, text: str) -> list[float]:
        if not self.settings.mistral_api_key:
            raise ExternalServiceError(
                code="EMBEDDING_PROVIDER_UNAVAILABLE",
                message="Mistral API key is required for embeddings.",
                status_code=503,
            )

        try:
            vector = await asyncio.wait_for(
                self.embedding_client.aembed_query(text), timeout=self.settings.mistral_timeout_seconds
            )
        except TimeoutError as exc:
            raise ExternalServiceError(code="EMBEDDING_TIMEOUT", message="Embedding request timed out.", status_code=504) from exc
        except Exception as exc:
            raise ExternalServiceError(code="EMBEDDING_REQUEST_FAILED", message="Embedding request failed.", status_code=502) from exc

        return vector
