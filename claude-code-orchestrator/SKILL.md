---
name: claude-code-orchestrator
description: Coordinate one or more local Claude Code CLI runs from Codex for bounded implementation, frontend polish, demo building, or documentation work. Use when Codex wants to delegate a subtask to Claude Code, needs a repeatable launch/status/resume workflow, must handle deferred Claude Code questions in non-interactive runs, or wants Codex to remain the primary reviewer after Claude finishes.
---

# Claude Code Orchestrator

Use this skill when Claude Code is the right subordinate agent for a focused task, but Codex should stay responsible for scoping, verification, and final review.

## Quick Start

1. Decide whether Claude Code is a good fit.
   Use Claude Code for UI polish, prototype implementation, documentation drafting, or other bounded execution-heavy work.
   Keep work in Codex when the task is mostly debugging, fact-checking, or deep architecture review.
2. Build a strong handoff prompt.
   Read [references/handoff-template.md](references/handoff-template.md) and give Claude Code:
   - the concrete task
   - the relevant repository paths
   - the expectation that it must verify context independently instead of trusting the parent prompt blindly
   - the requirement to stop only for real blockers
3. Launch a tracked job.

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch \
  --prompt-file /abs/path/to/prompt.txt \
  --workdir /abs/path/to/repo \
  --model sonnet \
  --effort high \
  --output-dir /abs/path/to/state
```

The helper launches Claude through `bash -lc` by default so the run sees the same login-shell configuration, wrapper scripts, and PATH setup that a human operator would expect in a normal terminal session.

4. Inspect progress or resume the same Claude session later.

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status --output-dir /abs/path/to/state
python ./claude-code-orchestrator/scripts/claude_orchestrator.py resume JOB_ID --output-dir /abs/path/to/state
```

5. If Claude Code defers a user question, inspect the saved payload and answer it through the orchestrator workflow.
   Read [references/deferred-questions.md](references/deferred-questions.md) before using `answer`.

6. Review everything Claude Code produced before accepting it.
   Codex remains the primary agent. Do not forward Claude Code output directly to the user without checking it.

## Operating Rules

- Default to standard Claude Code execution. Do not add `--bare` unless you intentionally want a stripped-down run and have explicitly decided to provide all missing context yourself.
- Treat Claude Code as a capable worker, not as an authority. Give it rich task context, but require it to read files, inspect the repo, and verify assumptions on its own.
- Prefer one bounded job per outcome. If you need unrelated workstreams, launch multiple jobs and track them separately in the registry.
- Preserve model and effort choices in the job metadata so later reviewers can see how the run was configured.
- Use `--dry-run` first when you are checking prompt quality, hook wiring, or command construction.
- Prefer login-shell semantics for direct manual invocations too. If you are not using the helper script, prefer `bash -lc 'claude ...'` over calling `claude` from an unknown stripped shell.
- After Claude Code finishes, do a second-pass Codex review before you merge, present, or trust the output.

## Deferred Questions

The orchestrator generates a per-job Claude settings file that installs a `PreToolUse` hook for `AskUserQuestion` and `ExitPlanMode`. That gives you a controlled place to capture pending questions, persist them to the job directory, and resume the same Claude session later with `updatedInput`.

Read [references/deferred-questions.md](references/deferred-questions.md) for the exact flow, limitations, and artifact names.

## Resources

- `scripts/claude_orchestrator.py`: launch, status, resume, answer, and hook entrypoint
- [references/handoff-template.md](references/handoff-template.md): prompt structure for Codex-to-Claude delegation
- [references/operations.md](references/operations.md): command cookbook and job-state layout
- [references/deferred-questions.md](references/deferred-questions.md): deferred-question workflow and caveats
