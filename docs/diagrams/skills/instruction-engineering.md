<!-- diagram-meta: {"source": "skills/instruction-engineering/SKILL.md", "source_hash": "sha256:d5e6dd6a1204aa29e6fd81b31cfaa7d65191e665c9655ab2e8cd5e9bd4c98b0d", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: instruction-engineering

Orchestrator workflow for engineering LLM prompts and instructions. Analyzes the task, selects techniques, drafts using templates, optionally documents tools, sharpens for ambiguity, and validates against a comprehensive self-check.

```mermaid
flowchart TD
    Start([Prompt Engineering Task])
    Analyze[Analyze Task & Audience]
    Techniques[/ie-techniques/]
    Draft[/ie-template/]
    HasTools{Involves Tools?}
    ToolDocs[/ie-tool-docs/]
    SharpenAudit[/sharpen-audit/]
    AmbigFound{Ambiguities Found?}
    SharpenImprove[/sharpen-improve/]
    IsSkill{Is SKILL.md?}
    CSOCheck{CSO Compliant?}
    FixCSO[Fix Description]
    CoreCheck{Core Requirements?}
    FixCore[Fix Core Issues]
    SimplicityCheck{Simplicity Check?}
    FixSimplicity[Reduce Complexity]
    Complete([Prompt Finalized])

    Start --> Analyze
    Analyze --> Techniques
    Techniques --> Draft
    Draft --> HasTools
    HasTools -- "Yes" --> ToolDocs
    HasTools -- "No" --> SharpenAudit
    ToolDocs --> SharpenAudit
    SharpenAudit --> AmbigFound
    AmbigFound -- "CRITICAL/HIGH" --> SharpenImprove
    AmbigFound -- "None/LOW" --> IsSkill
    SharpenImprove --> SharpenAudit
    IsSkill -- "Yes" --> CSOCheck
    IsSkill -- "No" --> CoreCheck
    CSOCheck -- "Pass" --> CoreCheck
    CSOCheck -- "Fail" --> FixCSO
    FixCSO --> CSOCheck
    CoreCheck -- "Pass" --> SimplicityCheck
    CoreCheck -- "Fail" --> FixCore
    FixCore --> Draft
    SimplicityCheck -- "Pass" --> Complete
    SimplicityCheck -- "Fail" --> FixSimplicity
    FixSimplicity --> Draft

    style Start fill:#4CAF50,color:#fff
    style HasTools fill:#FF9800,color:#fff
    style AmbigFound fill:#FF9800,color:#fff
    style IsSkill fill:#FF9800,color:#fff
    style CSOCheck fill:#f44336,color:#fff
    style CoreCheck fill:#f44336,color:#fff
    style SimplicityCheck fill:#f44336,color:#fff
    style Techniques fill:#4CAF50,color:#fff
    style Draft fill:#4CAF50,color:#fff
    style ToolDocs fill:#4CAF50,color:#fff
    style SharpenAudit fill:#4CAF50,color:#fff
    style SharpenImprove fill:#4CAF50,color:#fff
    style Analyze fill:#2196F3,color:#fff
    style FixCSO fill:#2196F3,color:#fff
    style FixCore fill:#2196F3,color:#fff
    style FixSimplicity fill:#2196F3,color:#fff
    style Complete fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| Analyze Task & Audience | Lines 71, 47-53: Step 1 analyze task, reasoning schema |
| /ie-techniques/ | Lines 63, 72: 16 proven techniques reference |
| /ie-template/ | Lines 64, 73: Template and example for drafting |
| /ie-tool-docs/ | Lines 65, 74: Tool documentation guidance |
| /sharpen-audit/ | Lines 66, 75: Ambiguity detection |
| /sharpen-improve/ | Lines 67, 75: Ambiguity resolution |
| CSO Compliant? | Lines 80-101: Skill description CSO checklist |
| Core Requirements? | Lines 125-133: Persona, stimuli, few-shot checks |
| Simplicity Check? | Lines 135-138: Shortest prompt that achieves the goal |
