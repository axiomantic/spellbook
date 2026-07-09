---
name: writing-copy
description: >
  Use when writing or de-slopping outward-facing prose: newsletters, blog posts,
  announcements, marketing or landing copy, emails, release notes, doc intros.
  Triggers: 'make this sound human', 'this reads like AI', 'de-slop this',
  'remove the AI tells', 'make it less AI', 'why does this sound like ChatGPT',
  'help me draft this piece', 'write a newsletter', 'write a blog post', 'polish
  this copy', 'tighten this'. Composes with a personal voice skill (for example
  my-voice-skill) that supplies identity and register; this skill is voice-neutral
  and supplies the writing process plus the anti-slop catalog. NOT for: code logic
  or code review (use code-review), project doc structure (use documenting-projects),
  READMEs (use write-readme / polish-repo), or a specific person's voice (use their
  voice skill).
---

# Writing Copy

## Overview

A voice-neutral guide for writing outward-facing prose that reads like a human wrote
it, not an AI. It does two things: it runs the writing PROCESS (turn rough thoughts
into a grounded draft), and it strips AI TELLS (the finite, nameable set of moves
that make text read as generated).

It deliberately does NOT supply a person's identity. If the author has a personal
voice skill (for example `my-voice-skill`), load that too: the voice skill owns who
the author is (register, code-switch, signature phrasings), this skill owns process
and slop removal. Core principle: AI slop is a bounded catalog of tells. Name them,
cut them, and ground every claim in a concrete specific, and the prose reads human.

## When to Use

- Drafting or editing any outward-facing prose: newsletter, blog post, announcement,
  marketing copy, email, release notes, a doc's intro paragraph.
- A draft "sounds like AI" and you cannot say why. The catalog below names why.
- Turning a braindump or bullet notes into a finished piece.

When NOT to use:
- Code, code review, or technical logic (the tells here are prose tells).
- Reproducing a specific person's voice with no slop concern: load their voice skill.
- Neutral machine-facing text where human texture is irrelevant.

## The process

Writing well with AI is not one button. It is a loop that keeps the thoughts the
author's and the voice the author's.

1. **Braindump first.** Start from the author's raw notes: topic, audience, and loose
   bullets. If they are missing, ask for them. Do not invent the argument.
2. **Be a thought partner, not a ghostwriter.** Before drafting, ask sharpening
   questions. Notice when the notes hide two or three different pieces. Reflect back
   the possible shapes; let the author pick. The main point is discovered here, not
   invented by you.
3. **Draft against known taste.** Write the draft, then run the AI-tell catalog on
   your own output before showing it. Ground each claim in a concrete specific.
4. **Hand over for a human edit pass.** The author decides what sounds right. Your
   draft is a starting point, not the finished piece.

## The AI-tell catalog

Each entry: the tell, then a before -> after. These are voice-neutral; a personal
voice skill may add more.

**Vague, effort-theater, and jargon phrasings (say the concrete thing).** The
biggest tell, and the one humans rarely produce: filler that sounds like effort or a
rating but names nothing. Cut "I went deep", "did a deep dive", "really dug into",
"top box rating", "best-in-class", "move the needle", "at the end of the day", "when
it comes to", "in terms of", "it's important to note", "a lot to unpack", "in today's
world". Replace with the specific action, number, or behavior.
- "We went deep on performance." -> "We cut p95 latency from 800ms to 210ms."
- "It performs well." -> "It hallucinated once in about 200 runs, and obviously."

**Overclaimed confidence (intensifier adverbs).** Cut genuinely, truly, really,
actually (for emphasis), very, quite, literally. They push a claim harder than the
observation supports. Calibrated hedges that name real uncertainty ("I think",
"probably", "seems like") are fine and stay.
- "This is genuinely the right tool." -> "This feels like the right tool, because..."

**Rhetorical compression moves.** AI reaches for rhythm over information.
- X-not-Y: "it isn't a rewrite, it's a refactor" -> "it's a refactor. No behavior
  changes." (Hot zone: opening sentences.)
- Rule-of-three tricolons: "no install, no new tab, no new habit" -> one plain clause.
- Quantified punchline: "three bullets instead of fifteen" -> plain description.
- Comparative tail-end: cut "more X than anything else I use" from "than" onward.
- Manufactured punchline ending: a closing line tighter and punchier than the
  paragraph ("The discipline isn't free.") -> end on the plain sentence before it.
- Section-opener signpost: "A few things to flag:" -> open with the content.

**Metaphor-loaded verbs and nouns.** "becomes load-bearing", "users route around it",
"unlock", "double down", "lean into", "supercharge". Use the plain verb.
- "This becomes load-bearing." -> "This is now required."
- "Users route around the feature." -> "Users ignore the feature."

**Formatting tells.**
- Em-dashes (the easiest tell to leave behind). Use parentheses, comma clauses, a
  hyphen with spaces ( - ), or two sentences.
- Emoji-prefixed headers ("BREAKING"), over-bulleting that enumerates everything,
  "Sources:" citation blocks, relentless positivity. Cut or flatten to prose.

## Ground every claim in the concrete

The positive rule behind half the catalog. When you assert something works or fails,
attach a number or a specific behavior, not an adjective.
- Not "it works pretty well" but "it has failed once in a couple hundred runs".
- Not "it wasn't reliable" but "scheduled jobs failed and it hallucinated URLs".
Prefer observable behavior over abstract characterization. A coined label is fine if
you anchor it with concrete detail in the same sentence.

## Layering with a personal voice skill

This skill is neutral; a person's voice is not. If a voice skill exists for the
author, load both:
- Voice skill: identity, register, code-switch by audience, signature phrasings.
- This skill: the process and the universal anti-slop catalog.

On conflict, the voice skill wins on voice and register; this skill wins on slop
removal. A voice skill should inherit this catalog rather than restate it, and add
only the person-specific tells and preferences on top.

## The refinement loop (keep this guide alive)

The catalog gets better by learning from real human edits. After the author edits
your draft:
1. Put three things side by side: your draft, the author's edit, and this skill (or
   their voice skill).
2. Classify each change: one-off wording, or a repeatable rule the guide is missing?
3. For repeatable ones, propose a MINIMAL addition (a new tell, a tightened rule, a
   before -> after pair), grounded in the actual edit.
4. The author accepts or rejects. Only write accepted changes.
Naming what-not-to-do is how tacit taste becomes an explicit, reusable rule. Do not
invent rules the author did not demonstrate.

## Quick reference

| Tell | Fix |
|---|---|
| "I went deep", "top box rating", "move the needle" | Name the concrete action / number / behavior |
| genuinely, truly, really, very | Cut the intensifier; keep calibrated hedges |
| "isn't X, it's Y" | One plain statement |
| rule-of-three, quantified punchline | One plain clause |
| manufactured punchline ending | End on the plain sentence before |
| "A few things to flag:" | Open with the content |
| load-bearing, route around, unlock | Plain verb |
| em-dash | Parens, hyphen with spaces, or split |

## Common mistakes

- Deleting a punchy line but not replacing it. The strongest fix names what is
  actually happening (the mechanism), not just a shorter version of the slogan.
- Over-hedging to sound human. Softening every claim is its own tell; cut intensifiers,
  do not add mush. Keep only hedges that name real uncertainty.
- Restating a personal voice skill's rules here. This skill stays neutral; person-
  specific taste lives in the voice skill.
- Inventing the argument. The thoughts are the author's; you sharpen and draft, you do
  not supply the point.
