"""The Schema: GATE computed census — adapted from
nmg2-tools/tests/planlint/test_marker_census.py, retargeted from the Files:
marker onto the Schema: gate (design §7.2). See that design section for the
full rationale on why Schema: is censused and Check: is not.

Four verdicts: PARSES (builds the gate value from the raw field), GATES
(calls declares_schema and branches), READS-RAW-TEXT (reads schema_text
without gating — rules/schema.py, on purpose), UNGATED (a bug — asserted
zero, separately from the whole-mapping assertion).
"""

import ast
from pathlib import Path

import spellbook.planlint

PACKAGE = Path(spellbook.planlint.__file__).parent
SEED = "schema_text"

# Every member of PlanDocument/TaskBlock that reaches the seed by reading it,
# directly or through another member. Computed by accessor_set(); named here so
# a member added to document.py that touches the gate value cannot arrive
# unannounced.
EXPECTED_ACCESSORS = frozenset(
    {"schema_text", "declares_planlint_schema", "_resolve_plan_schema"}
)

# Every function in the package that reads the gate value or reaches the gate.
# One row per function; the verdict is what the AST says it does, not what a
# reader hopes it does.
EXPECTED_CENSUS = {
    "document.PlanDocument.declares_planlint_schema": "PARSES",
    "document.PlanDocument._resolve_plan_schema": "PARSES",
    "api._first_schema_value": "GATES",
    "api._opts_in": "GATES",
    "api.declares_schema": "GATES",
    "api.lint_text": "GATES",
    "api.lint_path": "GATES",
    "api.lint_for_authoring": "GATES",
    "api.lint_for_review": "GATES",
    "api.lint_on_write": "GATES",
    "rules.schema.run": "READS-RAW-TEXT",
    "cli.main": "GATES",
}

# The modules whose functions are ALLOWED to read the gate value without
# gating on it. rules/schema.py is the whole list, and it is deliberate: that
# rule must see a value the gate rejected in order to report the conflict or
# the unknown version, so gating it would make it unable to do its job
# (design §4.7). Any OTHER module that starts reading `schema_text` is making
# its own private admission decision behind the gate's back, which is exactly
# the drift this census exists to catch — so it is censused UNGATED and
# `test_no_consumer_is_ungated` goes red naming it.
RAW_READERS_ALLOWED = frozenset({"rules.schema"})

# The three gate PRIMITIVES. `_first_schema_value` performs the raw scan,
# `_opts_in` decides family membership over that value, and `declares_schema`
# is the public predicate composing the two. All three are seeds because the
# call sites do not agree on which one they use: `lint_text` calls the scan and
# `_opts_in` directly (it needs the VALUE to phrase a skip reason without
# building a document — design §6.1's zero-further-work contract), while
# `lint_on_write` calls the public predicate. Seeding a subset would leave the
# call sites that use the others reported as touching nothing.
GATE_FUNCTIONS = frozenset({"_first_schema_value", "_opts_in", "declares_schema"})


def module_sources():
    """{module name: syntax tree} for EVERY module in the package. Walks the
    WHOLE tree with rglob, reads __init__.py like any other module."""
    return {
        ".".join(path.relative_to(PACKAGE).with_suffix("").parts): ast.parse(
            path.read_text(encoding="utf-8")
        )
        for path in sorted(PACKAGE.rglob("*.py"))
    }


def functions_in(tree):
    found = {}

    def descend(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found[".".join(stack + [child.name])] = (child, stack + [child.name])
                descend(child, stack + [child.name])
            elif isinstance(child, ast.ClassDef):
                descend(child, stack + [child.name])

    descend(tree, [])
    return found


def attributes_read(node):
    """Attribute names this function READS as values.

    A method CALL is not an attribute read. `self._resolve_plan_schema()` is an
    `Attribute` in Load context, so a naive walk counts it as reading
    `_resolve_plan_schema` — which would make `_parse` an accessor for calling
    it, then `__init__` an accessor for calling `_parse`, and the accessor set
    would grow to cover half the class without anyone touching the gate value.
    Reads and calls are two different relations and this file measures them
    with two different functions: reads here, calls in `calls_in`.
    """
    called_funcs = {
        child.func
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
    }
    names = set()

    def descend(current):
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Load):
                if child not in called_funcs:
                    names.add(child.attr)
            descend(child)

    descend(node)
    return names


def reads_outside_functions(tree, accessors):
    names = set()

    def descend(current):
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Load):
                if child.attr in accessors:
                    names.add(child.attr)
            descend(child)

    descend(tree)
    return names


def calls_in(node):
    names = set()

    def descend(current):
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    names.add(func.attr)
            descend(child)

    descend(node)
    return names


def accessor_set(trees):
    members = {}
    for name, (node, stack) in functions_in(trees["document"]).items():
        if len(stack) == 2 and stack[0] in ("TaskBlock", "PlanDocument"):
            members[stack[1]] = attributes_read(node)

    found = {SEED}
    while True:
        grown = set(found)
        for name, reads in members.items():
            if reads & found:
                grown.add(name)
        if grown == found:
            return frozenset(found)
        found = grown


