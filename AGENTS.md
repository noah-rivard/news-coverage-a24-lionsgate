# Repo Rules for Agents

- Add all updates to CHANGELOG and modify README to reflect the new structure/function of the repo once all tasks are complete.
- Run tests (`pytest`) and linter (`flake8`) for every code change except when modifying documentation or comments.
- When possible, return results as a brief overview of work done and a list of decisions, if any, that need to be made with some very brief context. Decisions should be in a numbered list.
- When appropriate, feel free to proactively suggest changes in code architecture or syntax that would increase efficiency or further the goals of this repo.
- When responding to the user, when possible, translate the language into non-coding terms. The user does not have a technical background.

# API usage
When calling the OpenAI API, default to the Responses API over the Completions API.

# ExecPlans
When writing complex features or significant refactors, use an ExecPlan (as described in .agent/PLANS.md) from design to implementation.

# Component AGENTS
Each major area of the repo now carries its own `AGENTS.md` with gotchas for that slice of the system. Before changing files inside one of those directories, read (and, if needed, update) the colocated guide so future contributors inherit the latest context. If you touch a section that lacks an `AGENTS.md`, add one that documents the risks you observed.

Current component guides:

Keep these files in sync with the code they describe; any change that alters behavior in a component should be reflected in both the implementation and that component's `AGENTS.md`.
