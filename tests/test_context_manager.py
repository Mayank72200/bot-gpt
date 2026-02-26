from app.models.message import Message
from app.services.context_manager import ContextManager


def test_token_trimming_keeps_recent_with_budget() -> None:
    manager = ContextManager(max_context_tokens=20, min_recent_messages=2)
    messages = [
        Message(conversation_id="c1", role="user", content="one two three four five", token_count=7, sequence_number=1),
        Message(conversation_id="c1", role="assistant", content="six seven eight", token_count=4, sequence_number=2),
        Message(conversation_id="c1", role="user", content="nine ten eleven", token_count=4, sequence_number=3),
        Message(conversation_id="c1", role="assistant", content="twelve thirteen", token_count=3, sequence_number=4),
    ]

    trimmed = manager.trim_messages(messages)
    seq = [msg.sequence_number for msg in trimmed]
    assert seq[-2:] == [3, 4]
    assert sum(msg.token_count for msg in trimmed) <= 20
