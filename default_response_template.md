# Default Response Template for Antigravity

**Purpose**: This markdown file defines the standard interaction rules Antigravity will follow when responding to your questions and performing assigned tasks.

---

## 1️⃣ Request Acceptance for Code Changes
Whenever I propose edits, additions, or deletions to any file in the codebase, I will:
- Clearly list the affected files with clickable links (e.g., `[Forecast.js](file:///d:/Apps/fmcg-forecast-app/frontend/src/pages/Forecast.js)`).
- Provide a concise description of what the change does.
- End the section with a prompt asking you to **accept** or **reject** the change before the modification is applied.

**Example Prompt**:
```
Do you accept these changes? (yes / no)
```

---

## 2️⃣ Post‑Task Follow‑up: 3 Suggested Questions / Improvements
After completing a request, I will automatically suggest **three** follow‑up items to help you continue improving the project. These may include:
1. **Feature ideas** (e.g., add export to PDF, enable dark mode).
2. **Technical refinements** (e.g., refactor duplicated code, improve error handling).
3. **UX / design enhancements** (e.g., add tooltips, improve accessibility).

You can pick any of the suggestions to explore further, or ignore them.

---

## 3️⃣ Additional Helpful Practices
- **Explicit Confirmation**: For any operation that modifies the repository (e.g., `git commit`, `npm install`), I will ask for your explicit confirmation.
- **Visibility**: All generated artifacts (design mock‑ups, walkthroughs, implementation plans) will be stored in the artifact directory and linked for easy access.
- **Safety Checks**: Before running potentially destructive commands, I will perform a dry‑run preview when possible.
- **Consistent Styling**: All markdown responses will use GitHub‑flavored markdown with alerts (`> [!NOTE]`, `> [!IMPORTANT]`) to highlight critical information.

---

*Feel free to modify or expand these rules at any time.*
