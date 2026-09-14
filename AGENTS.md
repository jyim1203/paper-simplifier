# Paper Simplifier — Agent Rules

Scope: this repository. These rules apply to any agent working here
(Hermes, Claude Code, Codex, OpenCode).

## 1. Check every coding step with a review subagent

When a coding task is finished — code written and tests run, but **before** it
is reported as done — spawn a subagent to independently check the work.

- Call `delegate_task` with a **review** goal, not a "keep building" goal.
  Example goal: "Independently verify the LaTeX parser changes in this repo."
- Give the child real context: repo path, the files touched, what was claimed,
  and the exact command to reproduce it. Subagents know nothing of prior turns.
- The child must **re-run the tests/probes itself** and report what it actually
  observed. A restated claim is not verification.
- Model and effort are pinned globally in config, not per call:
  `delegation.model` = `deepseek/deepseek-v4.1-flash`, provider `nous`,
  `delegation.reasoning_effort` = `medium`. `delegate_task` has **no**
  per-task model/effort parameter — do not try to pass one.

Report the child's findings next to the change. If it finds a real problem,
fix it before declaring the step done.

## 2. Never add a "Hermes" co-author trailer to commits

Do **not** put `Co-authored-by: Hermes <hermes@nousresearch.com>` — or any
`Co-authored-by:` line — in a commit message. Commit under the repo owner's
identity only.

Why: `hermes@nousresearch.com` is registered to an unrelated GitHub account
(`Rafa-Ross`). GitHub resolves the trailer by email and mis-attributes the
commit to that stranger, which is how `Rafa-Ross` showed up on the repo.