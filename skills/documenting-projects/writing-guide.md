# Writing Guide

## Dead Tells

Patterns that immediately out writing as AI-generated. These are not just about individual words;
the structural habits are harder to catch and more damaging than any single banned phrase.

### Banned Phrases

These MUST NOT appear in any generated documentation:

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

### Structural Dead Tells

These are the patterns that survive even after you strip the banned phrases. They're about
the shape and rhythm of the writing, not the vocabulary.

1. **Performative punchiness.** Short sentence. Alone on a line. For impact. Every sentence is
   trying to be a pull quote. If you find yourself writing a one-sentence paragraph that's meant
   to "land," rewrite it as part of the surrounding paragraph.

2. **Relentless parallelism.** Every list item has the exact same grammatical structure, the exact
   same length, the exact same cadence. Real humans vary their rhythm, sometimes awkwardly.

3. **Mic-drop positioning.** A short declarative sentence placed after a longer explanation, always
   as the "landing" moment. Real writing doesn't stick the landing every time.

4. **Copywriter compression.** Cramming an idea into the fewest possible words not because it's
   clearer but because it sounds punchier. "No fixtures. Import and go." sounds like ad copy.
   The slightly wordier version is often more natural to read.

5. **The triple structure.** "X, Y, and Z" repeated across bullet points or sentences where each
   list has exactly three items. LLMs are drawn to threes like moths to light.

6. **Bolded phrase followed by colon as a sentence opener.** "**The key insight:** tripwire forces
   you to..." Humans write topic sentences; they don't label them.

7. **Uniform paragraph length.** Real writing has short paragraphs and long paragraphs. When every
   paragraph is roughly the same size, it reads like it was generated to fill a template.

8. **Overuse of "Not X, but Y."** "Not just a linter, but a full verification system." Once in a
   doc, fine. LLMs reach for this construction constantly.

9. **Superlative framing of mundane features.** Making everything sound like a breakthrough when
   you're just explaining how something works.

10. **Trailing summary sentences.** Ending a section by restating what the section just said. The
    reader just read the section. They know.

11. **The false choice.** "You can either write flaky tests with X, or use Y for full certainty."
    Framing everything as a binary where the reader would be dumb to pick the other option.

12. **Relentless confidence.** Never hedging, never saying "usually" or "in most cases" even when
    that would be more honest. Everything stated as absolute.

13. **Summarize-then-restate.** Saying the same thing twice in slightly different words for emphasis.
    Humans say it once and move on.

## Human Signals

Patterns that make writing feel like it came from someone who actually thinks about what they're
saying. These aren't rules to mechanically apply; they're characteristics of writing that sounds
like a person.

1. **Uneven sentence length.** A long sentence followed by a medium one followed by another long one.
   Not the short-long-short pattern that reads like copywriting. Real paragraphs don't have rhythm
   sections.

2. **Explaining the long way around when it's natural.** "tripwire doesn't use fixtures, so you don't
   need to set up any special test infrastructure" is wordier than "No fixtures needed" but it sounds
   like a person talking.

3. **Subordinate clauses.** "Since tripwire already intercepts calls at the session level, you don't
   need to do anything special per-test" rather than splitting into two sentences. Humans connect
   ideas within sentences. LLMs love to split them apart.

4. **Occasional imprecision.** "Most of the time" instead of always stating things as absolutes. Not
   hedging for the sake of hedging, but acknowledging when something is genuinely "usually" rather
   than "always."

5. **Letting information just be information.** Not every fact needs to land. Sometimes you're just
   telling someone how something works and it doesn't need to be impressive.

6. **Transitions that sound like thinking.** "The other thing worth knowing is" or "There's a
   subtlety here" rather than perfectly structured topic-sentence-first paragraphs. Real writing
   sometimes arrives at the point mid-paragraph.

7. **Specificity over abstraction.** "tripwire will show you the exact URL, headers, and status code"
   rather than "tripwire provides full observability into every interaction." The concrete version is
   longer but sounds like someone who actually uses the tool wrote it.

8. **Second person where it fits.** "If you forget to assert a call, you'll see this error" rather
   than "Unasserted calls produce errors at teardown." Someone is talking to you, not writing a spec.

