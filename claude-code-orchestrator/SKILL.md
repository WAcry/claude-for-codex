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
  --effort high
```

The helper uses a platform-aware launcher so the run matches the host operating system:
- Linux and macOS: `bash -lc`
- Windows: direct `claude` invocation without a Bash wrapper
Launch automatically allocates a random 6-character `state_id` and a matching state directory under the system temp folder. Treat that generated `state_id` as the handle for every follow-up command in the same orchestration run.

4. Inspect progress or resume the same Claude session later.

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status --state-id abc123
python ./claude-code-orchestrator/scripts/claude_orchestrator.py resume JOB_ID --state-id abc123
```

5. If Claude Code defers a user question, inspect the saved payload and answer it through the orchestrator workflow.
   Read [references/deferred-questions.md](references/deferred-questions.md) before using `answer`.

6. Review everything Claude Code produced before accepting it.
   Codex remains the primary agent. Do not forward Claude Code output directly to the user without checking it.

## Operating Rules

- Default to standard Claude Code execution. Do not add `--bare` unless you intentionally want a stripped-down run and have explicitly decided to provide all missing context yourself.
- Treat Claude Code as a capable worker, not as an authority. Give it rich task context, but require it to read files, inspect the repo, and verify assumptions on its own.
- Prefer one bounded job per outcome. If you need unrelated workstreams, launch multiple jobs and track them separately in the registry.
- Always let launch allocate isolated temp-backed state by default. Codex cannot assume it is the only orchestrator in the environment, so the default posture must be isolated state.
- Never let unrelated orchestrators share the same `state_id`. If two Codex instances intentionally point different work at the same state directory, they can collide on `job_id`, registry contents, cleanup expectations, or follow-up commands.
- Preserve model and effort choices in the job metadata so later reviewers can see how the run was configured.
- Use `--dry-run` first when you are checking prompt quality, hook wiring, or command construction.
- Prefer login-shell semantics for direct manual invocations on Linux and macOS too. If you are not using the helper script there, prefer `bash -lc 'claude ...'` over calling `claude` from an unknown stripped shell.
- On Windows, prefer PowerShell conventions when designing temp paths, operator steps, and examples. Use `%TEMP%` / `$env:TEMP` semantics for state directories rather than Unix-specific `/tmp` assumptions.
- After Claude Code finishes, do a second-pass Codex review before you merge, present, or trust the output.

## State Root Guidance

The required default behavior for this skill is isolated state. Launch creates a unique temp-backed state root for every orchestrated run and prints both `state_id` and `state_root`. Reuse that exact `state_id` for every follow-up command in the same run.

Examples:

- Linux:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch ...
# Read the printed state_id, for example: abc123
```

- macOS:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch ...
# Read the printed state_id, for example: abc123
```

- PowerShell:

```powershell
python .\claude-code-orchestrator\scripts\claude_orchestrator.py launch ...
# Read the printed state_id, for example: abc123
```

Use that printed `state_id` for `status`, `resume`, and `answer`.

## Platform Notes

- Linux: first-class target for the current helper
- macOS: shell and filesystem conventions are close to Linux; the helper uses the same `bash -lc` launcher
- Windows: prefer PowerShell examples and temp directories in documentation; the helper uses direct `claude` invocation instead of Bash

## Deferred Questions

The orchestrator generates a per-job Claude settings file that installs a `PreToolUse` hook for `AskUserQuestion` and `ExitPlanMode`. That gives you a controlled place to capture pending questions, persist them to the job directory, and resume the same Claude session later with `updatedInput`.

Read [references/deferred-questions.md](references/deferred-questions.md) for the exact flow, limitations, and artifact names.

## Core Commands

Launch a tracked Claude Code job:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch \
  --prompt-file /abs/path/to/prompt.txt \
  --workdir /abs/path/to/repo
```

The full prompt is sent to Claude through stdin. The command metadata keeps a short preview, while `prompt.txt` stores the full launch prompt on disk.
The helper uses a platform-aware launcher:
- Linux and macOS: `bash -lc`
- Windows: direct `claude` invocation without a Bash wrapper
Launch creates a random 6-character `state_id` and a matching state directory in the system temp folder. Save the printed `state_id` and reuse it for every follow-up command.

Inspect every job in the registry:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status \
  --state-id abc123
```

Inspect one job and tail its logs:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status JOB_ID \
  --state-id abc123 \
  --tail 30 \
  --tail-both
```

Every orchestrator run should have its own generated `state_id`, and every follow-up command should reuse that exact id.

Resume the same Claude session:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py resume JOB_ID \
  --state-id abc123 \
  --message "Continue with the remaining UI polish and rerun the tests."
```

Queue an answer payload for a deferred tool call:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py answer JOB_ID \
  --state-id abc123 \
  --updated-input-json '{"selectedOptionIds":["frontend"]}' \
  --resume-now
```

Replace an existing stopped job only when you explicitly mean to discard its old registry entry:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch \
  --prompt-file /abs/path/to/prompt.txt \
  --workdir /abs/path/to/repo \
  --state-id abc123 \
  --job-id frontend-pass \
  --replace
```

## Job Layout

The orchestrator stores state under `OUTPUT_DIR/jobs/JOB_ID/`.

Important files:

- `job.json`: durable job metadata and attempt history
- `settings.json`: generated Claude settings with the per-job hook command
- `prompt.txt`: the last prompt text used for `launch`
- `attempt-*.txt`: stdin payloads for later resume attempts
- `stdout.log` and `stderr.log`: Claude Code process logs
- `pending-tool.json`: captured deferred tool payload
- `pending-answer.json`: operator-provided `updatedInput` payload waiting to be consumed by the hook

The registry root also contains `registry.json`, a summary index of all jobs.

## Temp Directory Behavior

Launch stores state under the system temp directory using:

```bash
<system temp>/codex-claude-code-orchestrator-state-<state_id>/
```

Examples:

- Linux or macOS:

```text
/tmp/codex-claude-code-orchestrator-state-abc123/
```

- PowerShell / Windows:

```text
$env:TEMP\codex-claude-code-orchestrator-state-abc123\
```

Do not share one `state_id` across unrelated orchestrators. Assume other Codex instances may exist and isolate state by default.

## Recommended Workflow

1. Dry-run first when changing prompt shape, model/effort, or hook behavior.
2. Launch the real run once the command looks correct. The recorded command should show `bash -lc 'claude ...'` on Linux and macOS, and a direct `claude ...` argv launch on Windows.
3. Use `status` instead of guessing which session ID belongs to which task, and check `stderr.log` when a run fails or stalls.
4. Resume the same job instead of creating ad hoc new sessions for follow-up instructions.
5. Leave Codex review until after Claude Code finishes.
6. Reuse the same printed `state_id` for every command in that one orchestration run.

## Platform Guidance

- Linux: use the Bash examples as written
- macOS: use the same Bash examples and the same generated temp-backed `state_id` flow
- Windows: prefer PowerShell path conventions in operator docs and wrappers; the current helper does not require Bash and launches `claude` directly

## Multi-Job Scheduling

The registry is the minimum orchestration layer. Use separate jobs when:

- you want one Claude run per subtask
- you want different model or effort settings
- you need clean audit trails for frontend, docs, and demo work

Do not overload one session with unrelated tasks just because resuming is convenient.

## Handoff Prompt Template

Use this template when Codex delegates work to Claude Code.

```text
<role>
You are Claude Code working as a subordinate agent for Codex.
Codex remains the primary accountable agent and will review your work.
</role>

<task>
[Describe the concrete outcome.]
</task>

<context>
- Working directory: [...]
- Relevant files or paths: [...]
- Known constraints: [...]
- Known risks: [...]
</context>

<operating_rules>
- Do not rely only on this prompt. Read the repository and verify assumptions before acting.
- Stay within the requested scope. Avoid unrelated refactors.
- If the task is long-running, leave clear progress evidence in your output or artifacts.
- Stop only for real blockers or missing high-risk information.
</operating_rules>

<deliverable>
- State what you changed or learned.
- List the files you touched.
- Explain how you verified the result.
- Call out any uncertainty or follow-up work.
</deliverable>
```

Practical guidance:

- Add repository-relative paths, not vague file descriptions.
- Tell Claude Code what "done" looks like.
- Include verification instructions when wrong output would be expensive.
- If Codex plans to compare multiple Claude runs, keep the prompts scoped and separate so job histories stay readable.


## Deferred Questions

This skill uses a per-job `PreToolUse` hook to intercept `AskUserQuestion` and `ExitPlanMode` during `claude -p` runs.

### Why This Exists

Non-interactive Claude Code runs are good for automation, but some tools require user input. Claude Code hooks can inspect tool calls and return a permission decision before the tool runs. For `AskUserQuestion` and `ExitPlanMode`, the hook can return `permissionDecision: "allow"` together with `updatedInput` so the tool can proceed with externally supplied input. Hooks receive JSON on stdin, and settings files can register command hooks for `PreToolUse`. The built-in `AskUserQuestion` tool is the standard way Claude asks clarifying multiple-choice questions.

### Repository Flow

1. `launch` or `resume` generates `settings.json` for the job, passes it to Claude with `--settings`, and feeds any prompt or follow-up message over stdin rather than embedding it in the command line.
2. If Claude hits `AskUserQuestion` or `ExitPlanMode`, the hook stores the tool payload in `pending-tool.json`.
3. If an operator answer already exists in `pending-answer.json`, the hook returns `permissionDecision: "allow"` with the stored `updatedInput`.
4. Otherwise, the hook returns `permissionDecision: "defer"` so the run can stop cleanly while preserving the session for a later `resume`.
5. Codex inspects `pending-tool.json`, prepares the correct `updatedInput` payload, writes it with `answer`, and resumes the same job.

### Important Limits

- The exact `updatedInput` shape depends on the tool payload. Inspect `pending-tool.json` before answering.
- `AskUserQuestion` usually expects a structured selection payload, not a free-form note.
- The live deferred flow depends on Claude Code support for deferred tool handling in `-p` mode.
- In this repository, the flow is tested with deterministic fixtures because the current workspace cannot complete real Claude API calls.

### Safe Usage Pattern

1. Run `status JOB_ID --tail 30 --tail-both` and inspect `pending-tool.json`.
2. Build the `updatedInput` object that matches the captured tool payload.
3. Use `answer JOB_ID --updated-input-json ... --resume-now`.
4. Run `status JOB_ID --tail 30` to confirm the resumed attempt progressed.


- [references/handoff-template.md](references/handoff-template.md): prompt structure for Codex-to-Claude delegation
- [references/operations.md](references/operations.md): command cookbook and job-state layout

