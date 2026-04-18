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
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch \
  --prompt "Build a login page" --workdir /path/to/repo --model opus --effort high

# Check status
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status --state-id STATE_ID

# Resume in the same session
python ./claude-code-orchestrator/scripts/claude_orchestrator.py resume JOB_ID \
  --state-id STATE_ID --message "Fix the header alignment"

# Answer a deferred question
python ./claude-code-orchestrator/scripts/claude_orchestrator.py answer JOB_ID \
  --state-id STATE_ID --updated-input-json '{"selectedOptionIds":["option1"]}' --resume-now
```

## Commands for the Agent

| Command | Purpose |
|---------|---------|
| `launch` | Start a scoped task |
| `status` | View task status and logs |
| `resume` | Continue a task with follow-up instructions |
| `answer` | Respond to Claude's deferred questions |

## License

MIT
