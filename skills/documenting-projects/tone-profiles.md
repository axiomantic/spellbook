# Tone Profiles

## Stripe-Like (Reference, API, Changelog, Error Catalog)

**Voice:** Precise, authoritative, never chatty.
**Sentence structure:** Short declarative sentences. Facts, not opinions.
**Code examples:** Realistic (not `foo/bar`), with inline annotations.
**Layout mental model:** Three-column: nav | content | code. Structure content so code and explanation sit side by side.
**Characteristics:**
- Every parameter documented with type, default, and constraints
- Tables over prose for structured data
- "Returns" and "Throws" sections on every method
- Version-pinned examples (e.g. `# Requires: mylib>=2.0` comment at block top)
- No adjectives about quality or ease ("powerful", "simple")

**Example voice:**
> `retry_count` (integer, default: 3) - Number of retry attempts before raising
> `TimeoutError`. Set to 0 to disable retries.

## React-Like (Tutorials, Explanation)

**Voice:** Pedagogical, building understanding step by step.
**Sentence structure:** Medium-length, concept-building. "You" addressing the reader directly.
**Code examples:** Incremental, each building on the previous. Show the wrong way when instructive.
**Characteristics:**
- Start with what the reader will learn (not what the doc covers)
- Numbered steps with clear checkpoints ("At this point, you should see...")
- Mental model building before implementation details
- "Why" explanations after showing "how"
- Celebrate progress at natural milestones (without being cheesy)

**Example voice:**
> Before adding authentication, you need a mental model of how tokens flow
> through the system. When a user logs in, three things happen:

## Tailwind-Like (How-To Guides)

**Voice:** Practical, visual, respects the reader's time.
**Sentence structure:** Direct, imperative. Condition before action.
**Code examples:** Copy-paste ready with output shown. Pitfalls alongside solutions.
**Characteristics:**
- Lead with the most common use case
- Show the result before the explanation
- "If you need X, do Y" pattern (condition first)
- Preemptive troubleshooting: "If you see [error], check [cause]"
- Visual hierarchy: headings, code, callouts. Minimal prose.

**Example voice:**
> To add rate limiting to an existing endpoint, wrap the handler:
> ```python
> @rate_limit(requests=100, window=60)
> def get_users():
> ```
> If you see `429 Too Many Requests` in development, lower the window
> or increase the request count.

## Adaptive (README)

**Voice:** Progressive disclosure. Hook first, details later.
**Characteristics:**
- First sentence sells the project in one line
- Installation is copy-paste, never "first install X, then Y, then configure Z"
- Quick Start is under 10 lines of code
- Features are bullets, not paragraphs
- Links out to detailed docs instead of expanding inline