def gate_names(trees, accessors):
    """Every function that REACHES the gate, grown to a fixed point across the
    WHOLE package.

    The closure is global, not per-module, because the real call chain crosses
    three modules: `cli.main` calls `api.lint_path`, which calls
    `api.lint_text`, which calls `declares_schema`. A per-module closure sees
    only the last hop and would report `cli.main` as touching nothing — a
    census that quietly stops measuring at the module boundary.

    A function that READS an accessor is excluded: it consumes the gate value
    directly, which is a different verdict (READS-RAW-TEXT or PARSES) and must
    not be laundered into GATES by also calling something.

    Names are matched unqualified, so two functions with the same base name in
    different modules are treated as one node. That is a deliberate
    over-approximation: it can only ever widen the gate set, and a function
    wrongly reported as GATED is caught by `test_the_whole_mapping_is_the_expected_one`
    the moment it appears, because every row is named.
    """
    found = set(GATE_FUNCTIONS)
    while True:
        grown = set(found)
        for tree in trees.values():
            for _, (node, stack) in functions_in(tree).items():
                if attributes_read(node) & accessors:
                    continue
                if calls_in(node) & grown:
                    grown.add(stack[-1])
        if grown == found:
            return found
        found = grown


def census(trees, accessors):
    gates = gate_names(trees, accessors)
    out = {}
    for module, tree in trees.items():
        for name, (node, stack) in functions_in(tree).items():
            reads = attributes_read(node) & accessors
            is_gate = stack[-1] in gates

            if not reads and not is_gate:
                continue

            if is_gate:
                out[f"{module}.{name}"] = "GATES"
                continue

            parses = (
                reads == {SEED}
                and module == "document"
                and len(stack) == 2
                and stack[0] in ("TaskBlock", "PlanDocument")
                and stack[-1] in accessors
            )
            if parses:
                out[f"{module}.{name}"] = "PARSES"
            elif module in RAW_READERS_ALLOWED:
                out[f"{module}.{name}"] = "READS-RAW-TEXT"
            else:
                # A function that reads the gate value, calls no gate, and is
                # neither the parser that builds it nor an allowed raw reader.
                # This verdict is the whole point of the census, so it MUST be
                # reachable: an earlier draft assigned READS-RAW-TEXT to every
                # non-gate reader, which made the verdict set closed over
                # {GATES, PARSES, READS-RAW-TEXT} and left
                # test_no_consumer_is_ungated structurally unable to fail.
                out[f"{module}.{name}"] = "UNGATED"
    return out


def test_the_schema_field_is_assigned_to_one_attribute_only():
    """_resolve_plan_schema / _fill_fields assign the Schema: value to
    self.schema_text or task.schema_text and nothing else."""
    tree = ast.parse(
        (PACKAGE / "document.py").read_text(encoding="utf-8")
    )
    targets = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                unparsed = ast.unparse(target)
                if unparsed in ("task.schema_text", "self.schema_text"):
                    targets.append(unparsed)
    assert set(targets) == {"task.schema_text", "self.schema_text"}


def test_one_module_reads_the_field_regex_out_of_the_document():
    users = []
    for name, tree in module_sources().items():
        for node in ast.walk(tree):
            named = isinstance(node, ast.Name) and node.id == "FIELD"
            attributed = isinstance(node, ast.Attribute) and node.attr == "FIELD"
            if named or attributed:
                users.append(name)
                break
    assert sorted(users) == ["document"]


def test_the_accessor_set_is_the_one_this_file_names():
    assert accessor_set(module_sources()) == EXPECTED_ACCESSORS


def test_the_seed_alone_is_not_the_answer():
    """The closure must GROW past its seed, and grow to the named members.

    `assert found != {SEED}` alone is too weak to be worth running: a closure
    that grew by one accidental member satisfies it just as well as the correct
    one, so it cannot distinguish a working transitive walk from a broken walk
    that happened to pick something up. This names the members the growth must
    produce, which is a claim the walker can actually fail."""
    found = accessor_set(module_sources())
    assert SEED in found
    assert found - {SEED} == {"declares_planlint_schema", "_resolve_plan_schema"}


def test_no_accessor_is_read_outside_a_function_body():
    trees = module_sources()
    accessors = accessor_set(trees)
    offenders = {}
    for module, tree in trees.items():
        found = reads_outside_functions(tree, accessors)
        if found:
            offenders[module] = sorted(found)
    assert offenders == {}


def test_the_package_holds_exactly_the_consumers_this_file_names():
    trees = module_sources()
    found = census(trees, accessor_set(trees))
    added = sorted(set(found) - set(EXPECTED_CENSUS))
    removed = sorted(set(EXPECTED_CENSUS) - set(found))
    assert {"undocumented": added, "gone": removed} == {"undocumented": [], "gone": []}


def test_no_consumer_is_ungated():
    """Every UNGATED row is a bug: reads an accessor, calls no gate, and is
    not READS-RAW-TEXT/PARSES. Asserted separately so a failure says which
    of the two things happened."""
    trees = module_sources()
    accessors = accessor_set(trees)
    found = census(trees, accessors)
    ungated = [
        name
        for name, verdict in found.items()
        if verdict not in ("GATES", "PARSES", "READS-RAW-TEXT")
    ]
    assert ungated == []


def test_the_whole_mapping_is_the_expected_one():
    trees = module_sources()
    found = census(trees, accessor_set(trees))
    assert found == EXPECTED_CENSUS
