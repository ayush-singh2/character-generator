# Blue Balloon frontend API contract

This is the definitive contract for the audited frontend. The repository contains no backend routes, controllers, database, authentication implementation, or API tests. Every endpoint below is therefore **❌ REQUIRED**. No endpoint is marked “exists” unless it was verified in the repository.

The frontend currently works offline with browser storage. The backend should replace that storage behind the same UI flows. Use cookie-based sessions when authentication is introduced; do not put access tokens in storybook documents or local storage.

## Master endpoint table

| Module | Method | Endpoint | Purpose | Used By | Status |
| --- | --- | --- | --- | --- | --- |
| Storybooks | GET | `/api/storybooks` | Load the user’s library | Home / Storybook Library | ❌ REQUIRED |
| Storybooks | POST | `/api/storybooks` | Create a storybook from setup choices | New Storybook | ❌ REQUIRED |
| Storybooks | GET | `/api/storybooks/:storybookId` | Load the full editable document | Workspace bootstrap | ❌ REQUIRED |
| Storybooks | PATCH | `/api/storybooks/:storybookId` | Autosave document changes | Workspace, manuscript, settings | ❌ REQUIRED |
| Storybooks | POST | `/api/storybooks/:storybookId/sync` | Batch save with revision conflict protection | Future offline sync | ❌ REQUIRED |
| Characters | GET | `/api/storybooks/:storybookId/characters` | Load cast and design metadata | Characters panel | ❌ REQUIRED |
| Characters | POST | `/api/storybooks/:storybookId/characters` | Add a character | Characters panel | ❌ REQUIRED |
| Characters | PATCH | `/api/storybooks/:storybookId/characters/:characterId` | Update role, design, or variants | Characters / Character Design | ❌ REQUIRED |
| Characters | DELETE | `/api/storybooks/:storybookId/characters/:characterId` | Remove a character | Characters panel | ❌ REQUIRED |
| Assets | POST | `/api/storybooks/:storybookId/assets/upload-url` | Create a signed upload target | Image and manuscript uploads | ❌ REQUIRED |
| Assets | POST | `/api/storybooks/:storybookId/assets/complete` | Commit an uploaded asset | Image and manuscript uploads | ❌ REQUIRED |
| Assets | DELETE | `/api/storybooks/:storybookId/assets/:assetId` | Remove an unused upload | Future asset cleanup | ❌ REQUIRED |
| AI | POST | `/api/storybooks/:storybookId/ai/complete` | Apply structured assistant actions | Canvas AI assistant | ❌ REQUIRED |
| AI | POST | `/api/storybooks/:storybookId/ai/scene` | Generate a scene result | Scene builder | ❌ REQUIRED |
| AI | GET | `/api/storybooks/:storybookId/ai/tasks/:taskId` | Poll asynchronous generation | Scene builder / Character Design | ❌ REQUIRED |
| AI | POST | `/api/storybooks/:storybookId/ai/manuscript` | Generate a manuscript suggestion | Manuscript assistant | ❌ REQUIRED |
| AI | POST | `/api/storybooks/:storybookId/ai/character-design` | Generate a character design result | Character Design | ❌ REQUIRED |
| Sharing | POST | `/api/storybooks/:storybookId/share-links` | Create a read-only share link | Share dialog | ❌ REQUIRED |
| Sharing | GET | `/api/shared/:shareToken` | Load a public read-only storybook | Future shared reader | ❌ REQUIRED |
| Sharing | PATCH | `/api/storybooks/:storybookId/share-links/:shareToken` | Change access or download policy | Share management | ❌ REQUIRED |
| Sharing | DELETE | `/api/storybooks/:storybookId/share-links/:shareToken` | Revoke a link | Share management | ❌ REQUIRED |

There is **no backend endpoint required** for Preview Book, local PDF export, local PNG ZIP export, or local crop-mark rendering. Those are client-side capabilities in the current implementation. A server export service can be added later for print-grade rendering, but it is not needed to make this frontend functional.

## Contract details

### Storybooks

**List storybooks** — `GET /api/storybooks` replaces the Home page’s local project list. It is used by `src/pages/Home.jsx` and accepts `search`, `sort=updatedAt|title`, `page`, and `limit`. Authentication is required once accounts exist and may be optional for an anonymous demo tenant. Response:

