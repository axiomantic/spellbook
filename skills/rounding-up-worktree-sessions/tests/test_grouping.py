import pytest
import roundup


@pytest.mark.parametrize("title,expected", [
    ("query-opt-a", "query-opt"),
    ("query-opt-b", "query-opt"),
    ("lfq-lychee", "lfq"),
    ("lfq-guava", "lfq"),
    ("lfq-pepper", "lfq"),
    ("ody-2957-styleseat-a", "ody-2957-styleseat"),   # strips final -a
    ("ody-2957-styleseat", "ody-2957-styleseat"),     # UNCHANGED (styleseat 9>8 chars; 2957 is middle)
])
def test_strip_disambiguator_table(title, expected):
    assert roundup.strip_disambiguator(title) == expected


def test_strip_does_not_touch_middle_digit_token():
    # 2957 is a middle token, never the final token -> never stripped
    assert roundup.strip_disambiguator("ody-2957-styleseat") == "ody-2957-styleseat"


def test_strip_applied_once_not_repeatedly():
    # only the single final token is stripped
    assert roundup.strip_disambiguator("foo-bar-a") == "foo-bar"


def test_strip_empty_base_guard():
    assert roundup.strip_disambiguator("a-b") == "a"   # base 'a' is 1 char, allowed


def test_group_key_title_prefix():
    s = {"title": "query-opt-b", "resolved_workspace": None, "encoded_cwd_current": "-X"}
    assert roundup.compute_group_key(s) == ("query-opt", "title_prefix")


def test_group_key_resolved_workspace_fallback():
    s = {"title": None, "resolved_workspace": "ws-1", "encoded_cwd_current": "-X"}
    assert roundup.compute_group_key(s) == ("ws-1", "resolved_workspace")


def test_group_key_encoded_dir_fallback():
    s = {"title": None, "resolved_workspace": None, "encoded_cwd_current": "-Users-eek-x"}
    assert roundup.compute_group_key(s) == ("-Users-eek-x", "encoded_project_dir")
