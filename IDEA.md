# Paper Simplifier — Project Summary & Design Decisions

> This is the concise decision history. See `PROJECT_SPEC.md` for the current architecture, `HOW_IT_WORKS.md` for a learner-facing explanation, and `PROGRESS.md` for milestones.

**Goal:** Fine-tune a small (~8B param) Qwen-based LLM to turn AI/ML research papers into plain-language summaries, using teacher-generated synthetic instruction tuning (sequence-level distillation) from a larger Qwen teacher. Scope is deliberately narrow: recent breakthroughs and methods in AI/frontier models, not all of science.

## Constraints
- GPU: RTX 5070, 12GB VRAM
- RAM: 32GB DDR5
- Preferred total API spend: under $10, with a reserve for retries and evaluation
- First time doing a fine-tuning project like this

## Key Design Decisions

### 1. Distillation pipeline
Standard teacher → student distillation: a larger model generates plain-language summaries, a small model is fine-tuned to imitate that behavior. Same pattern used by Alpaca/Vicuna-style instruction tuning.

### 2. Corpus scope & size
~1,000 papers pulled from arXiv's `cs.AI` / `cs.CL` / `cs.LG` categories, filtered toward frontier-model relevance (date range and/or keywords). Free via the arXiv API — no cost, no auth needed.

### 3. Input representation — the "abstract trap"
**Problem caught mid-planning:** training on abstract → simplified-abstract teaches the model to *paraphrase*, not to *summarize a paper*, since abstracts are already dense summaries. It also mismatches inference-time use (a real user would hand over more than just an abstract).

**Decision:** input = title + abstract + introduction + conclusion, pulled from each paper's **LaTeX source** (via arXiv's e-print endpoint) rather than PDF-parsed text — LaTeX section headers (`\section{Introduction}`, `\section{Conclusion}`) are far easier to extract reliably than PDF section boundaries. This keeps input length around 1,500–4,000 tokens per paper — richer than the abstract alone, well short of full-paper length, and manageable on 12GB VRAM.

### 4. Teacher model
Evaluated in order:
- **Qwen3.8-Flash** — final choice. ~$0.10–0.14/M input, $0.40–0.42/M output. Reachable through the existing Hermes credit (no new account needed), and matches the family of the planned student model, which is a nice bonus for later comparing teacher vs. student behavior within the same lineage.

Estimated total teacher-generation cost for ~1,000 papers at this richer input size: well under $1 — a small fraction of the $8 budget.

### 5. Student model & training method
- Candidate base models: Qwen2.5-7B-Instruct, Qwen3-8B, or Llama 3.1 8B Instruct — all have decent out-of-the-box summarization ability, so fine-tuning is shaping behavior/style, not teaching from scratch.
- **Training stack:** Hugging Face ecosystem — `transformers` + `peft` (LoRA) + `trl` (SFTTrainer) + `bitsandbytes` (4-bit quantization). **Not Ollama** — Ollama is for easy local *inference* later (e.g. demoing the finished model), not for fine-tuning.
- **Method:** QLoRA, 4-bit base weights, LoRA rank ~8–16, gradient checkpointing, batch size 1–2 with gradient accumulation. Expected to fit on the 5070's 12GB VRAM given the input lengths chosen above; a run over ~1,000 examples should take hours, not days.

### 6. Evaluation plan
Compare three outputs side by side on held-out papers: base (non-fine-tuned) small model, fine-tuned small model, and teacher summaries. Use both automated metrics (ROUGE, BERTScore) and qualitative human-readability judgment — ideally from a few readers outside the field, since "digestible to a layperson" is the actual target, not just textual similarity to the teacher.

## Roadmap (7 steps)
1. Scrape ~1,000 papers from arXiv (metadata + LaTeX source for intro/conclusion)
2. Generate teacher summaries with Qwen3.8-Flash via Hermes
3. Pick and download the base student model (Hugging Face Hub)
4. Set up the training environment (`transformers`, `peft`, `trl`, `bitsandbytes`)
5. Format the dataset into the base model's chat template
6. Fine-tune with QLoRA
7. Merge, test, and evaluate (base vs. fine-tuned vs. teacher)

## Status
Steps 1–7 planned; **Step 1 (arXiv scraper) is the next concrete action, not yet built.**
