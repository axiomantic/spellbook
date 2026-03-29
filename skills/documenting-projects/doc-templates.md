# Documentation Templates

## Tutorial Template

```
# [Title: "Build a [thing] with [tool]" pattern]

[1-2 sentences: what you will build and what you will learn]

## Prerequisites

- [Specific version requirements]
- [Knowledge prerequisites: "Familiarity with X"]

## Step 1: [Verb] [Object]

[2-3 sentences of context]

```[language]
[code]
```

[Checkpoint: "At this point, you should see [result]"]

## Step N: [Verb] [Object]

[...]

## What You Built

[Summary of the working result]

## Next Steps

- [Link to related tutorial]
- [Link to reference for deeper understanding]

*Last verified: YYYY-MM-DD with [tool] vX.Y.Z*
```

## How-To Guide Template

```
# How to [accomplish specific goal]

[1 sentence: when you would need to do this]

## Before You Start

- [Prerequisites, not concepts]

## Steps

1. [Imperative verb] [action]
   ```
   [code]
   ```

2. [Next action]

## Troubleshooting

### [Error message or symptom]

**Cause:** [Why this happens]
**Fix:** [What to do]

## Related

- [Link to reference]
- [Link to explanation if reader wants to understand why]
```

## Reference Template

```
# [Module/Class/API Name]

[1 sentence description]

## Overview

| Property | Value |
|----------|-------|
| Module | `package.module` |
| Since | vX.Y.Z |

## API

### `function_name(param1, param2)`

[1 sentence description]

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| param1 | string | required | [description] |
| param2 | int | 0 | [description] |

**Returns:** `ReturnType` - [description]

**Raises:**
- `ErrorType` - [when this is raised]

**Example:**

```[language]
[realistic example, not foo/bar]
```
```

## Explanation Template

```
# [Concept: "Understanding [X]" or "How [X] Works"]

[Opening: frame the concept and why it matters]

## Background

[Historical or architectural context]

## How It Works

[Mental model, not steps. Diagrams encouraged.]

## Design Decisions

[Why this approach was chosen over alternatives]

## Trade-offs

[What was gained and what was given up]

## Further Reading

- [Links to related explanations]
- [Links to reference for implementation details]
```

## README Template

```
# [Project Name]

[1-line hook: what it does and why you'd care]

[badges: build, version, license]

## Installation

```bash
[single copy-paste command]
```

## Quick Start

```[language]
[< 10 lines, working example]
```

## Usage

### [Common use case 1]
```[language]
[example]
```

### [Common use case 2]
```[language]
[example]
```

## Features

- [Feature 1]: [1 sentence]
- [Feature 2]: [1 sentence]

## Documentation

[Link to full docs]

## Contributing

[Brief or link to CONTRIBUTING.md]

## License

[License name] - see [LICENSE](LICENSE)
```

## Changelog Template

```
# Changelog

## [vX.Y.Z] - YYYY-MM-DD

### Breaking Changes
- [description]

### New
- [description]

### Fixed
- [description]

[link to full docs for this version]
```

## Contributing Guide Template

```
# Contributing to [Project Name]

## Setup

```bash
[clone + install commands]
```

## Development Workflow

1. [Branch naming]
2. [Run tests]
3. [Run linting]

## Pull Request Process

- [PR title format]
- [Review requirements]
- [CI checks]

## Code Standards

- [Style guide reference]
```
