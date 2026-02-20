<!-- diagram-meta: {"source": "commands/simplify-analyze.md", "source_hash": "sha256:1c3f807263d035109daa49e3243d660e592cba4b2d7117a5ac670b306680d452", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: simplify-analyze

Analyze code for cognitive complexity and identify simplification opportunities. Covers mode selection, discovery, and analysis phases.

```mermaid
flowchart TD
    Start([Start]) --> ParseArgs["Parse Command\nArguments"]
    ParseArgs --> ScopeDecision{"Targeting Mode?"}
    ScopeDecision -->|Branch| BranchDiff["Git Diff Against\nMerge Base"]
    ScopeDecision -->|File/Dir| ExplicitScope["Parse Explicit\nScope"]
    ScopeDecision -->|--staged| StagedDiff["Git Staged\nChanges"]
    ScopeDecision -->|--repo| RepoConfirm{"Confirm Repo\nWide Scan?"}
    ScopeDecision -->|--function| FuncTarget["Target Specific\nFunction"]
    RepoConfirm -->|No| ParseArgs
    RepoConfirm -->|Yes| AllFiles["Find All Source\nFiles"]
    BranchDiff --> ModeSelect{"Select Mode?"}
    ExplicitScope --> ModeSelect
    StagedDiff --> ModeSelect
    AllFiles --> ModeSelect
    FuncTarget --> ModeSelect
    ModeSelect -->|Automated| SetAuto["Set Automated"]
    ModeSelect -->|Wizard| SetWizard["Set Wizard"]
    ModeSelect -->|Report Only| SetReport["Set Report Only"]
    SetAuto --> Discovery["Step 2: Discovery"]
    SetWizard --> Discovery
    SetReport --> Discovery
    Discovery --> IdentifyFuncs["Identify Changed\nFunctions"]
    IdentifyFuncs --> CalcComplexity["Calculate Cognitive\nComplexity"]
    CalcComplexity --> DetectLang["Detect Language\nPatterns"]
    DetectLang --> FilterThreshold{"Meets Min\nComplexity?"}
    FilterThreshold -->|No| SkipFunc["Skip Function"]
    FilterThreshold -->|Yes| CoverageCheck{"Has Test\nCoverage?"}
    CoverageCheck -->|No + no flag| SkipNoCov["Skip: No Coverage"]
    CoverageCheck -->|Yes or --allow| Analysis["Step 3: Analysis"]
    SkipFunc --> NextFunc{"More Functions?"}
    SkipNoCov --> NextFunc
    NextFunc -->|Yes| IdentifyFuncs
    NextFunc -->|No| Analysis
    Analysis --> ScanPatterns["Scan Pattern\nCatalog"]
    ScanPatterns --> CatA["Cat A: Control Flow"]
    ScanPatterns --> CatB["Cat B: Boolean Logic"]
    ScanPatterns --> CatC["Cat C: Pipelines"]
    ScanPatterns --> CatD["Cat D: Modern Idioms"]
    ScanPatterns --> CatE["Cat E: Dead Code"]
    CatA --> RankSimplify["Rank by Impact\nand Risk"]
    CatB --> RankSimplify
    CatC --> RankSimplify
    CatD --> RankSimplify
    CatE --> RankSimplify
    RankSimplify --> Output([Ranked Candidates\n+ SESSION_STATE])

    style Start fill:#4CAF50,color:#fff
    style Output fill:#4CAF50,color:#fff
    style ParseArgs fill:#2196F3,color:#fff
    style BranchDiff fill:#2196F3,color:#fff
    style ExplicitScope fill:#2196F3,color:#fff
    style StagedDiff fill:#2196F3,color:#fff
    style AllFiles fill:#2196F3,color:#fff
    style FuncTarget fill:#2196F3,color:#fff
    style SetAuto fill:#2196F3,color:#fff
    style SetWizard fill:#2196F3,color:#fff
    style SetReport fill:#2196F3,color:#fff
    style Discovery fill:#2196F3,color:#fff
    style IdentifyFuncs fill:#2196F3,color:#fff
    style CalcComplexity fill:#2196F3,color:#fff
    style DetectLang fill:#2196F3,color:#fff
    style SkipFunc fill:#2196F3,color:#fff
    style SkipNoCov fill:#2196F3,color:#fff
    style Analysis fill:#2196F3,color:#fff
    style ScanPatterns fill:#2196F3,color:#fff
    style CatA fill:#2196F3,color:#fff
    style CatB fill:#2196F3,color:#fff
    style CatC fill:#2196F3,color:#fff
    style CatD fill:#2196F3,color:#fff
    style CatE fill:#2196F3,color:#fff
    style RankSimplify fill:#2196F3,color:#fff
    style ScopeDecision fill:#FF9800,color:#fff
    style RepoConfirm fill:#FF9800,color:#fff
    style ModeSelect fill:#FF9800,color:#fff
    style NextFunc fill:#FF9800,color:#fff
    style FilterThreshold fill:#f44336,color:#fff
    style CoverageCheck fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
