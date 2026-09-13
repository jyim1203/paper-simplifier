# Model Options — Provisional

**Status:** Shortlist only; verify current model IDs, context limits, licenses, and pricing before use.

## Teacher

The proposed Qwen Flash teacher is a reasonable default if the exact Hermes model identifier is available and its price/context behavior fit the budget. The teacher's job is to produce consistent, factual, readable labels; maximum benchmark capability is less important than cost, reliability, and a stable API.

Before bulk generation, run a 10–25-paper pilot and record actual input/output tokens, retries, latency, and cost. Keep a budget reserve and stop before the hard ceiling.

Teacher selection criteria:

1. Reliable Hermes availability
2. Current documented price
3. Adequate context for the selected sections
4. Consistent instruction following and output format
5. Good factuality on a manually audited pilot
6. Cheap enough to leave budget for retries and evaluation

A stronger teacher is not automatically better if it is inconsistent or too expensive to audit and iterate with.

## Student shortlist

Start with Qwen models because they align with the project goal and should provide a coherent family comparison. Candidate families can include:

- Qwen2.5 7B Instruct — conservative baseline and mature tooling
- Qwen3 8B — newer candidate; benchmark context handling and training compatibility
- A larger Qwen variant only if the exact quantized training setup is proven to fit the 12 GB GPU

Do not choose solely from parameter count or release date. Benchmark candidates on the same pilot input and use the result plus VRAM/training behavior to select one.

Student selection criteria:

- Base output quality on the project rubric
- Peak VRAM during inference and QLoRA smoke test
- Speed on the local GPU
- Context length and tokenization behavior
- Chat-template stability
- License and redistribution constraints
- Ease of reproducing the training run

## Decision rule

Select the model with the best constrained value:

```text
usefulness per dollar + usefulness per GB of VRAM + reproducibility
```

Document why the selected model won. A cheaper model that trains reliably is a defensible choice, not a compromise that needs to be hidden.
