# Diataxis Framework Reference

## The Four Types

| Type | Orientation | User Need | Key Question |
|------|-------------|-----------|-------------|
| Tutorial | Learning | "Teach me" | "What do I need to learn?" |
| How-To Guide | Problem | "Help me do X" | "How do I accomplish X?" |
| Reference | Information | "Look up Y" | "What are the details of Y?" |
| Explanation | Understanding | "Help me understand" | "Why does Z work this way?" |

## Boundary Rules (What Belongs Where)

### Tutorial
- ALWAYS: guided, sequential, hands-on, complete working result
- NEVER: options, alternatives, edge cases, exhaustive coverage
- BOUNDARY: If you are listing alternatives, you left tutorial territory

### How-To Guide
- ALWAYS: goal-oriented, assumes knowledge, practical steps
- NEVER: teaching concepts, explaining why, comprehensive theory
- BOUNDARY: If you are explaining a concept, move it to Explanation

### Reference
- ALWAYS: factual, complete, structured (tables/lists), austere
- NEVER: tutorials disguised as reference, opinions, narrative
- BOUNDARY: If you are guiding the reader through steps, move it to Tutorial or How-To

### Explanation
- ALWAYS: conceptual, narrative, "why" focused, connects ideas
- NEVER: step-by-step instructions, exhaustive parameter lists
- BOUNDARY: If you are listing parameters, move it to Reference

## Mode Mixing Detector

A section is mode-mixed if it contains elements from 2+ types:
- Steps + parameter tables = Tutorial/Reference mix
- Concept explanation + "run this command" = Explanation/How-To mix
- "First, understand X" + "Then do Y" = Explanation/Tutorial mix

Resolution: Split into separate sections, each pure to one type.
Cross-reference between them with hyperlinks.
