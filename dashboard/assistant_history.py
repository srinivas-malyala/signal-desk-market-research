"""Bound server-owned completed turns; never accept browser-supplied history."""

from __future__ import annotations

MAX_MESSAGES = 20
MAX_INPUT_BYTES = 24_000
MAX_MESSAGE_CHARS = 4_000


def build_history(turns: list[dict], question: str, *, context: str = "") -> tuple[list[dict], bool]:
    """Turns must be owner-scoped repository records, ordered oldest first.

    Trim complete pairs, never leave an orphaned assistant message. Tool outputs
    and model-provided roles are not replayed. Trusted receipts/context require a
    separate application-owned path in the orchestration layer.
    """
    if not isinstance(question, str) or not question.strip() or len(question) > MAX_MESSAGE_CHARS:
        raise ValueError("invalid_message")
    current = {"role": "user", "content": question.strip()}
    if not isinstance(context, str) or len(context.encode("utf-8")) > 4000:
        raise ValueError("invalid_context")
    if context:
        current["content"] = context + "\n\nCurrent user question:\n" + current["content"]
    pairs = []
    omitted = False
    for turn in turns:
        if turn.get("state") != "completed":
            omitted = True
            continue
        user, assistant = turn.get("user_text"), turn.get("assistant_text")
        if not isinstance(user, str) or not isinstance(assistant, str) or not user or not assistant:
            omitted = True
            continue
        pairs.append([{"role": "user", "content": user}, {"role": "assistant", "content": assistant}])
    result = [current]
    used = len(current["content"].encode("utf-8"))
    for pair in reversed(pairs):
        size = sum(len(item["content"].encode("utf-8")) for item in pair)
        if len(result) + 2 > MAX_MESSAGES or used + size > MAX_INPUT_BYTES:
            omitted = True
            break
        result = pair + result
        used += size
    return result, omitted
