# Anti-AI Tone Rules

## Banned Phrases (grep-checkable)

These phrases MUST NOT appear in any generated documentation:

- "Let's dive in"
- "Let's get started"
- "It is important to note"
- "It's worth noting"
- "Simply"
- "Easily"
- "Just" (when minimizing difficulty)
- "In conclusion"
- "In summary"
- "In this guide, we will"
- "In this tutorial, we will"
- "Welcome to this guide"
- "Without further ado"
- "As you can see"
- "As mentioned earlier"
- "At the end of the day"
- "In today's world"
- "First and foremost"
- "Needless to say"
- "Last but not least"
- "Robust"
- "Powerful"
- "Elegant"
- "Seamless"
- "Cutting-edge"
- "Best-in-class"
- "Game-changing"
- "Leverage" (as verb meaning "use")
- "Utilize" (use "use" instead)
- "Facilitate"
- "Streamline"
- "Comprehensive" (when self-describing the doc)

## Voice Rules

1. **Active voice exclusively** for instructions: "Run the command" not "The command should be run"
2. **Condition before action**: "If you need X, run Y" not "Run Y if you need X"
3. **Imperative mood** for instructions: "Install the package" not "You should install the package"
4. **Consistent tense**: Present tense for descriptions, imperative for instructions. Never mix within a section.
5. **No hedging**: "This returns X" not "This should return X" or "This will typically return X"

## Cohesion Rules

1. **No info-dump**: Each section flows from the previous and sets up the next
2. **No orphan sections**: Every section is referenced by or references at least one other
3. **Consistent terminology**: Pick one term for each concept, use it everywhere. Define in a glossary if needed.
4. **Natural transitions**: Section endings connect to what comes next. No abrupt topic changes.
5. **Progressive complexity**: Simpler concepts before complex ones within each doc

## Code Comment Rules

1. Comments explain "why" not "what"
2. No comments that restate the code: `x = 5  # set x to 5`
3. Show the "wrong" way alongside the right way when instructive
4. Cross-references MUST be hyperlinks, never "see X" without a link
