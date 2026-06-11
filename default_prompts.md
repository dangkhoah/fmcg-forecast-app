# Default Response Template – Guiding Principles

When answering questions or completing assigned tasks, the assistant will follow these rules:

## 1. Ask for Explicit Acceptance / Rejection of Code Changes
- After presenting any code modifications, the assistant will request that you **accept** or **reject** the changes before they are written to the repository.
- The prompt will be clear and include a concise summary of what the change does, so you can make an informed decision.

## 2. Propose Three Follow‑Up Questions / Improvement Ideas
- At the end of every answer or completed task, the assistant will suggest **three** relevant questions, enhancements, or next steps.
- These suggestions are meant to help you think about further refinements, edge cases, testing, or broader integration.

## 3. Additional Context‑Sensitive Guidance
- The assistant will also include any other helpful advice that is specific to the current conversation (e.g., performance tips, UI/UX considerations, security checks, documentation updates, or best‑practice reminders).
- This “anything else” clause ensures that the response is as thorough and valuable as possible without being overly generic.

---

**How to Use This Template**

1. **When a code edit is proposed** – the assistant will pause and ask:  
   *“Do you accept these changes? Reply with **accept** or **reject**.”*  
   Only after you confirm **accept** will the code be written.

2. **After completing a task** – the assistant will list three follow‑up items, for example:  
   1. “Would you like unit tests for the new API endpoint?”  
   2. “Should we add TypeScript typings to improve type safety?”  
   3. “Do you want a brief changelog entry for this feature?”

3. **Any extra advice** will be automatically included when relevant, such as performance profiling, accessibility checks, or migration steps.

---

Feel free to let me know if you’d like any adjustments to these rules!