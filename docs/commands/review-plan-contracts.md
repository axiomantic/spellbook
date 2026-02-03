# /review-plan-contracts

## Command Content

``````````markdown
# Phase 2: Interface Contract Audit

You are executing Phase 2 of the implementation plan review. This is the most critical phase.

## Invariant Principles

1. **Missing contract fields are critical defects** - Any interface without fully specified request, response, and error formats will produce incompatible code
2. **Shared types must have single source of truth** - Type definitions used across parallel tracks must be defined in one location, not duplicated
3. **Ambiguity is worse than absence** - A vaguely specified contract misleads more than a missing one; flag both but prioritize vagueness

<CRITICAL>
This is the most important phase. Parallel work FAILS when agents hallucinate incompatible interfaces.
</CRITICAL>

For EACH interface between parallel work:

```
Interface: [Component A] <-> [Component B]
Developed by: [Agent/Track A] and [Agent/Track B]

Contract location: [section/line or MISSING]
Request format: SPECIFIED / MISSING
Response format: SPECIFIED / MISSING
Error format: SPECIFIED / MISSING
Protocol (method/endpoint/auth): SPECIFIED / MISSING

If ANY missing: Flag as CRITICAL. Agents will produce incompatible code.
Required addition: [exact specification needed]
```

## Type/Schema Contracts

For each shared type or schema:

```
Type: [name]
Used by: [list components]
Defined where: [location or MISSING]

| Field | Type | Required | Default | Validation | Specified |
|-------|------|----------|---------|------------|-----------|
| | | | | | Y/N |

If incomplete: [what must be added]
```

## Event/Message Contracts

For each event or message between components:

```
Event: [name]
Publisher: [component]
Subscribers: [components]
Schema: SPECIFIED / MISSING
Ordering guarantees: SPECIFIED / MISSING
Delivery guarantees: SPECIFIED / MISSING
```

## File/Resource Contracts

For each shared file, directory, or resource:

```
Resource: [path or pattern]
Writers: [list components that write]
Readers: [list components that read]
Format: SPECIFIED / MISSING
Locking: NONE / ADVISORY / EXCLUSIVE / N/A
Merge strategy: OVERWRITE / APPEND / MERGE / N/A
Conflict resolution: SPECIFIED / MISSING

If ANY writer/reader conflict possible: Flag as CRITICAL.
Required addition: [exact specification needed]
```

## Deliverable

Populate the following sections of the review report:
- Interfaces: A total, B fully specified, C MISSING
- All CRITICAL findings for missing/incomplete contracts
- Specific remediation for each gap (exact specification needed)

Return your completed contract audit as structured output for the orchestrator.
``````````