9. **Casual connectives.** "Actually," "By the way," or "This gets interesting when."
   Not every transition needs to be a heading or a bold phrase.

10. **Parenthetical asides.** "(you'll probably want this for CI)" or "(this is the one most people
    start with)." Parentheticals are a very human way of adding context without breaking flow.

11. **Admitting limitations or tradeoffs.** "This adds some overhead to test startup" or "The error
    messages can be verbose, but they show you everything you need." LLMs almost never voluntarily
    mention downsides of the thing they're describing.

12. **Referring forward loosely.** "We'll get to the plugin system in a minute" rather than a
    perfectly structured cross-reference. Feels like someone writing in order of their thinking.

13. **Varying sentence openers.** LLMs love to start consecutive sentences with the subject. Real
    writing starts with "If," "When," "Since," "Because," prepositional phrases, dependent clauses.

14. **Opinions.** "The warn mode is probably the right starting point for most teams" rather than
    presenting every option as equally valid. Someone who built or uses the tool has opinions about it.

## Voice Rules

1. **Active voice exclusively** for instructions: "Run the command" not "The command should be run"
2. **Condition before action**: "If you need X, run Y" not "Run Y if you need X"
3. **Imperative mood** for instructions: "Install the package" not "You should install the package"
4. **Consistent tense**: Present tense for descriptions, imperative for instructions. Never mix within a section.
5. **No hedging on facts**: "This returns X" not "This should return X" or "This will typically return X"
   (But DO hedge on recommendations and generalizations when honesty calls for it. See Human Signals #4.)

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

## Sniff Test

Mechanical checks to run against a finished draft. If you're failing several of these, the writing
probably needs another pass.

1. **Paragraph openers.** Read the first sentence of each paragraph. Are more than half starting with
   the subject noun? Vary them.
2. **Paragraph length.** Are all paragraphs within one or two sentences of each other? Mix it up.
3. **Standalone sentences.** How many sentences sit alone as their own paragraph? More than one or two
   in the whole doc is a smell.
4. **List item structure.** Do all items in a list follow the exact same grammatical template? Break
   the pattern on at least one.
5. **Section endings.** Does the last sentence of each section restate the section's point? Cut it.
6. **Bold usage.** Is every other phrase bolded? Bold loses its emphasis when everything is emphasized.
7. **Read it out loud.** Does it sound like something you'd say to a coworker, or something you'd
   hear in a product launch keynote? Aim for the coworker.

## Before and After

### Example 1: Feature description

**Dead tell version:**
> No fixture injection required. Install tripwire, `import tripwire`, and go.

**Human version:**
> tripwire doesn't use fixtures. You just import it and use it directly in your test functions.

### Example 2: Selling a feature

**Dead tell version:**
> **Firewall mode** (enabled by default) goes further: tripwire installs interceptors at test session
> startup, catching any real I/O call that happens outside a sandbox.

**Human version:**
> Firewall mode is on by default. When your test session starts, tripwire installs interceptors that
> catch any real I/O call happening outside a sandbox.

### Example 3: The mic drop

**Dead tell version:**
> `unittest.mock` makes it your responsibility to remember what to assert. tripwire makes it
> impossible to forget.

**Human version:**
> With `unittest.mock`, it's on you to remember to assert every call and verify every argument.
> tripwire doesn't give you that option. If you forget to assert something, the test fails.

### Example 4: Short punchy closer

**Dead tell version:**
> Every field is shown. Every value is real. Copy, paste, done.

**Human version:**
> The error output shows every field with its actual value, so you can usually just copy it into
> your test as the assertion.

## Context

These principles apply across all documentation types, but the degree varies:

- **README:** The most important place to get this right, since it's the first thing people read.
   Avoid sales language entirely. A README should sound like a knowledgeable person explaining
   what the project does and how to use it.
- **API reference / changelog:** Can be terse and declarative. Dead tells are less of a problem
   here because the format is naturally structured. But still avoid superlative framing.
- **Tutorials:** Most conversational. Human signals should be strongest here since you're walking
   someone through something step by step. Parenthetical asides, opinions, and forward references
   all fit naturally.
- **How-to guides:** Practical and direct. Less room for conversational warmth, but still avoid
   copywriter compression. Let instructions breathe.
