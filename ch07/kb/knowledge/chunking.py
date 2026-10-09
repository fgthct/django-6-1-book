"""Splitting Markdown documents into chunks. It knows nothing about Django."""
import re
from dataclasses import dataclass

MAX_CHARS = 700


@dataclass(frozen=True)
class Piece:
    section: str
    text: str


def split(markdown: str, max_chars: int = MAX_CHARS) -> tuple[str, list[Piece]]:
    """Return (document title, pieces).

    We cut at section headings (`## ...`), because that is where the author has
    already decided the topic changes. If a section is too long we split it
    at paragraph boundaries: never in the middle of a sentence.
    """
    title = ""
    section = ""
    paragraphs: list[str] = []
    pieces: list[Piece] = []

    def close():
        pieces.extend(_pack(section, paragraphs, max_chars))
        paragraphs.clear()

    for block in re.split(r"\n\s*\n", markdown.strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith("# ") and not title:
            title = block[2:].strip()
        elif block.startswith("## "):
            close()
            section = block[3:].strip()
        else:
            paragraphs.append(block)
    close()
    return title, pieces


def _pack(section: str, paragraphs: list[str], maximum: int) -> list[Piece]:
    pieces, current = [], []
    for p in paragraphs:
        # A paragraph longer than the maximum stays whole: splitting it is worse.
        if current and len("\n\n".join([*current, p])) > maximum:
            pieces.append(Piece(section, "\n\n".join(current)))
            current = []
        current.append(p)
    if current:
        pieces.append(Piece(section, "\n\n".join(current)))
    return pieces


def to_embed(title: str, piece: Piece) -> str:
    """What we give to the embedding model: the piece *with its context*.

    A paragraph that says "the request must be made 15 days ahead" doesn't say
    what it is about. The title and the section remind it.
    """
    heading = f"{title} — {piece.section}" if piece.section else title
    return f"{heading}\n{piece.text}"
