"""Splitting a text into passages. It knows nothing about Django."""

MAX_CHARS = 800


def split(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Passages of at most `max_chars` characters, breaking at paragraph boundaries."""
    passages, current = [], ""
    for paragraph in (p.strip() for p in text.split("\n\n")):
        if not paragraph:
            continue
        while len(paragraph) > max_chars:  # a paragraph that is too long is cut at a space
            cut = paragraph.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            if current:
                passages.append(current)
                current = ""
            passages.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        if current and len(current) + 2 + len(paragraph) > max_chars:
            passages.append(current)
            current = ""
        current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        passages.append(current)
    return passages
