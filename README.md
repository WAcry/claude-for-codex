# Claude for Codex

This skill enables Codex (or GPT-powered agents) to delegate scoped subtasks to a local Claude Code instance. GPT reasons much more accurately but has no eye for design and is so smart it forgets humans need explanations; Claude is less reliable and less intelligent, yet produces polished UI, accessible writing, and human-friendly documentation. This skill combines both.

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
