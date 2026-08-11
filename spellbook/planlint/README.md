# spellbook.planlint

A schema-gated linter for spellbook implementation plans.

The design document is NOT in this repository. It lives in the operator's
spellbook config directory, alongside the other plan artifacts for this project:

    $SPELLBOOK_CONFIG_DIR/docs/Users-eek-Development-spellbook/plans/2026-08-11-planlint-port-design.md

with `SPELLBOOK_CONFIG_DIR` defaulting to `~/.local/spellbook`. Written as a
repo-relative `docs/...` path it would be a dead link: this repo's `docs/`
directory has no `Users-eek-Development-spellbook/` subtree and never will,
because plan artifacts are per-machine state, not shipped source.

## Fixtures

Every fixture lives at `tests/test_scripts/fixtures/planlint/`. A lint with
no negative fixture is not done.

| Fixture | Purpose |
|---------|---------|
| `clean_plan.md` | A plan every rule passes. |
| `legacy_plan.md` | No `Schema:` field. Must never be linted. |
| `opted_out_plan.md` | `Schema: legacy`. |
| `neg_unmatched_backtick.md` | `unmatched-backtick` |
| `neg_unclosed_fence.md` | `unclosed-fence` |
| `neg_depends_cycle.md` | `dependency-cycle` |
| `neg_depends_unknown.md` | `unknown-dependency` |
| `neg_depends_self.md` | `self-dependency` |
| `neg_depends_prose.md` | `depends-prose` |
| `neg_check_empty.md` | `check-empty` |
| `neg_check_not_a_command.md` | `check-not-a-command` |
| `neg_check_placeholder.md` | `check-placeholder` |
| `neg_check_not_runnable.md` | `check-not-runnable` |
| `neg_check_verify_drift.md` | `check-verify-pass-consistency` |
| `neg_modify_path_missing.md` | `modify-path-missing` |
| `neg_create_path_exists.md` | `create-path-exists` |
| `neg_shared_path_no_owner.md` | `shared-path-without-owner` |
| `neg_schema_conflict.md` | `schema-conflict` |
| `neg_schema_unknown_version.md` | `schema-unknown-version` |
| `neg_schema_fallback_unknown_version.md` | `schema-unknown-version`, reported once against the task that owns the copied-down plan-level `Schema:`, not twice. |
| `neg_schema_conflict_task_section.md` | `schema-conflict` and `schema-unknown-version` together, each attributed to its own owning section rather than a hardcoded `Task 1`. |

## Rollback

Two levels, per design §8.3. Neither requires a migration, because the linter never
modifies a plan file.

**Per plan.** Change the plan's field to `**Schema:** legacy`. The gate returns False
and the plan is never linted again — a decision recorded in the document rather than
an absence someone has to infer.

**Whole feature.** Revert the three SKILL.md edits (`writing-plans`,
`reviewing-impl-plans`, `executing-plans`). That is the entire integration surface:
nothing else in spellbook imports `spellbook.planlint`. The package stays on disk,
imported by nobody, and every plan reverts to the pre-port behavior in which no plan
is linted at all. The `spellbook-planlint` console script keeps working for anyone
invoking it by hand, which is harmless — it reads plans and writes nothing.

To confirm a whole-feature rollback actually landed, check that no SKILL.md still
names a call site:

```bash
grep -rn "lint_for_authoring\|lint_for_review\|lint_on_write" skills/
```

Expected after rollback: no matches. A match means one of the three edits survived and
the feature is only half reverted.
