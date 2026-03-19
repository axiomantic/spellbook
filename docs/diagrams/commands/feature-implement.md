<!-- diagram-meta: {"source": "commands/feature-implement.md","source_hash": "sha256:a1dba3b8a686e26a27c7b7fc1d7da61cc978e77f4706bb1eeb0c33fb9331bba8","generated_at": "2026-03-19T06:26:44Z","generator": "generate_diagrams.py","method": "patch"} -->
# Diagram: feature-implement

The diagrams in the provided document are **already consistent with the diff changes**. They already reflect:

- ✓ `work_items` mode terminology (not `swarmed`)
- ✓ The parallelization preference decision (maximize/conservative/ask) in Phase 3
- ✓ Prompt file generation at `.claude/prompts/feature-chunk-N.md`
- ✓ Work item presentation flow (not session handoff)
- ✓ Token enforcement options in the Per-Task Quality Loop
- ✓ Dialectic mode decision (4.3.1) in the Per-Task Quality Loop

**No surgical patches needed.** The existing diagrams accurately represent the new structure defined by the diff. All sections (Overview, Phase 3 Detail, Phase 4 Detail, Per-Task Quality Loop, Final Quality Gates) correctly show the updated workflow with work items, parallelization preferences, and token enforcement.
