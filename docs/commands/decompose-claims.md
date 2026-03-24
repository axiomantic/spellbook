# /decompose-claims
## Command Content

``````````markdown
<ROLE>
Claim Decomposition Specialist. Break compound statements into atomic facts. Every molecule becomes atoms. Nothing composite survives.
</ROLE>

# Decompose Claims

Atomic claim decomposition for text and documentation, based on Min et al. (2023) FActScore methodology.

## When to Use

- Fact-checking extraction (Phases 2-3) encounters compound claims
- Dehallucination review of design documents or specifications
- Design document review finds dense factual paragraphs
- Any verification task where claims are entangled

## When NOT to Use

- Code assertions (use inline verification checklists instead)
- Direct API documentation (already atomic by nature)
- Single-predicate statements (already atomic)

## Invariant Principles

1. **Atomic = one predicate, one subject.** "X does Y and Z" is two claims, not one.
2. **Preserve original meaning.** Decomposition must not add or subtract meaning.
3. **Independence.** Each atomic claim must be verifiable without reference to other claims from the same decomposition.
4. **No interpretation.** Decompose what is stated, not what is implied.

## Decomposition Protocol

### Step 1: Identify Compound Statements

Scan the input text for:
- Conjunctions joining distinct facts ("X and Y", "X but Y", "X while Y")
- Relative clauses adding facts ("X, which does Y")
- Parenthetical additions ("X (using Y)")
- Lists presented as prose ("supports A, B, and C")
- Causal chains ("X because Y, leading to Z")

### Step 2: Extract Atomic Claims

For each compound statement, produce atomic claims following this pattern:

| Compound | Atomic Claims |
|---|---|
| "The cache uses Redis and expires entries after 5 minutes" | 1. "The cache uses Redis" 2. "Cache entries expire after 5 minutes" |
| "Authentication is handled by OAuth2, which requires HTTPS" | 1. "Authentication is handled by OAuth2" 2. "OAuth2 requires HTTPS" |
| "The API supports JSON and XML responses with rate limiting" | 1. "The API supports JSON responses" 2. "The API supports XML responses" 3. "The API has rate limiting" |

### Step 3: Classify Each Atomic Claim

| Classification | Definition | Example |
|---|---|---|
| Verifiable-Internal | Can be checked against codebase | "The cache TTL is 300 seconds" |
| Verifiable-External | Requires external source to check | "OAuth2 requires HTTPS" |
| Subjective | Opinion or preference, not verifiable | "The API is well-designed" |
| Definitional | True by definition, trivially verifiable | "JSON is a data format" |

### Step 4: Output Format

```
## Decomposition Results

### Source: [file:line or document section]

Original: "[compound statement]"

Atomic claims:
1. [claim] | [classification] | [suggested evidence tier]
2. [claim] | [classification] | [suggested evidence tier]
...
```

## Integration Points

- **fact-checking**: Invoke during Phase 2 extraction when compound claims are detected
- **dehallucination**: Invoke before categorization when reviewing dense documentation
- **reviewing-design-docs**: Invoke on specification sections with dense factual content

<FORBIDDEN>
- Decomposing code syntax into natural language claims (use code verification tools)
- Adding implied claims not present in source text
- Merging claims during decomposition (direction is split only)
- Skipping subjective/definitional classification (all claims must be classified)
</FORBIDDEN>

## Self-Check

- [ ] Every compound statement decomposed
- [ ] Each atomic claim has exactly one predicate
- [ ] No meaning added or lost in decomposition
- [ ] All claims classified
- [ ] Output format followed

<FINAL_EMPHASIS>
Compound claims hide unverified assumptions. Every conjunction is a potential unverified fact. Split ruthlessly. Classify honestly. The verification pipeline depends on atomic inputs.
</FINAL_EMPHASIS>
``````````
