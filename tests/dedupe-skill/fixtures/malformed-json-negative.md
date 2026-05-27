# Malformed JSON Negative Control Fixture

This fixture deliberately contains malformed JSON inside fenced ` ```json `
blocks. D4 (`verify-json-blocks.sh`) MUST flag every block as a parse
failure. If D4 silently passes against this fixture, the gate is gutted
and the paired negative-control script (`verify-json-blocks-neg.sh`) will
fail loudly.

## Block 1 — trailing comma

```json
{
  "verdict": "duplicate",
  "confidence": 0.92,
}
```

## Block 2 — unclosed brace

```json
{
  "segments": [
    {"id": "a"},
    {"id": "b"}
  ]
```

## Block 3 — single-quoted strings (not valid JSON)

```json
{
  'verdict': 'unique',
  'confidence': 0.10
}
```