```json
{"items":[{"id":"stb_123","title":"The Lantern Boy","style":"Storybook Illustration","updatedAt":"2026-09-17T10:30:00Z"}],"page":1,"limit":24,"total":1}
```

Errors: `401`, `422`, `500`.

**Create storybook** — `POST /api/storybooks` replaces `createProject()` in `src/services/projects.js`. Authentication is required for cloud persistence. Body:

```json
{"name":"The Lantern Boy","author":"Ava","size":"A4","orientation":"Vertical","length":"32 pages","style":"Storybook Illustration","pageNums":true,"aesthetic":"Warm and magical"}
```

Return `201` with `{ "id": "stb_123", "title": "The Lantern Boy", "settings": {}, "revision": 1 }`; returning the full initial document is preferred. Errors: `400`, `409`, `422`, `500`.

**Read storybook** — `GET /api/storybooks/:storybookId` replaces `loadDoc()` in `src/editor/workspace.js`. Authentication is required for private books. Path parameter: `storybookId: string`. Response:

```json
{"id":"stb_123","revision":12,"settings":{"name":"The Lantern Boy","author":"Ava","size":"A4","orientation":"Vertical","length":"32 pages","style":"Storybook Illustration","pageNums":true,"aesthetic":"Warm and magical","theme":{}},"pages":[{"id":"pg_1","name":"Cover","kind":"cover","background":"#4a1512","layout":"title","elements":[]}],"manuscript":{"sections":[{"id":"ch_1","title":"Chapter One","kind":"chapter","html":"<p>…</p>","pageId":"pg_2"}]},"characters":[{"id":"char_1","name":"Ram","role":"Protagonist","mode":"constant","design":{},"variants":[]}]}
```

Errors: `401`, `403`, `404`, `500`.

**Save storybook document** — `PATCH /api/storybooks/:storybookId` replaces the debounced local autosave. It is used by canvas edits, page add/duplicate/delete/reorder, cover edits, manuscript edits, settings, book style, and project rename. Authentication is required. Body is partial and includes the revision read by the client:

```json
{"revision":12,"settings":{"name":"The Lantern Boy"},"pages":[{"id":"pg_2","name":"Page 1","elements":[]}],"manuscript":{"sections":[]},"characters":[]}
```

Element records include `id`, `kind`, `label`, `x`, `y`, `w`, optional `h`, `z`, `opacity`, `rotation`, text formatting, `assetId`, and `effect`. Return `200` with `{ "revision": 13, "updatedAt": "2026-09-17T10:31:00Z" }`. Errors: `401`, `403`, `404`, `409` revision conflict (include the latest document), `422`, `500`.

**Sync offline document** — `POST /api/storybooks/:storybookId/sync` is the future batch replacement for local queued edits. Authentication is required. Body: `{ "baseRevision": 12, "operations": [{"op":"replace-page","pageId":"pg_2","value":{}}] }`. Response: `{ "revision": 13, "applied": 1, "conflicts": [] }`. Errors: `401`, `403`, `404`, `409`, `422`, `500`.

There is currently no delete-project button in the frontend, so a project delete endpoint is not required by this UI.

### Characters

`GET /api/storybooks/:storybookId/characters` returns `{ "items": [], "total": 0 }` for the Characters panel. `POST /api/storybooks/:storybookId/characters` accepts `{ "name":"Ram", "role":"Protagonist", "mode":"constant|variants", "design":{}, "variants":[] }` and returns `201` with the character. `PATCH /api/storybooks/:storybookId/characters/:characterId` accepts those fields partially and returns the updated character plus `revision`. `DELETE /api/storybooks/:storybookId/characters/:characterId` returns `204`.

All require authentication and can return `401`, `403`, `404`, `409`, `422`, or `500`. The current Character Design screen stores a data URL; the backend version must store an `assetId` instead.

### Assets and uploads

**Create upload target** — `POST /api/storybooks/:storybookId/assets/upload-url` is used by canvas images, character references, cover illustrations, page illustrations, and manuscript files. Authentication is required. Body: `{ "filename":"ram.png", "contentType":"image/png", "size":245000, "purpose":"character-reference|page-image|cover-image|manuscript" }`. Response: `{ "assetId":"ast_123", "uploadUrl":"https://storage…", "method":"PUT", "headers":{"Content-Type":"image/png"}, "expiresAt":"2026-09-17T10:40:00Z" }`. Errors: `400`, `401`, `403`, `413`, `415`, `422`, `500`.

