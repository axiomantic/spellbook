# Research Citations

This page documents the research that informs spellbook's design, particularly the [fun-mode](../skills/fun-mode.md) and [emotional-stakes](../skills/emotional-stakes.md) skills.

## Creativity and Seed-Conditioning

**Raghunathan, A., et al.** (2025). Rethinking LLM Pre-training. *International Conference on Machine Learning (ICML 2025)*.

- **Link**: [https://www.cs.cmu.edu/~aditirag/icml2025.html](https://www.cs.cmu.edu/~aditirag/icml2025.html)
- **Key finding**: Training with random prefix strings ("seeds") improves algorithmic creativity. These meaningless prefixes condition the model on a single latent "leap of thought," sometimes outperforming temperature sampling for creative tasks.
- **Relevance**: Fun mode's random personas act as semantic seeds that steer generation toward diverse solution pathways.

## Persona Effects on Reasoning

**Tan, F. A., et al.** (2024). PHAnToM: Persona-based Prompting Has An Effect on Theory-of-Mind Reasoning in Large Language Models. *arXiv preprint arXiv:2403.02246*.

- **Link**: [https://arxiv.org/abs/2403.02246](https://arxiv.org/abs/2403.02246)
- **Key finding**: Personas significantly affect Theory of Mind (ToM) reasoning. Dark Triad personality traits have larger effects than Big Five traits. Models with higher variance across personas are more "controllable."
- **Relevance**: Personas enhance social-cognitive reasoning, which is relevant to creative dialogue and collaboration.

**Park, J. S., et al.** (2023). Generative Agents: Interactive Simulacra of Human Behavior. *36th Annual ACM Symposium on User Interface Software and Technology (UIST '23)*.

- **Link**: [https://arxiv.org/abs/2304.03442](https://arxiv.org/abs/2304.03442)
- **Key finding**: Memory-augmented persona architectures enable emergent social behaviors. Agents in the "Smallville" simulation autonomously coordinated complex social events while maintaining consistent personalities.
- **Relevance**: Demonstrates that persona consistency improves believability and emergent creative behaviors.

## Emotional Prompts

**Li, C., et al.** (2023). Large Language Models Understand and Can be Enhanced by Emotional Stimuli. *arXiv preprint arXiv:2307.11760*.

- **Link**: [https://arxiv.org/abs/2307.11760](https://arxiv.org/abs/2307.11760)
- **Key finding**: Emotional prompts ("This is important to my career") improve LLM performance by 8% on Instruction Induction and 115% on BIG-Bench tasks.
- **Relevance**: Emotional-stakes skill uses emotional framing to improve accuracy on critical tasks.

**Wang, X., et al.** (2024). NegativePrompt: Leveraging Psychology for Large Language Models Enhancement via Negative Emotional Stimuli. *International Joint Conference on Artificial Intelligence (IJCAI 2024)*.

- **Link**: [https://www.ijcai.org/proceedings/2024/719](https://www.ijcai.org/proceedings/2024/719)
- **Key finding**: Negative emotional stimuli ("If you fail, there will be consequences") improve performance by 12.89% on Instruction Induction and 46.25% on BIG-Bench.
- **Relevance**: Consequence framing in emotional-stakes improves truthfulness and accuracy.

## Theoretical Foundations

**Janus.** (2022). Simulators. *LessWrong*.

- **Link**: [https://www.lesswrong.com/posts/vJFdjigzmcXMhNTsx/simulators](https://www.lesswrong.com/posts/vJFdjigzmcXMhNTsx/simulators)
- **Key finding**: LLMs should be understood as "simulators" that can model any agent from their training data. Personas act as conditioning that steers generation to specific latent space regions corresponding to that agent type.
- **Relevance**: Theoretical foundation for why personas affect output quality differently across domains.

## Important Limitations

**Zheng, M., et al.** (2023). When "A Helpful Assistant" Is Not Really Helpful: Personas in System Prompts Do Not Improve Performances of Large Language Models. *arXiv preprint arXiv:2311.10054*.

- **Link**: [https://arxiv.org/abs/2311.10054](https://arxiv.org/abs/2311.10054)
- **Key finding**: Across 162 personas and 2410 factual questions (MMLU), personas do not improve performance on objective tasks compared to neutral prompts. Effects are inconsistent and sometimes negative.
- **Relevance**: **Critical caveat** - fun mode explicitly restricts personas to dialogue, never affecting code, commits, or documentation. Personas help creative/social tasks, not factual/STEM tasks.

**Gupta, S., et al.** (2024). Bias Runs Deep: Implicit Reasoning Biases in Persona-Assigned LLMs. *International Conference on Learning Representations (ICLR 2024)*.

- **Key finding**: Persona-assigned LLMs can exhibit implicit reasoning biases that affect downstream task performance.
- **Relevance**: Additional support for restricting personas to non-critical outputs.

## Additional Reading

**Kong, A., et al.** (2024). Better Zero-Shot Reasoning with Role-Play Prompting. *Proceedings of NAACL 2024*, pages 4099-4113.

- Role-play prompting can improve zero-shot reasoning in specific contexts.

**Wang, Z., et al.** (2024). Persona is a Double-edged Sword: Mitigating the Negative Impact of Role-playing Prompts in Zero-shot Reasoning Tasks. *arXiv preprint arXiv:2408.08631*.

- **Link**: [https://arxiv.org/abs/2408.08631](https://arxiv.org/abs/2408.08631)
- Proposes "Jekyll & Hyde" framework that ensembles persona and neutral perspectives to mitigate persona drawbacks.

---

## Summary

| Technique | Research Support | Domain | Used In |
|-----------|-----------------|--------|---------|
| Random personas | Raghunathan (ICML 2025), Tan (PHAnToM) | Creative, social reasoning | fun-mode |
| Emotional framing | Li (EmotionPrompt), Wang (NegativePrompt) | All reasoning tasks | emotional-stakes |
| Persona consistency | Park (Generative Agents) | Long-form interaction | fun-mode session persistence |

**Design principle**: Spellbook uses personas for creative dialogue only, never for code or documentation, based on Zheng et al.'s findings that personas do not improve objective task performance.
