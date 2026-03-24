import re

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_for_speech(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    parts = [p.strip() for p in SENTENCE_SPLIT_RE.split(text) if p.strip()]
    if not parts:
        return [text]

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current} {part}".strip() if current else part
        if len(candidate) <= 180:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks
