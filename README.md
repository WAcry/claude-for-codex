# Claude for Codex

A skill that enables Codex (or GPT-powered agents) to delegate scoped subtasks to a local Claude Code instance—combining GPT's reasoning with Claude's aesthetics and readability.

## What It Does

Codex investigates, reasons, plans, codes. Claude Code executes presentation-layer work:

| Delegated to Claude | Why |
|---------------------|-----|
| Front-end UI | Natural aesthetics |
| Documentation | Human-friendly writing |
| Conclusion rewriting | Turns concise findings into readable docs |
| Demos / prototypes | Visually appealing output |

Codex retains ownership of investigation, complex reasoning, and accuracy review.

## Quick Start for the Agent

```bash
# Launch a task
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py launch \
  --prompt "Build a login page" --workdir /path/to/repo --model opus --effort high

# The launch output prints the generated state_id and state_root.
# Use those values for status/resume commands.
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py status \
  --state-id GENERATED_STATE_ID

# Resume in the same session
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py resume JOB_ID \
  --state-id GENERATED_STATE_ID --message "Fix the header alignment"
```

Default to omitting `--state-id` on the first `launch`. The orchestrator generates a fresh `state_id`, which avoids accidental collisions.

If the prompt needs Claude to know generated paths up front, use placeholders inside the prompt text:

- `{{STATE_ID}}`
- `{{STATE_ROOT}}`
- `{{JOB_ID}}`
- `{{JOB_DIR}}`
- `{{WORKDIR}}`
- `{{SESSION_ID}}`

The orchestrator expands those placeholders before Claude starts, and it automatically grants Claude access to `state_root`.

Only pass `--state-id` manually when you intentionally want multiple jobs to share one state.

Write prompts that Claude can complete in one pass without follow-up interaction.

## Commands for the Agent

| Command | Purpose |
|---------|---------|
| `launch` | Start a scoped task |
| `status` | View task status and logs |
| `resume` | Continue a task with follow-up instructions |

## License

MIT
