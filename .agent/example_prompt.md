---
# Initial Explanation Stage

Your task is NOT to implement this yet, but to fully understand and prepare.

Here is exactly what I need implemented:

XXXX

--

Your responsibilities:

- Analyze and understand the existing codebase thoroughly.
- Determine exactly how this feature integrates, including dependencies, structure, edge cases (within reason, don't go overboard), and constraints.
- Clearly identify anything unclear or ambiguous in my description or the current implementation.
- List clearly all questions or ambiguities you need clarified.

Remember, your job is not to implement (yet). Just exploring, planning, and then asking me questions to ensure all ambiguities are covered. We will go back and forth until you have no further questions. Do NOT assume any requirements or scope beyond explicitly described details.
---

Once you've answered all of GPT-5's questions and it has nothing more to ask, paste in this prompt:

---
# Plan Creation Stage

Based on our full exchange, now, produce an ExecPlan

Again, for clarity, it's still not time to build yet. Just write the clear plan document. No extra complexity or extra scope beyond what we discussed. The plan should lead to simple, elegant, minimal code that does the job we want it to (exactly as we intend).
---

Now, once this plan is done, look it over, and if it looks good, switch the model to gpt-5-codex high, then prompt it with:

---
Now implement precisely as planned, in full.

Implementation Requirements:

- Write elegant, minimal, modular code.
- Adhere strictly to existing code patterns, conventions, and best practices.
- Include thorough, clear comments/documentation within the code.
- As you implement each step:
  - Update the ExecPlan (the markdown tracking document) and overall progress dynamically.
---