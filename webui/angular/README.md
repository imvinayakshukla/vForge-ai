# VForge Angular Console

An Angular implementation of the VForge developer console. It consumes the
same console API (`/api/*`, `/health`) as the built-in single-file console,
so it is a **drop-in replacement** — and a starting point for your own UI:
copy this workspace into your agent application and customise freely.

Tabs: Chat, Agents, Tools, Prompts, Skills, Sessions, Logs, Metrics, Health,
Config.

## Requirements

- Node.js 18.19+ (or 20+)
- npm

## Develop (live reload against a running agent)

Terminal 1 — start your agent app:

```bash
cd your-agent-app
vforge start                     # serves the API on :8000
```

Terminal 2 — start the Angular dev server:

```bash
cd webui/angular
npm install
npm start                        # http://localhost:4200, proxies /api → :8000
```

## Build & serve through VForge

```bash
cd webui/angular
npm install
npm run build                    # outputs dist/vforge-console/browser/
```

Point your application at the build via `server.ui_dir` in
`application.yaml` (path is relative to the app directory):

```yaml
server:
  port: 8000
  ui_dir: ../../webui/angular/dist/vforge-console/browser
```

Restart `vforge start` — the Angular console is now served at `/`, replacing
the built-in one. `/a2a`, `/health` and `/api/*` are unaffected; when
`auth.api_key` is set, UI assets stay public and only `/api` + `/a2a`
require the key.

## Customising / overriding

Two supported paths:

1. **Fork this workspace** — copy `webui/angular` into your agent repo, edit
   components (`src/app/*.ts`), rebuild, and keep `ui_dir` pointed at your
   build. `api.service.ts` is the only file that talks to the backend.
2. **Bring any framework** — `ui_dir` serves any static build (React, Vue,
   plain HTML). The contract is just the console API, documented in
   [docs/api-reference.md](../../docs/api-reference.md).

## Layout

```
src/
├── main.ts                  # bootstrap + HttpClient provider
├── styles.css               # shared dark theme (matches the built-in console)
└── app/
    ├── app.component.ts     # shell: header, tabs, routing between panels
    ├── chat.component.ts    # chat tab (agent picker, session, send loop)
    ├── panel.component.ts   # all read-only data tabs
    └── api.service.ts       # typed client for the console API
```
