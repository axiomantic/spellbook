<!-- diagram-meta: {"source": "commands/execute-work-packets-seq.md", "source_hash": "sha256:f443576862b20f62e1fcb11ae118315eb81b61fee6d213f5ef3b9907f569f058", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: execute-work-packets-seq

Execute all work packets in dependency order, one at a time, with context compaction between tracks.

```mermaid
flowchart TD
    Start([Start]) --> S1[Step 1: Load Manifest]
    S1 --> ValidateManifest{Manifest Valid?}
    ValidateManifest -->|No| AbortManifest([Abort: Bad Manifest])
    ValidateManifest -->|Yes| S2[Step 2: Topological Sort]
    S2 --> CycleCheck{Circular Deps?}
    CycleCheck -->|Yes| AbortCycle([Abort: Cycle Detected])
    CycleCheck -->|No| S3[Step 3: Execution Loop]
    S3 --> NextTrack[Select Next Track]
    NextTrack --> AlreadyDone{Completion Marker?}
    AlreadyDone -->|Yes| SkipTrack[Skip: Already Complete]
    SkipTrack --> MoreTracks
    AlreadyDone -->|No| ExecPacket[/execute-work-packet/]
    ExecPacket --> TrackPass{Track Passed?}
    TrackPass -->|No| HaltSeq([Halt: Track Failed])
    TrackPass -->|Yes| VerifyMarker{Marker Exists?}
    VerifyMarker -->|No| MarkerError([Error: No Marker])
    VerifyMarker -->|Yes| S4[Step 4: Context Compaction]
    S4 --> Compact{User Compacts?}
    Compact -->|Yes| Handoff[/handoff/]
    Compact -->|No| Progress
    Handoff --> Progress
    Progress --> S5[Step 5: Display Progress]
    S5 --> MoreTracks{More Tracks?}
    MoreTracks -->|Yes| NextTrack
    MoreTracks -->|No| S6[Step 6: Verify All Complete]
    S6 --> AllComplete{All Markers Present?}
    AllComplete -->|No| ReportMissing[Report Incomplete]
    ReportMissing --> HaltSeq
    AllComplete -->|Yes| S7[Step 7: Suggest Merge]
    S7 --> Done([End])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style AbortManifest fill:#4CAF50,color:#fff
    style AbortCycle fill:#4CAF50,color:#fff
    style HaltSeq fill:#4CAF50,color:#fff
    style MarkerError fill:#4CAF50,color:#fff
    style ExecPacket fill:#4CAF50,color:#fff
    style Handoff fill:#4CAF50,color:#fff
    style ValidateManifest fill:#FF9800,color:#fff
    style CycleCheck fill:#FF9800,color:#fff
    style AlreadyDone fill:#FF9800,color:#fff
    style Compact fill:#FF9800,color:#fff
    style MoreTracks fill:#FF9800,color:#fff
    style TrackPass fill:#f44336,color:#fff
    style VerifyMarker fill:#f44336,color:#fff
    style AllComplete fill:#f44336,color:#fff
    style S1 fill:#2196F3,color:#fff
    style S2 fill:#2196F3,color:#fff
    style S3 fill:#2196F3,color:#fff
    style S4 fill:#2196F3,color:#fff
    style S5 fill:#2196F3,color:#fff
    style S6 fill:#2196F3,color:#fff
    style S7 fill:#2196F3,color:#fff
    style NextTrack fill:#2196F3,color:#fff
    style SkipTrack fill:#2196F3,color:#fff
    style Progress fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
