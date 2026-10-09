from knowledge.chunking import MAX_CHARS, Piece, split, to_embed

DOC = """# Title

Intro paragraph that belongs to no section.

## First

Alpha one.

Alpha two.

## Second

Beta one.
"""


def test_the_title_is_the_first_heading():
    title, _ = split(DOC)
    assert title == "Title"


def test_we_cut_at_the_section_headings():
    _, pieces = split(DOC)
    assert [p.section for p in pieces] == ["", "First", "Second"]


def test_short_paragraphs_of_a_section_stay_together():
    _, pieces = split(DOC)
    assert pieces[1].text == "Alpha one.\n\nAlpha two."


def test_a_long_section_is_split_at_paragraph_boundaries():
    paragraph = "word " * 60  # 300 characters
    markdown = "# T\n\n## S\n\n" + "\n\n".join([paragraph.strip()] * 5)
    _, pieces = split(markdown, max_chars=700)
    assert len(pieces) > 1
    assert all(p.section == "S" for p in pieces)
    assert all(len(p.text) <= 700 for p in pieces)


def test_no_piece_is_empty_or_lost():
    paragraph = "word " * 60
    markdown = "# T\n\n## S\n\n" + "\n\n".join([paragraph.strip()] * 5)
    _, pieces = split(markdown, max_chars=700)
    assert sum(p.text.count("word") for p in pieces) == 300


def test_a_paragraph_longer_than_the_maximum_stays_whole():
    long_paragraph = "sentence. " * 200
    _, pieces = split(f"# T\n\n## S\n\n{long_paragraph.strip()}", max_chars=100)
    assert len(pieces) == 1
    assert pieces[0].text == long_paragraph.strip()


def test_an_empty_document_has_no_pieces():
    assert split("") == ("", [])


def test_the_default_maximum_is_700():
    assert MAX_CHARS == 700


def test_what_we_embed_carries_the_context():
    text = to_embed("Vacation and Leave", Piece("Illness", "Send the certificate within two days."))
    assert text == "Vacation and Leave — Illness\nSend the certificate within two days."


def test_without_a_section_only_the_title_is_the_context():
    assert to_embed("Title", Piece("", "Text.")) == "Title\nText."


def test_the_function_that_builds_the_text_is_not_collected_as_a_test():
    # to_embed (not "test_...") because pytest collects as tests the imported functions
    # whose name starts with "test".
    assert not to_embed.__name__.startswith("test")
