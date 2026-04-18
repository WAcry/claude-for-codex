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

## Commands for the Agent

| Command | Purpose |
|---------|---------|
| `launch` | Start a scoped task |
| `status` | View task status and logs |
| `resume` | Continue a task with follow-up instructions |

## License

MIT
