# Component Guide: `.agent/`

Scope: ExecPlans, planning templates, and related guidance.

Gotchas and expectations:
- Keep every ExecPlan compliant with `.agent/PLANS.md` (living document sections, self-contained instructions, ASCII text, and no nested code fences).
- Active plans stay in `.agent/in_progress/`; once fully populated (Progress/Surprises/Decision Log/Outcomes up to date and work validated), move them to `.agent/complete/` and adjust any pointers in README/CHANGELOG.
- When you revise a plan, update `Progress`, `Decision Log`, `Surprises & Discoveries`, and `Outcomes & Retrospective` in the same edit; note dates so future contributors see the timeline.
- Use clear absolute paths and commands so a new contributor can execute the plan without prior repo knowledge.
- If a plan’s status or directory structure changes, reflect it in README and the changelog to avoid drift.
