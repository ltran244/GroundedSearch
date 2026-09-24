from app.retrieval.chunker import TARGET, chunk


def sizes(text: str) -> list[int]:
    return [len(passage) for passage in chunk(text)]


def test_short_text_is_one_passage():
    assert chunk("One short line.") == ["One short line."]


def test_empty_text_is_no_passages():
    assert chunk("") == []


def test_short_lines_are_packed_together():
    # 60 lines of ~50 chars would be 60 useless fragments if split per line.
    text = "\n".join(["A line about solar panels."] * 60)

    assert len(chunk(text)) < 10


def test_no_passage_exceeds_the_target():
    cases = [
        "Sentence one. " * 300,  # one long line, split at sentence ends
        "word " * 900,  # one long line with no sentence ends
        "x" * 5000,  # one long line with no spaces at all
        "\n".join(["A line about solar panels."] * 200),
    ]

    for text in cases:
        assert max(sizes(text)) <= TARGET


def test_passages_overlap():
    text = "\n".join([f"Line number {n} about panels." for n in range(200)])
    passages = chunk(text)

    # The end of one passage reappears at the start of the next.
    assert passages[1].split("\n")[0] in passages[0]
