---
name: claude-for-codex
description: Delegate subtasks to a local Claude Code instance. Suited for front-end UI implementation, documentation writing, rewriting investigation conclusions into human-readable formats, demo prototypes, and other tasks requiring aesthetics or human readability. Triggered when coordinating Claude Code to complete limited-scope work. This skill is for use only by agents powered by OpenAI GPT models.
---

# Claude Code Orchestrator

## Delegation Model

GPT and Claude have complementary strengths. GPT reasons much more accurately; Claude is less reliable and less intelligent. However, GPT's training favors precision and brevity—its output lacks design sense and reads as expert notes, not step-by-step pedagogical explanations. Claude's training favors patient, accessible teaching and polished visual design. These are model-level tendencies, not prompting problems—neither can replicate the other's strength by trying harder. GPT provides accuracy, Claude provides readability. Therefore GPT must not rephrase Claude's output.

### Tasks Suitable for Delegating to Claude Code

| Task Type | Claude's Strengths | Your Follow-up Action |
|-----------|-------------------|----------------------|
| Front-end UI implementation | Naturally good aesthetics, generates beautiful interfaces | Review and fix code bugs |
| Simple documentation (based on well-scoped code, PRs) | Clear, self-contained, human-friendly | Review and fix factual accuracy and logic |
| Complex document rewriting / polishing | Rewrites concise docs into thorough explanations with good formatting | Review and fix factual accuracy and logic |
| Implementation demos / prototypes | Quickly produces visually appealing prototypes | Review and fix factual accuracy and logic |

### Tasks Requiring GPT First, Claude Code Polish After

| Task Type | Why GPT Goes First | Workflow |
|-----------|-------------------|----------|
| System design documents | Requires broad search and deep reasoning, not limited to a single diff | GPT writes first draft → Claude Code polishes formatting → GPT reviews |
| Investigation analysis, answering user questions | Scope is unclear, requires deep codebase investigation, synthesizing information from multiple sources, requires high reasoning ability | GPT investigates and writes conclusions → Claude Code thoroughly restructures into a readable document at length → GPT reviews |
| Task implementation plans | Scope is unclear, requires deep investigation of feasible approaches, evaluating trade-offs, original design, requires high reasoning ability | GPT writes plan → Claude Code improves descriptions, adds readability, adds necessary examples → GPT reviews |

### Tasks Not Suitable for Independent Completion

- Complex bug investigation or deep investigation/reasoning—Claude often reaches wrong conclusions
- Writing bug-free code—Claude's code frequently has bugs
- Writing original design documents or task plans that require deep thinking—Claude's plans are usually not the best approach and may even contain errors

### Conclusion Rewriting Workflow

When a user question requires deep investigation and the answer needs to be human-readable:

1. **You investigate first**, reaching an accurate conclusion (your conclusion is accurate but concise; the user may have difficulty understanding it)
2. **Delegate to Claude Code**: hand it your conclusion + relevant files and context paths, asking it to rewrite your conclusion into a human-readable explanatory document, generate a markdown document, and provide the path.
3. **You review the document**: only check for factual deviations, make factual corrections, do not change style or length, do not compress, supplement, or restructure.
4. **Deliver**: provide the file path to the user with a brief summary.

## Common Paths for Documents, Artifacts, and Prompts

Unless otherwise specified, store them in `state_root`. Do not place them in `workdir` to avoid polluting the Git environment.

## Output Handling Rules

Claude's output is more readable for users. Your responsibility is to review accuracy, not rewrite style.

| Rule | Description |
|------|-------------|
| Fix only actual errors | Only correct factual errors and obvious bugs; do not modify wording or style |
| Do not add or remove content | Do not add to, remove from, or compress Claude's output |
| Do not paraphrase | Do not redescribe Claude's output in your own words |
| Use files for long content | Have Claude output to a markdown file; after review, provide the file path to the user |

**Self-check signal**: if you find yourself restructuring or condensing Claude's paragraphs—stop. Only fix errors, not content.

## Quick Start

```bash
# Launch a task
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py launch \
  --prompt-file /abs/path/to/prompt.txt \
  --workdir /abs/path/to/repo \
  --model opus --effort high

# View all tasks
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py status \
  --state-id GENERATED_STATE_ID

# View a single task + log tail
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py status JOB_ID \
  --state-id GENERATED_STATE_ID --tail 30

# Resume the same session
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py resume JOB_ID \
  --state-id GENERATED_STATE_ID --message "Continue with the remaining work"
```

