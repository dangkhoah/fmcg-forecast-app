# FMCG Forecast App

## Project Overview

This repository contains a full‑stack application for forecasting FMCG sales. It includes a FastAPI backend, a React frontend, and a model‑service for generating forecasts.

## Interaction Policy

The project now includes a **`.cursorrules`** file that defines how the Antigravity assistant should interact with the codebase.

- **Acceptance Prompt** – All code changes are presented with file links and a brief description. You must explicitly **accept** or **reject** before any modification is applied.
- **Follow‑up Suggestions** – After each completed task, the assistant provides **three** follow‑up ideas (feature ideas, technical refinements, UI/UX enhancements).
- **Repository‑modification Confirmation** – Any git, npm, or other commands that change the repository require your confirmation first.
- **Artifact Management** – All generated artifacts (design mocks, implementation plans, walkthroughs) are stored in the Antigravity brain artifact folder.
- **Markdown Style** – Responses use GitHub‑flavored markdown with alerts for clear visual cues.

You can edit `.cursorrules` to customise these behaviours. See the file for the full set of options.

---

## Getting Started

```bash
# Install backend dependencies
cd backend
pip install -r requirements.txt

# Install frontend dependencies
cd ../frontend
npm install

# Run development servers
npm run dev   # frontend (Vite)
uvicorn app.main:app --reload   # backend FastAPI
```

---

## Contributing

When contributing, ensure that the `.cursorrules` policies are respected. Any pull request should be reviewed for compliance with the acceptance prompts and follow‑up guidelines.
