# Research Citations

This page documents the research that informs spellbook's design, particularly the [fun-mode](../skills/fun-mode.md) and [emotional-stakes](../skills/emotional-stakes.md) skills.

## Creativity and Seed-Conditioning

**Nagarajan, V., Wu, C. H., Ding, C., & Raghunathan, A.** (2025). Roll the dice & look before you leap: Going beyond the creative limits of next-token prediction. *International Conference on Machine Learning (ICML 2025)*, Outstanding Paper Award.

- **Link**: [https://arxiv.org/abs/2504.15266](https://arxiv.org/abs/2504.15266) (group page: [https://www.cs.cmu.edu/~aditirag/icml2025.html](https://www.cs.cmu.edu/~aditirag/icml2025.html))
- **Key finding**: Injecting noise at the input layer ("seed-conditioning") works as well as, and sometimes better than, temperature sampling at the output layer for eliciting creative and diverse outputs from language models. The paper argues that standard next-token prediction has inherent limits for tasks requiring planning and novel pattern discovery.
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
- **Key finding**: Across 162 personas and 2,410 factual questions (MMLU), personas do not improve performance on factual tasks compared to neutral prompts. Effects are inconsistent and sometimes negative.
- **Relevance**: **Critical caveat** - fun mode explicitly restricts personas to dialogue, never affecting code, commits, or documentation. Personas may help creative and social reasoning tasks but do not help factual question-answering.

**Gupta, S., et al.** (2024). Bias Runs Deep: Implicit Reasoning Biases in Persona-Assigned LLMs. *International Conference on Learning Representations (ICLR 2024)*.

- **Key finding**: Persona-assigned LLMs can exhibit implicit reasoning biases that affect downstream task performance.
- **Relevance**: Additional support for restricting personas to non-critical outputs.

## Hallucination Prevention and Detection

**Dhuliawala, S., Komeili, M., Xu, J., Raileanu, R., Li, X., Celikyilmaz, A., & Weston, J.** (2023). Chain-of-Verification Reduces Hallucination in Large Language Models. *arXiv preprint arXiv:2309.11495*.

- **Link**: [https://arxiv.org/abs/2309.11495](https://arxiv.org/abs/2309.11495)
- **Key finding**: A multi-step self-correction protocol where the LLM generates verification questions about its own claims, answers them independently, and revises based on contradictions. Reduces hallucination across multiple tasks.
- **Relevance**: Foundation for the CoVe self-interrogation protocol used in fact-checking, dehallucination, and verifying-hunches skills.

**Min, S., Krishna, K., Lyu, X., Lewis, M., Yih, W., Koh, P. W., Iyyer, M., Zettlemoyer, L., & Hajishirzi, H.** (2023). FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation. *Proceedings of EMNLP 2023*.

- **Link**: [https://aclanthology.org/2023.emnlp-main.741/](https://aclanthology.org/2023.emnlp-main.741/)
- **Key finding**: Breaking text into atomic, independently verifiable claims enables fine-grained factual evaluation. The atomic decomposition approach reveals errors hidden in compound statements.
- **Relevance**: Foundation for the `/decompose-claims` protocol command used during fact-checking extraction and design document review.

**Tambon, F., Nikanjam, A., An, L., Khomh, F., & Bhatt, G.** (2025). Detecting and Correcting Hallucinations in LLM-Generated Code via Deterministic AST Analysis. *arXiv preprint arXiv:2601.19106*.

- **Link**: [https://arxiv.org/abs/2601.19106](https://arxiv.org/abs/2601.19106)
- **Key finding**: AST-based analysis can deterministically detect code hallucinations including non-existent API calls, incorrect parameter usage, and fabricated import paths.
- **Relevance**: Informs the API hallucination detection checklists in code-review and enforcing-code-quality skills.

**Pomian, R., Santu, S. K. K., Guha, A., & Ahmed, T.** (2025). HalluJudge: A Reference-Free Hallucination Detection for Context Misalignment in Code Review Automation. *arXiv preprint arXiv:2601.19072*.

- **Link**: [https://arxiv.org/abs/2601.19072](https://arxiv.org/abs/2601.19072)
- **Key finding**: Reference-free hallucination detection can identify context misalignment in automated code review, where review comments address code that does not exist or mischaracterize actual behavior.
- **Relevance**: Supports the API hallucination detection approach in code-review audit mode, specifically checking that review findings reference real code structures.

**De Langis, K., & Zheng, R.** (2026). Reasoning Improves Accuracy but Hurts Recall at Strict False Positive Rates. *Proceedings of EACL 2026*.

- **Link**: [https://aclanthology.org/2026.eacl-long.190.pdf](https://aclanthology.org/2026.eacl-long.190.pdf)
- **Implementation note**: This URL was provided from user source research and should be verified during implementation (confirm the ACL Anthology URL resolves correctly).
- **Key finding**: Chain-of-thought reasoning improves accuracy but can reduce recall at strict false positive thresholds. Verification systems must balance thoroughness against over-flagging.
- **Relevance**: Calibrates expectations for CoVe protocol: self-interrogation improves precision but should not be used to suppress genuine findings.

**Gekhman, Z., Yona, G., Aharoni, R., Eyal, M., Feder, A., Reichart, R., & Herzig, J.** (2025). The Law of Knowledge Overshadowing: Towards Understanding, Predicting, and Preventing LLM Hallucination. *Findings of ACL 2025*.

- **Link**: [https://aclanthology.org/2025.findings-acl.1199.pdf](https://aclanthology.org/2025.findings-acl.1199.pdf)
- **Key finding**: LLMs hallucinate when "popular" knowledge overshadows less common but correct facts. The model's confidence in a hallucination correlates with the dominance of the overshadowing knowledge.
- **Relevance**: Explains why API hallucinations are common (popular API patterns overshadow less-used but correct alternatives) and supports the evidence hierarchy's prohibition on Tier 6 (parametric knowledge) as sole evidence.

**Yaldiz, A., Su, H., Deshpande, A., Kumar, V., & Awadallah, A. H.** (2025). Uncertainty Quantification for Hallucination Detection in Large Language Models. *arXiv preprint arXiv:2510.12040*.

- **Link**: [https://arxiv.org/abs/2510.12040](https://arxiv.org/abs/2510.12040)
- **Key finding**: Uncertainty quantification metrics can predict hallucination likelihood. High model uncertainty on a claim correlates with hallucination risk, suggesting verification effort should be concentrated on uncertain outputs.
- **Relevance**: Theoretical support for the depth escalation protocol: claims where the model expresses uncertainty should be escalated to deeper verification, not accepted at face value.

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
| Random personas | Nagarajan et al. (ICML 2025), Tan (PHAnToM) | Creative, social reasoning | fun-mode |
| Emotional framing | Li (EmotionPrompt), Wang (NegativePrompt) | All reasoning tasks | emotional-stakes |
| Persona consistency | Park (Generative Agents) | Long-form interaction | fun-mode session persistence |
| CoVe self-interrogation | Dhuliawala et al. (2023) | Verification, claim checking | fact-checking, dehallucination, verifying-hunches |
| Atomic claim decomposition | Min et al. (FActScore, EMNLP 2023) | Claim extraction, verification | decompose-claims command |
| API hallucination detection | Tambon et al. (2025), Pomian et al. (2025) | Code review, quality | code-review, enforcing-code-quality |

**Design principle**: Spellbook uses personas for creative dialogue only, never for code or documentation, based on Zheng et al.'s findings that personas do not improve objective task performance.
