from app.models.message import Message


class ContextManager:
    def __init__(self, max_context_tokens: int, min_recent_messages: int, max_history_messages: int = 10):
        self.max_context_tokens = max_context_tokens
        self.min_recent_messages = min_recent_messages
        self.max_history_messages = max_history_messages

    @staticmethod
    def estimate_tokens(text: str) -> int:
        words = len(text.split())
        return int(words * 1.3) + 1

    def last_n_messages(self, messages: list[Message], n: int | None = None) -> list[Message]:
        """Return only the last *n* messages (default: ``max_history_messages``).

        This is the primary context-window strategy: a hard cap on message
        count so we never exceed the LLM token / context-window limits
        regardless of individual message length.
        """
        limit = n if n is not None else self.max_history_messages
        if limit <= 0 or not messages:
            return []
        return messages[-limit:]

    def trim_messages(self, messages: list[Message]) -> list[Message]:
        return self.trim_messages_to_budget(messages, self.max_context_tokens)

    def trim_messages_to_budget(self, messages: list[Message], budget_tokens: int) -> list[Message]:
        if not messages:
            return []

        retained: list[Message] = []
        running_tokens = 0

        for message in reversed(messages):
            tokens = message.token_count or self.estimate_tokens(message.content)
            if len(retained) < self.min_recent_messages:
                retained.append(message)
                running_tokens += tokens
                continue

            if running_tokens + tokens > budget_tokens:
                continue
            retained.append(message)
            running_tokens += tokens

        retained.reverse()
        return retained

    def select_full_chunks_with_budget(self, chunks: list[str], budget_tokens: int) -> list[str]:
        selected: list[str] = []
        running_tokens = 0
        for chunk in chunks:
            chunk_tokens = self.estimate_tokens(chunk)
            if running_tokens + chunk_tokens > budget_tokens:
                continue
            selected.append(chunk)
            running_tokens += chunk_tokens
        return selected
