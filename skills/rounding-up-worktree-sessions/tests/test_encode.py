import roundup


def test_encode_keeps_leading_dash():
    assert roundup.encode_cwd_literal("/Users/eek/Development/x") == "-Users-eek-Development-x"


def test_encode_does_not_strip_leading_dash_regression():
    # Guards the §8.4 discrepancy: must NOT produce the old stripped form.
    out = roundup.encode_cwd_literal("/Users/eek")
    assert out.startswith("-")
    assert out != "Users-eek"


def test_encode_replaces_all_non_alnum_with_dash():
    # Bug A: Claude Code replaces EVERY non-[A-Za-z0-9] char with '-', not just '/'.
    # A Windows-style path therefore loses its colon and backslashes alike.
    assert roundup.encode_cwd_literal("C:\\Users\\eek") == "C--Users-eek"


def test_encode_worktree_not_collapsed_to_git_root():
    p = "/Users/eek/Development/worktrees/ODY-2957/styleseat"
    assert roundup.encode_cwd_literal(p) == "-Users-eek-Development-worktrees-ODY-2957-styleseat"


# ---------------------------------------------------------------------------
# Bug A — encode_cwd_literal must match Claude Code's ACTUAL project-dir
# encoding: every non-[A-Za-z0-9] char becomes '-', runs are NOT collapsed,
# the leading dash is kept. Verified empirically against ~/.claude/projects/
# and ~/.claude-work/projects/ (40 samples, 0 mismatches; the double-dash dir
# `-Users-eek-Development-nim-typestates--claude-worktrees-v0-5-bundle` proves
# runs are not collapsed).
# ---------------------------------------------------------------------------
def test_encode_dot_becomes_dash():
    # Regression for the styleseat.github case verified on disk: the DOT in the
    # real dir `/Users/eek/Development/styleseat.github` is stored by Claude as a
    # DASH -> `-Users-eek-Development-styleseat-github`.
    assert (
        roundup.encode_cwd_literal("/Users/eek/Development/styleseat.github")
        == "-Users-eek-Development-styleseat-github"
    )


def test_encode_underscore_becomes_dash():
    assert (
        roundup.encode_cwd_literal("/Users/eek/Development/my_cool_repo")
        == "-Users-eek-Development-my-cool-repo"
    )


def test_encode_digits_preserved():
    assert (
        roundup.encode_cwd_literal("/Users/eek/Development/ODY-2957")
        == "-Users-eek-Development-ODY-2957"
    )


def test_encode_existing_dashes_preserved():
    assert (
        roundup.encode_cwd_literal("/Users/eek/Development/nim-skills")
        == "-Users-eek-Development-nim-skills"
    )


def test_encode_space_becomes_dash():
    assert (
        roundup.encode_cwd_literal("/Users/eek/My Drive")
        == "-Users-eek-My-Drive"
    )


def test_encode_consecutive_separators_not_collapsed():
    # Decisive evidence (verified on disk): the cwd
    # `/Users/eek/Development/nim-typestates/.claude/worktrees/v0.5-bundle`
    # is stored as `-Users-eek-Development-nim-typestates--claude-worktrees-v0-5-bundle`.
    # The `/.` run produces TWO adjacent dashes -> Claude does NOT collapse runs.
    p = "/Users/eek/Development/nim-typestates/.claude/worktrees/v0.5-bundle"
    assert (
        roundup.encode_cwd_literal(p)
        == "-Users-eek-Development-nim-typestates--claude-worktrees-v0-5-bundle"
    )


def test_encode_roundtrip_against_fixture_project_dir(tmp_path):
    # Round-trip-ish: a project dir whose name was produced by Claude from a known
    # cwd must equal encode_cwd_literal(that_cwd), and _find_project_dir must locate
    # it from the literal cwd. Uses the styleseat.github case.
    cwd = "/Users/eek/Development/styleseat.github"
    dir_name = "-Users-eek-Development-styleseat-github"
    assert roundup.encode_cwd_literal(cwd) == dir_name
    projects = tmp_path / "projects"
    (projects / dir_name).mkdir(parents=True)
    assert roundup._find_project_dir(str(projects), cwd) == str(projects / dir_name)


def test_find_project_dir_dotted_dir(tmp_path):
    # _find_project_dir inherits the fix: a dotted cwd must locate its dash-encoded dir.
    projects = tmp_path / "projects"
    (projects / "-Users-eek-Development-styleseat-github").mkdir(parents=True)
    found = roundup._find_project_dir(str(projects), "/Users/eek/Development/styleseat.github")
    assert found == str(projects / "-Users-eek-Development-styleseat-github")


def test_find_project_dir_underscored_dir(tmp_path):
    projects = tmp_path / "projects"
    (projects / "-Users-eek-my-cool-repo").mkdir(parents=True)
    found = roundup._find_project_dir(str(projects), "/Users/eek/my_cool_repo")
    assert found == str(projects / "-Users-eek-my-cool-repo")


def test_find_project_dir_leading_form(tmp_path):
    projects = tmp_path / "projects"
    (projects / "-Users-eek-x").mkdir(parents=True)
    found = roundup._find_project_dir(str(projects), "/Users/eek/x")
    assert found == str(projects / "-Users-eek-x")


def test_find_project_dir_stripped_fallback(tmp_path):
    projects = tmp_path / "projects"
    (projects / "Users-eek-x").mkdir(parents=True)
    found = roundup._find_project_dir(str(projects), "/Users/eek/x")
    assert found == str(projects / "Users-eek-x")


def test_find_project_dir_missing_returns_none(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    assert roundup._find_project_dir(str(projects), "/Users/eek/x") is None
