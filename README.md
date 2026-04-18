# Claude 4 Codex

This repository contains an installable Codex skill named `claude-code-orchestrator`.

The skill helps Codex delegate focused work to one or more local Claude Code CLI runs while keeping Codex as the primary responsible agent. It is designed for cases where Claude Code is a good execution partner, such as frontend polish, demo building, and documentation drafting, but the final review and acceptance should still stay with Codex.

The helper currently defaults to launching Claude through `bash -lc`, so the delegated run inherits the same login-shell configuration and wrapper behavior that users normally rely on in a terminal session.

## What Is Included

- `claude-code-orchestrator/SKILL.md`: the skill itself
- `claude-code-orchestrator/scripts/claude_orchestrator.py`: tracked launch, status, resume, answer, and hook handling
- `claude-code-orchestrator/references/`: prompt and operations notes
- `tests/test_claude_orchestrator.py`: regression coverage for multi-job state and deferred-question behavior

## Install

Copy or symlink `claude-code-orchestrator/` into your Codex skills directory.

Typical location:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R ./claude-code-orchestrator "${CODEX_HOME:-$HOME/.codex}/skills/"
```

## When To Use It

Use this skill when:

- Codex wants to delegate a bounded subtask to Claude Code
- you want a reusable launch/status/resume workflow instead of ad hoc shell commands
- you need a per-job registry for multiple Claude runs
- you need a controlled path for deferred Claude questions in non-interactive runs

Do not use this skill when Codex should do the work directly, especially for fact-heavy debugging, final correctness review, or deep architectural reasoning.

## Quick Start

Create a prompt file using the handoff structure in [claude-code-orchestrator/references/handoff-template.md](claude-code-orchestrator/references/handoff-template.md), then run a dry-run first:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch \
  --prompt-file /abs/path/to/prompt.txt \
  --workdir /abs/path/to/repo \
  --model sonnet \
  --effort high \
  --dry-run
```

The orchestrator stores the full prompt in `prompt.txt` and feeds it to Claude over stdin, so long handoff prompts do not need to appear in the shell command or process list.
The generated command uses `bash -lc 'claude ...'` by default rather than calling `claude` directly.
Launch now allocates a random 6-character `state_id` and a matching state directory under the system temp folder. Save that printed `state_id` for every follow-up command.

Inspect tracked jobs:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status \
  --state-id abc123
```

Resume a saved session:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py resume JOB_ID \
  --state-id abc123 \
  --message "Continue from the last stopping point."
```

Reuse the same printed `state_id` for `status`, `resume`, and `answer`.

Answer a deferred tool call:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py answer JOB_ID \
  --state-id abc123 \
  --updated-input-json '{"selectedOptionIds":["frontend"]}' \
  --resume-now
```

## State Model

State now lives under the system temp directory by default, in a path shaped like:

```text
<system temp>/claude-code-orchestrator-<state_id>/
```

Each job gets its own directory with:

- `job.json` for durable metadata
- `settings.json` for the generated Claude hook configuration
- `prompt.txt` for the last launch prompt
- `attempt-*.txt` for resume-time stdin payloads
- `stdout.log` and `stderr.log` for process output
- `pending-tool.json` and `pending-answer.json` for deferred tool handling

Job IDs are unique by default. Reusing an existing `--job-id` is rejected unless you explicitly pass `--replace`.

## Multi-Run Isolation

If multiple Codex instances are orchestrating multiple Claude Code jobs at the same time, do not point them all at the same state root by accident.

Safe default pattern:

- one orchestrator session
- one generated `state_id`
- many `JOB_ID`s inside that one state root only when you intentionally want one shared registry for that one orchestrator session

Assume other Codex instances may exist and isolate state by default. Give each Codex session its own generated `state_id`.

## Platform Guidance

- Linux: first-class target for the current helper and examples
- macOS: use the same Bash examples and the same temp-backed state-root pattern
- Windows: prefer PowerShell conventions for temp paths and operator docs. If you need native Windows execution, validate the local Claude launcher path carefully because the current helper still wraps Claude with `bash -lc`

PowerShell temp-root example:

```powershell
python .\claude-code-orchestrator\scripts\claude_orchestrator.py launch `
  --prompt-file C:\path\to\prompt.txt `
  --workdir C:\path\to\repo `
  --dry-run

# Read the printed state_id and reuse it later:
python .\claude-code-orchestrator\scripts\claude_orchestrator.py status --state-id abc123
```

## Deferred Questions

The orchestrator uses a per-job Claude settings file and a `PreToolUse` hook entrypoint to capture `AskUserQuestion` or `ExitPlanMode` requests. If an operator answer is already present, the hook returns `updatedInput`; otherwise it defers and records the payload for a later resume.

See [claude-code-orchestrator/references/deferred-questions.md](claude-code-orchestrator/references/deferred-questions.md) for the exact flow.

## Validation

Run the local validation set from the repository root:

```bash
python "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" ./claude-code-orchestrator
python ./claude-code-orchestrator/scripts/claude_orchestrator.py --help
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch --help
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status --help
python ./claude-code-orchestrator/scripts/claude_orchestrator.py resume --help
python ./claude-code-orchestrator/scripts/claude_orchestrator.py answer --help
python -m unittest discover -s tests -p 'test_*.py'
```

## Operating Principle

This repository does not try to make Claude Code the primary agent. The intended loop is:

1. Codex scopes the task and prepares the handoff.
2. Claude Code performs the bounded delegated work and re-checks context independently.
3. Codex reviews the result before accepting or presenting it.

For a real live run, the only assumption is that `claude -p` already works in your own shell environment. Use `--dry-run` first if you want to verify command construction before spending model calls.
