import re

TARGET = 1500  # characters, ~375 tokens
OVERLAP = 200

# Split after . ! ? followed by whitespace, keeping the punctuation.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _split_long(line: str) -> list[str]:
    """Break a line longer than TARGET into pieces that fit."""
    pieces: list[str] = []
    for sentence in _SENTENCE_END.split(line):
        while len(sentence) > TARGET:
            pieces.append(sentence[:TARGET])
            sentence = sentence[TARGET:]
        if sentence:
            pieces.append(sentence)
    return pieces


def chunk(text: str) -> list[str]:
    """Split text into passages of up to TARGET characters, with overlap."""
    chunks, current = [], ""
    lines = (raw.strip() for raw in text.split("\n") if raw.strip())
    for line in (piece for raw in lines for piece in _split_long(raw)):
        if len(current) + len(line) + 1 <= TARGET:
            current += ("\n" if current else "") + line
        else:
            if current:
                chunks.append(current)

            tail = current[-OVERLAP:] if current else ""
            fits = tail and len(tail) + 1 + len(line) <= TARGET
            current = f"{tail}\n{line}" if fits else line
    if current:
        chunks.append(current)
    return chunks
