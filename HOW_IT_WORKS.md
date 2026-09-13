# How Paper Simplifier Works

This project is a small experiment in teaching one language model to explain research papers more clearly.

## The short version

1. Find a carefully selected set of AI/ML papers.
2. Extract the title, abstract, introduction, and conclusion-like text.
3. Ask a larger Qwen teacher model to write a plain-language explanation.
4. Check and audit those explanations.
5. Teach a smaller Qwen model using the paper text as input and the teacher explanation as the desired output.
6. Compare the original small model, the trained small model, and the teacher.

The important idea is that the student is not learning from the paper's abstract alone. It sees a richer slice of the paper, so the task is closer to explaining a paper than simply rewriting its abstract.

## What happens to one paper?

```text
arXiv metadata
      │
      v
source text requested temporarily
      │
      v
relevant sections extracted and cleaned
      │
      v
token count measured with the student tokenizer
      │
      v
teacher writes a plain-language explanation
      │
      v
record is checked, logged, and eventually used for training
```

A paper record is more than just two strings. It also carries information about where the text came from, whether a conclusion was missing, how many tokens it contains, which prompt and teacher produced the label, and whether any warnings were raised.

## Why use a tokenizer?

A model does not read characters or words directly. It reads token IDs. A token may be a whole short word, part of a long word, punctuation, or a special control marker.

For example, the text:

```text
Transformers simplify language modeling.
```

is converted into a sequence of IDs such as:

```text
[integer, integer, integer, integer, integer, ...]
```

The exact IDs depend on the model family. We therefore load the tokenizer that belongs to the student model using Hugging Face's `transformers` library. We do not invent a tokenizer ourselves.

Token counting matters for two reasons:

- The model has a maximum context length.
- Longer training examples use more VRAM and take more time.

We count tokens during data preparation, flag long records, and apply an explicit truncation or filtering policy. We also use the same tokenizer and chat template when creating the final training data.

## What does QLoRA do?

An 8-billion-parameter model is too large for comfortable full-parameter training on a 12 GB GPU. QLoRA reduces the memory requirement in two ways:

- The original model weights are loaded in a compressed 4-bit representation.
- Instead of changing every original weight, training learns a much smaller set of adapter weights called LoRA weights.

The base model remains mostly fixed. The adapters learn the project-specific behavior: how to turn the selected paper input into the desired type of explanation.

This is why the model can be fine-tuned on a consumer GPU, although the exact sequence length and settings still need to be tested rather than assumed.

## What does the teacher contribute?

The teacher provides example answers. It is not guaranteed to be correct, so teacher outputs are synthetic labels rather than unquestionable truth.

That creates a key rule for this project:

> A cheaper or larger dataset is not automatically better if its labels are inconsistent or inaccurate.

We will inspect a small sample, automatically flag suspicious outputs, and keep a human review step for factuality and readability.

## What counts as success?

The fine-tuned model should be better than the base model at explaining the selected paper inputs to a non-specialist, without inventing unsupported claims.

We will measure several things because no single metric captures that goal:

- Does the output cover the problem, idea, result, and limitations?
- Is it understandable to someone outside the field?
- Are important claims supported by the supplied paper text?
- Are acronyms and jargon explained?
- Is it concise without becoming misleading?
- Does it resemble the teacher enough to show learning, without treating teacher similarity as the definition of truth?

## Why start with a small batch?

A 1,000-paper run can fail for many unrelated reasons. A 10–25-paper pilot lets us inspect the entire path cheaply:

```text
scrape → extract → count tokens → generate labels → audit → train smoke test → evaluate
```

Only after this path works should the corpus be expanded.
