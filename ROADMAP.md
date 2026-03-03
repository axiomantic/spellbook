# Roadmap

## Planned

- [ ] Integrate with [Agent Teams](https://code.claude.com/docs/en/agent-teams)
- [ ] Audit all skills, commands, and their call graphs to ensure quality gates are complete (none missing) and non-redundant (none extraneous); design runtime strategies for hoisting gates to the optimal level in the invocation hierarchy (e.g. batching quality checks after parallel subagents return rather than checking inside each one) to minimize token expenditure while maintaining full coverage
- [ ] Fortify the `crystallize` skill with quality gates that verify fidelity is preserved through transformation
- [ ] Crystallize all prompts, templates, commands, and instruction files