**Complete upload** — `POST /api/storybooks/:storybookId/assets/complete` verifies the object-store upload. Body: `{ "assetId":"ast_123", "etag":"…", "width":1024, "height":1024 }`. Response: `{ "id":"ast_123","url":"https://cdn…","mimeType":"image/png","size":245000,"status":"ready" }`. Errors: `401`, `403`, `404`, `409`, `422`, `500`.

**Delete asset** — `DELETE /api/storybooks/:storybookId/assets/:assetId` returns `204` and cleans up replaced or abandoned uploads. Errors: `401`, `403`, `404`, `409` when still referenced.

### AI

All AI endpoints require authentication, project access, rate limiting, and provider-side usage controls. The provider/model is a backend concern.

**Canvas assistant** — `POST /api/storybooks/:storybookId/ai/complete`, used by the assistant dock in `src/editor/workspace.js`. Body: `{ "pageId":"pg_2", "prompt":"Make the lantern warmer", "scope":{"elementIds":["el_3"]}, "attachments":["ast_123"] }`. Response: `{ "reply":"I warmed the lantern illustration.", "actions":[{"op":"setColor","id":"el_3","color":"#f3b85e"}], "usage":{"inputTokens":120,"outputTokens":48} }`. Only existing element IDs may be returned. Errors: `401`, `403`, `404`, `409`, `422`, `429`, `502`, `503`.

**Scene generation** — `POST /api/storybooks/:storybookId/ai/scene`, used by Scene Builder. Body: `{ "pageId":"pg_2", "prompt":"Ram finds the hidden gate", "characterIds":["char_1"], "previousPageIds":["pg_1"] }`. Response: `{ "heading":"The Hidden Gate", "text":"…", "assetId":"ast_456", "taskId":"task_123" }`. For asynchronous work, add `GET /api/storybooks/:storybookId/ai/tasks/:taskId` returning `{ "status":"running|ready|error", "result":{}, "error":null }`. Errors: `401`, `403`, `404`, `422`, `429`, `502`, `503`.

**Manuscript suggestion** — `POST /api/storybooks/:storybookId/ai/manuscript`, used by the Manuscript assistant. Body: `{ "sectionId":"ch_1", "action":"rewrite|continue|shorten|tone", "tone":"gentle", "selection":"…", "html":"<p>…</p>" }`. Response: `{ "suggestion":"…", "format":"plain-text" }`. Errors: `401`, `403`, `404`, `422`, `429`, `502`, `503`.

**Character design** — `POST /api/storybooks/:storybookId/ai/character-design`, used by Character Design and the workspace’s Design with AI action. Body: `{ "characterId":"char_1", "description":"A curious boy…", "referenceAssetIds":["ast_123"], "variantId":null }`. Response: `{ "taskId":"task_789", "assetIds":["ast_800"], "design":{"description":"…"} }`. Errors: `401`, `403`, `404`, `422`, `429`, `502`, `503`.

### Sharing

**Create share link** — `POST /api/storybooks/:storybookId/share-links`, used by the Share dialog. Authentication: owner/editor required. Body: `{ "access":"anyone|invited", "allowDownload":false, "expiresAt":null }`. Response `201`: `{ "token":"sh_abc123", "url":"https://read.example/s/sh_abc123", "access":"anyone", "allowDownload":false, "expiresAt":null }`. Errors: `401`, `403`, `404`, `422`, `500`.

**Read shared book** — `GET /api/shared/:shareToken` powers the future read-only reader, which is not yet a frontend route. Authentication is public for `anyone` links and invitation-session based for `invited` links. Response: `{ "storybook":{"title":"…","pages":[],"theme":{}}, "allowDownload":false }`. Errors: `403`, `404`, `410`, `500`.

**Update share link** — `PATCH /api/storybooks/:storybookId/share-links/:shareToken` accepts `{ "access":"invited", "allowDownload":true, "expiresAt":"2026-10-01T00:00:00Z" }` and returns the updated link. **Revoke share link** — `DELETE /api/storybooks/:storybookId/share-links/:shareToken` returns `204`. Both require owner/editor access and return `401`, `403`, `404`, `409`, `422`, or `500`.