Default to omitting `--state-id` on the first launch. The orchestrator auto-generates a fresh state id, which avoids accidental collisions when agents launch jobs by habit.

## Key Concepts

| Term | Meaning |
|------|---------|
| **State** (`state_id`, `state_root`) | A single orchestration run, holding one or more jobs under an isolated temp directory. Each run gets its own `state_id`. |
| **Job/Task** (`job_id`) | A single Claude Code invocation within a state, with its own session, logs, and prompt. One job = one focused task. |
| **Attempt/Resume** | One interaction within a job. A job may have multiple attempts via `resume`. All attempts share the same Claude session, so Claude retains full history. |

## Handoff Prompt Template

```text
<role>
You are Claude Code working as a subordinate agent.
state-id: ......
state-root: ......
</role>

<task>
[Specific expected output. Clearly define what "done" looks like.]
</task>

<context>
- Working directory: [...]
- Relevant file paths: [...] (provide paths, not full content)
- Known constraints: [...]
</context>

<operating_rules>
- Read the repository and relevant files first; verify assumptions before acting.
- Stay within the requested scope; avoid unrelated work.
- For explanatory tasks, output to a markdown file inside state-root and return the path.
</operating_rules>

<deliverable>
- Describe what you changed or learned.
- List the files you touched.
- Explain how you verified the results.
- Note any uncertainties or follow-up work.
</deliverable>
```

If the prompt needs Claude to know generated paths up front, use placeholders instead of manually fixing `state_id`:

- `{{STATE_ID}}`
- `{{STATE_ROOT}}`
- `{{JOB_ID}}`
- `{{JOB_DIR}}`
- `{{WORKDIR}}`
- `{{SESSION_ID}}`

The orchestrator expands those placeholders before Claude starts.
It also automatically adds `state_root` to Claude's allowed directories. Use `--add-dir` only for extra paths outside `workdir` and `state_root`.

**Prompt writing tips**:
- Provide file paths and let Claude read them itself—it is an agent with investigation capabilities; you do not need to copy content into the prompt
- When incorrect output is costly, include verification instructions in the task
- When comparing multiple tasks, keep each prompt's scope independent

## Operating Rules

- **One task, one focus**: each launch corresponds to a limited-scope task. Unrelated work should be launched as separate tasks and tracked independently.
- **Review after completion**: wait for Claude Code to finish before reviewing; do not intervene midway.
- **Use one-pass prompts**: write prompts that Claude can finish without follow-up interaction.

## Command Reference

### launch

```bash
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py launch \
  --prompt "task description" \   # or --prompt-file path, or stdin
  --workdir /abs/path/to/repo \
  --model opus \                  # opus (recommended) or sonnet (cheaper)
  --effort high \
  --add-dir /extra/dir \          # additional accessible directory
  --replace \                     # replace a stopped task with the same id
  --dry-run                       # generate command only, do not execute
```

Add `--state-id` only when you intentionally want multiple launches to share one state.
Design prompts so Claude can finish in one pass.

After running, the following fields are printed:
```text
job_id: ...
state_id: ...
state_root: ...
status: ...
session_id: ...
command: ...
```

### status

```bash
# All tasks
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py status \
  --state-id STATE_ID

# Single task + view both stdout and stderr
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py status JOB_ID \
  --state-id STATE_ID --tail 30 --tail-both
```

### resume

```bash
python ~/.codex/skills/claude-for-codex/scripts/claude_orchestrator.py resume JOB_ID \
  --state-id STATE_ID \
  --message "follow-up instructions" \
  --model opus \   # optional override
  --effort high    # optional override
```

All commands support `--json` for JSON-formatted output.

## Task Directory Structure

```
<system temp dir>/codex-claude-code-orchestrator-state-<state_id>/
├── registry.json              # Summary index of all tasks
└── jobs/JOB_ID/
    ├── job.json               # Task metadata and attempt history
    ├── settings.json          # Claude settings
    ├── prompt.txt             # Launch prompt
    ├── attempt-NNNN-input.txt # Input for resume attempts
    ├── stdout.log             # Claude stdout
    ├── stderr.log             # Claude stderr
    └── output_doc_v1.md       # Document written for the user
```
