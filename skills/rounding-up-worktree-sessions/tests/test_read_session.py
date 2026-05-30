import roundup


def test_reads_valid_jsonl(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text('{"a": 1}\n{"b": 2}\n')
    recs = roundup._read_session(str(f))
    assert recs == [{"a": 1}, {"b": 2}]


def test_skips_malformed_lines(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text('{"a": 1}\nNOT JSON\n{"b": 2}\n')
    recs = roundup._read_session(str(f))
    assert recs == [{"a": 1}, {"b": 2}]


def test_skips_blank_lines(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text('{"a": 1}\n\n   \n{"b": 2}\n')
    recs = roundup._read_session(str(f))
    assert recs == [{"a": 1}, {"b": 2}]


def test_missing_file_returns_empty(tmp_path):
    recs = roundup._read_session(str(tmp_path / "nope.jsonl"))
    assert recs == []


def test_never_raises_on_garbage(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_bytes(b"\xff\xfe garbage \x00\n{\"a\":1}\n")
    recs = roundup._read_session(str(f))  # must not raise
    assert {"a": 1} in recs
