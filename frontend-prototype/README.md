# Frontend Prototype

This directory contains the extracted PolicyManus frontend prototype.

## Contents

- `ui-source/`: Next.js frontend source used as the PolicyManus UI prototype.
- Design screenshots are included under `ui-source/docs/design`.

## Excluded

The extraction intentionally excludes local/runtime artifacts:

- `node_modules/`
- `.next/`
- `.env.local`
- `.env.production`
- editor/assistant local folders such as `.claude/` and `.cursor/`

## Run

```powershell
cd E:\workspace\policy_manus\frontend-prototype\ui-source
npm install
npm run dev
```

## Mock Mode

The extracted prototype uses a local mock session API by default, so the task list,
new task flow, session detail view, and chat streaming demo can run without the
PolicyManus backend.

To switch session APIs back to a real backend, create `ui-source/.env.local`:

```env
NEXT_PUBLIC_USE_MOCK_SESSION_API=false
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

Then restart `npm run dev`.
