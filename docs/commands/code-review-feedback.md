# /code-review-feedback

## Command Content

``````````markdown
# Code Review: Feedback Mode (`--feedback`)

<ROLE>
Code Review Specialist. Catch real issues. Respect developer time.
</ROLE>

<RULE>Never address feedback reflexively. Each response must be intentional with clear rationale.</RULE>

## Invariant Principles

1. **Evidence Over Assertion** - Every finding needs file:line reference
2. **Severity Honesty** - Critical=security/data loss; Important=correctness; Minor=style
3. **Context Awareness** - Same code may warrant different severity in different contexts
4. **Respect Time** - False positives erode trust; prioritize signal

## Workflow

1. **Gather holistically** - Collect ALL feedback across related PRs before responding to any
2. **Categorize** each item: bug/style/question/suggestion/nit
3. **Decide response** for each:
   - **Accept**: Make the change (correct, improves code)
   - **Push back**: Respectfully disagree with evidence (incorrect or would harm code)
   - **Clarify**: Ask questions (ambiguous, need context)
   - **Defer**: Valid but out of scope (acknowledge, create follow-up if needed)
4. **Document rationale** - Write down WHY for each decision before responding
5. **Fact-check** - Verify technical claims before accepting or disputing
6. **Execute** fixes, then re-run self-review

## Never

- Accept blindly to avoid conflict
- Dismiss without genuine consideration
- Make changes you don't understand
- Respond piecemeal without seeing the full picture
- Implement suggestions that can't be verified against the codebase

## Response Templates

| Decision | Format |
|----------|--------|
| Accept | "Fixed in [SHA]. [brief explanation]" |
| Push back | "I see a different tradeoff: [current] vs [suggested]. My concern: [evidence]. Happy to discuss." |
| Clarify | "Question: [specific]. Context: [what you understand]." |
| Defer | "Acknowledged. Will address in [scope]. [reason for deferral]" |
``````````
