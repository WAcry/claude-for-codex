# Operations Guide

## Core Commands

Launch a tracked Claude Code job:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch \
  --prompt-file /abs/path/to/prompt.txt \
  --workdir /abs/path/to/repo \
  --output-dir /abs/path/to/state
```

The full prompt is sent to Claude through stdin. The command metadata keeps a short preview, while `prompt.txt` stores the full launch prompt on disk.
The helper wraps Claude with `bash -lc` so the job runs with login-shell semantics by default.

Inspect every job in the registry:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status \
  --output-dir /abs/path/to/state
```

Inspect one job and tail its logs:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status JOB_ID \
  --output-dir /abs/path/to/state \
  --tail 30 \
  --tail-both
```

If you prefer the default repo-local state directory, replace `--output-dir` with `--workdir /abs/path/to/repo` for `status`, `resume`, and `answer`.

Resume the same Claude session:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py resume JOB_ID \
  --output-dir /abs/path/to/state \
  --message "Continue with the remaining UI polish and rerun the tests."
```

Queue an answer payload for a deferred tool call:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py answer JOB_ID \
  --output-dir /abs/path/to/state \
  --updated-input-json '{"selectedOptionIds":["frontend"]}' \
  --resume-now
```

Replace an existing stopped job only when you explicitly mean to discard its old registry entry:

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch \
  --prompt-file /abs/path/to/prompt.txt \
  --workdir /abs/path/to/repo \
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

## Recommended Workflow

1. Dry-run first when changing prompt shape, model/effort, or hook behavior.
2. Launch the real run once the command looks correct. The recorded command should show `bash -lc 'claude ...'` rather than a direct bare executable call.
3. Use `status` instead of guessing which session ID belongs to which task, and check `stderr.log` when a run fails or stalls.
4. Resume the same job instead of creating ad hoc new sessions for follow-up instructions.
5. Leave Codex review until after Claude Code finishes.

## Multi-Job Scheduling

The registry is the minimum orchestration layer. Use separate jobs when:

- you want one Claude run per subtask
- you want different model or effort settings
- you need clean audit trails for frontend, docs, and demo work

Do not overload one session with unrelated tasks just because resuming is convenient.
