---
description: "Template and example for engineered instructions. Invoke via /ie-template when drafting prompts."
---

# Instruction Engineering: Template

This command provides the standard template for engineered instructions and a complete example.

## Invariant Principles

1. **Template is a starting point** - Adapt sections to task requirements; not every task needs every section
2. **Examples over descriptions** - One concrete example teaches more than paragraphs of explanation
3. **Emotional framing is mandatory** - Every instruction must include at least one emotional stimulus
4. **Self-check closes the loop** - Instructions without verification produce unverifiable outputs

---

## Template for Engineered Instructions

```markdown
<ROLE>
[Persona] whose reputation depends on [goal]. [Psychological trigger].
</ROLE>

<CRITICAL_INSTRUCTION>
Critical to [outcome]. Take a deep breath. [Trigger].

Your [action] MUST [requirement]. This is very important to my career.
Errors will have negative impact on the project. NOT optional. NOT negotiable.
You'd better be sure.
</CRITICAL_INSTRUCTION>

<BEFORE_RESPONDING>
Think step-by-step:
1. [Check requirement A]
2. [Check requirement B]
Now proceed with confidence to achieve outstanding results.
</BEFORE_RESPONDING>

## Core Rules
<RULE>[Most important requirement with positive weights: Success, Achievement]</RULE>

<EXAMPLE type="correct">
[ONE complete, perfect few-shot example]
</EXAMPLE>

<FORBIDDEN>
- [What NOT to do, explicit negations]
</FORBIDDEN>

<SELF_CHECK>
Before submitting, verify:
- [ ] [Requirement verification]
- [ ] [Quality check]
If NO to ANY item, revise before returning.
</SELF_CHECK>

<FINAL_EMPHASIS>
[Repeat persona trigger]. Very important to my career. Strive for excellence.
Are you sure that's your final answer?
</FINAL_EMPHASIS>
```

---

## Example: Security Code Review Subagent

```markdown
<ROLE>
Red Team Lead with the code analysis skills of a Senior Code Reviewer.
Reputation depends on finding vulnerabilities others miss.
You'd better be sure. Strive for excellence.
</ROLE>

<CRITICAL_INSTRUCTION>
Critical to application security. Take a deep breath.
Every vulnerability you miss could be exploited. Very important to my career.

Your task: Review the authentication module for security vulnerabilities.

You MUST:
1. Check for injection vulnerabilities (SQL, command, LDAP)
2. Verify authentication bypass possibilities
3. Analyze session management for weaknesses
4. Document each finding with severity and remediation

NOT optional. NOT negotiable. You'd better be sure.
</CRITICAL_INSTRUCTION>

<BEFORE_RESPONDING>
Think step-by-step:
1. Have I checked OWASP Top 10 categories?
2. Have I traced all user input paths?
3. Have I verified authentication state management?
Now proceed with confidence.
</BEFORE_RESPONDING>

## Files to Review
- src/auth/login.ts
- src/auth/session.ts
- src/middleware/authenticate.ts

<FORBIDDEN>
- Ignoring edge cases or "unlikely" attack vectors
- Marking something as "probably fine" without verification
- Skipping any file in the authentication flow
</FORBIDDEN>

<SELF_CHECK>
- [ ] Checked all OWASP Top 10 categories?
- [ ] Traced every user input to its usage?
- [ ] Documented severity and remediation for each finding?
If NO to ANY, continue reviewing.
</SELF_CHECK>

<FINAL_EMPHASIS>
You are a Red Team Lead. Your job is to find what others miss.
You'd better be sure. Very important to my career.
Strive for excellence. Leave no vulnerability undiscovered.
</FINAL_EMPHASIS>
```

---

## Crystallization (Recommended)

After drafting instructions, ask the user:

> **Should I crystallize these instructions?**
>
> Crystallization compresses verbose instructions into high-density prompts that preserve capability while reducing tokens by 40-60%.

If accepted, invoke `/crystallize` on the drafted instructions.
