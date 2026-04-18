# Operations Guide

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
