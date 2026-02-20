<!-- diagram-meta: {"source": "commands/writing-commands-create.md", "source_hash": "sha256:8fb89918d4164547b5d4b246ff6162e5572395db6f21ae164066692e01656893", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: writing-commands-create

Create a new command file following the command schema. Applies file naming conventions, YAML frontmatter, required sections (MISSION, ROLE, Invariant Principles, execution steps, Output, FORBIDDEN, analysis, reflection), and token efficiency targets.

```mermaid
flowchart TD
  Start([Start]) --> ChooseName[Choose imperative\nverb-noun name]
  ChooseName --> CreateFile[Create commands/name.md]
  CreateFile --> WriteFrontmatter[Write YAML frontmatter\nwith description]
  WriteFrontmatter --> FMCheck{Description < 1024\nchars with triggers?}
  FMCheck -- No --> FixFM[Fix frontmatter]
  FixFM --> FMCheck
  FMCheck -- Yes --> WriteMission[Write MISSION section]
  WriteMission --> WriteRole[Write ROLE tag\nwith stakes]
  WriteRole --> WriteInvariants[Write Invariant\nPrinciples 3-5]
  WriteInvariants --> WriteExecution[Write execution\nsteps/phases]
  WriteExecution --> WriteOutput[Write Output section]
  WriteOutput --> WriteForbidden[Write FORBIDDEN\nsection]
  WriteForbidden --> WriteAnalysis[Write analysis tag]
  WriteAnalysis --> WriteReflection[Write reflection tag]
  WriteReflection --> TokenCheck{Within token\nlimits?}
  TokenCheck -- No --> Compress[Compress: tables\nover prose]
  Compress --> TokenCheck
  TokenCheck -- Yes --> StructureReview{All required\nsections present?}
  StructureReview -- No --> AddMissing[Add missing sections]
  AddMissing --> StructureReview
  StructureReview -- Yes --> Done([Done])

  style Start fill:#4CAF50,color:#fff
  style Done fill:#4CAF50,color:#fff
  style FMCheck fill:#f44336,color:#fff
  style TokenCheck fill:#f44336,color:#fff
  style StructureReview fill:#f44336,color:#fff
  style ChooseName fill:#2196F3,color:#fff
  style CreateFile fill:#2196F3,color:#fff
  style WriteFrontmatter fill:#2196F3,color:#fff
  style FixFM fill:#2196F3,color:#fff
  style WriteMission fill:#2196F3,color:#fff
  style WriteRole fill:#2196F3,color:#fff
  style WriteInvariants fill:#2196F3,color:#fff
  style WriteExecution fill:#2196F3,color:#fff
  style WriteOutput fill:#2196F3,color:#fff
  style WriteForbidden fill:#2196F3,color:#fff
  style WriteAnalysis fill:#2196F3,color:#fff
  style WriteReflection fill:#2196F3,color:#fff
  style Compress fill:#2196F3,color:#fff
  style AddMissing fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