## Frontend to Backend Mapping

### Storybook Library

The frontend currently reads `bb_projects` from local storage, filters and sorts in the browser, and opens a local project. Replace reads with `GET /api/storybooks`. The New Storybook flow writes a generated ID and setup object locally; replace it with `POST /api/storybooks` and navigate with the returned ID. No delete-project button exists today.

### Workspace, Pages, Canvas, Cover, Book Style, and Settings

The workspace loads generated sample pages through `loadDoc()` and saves `{settings,pages,manuscript,chars}` locally. Replace initial load with `GET /api/storybooks/:storybookId` and debounced save with `PATCH /api/storybooks/:storybookId`. Page add, duplicate, delete, reorder, element drag/resize, cover edits, style edits, and project renames can remain one versioned document PATCH.

### Manuscript

The manuscript editor derives chapters from the local document, sanitizes HTML with DOMPurify, and saves through the same document save. Send `manuscript.sections` in the storybook PATCH. Only an accepted AI suggestion should be saved.

### Characters and Character Design

The panel and Character Design screen read/write `bb_characters`, with reference images stored as data URLs and a regeneration flag locally. Replace roster reads/writes with character CRUD. Upload the image through the signed asset flow, then store `assetId` in the character record. AI design maps to `/ai/character-design`.

### AI assistant and scene generation

Frontend sends storybook ID, page ID, selected element IDs, prompt, prior-page context, character IDs, and asset IDs → backend AI endpoint → provider/model → structured response → frontend validates actions and applies them → document PATCH. Scene generation uses the same pattern and may be asynchronous through an AI task resource.

### Preview and Export

Preview reads the in-memory document. PDF and PNG ZIP export run locally with `html-to-image`, `jsPDF`, and `JSZip`. **No backend endpoint is required.** Server export is only a later option for print production, CMYK, or long-running jobs.

### Share

The current dialog explicitly explains that online sharing is unavailable and offers local export; it does not create a fake URL. Replace the disabled state with share-link creation, and add the shared-reader route before exposing `GET /api/shared/:shareToken`.

## Current Local Implementations To Replace

| File | Current behavior | Future API | Offline cache after integration? |
| --- | --- | --- | --- |
| `src/services/storage.js` | Browser `localStorage` JSON and image data | Storybook, character, and asset APIs | Yes, as a versioned draft cache |
| `src/services/projects.js` | `crypto.randomUUID()` project IDs and local setup | `GET/POST /api/storybooks` | Yes, for unsynced drafts |
| `src/editor/workspace.js` | Sample pages and debounced local document saves | `GET/PATCH /api/storybooks/:storybookId`, `/sync` | Yes, with revision metadata |
| `src/editor/characters.js` | Cast and design metadata in `bb_characters` | Character CRUD | Yes, as stale-read cache |
| `src/pages/CharacterDesign.jsx` | Reference image stored as data URL | Signed upload + character PATCH | Temporarily |
| `src/editor/workspace.js` | Canvas upload uses object/data URLs directly | Signed upload + document PATCH with `assetId` | Temporarily |
| `src/editor/scene-builder.js` | Canned fallback scenes and simulated progress | AI scene + task status | No; retain an explicit unavailable state |
| `src/editor/manuscript.js` | Local rewrite fallback suggestions | AI manuscript | No; preserve original text |
| `src/services/ai.js` | Always throws because no provider is connected | AI routes | No |
| `src/components/ExportDialogs.jsx`, `src/services/export.js` | Local PDF/PNG ZIP | No endpoint required | N/A |
| `sessionStorage` in workspace/preview | Assistant callout and preview preference | No endpoint required | Yes |

## Data and security requirements

Treat a storybook as a versioned aggregate. Validate page element bounds, asset ownership, sanitized manuscript HTML, and character IDs on every save. Return `409` with the latest revision on concurrent edits. Asset URLs should be signed/private and never accepted as arbitrary HTML. AI actions must be constrained to requested page and element IDs before persistence. Public share responses must strip editor metadata, private asset paths, teammate data, and unpublished revisions.
