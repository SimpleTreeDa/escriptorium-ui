# AI Chat tab: implementation plan

Status: plan, nothing implemented yet. Written 2026-10-07 after a survey of the
code and a probe of the LM Studio server.

## What we are building

A new **AI Chat** entry in the left navigation, under Tasks, that opens a page
where a signed-in user can ask questions about their projects, documents,
tasks and recent activity. The answers come from the Qwen 3.6 model served by
LM Studio on the LAN, through an OpenAI-compatible chat-completions API.

The browser never talks to LM Studio. It talks to a new Django endpoint, which
builds a snapshot of the user's projects and tasks, sends it to the model with
the conversation, and returns the answer. See "Decisions" for why.

## What exists today (survey)

**Navigation.** The left bar is one Vue component,
`front/vue/components/GlobalNavigation/GlobalNavigation.vue`, mounted by
`base.html` on every page for users not in legacy mode. Entries are plain
links (Projects, Models) or a `VMenu` popover (Search, Tasks, Profile). "Active"
state is computed from `window.location`. Icons are small SVG components under
`front/vue/components/Icons/<Name>Icon/`. Legacy-mode users get a Bootstrap
navbar rendered by Django instead.

**Pages.** Each new-UI page is a Django `TemplateView`/`DetailView` whose
template mounts a Vue app on a div and loads a dedicated webpack bundle
(`project_dashboard.html` + `vue/exports/projectDashboard.js` +
`webpack.common.js` entry). Pages share the Vuex store in
`front/vue/store/index.js`, one module per concern, and the `EscrPage`
shell, which also renders toasts and opens the notification websocket.

**API.** Django REST Framework, routed in `app/apps/api/urls.py` under `/api/`,
session or token auth, `IsAuthenticated` by default, CSRF cookie sent by axios
(`front/src/api/index.js` sets the base URL and the `X-CSRFToken` header).
The frontend API client is one function per endpoint under `front/src/api/`.

**Project and task data available to a user** (all already permission-scoped):

| Data | Where | Notes |
| --- | --- | --- |
| Projects | `Project.objects.for_user_read(user)` | name, slug, owner, tags, guidelines URL, timestamps, document count |
| Documents | `Document.objects.for_user(user)` | name, project, owner, Draft/Published state, script, transcription layers, tags, timestamps |
| Pages (parts) | `DocumentPart` per document | `workflow_state` (Created … Segmented, Transcribing, Aligned), `editorial_status` (Not started, In progress, Initial transcription complete, Reviewed by Editor 1/2, Ground truth, Final, Ready for TEI), `updated_at` |
| Tasks | `TaskReport` (filtered by `user`) and `TaskGroup` per document | method (`core.tasks.transcribe` …), Queued/Running/Crashed/Finished/Canceled, queued/started/done times, log `messages` |
| Models | `OcrModel` | `training` flag, job type |

The task monitoring page (`/documents/tasks/`) reads `/api/documents/tasks/`;
the editor's task status reads `/api/tasks/` and hides automatic tasks
(`front/src/editor/taskStatus.js` lists them). The AI context will reuse that
hidden list.

**Tests.** Backend: Django `TestCase`/`CoreFactoryTestCase` with
`core/tests/factory.py`, run per app (`manage.py test users api versioning
imports core` in `.gitlab-ci.yml`), plus flake8 (120 cols) and isort. On this
Windows machine the suite runs inside the `escr-sp-test:kraken6` container.
Frontend: `npm test` in `front/` runs `node --test tests/**/*.test.mjs` with no
other dependency, so only pure modules (no DOM, no axios) are unit-tested, for
example `front/src/taskGroups.js` and `front/src/editor/taskStatus.js`.

**Deployment.** nginx proxies `/` to uwsgi (`web:8000`) and `/ws/` to daphne.
`app/uwsgi.ini` sets no `processes` or `threads`, so uwsgi runs a single
synchronous worker. nginx's uwsgi read timeout is the default 60 s.

**LM Studio (probed 2026-10-07 from this machine).** `GET /v1/models` answers
without an API key and lists `qwen3.6-35b-a3b-m5` (plus `qwen/qwen3.8-27b`,
`google/gemma-4-31b`, `google/gemma-4-12b-qat`, and an embedding model).
A chat completion returns the standard shape, with the model's reasoning in a
separate `reasoning_content` field and a clean `content`. In the probe the
reasoning used 145 of a 150-token budget, so `max_tokens` must be generous or
the answer is cut off. The response also carries `tool_calls: []`, so function
calling is available for later.

## Decisions

1. **Requests go browser → Django → LM Studio.** Reasons: LM Studio has no
   authentication, so a direct browser call would expose an open LAN endpoint
   to anyone who can load the page. The project context is built where the
   data and the permission rules live. The browser keeps using the existing
   same-origin API with session auth and CSRF, so no CORS setup anywhere.
   The URL and model name stay out of client code and error messages.
2. **uwsgi needs more than one worker.** Each chat call holds a worker for
   the model's full generation time (several seconds to a minute). With the
   current single worker, one question would stall every other request on the
   instance. Set `processes = 2` and `threads = 4` (with `enable-threads`) in
   `app/uwsgi.ini` as part of this change. This is an infrastructure change
   and should be agreed before implementation. A Celery-backed asynchronous
   design (queue the call, deliver the answer over the existing notification
   websocket) is the fallback if latency grows; it is listed under
   "Later", not built now.
3. **Timeouts.** The server-side call to LM Studio times out at 55 s, under
   nginx's 60 s, and returns a readable error instead of a 504.
4. **Stateless conversations.** The browser sends the whole history on every
   request. The server caps it (last 20 messages, 8 000 characters each) and
   drops any `system` message a client sends, so the system prompt cannot be
   overridden. Persistence later is an additive change.
5. **Context is a compact structured snapshot, not retrieval.** All questions
   in scope ("what is happening", "open tasks", "what next", "what changed")
   are answered from project, document, page-status and task metadata, which
   fits in a few thousand tokens. No vector store. Document *text* is out of
   scope for v1.
6. **Configuration lives in one place in `settings.py`** as literal values
   (the brief asks for hard-coded). Moving to environment variables later is
   wrapping each value in `os.getenv`.
7. **New Django app `assistant`** rather than more code in the 1 500-line
   `api/views.py`. No models in v1, so no migration. It is the natural home
   for conversation models, tools and other providers later.
8. **Naming.** Tab label "AI Chat", page at `/assistant/`, API at
   `/api/assistant/chat/`. The product name is in flux (Transcriptus rebrand
   in PR #94), so the system prompt keeps the name in one string.
9. **No new dependencies.** The backend uses `requests` (already used by
   imports); the frontend uses axios and the existing components. Model
   answers render as plain text with preserved line breaks, never through
   `v-html`.

## Files

### Backend, new

| File | Purpose |
| --- | --- |
| `app/apps/assistant/__init__.py`, `apps.py` | App registration |
| `app/apps/assistant/client.py` | `ChatProvider` interface, `OpenAICompatibleProvider` (requests, timeout, error mapping), `ProviderError`, `get_provider()` built from settings |
| `app/apps/assistant/context.py` | `build_context(user, project=None, now=None)` returning a dict, and `render_context(ctx)` returning the text block for the prompt |
| `app/apps/assistant/prompts.py` | `SYSTEM_PROMPT` template and `system_message(user, context_text, now)` |
| `app/apps/assistant/serializers.py` | `ChatRequestSerializer` (messages, optional project) |
| `app/apps/assistant/views.py` | `AssistantPage` (login-required TemplateView) and `ChatView` (DRF APIView) |
| `app/apps/assistant/urls.py` | `path('assistant/', AssistantPage)` |
| `app/apps/assistant/tests/__init__.py`, `test_client.py`, `test_context.py`, `test_views.py` | See Testing |
| `app/escriptorium/templates/assistant/chat.html` | Extends `base.html`, mounts `<ai-chat>` with the display name as a prop; legacy mode shows the same "not available in legacy mode" text as the project dashboard |

### Backend, changed

| File | Change |
| --- | --- |
| `app/escriptorium/settings.py` | Add `'assistant'` to `INSTALLED_APPS`; add the `ASSISTANT` dict (below); optional throttle rate |
| `app/escriptorium/urls.py` | `path('', include('assistant.urls'))` |
| `app/apps/api/urls.py` | `path('assistant/chat/', ChatView.as_view(), name='assistant-chat')` so the endpoint lives under the `api` namespace like everything else |
| `app/uwsgi.ini` | `processes`, `threads`, `enable-threads` (decision 2) |
| `.gitlab-ci.yml` | Add `assistant` to the tested apps |
| `.isort.cfg` | Add `assistant` to `known_first_party` |

```python
# settings.py, hard-coded for now; each value becomes os.getenv(...) later
ASSISTANT = {
    'PROVIDER': 'openai_compatible',
    'BASE_URL': 'http://192.168.50.212:1234/v1',
    'MODEL': 'qwen3.6-35b-a3b-m5',
    'DISPLAY_NAME': 'Qwen 3.6',
    'API_KEY': '',          # LM Studio needs none; sent as a Bearer header when set
    'TIMEOUT': 55,          # seconds, under nginx's 60 s
    'MAX_TOKENS': 1500,     # the model reasons before answering; see concerns
    'TEMPERATURE': 0.3,
    'MAX_HISTORY': 20,      # messages kept from the client's history
}
```

### Frontend, new

| File | Purpose |
| --- | --- |
| `front/vue/components/Icons/ChatIcon/ChatIcon.vue` | 24×20 `currentColor` speech-bubble icon, same shape as `TasksIcon.vue` |
| `front/vue/exports/assistantChat.js` | Mounts `AiChat.vue` on `#assistant-chat` with the shared store |
| `front/vue/pages/AiChat/AiChat.vue`, `AiChat.css` | The page: header (title, model name, "New conversation"), message list, composer, empty/loading/error states |
| `front/vue/components/ChatMessage/ChatMessage.vue`, `.css` | One message: role label, text with `white-space: pre-wrap`, timestamp; "thinking" variant with the existing spinner |
| `front/vue/components/ChatComposer/ChatComposer.vue`, `.css` | Textarea (reuses `TextField` with `textarea`) and `EscrButton` send; Enter sends, Shift+Enter inserts a newline; disabled while loading |
| `front/vue/store/modules/assistant.js` | State `{ messages, loading, error, project, projects }`; actions `send`, `retry`, `reset`, `setProject`, `fetchProjects` |
| `front/src/api/assistant.js` | `sendChat({ messages, project })` → `POST /api/assistant/chat/` |
| `front/src/assistant/chat.js` | Pure helpers, no DOM or axios: `toApiMessages`, `parseChatResponse`, `errorMessage`, `shouldSend`, `SUGGESTED_QUESTIONS` |
| `front/tests/assistantChat.test.mjs` | Unit tests for the helpers |

### Frontend, changed

| File | Change |
| --- | --- |
| `front/vue/components/GlobalNavigation/GlobalNavigation.vue` | Import `ChatIcon`; add an `<a href="/assistant/">` link with label "AI Chat" right after the Tasks `VMenu`, active when `location.pathname === '/assistant/'` |
| `front/webpack.common.js` | Entry `assistantChat: "./vue/exports/assistantChat.js"` |
| `front/vue/store/index.js` | Register the `assistant` module |
| `front/src/api/index.js` | `export * from "./assistant"` |

## Responsibilities

**Backend** owns: authentication and permission scoping, building the
context, the system prompt, the provider call, timeouts, input limits, error
mapping, and hiding the endpoint and model details. Everything that touches
data or LM Studio.

**Frontend** owns: the conversation held in memory for the page's lifetime,
rendering, the loading/error/empty states, retry, the optional project
focus, and keyboard handling.

## Request and response flow

1. User opens `/assistant/`. `AssistantPage` (login required) renders the
   template, which mounts the Vue page and passes `ASSISTANT['DISPLAY_NAME']`
   as a prop. The page shows the empty state: a short welcome naming the
   model, and the four suggested questions as buttons that fill the composer.
2. User sends a question. The store appends
   `{ id, role: "user", content, at }`, sets `loading`, clears `error`, and
   calls `sendChat` with the last 20 messages reduced to `{ role, content }`
   and the selected project pk, if any.

   ```http
   POST /api/assistant/chat/
   { "messages": [ { "role": "user", "content": "What tasks are still open?" } ],
     "project": 12 }
   ```
3. `ChatView` validates the body with `ChatRequestSerializer` (1–40 messages,
   roles `user`/`assistant` only, content 1–8 000 characters, last message
   from the user; `system` entries are dropped). If `project` is given it must
   be in `Project.objects.for_user_read(user)`, else 404.
4. `build_context(user, project)` gathers the snapshot (next section) and
   `render_context` turns it into text. `system_message` wraps it with the
   role instructions, today's date and the user's name.
5. `get_provider().complete([system] + history, max_tokens, temperature)`
   posts to `{BASE_URL}/chat/completions` with `stream: false` and the
   configured timeout, and returns `ChatResult(content, model, usage,
   finish_reason)`. Connection errors, timeouts, non-2xx responses, malformed
   JSON and empty `content` all raise `ProviderError` with a user-safe message;
   the detail is logged server-side only.
6. Response:

   ```json
   { "message": { "role": "assistant", "content": "Two tasks are still running…" },
     "model": "Qwen 3.6",
     "context": { "projects": 3, "documents": 12, "tasks": 7, "generated_at": "2026-10-07T15:04:00Z" },
     "usage": { "prompt_tokens": 2140, "completion_tokens": 310 } }
   ```

   Errors use the codebase's shape `{ "status": "error", "error": "…" }`:
   400 invalid body, 403/401 not signed in, 404 project, 502 provider failure
   (including timeout and empty answer), 429 if throttled.
7. The store appends the assistant message, or sets `error` and keeps the
   user's message so "Retry" resends the same history.

## Project context given to the model

Built server-side, per request, from the user's own view of the data.
Everything goes through the existing managers, so sharing rules hold.

| Section | Source | Limit |
| --- | --- | --- |
| Projects | `Project.objects.for_user_read(user)` annotated with document count, newest first | 20 |
| Documents | `Document.objects.for_user(user)` (restricted to the focused project when one is set), newest updated first, with per-document page counts by `workflow_state` and `editorial_status`, transcription layer names, tags | 30 |
| Tasks | `TaskReport.objects.filter(user=user)`: all queued/running, plus ended in the last 7 days, excluding the automatic methods hidden by `taskStatus.js`; grouped by `TaskGroup` with counts per state, document, timestamps, last log line of crashed tasks | 50 |
| Recent changes | Documents and pages updated in the last 7 days, counted per document per day; task groups finished in that window | 7 days |
| Models | The user's `OcrModel`s with `training=True` | all |

Rendered as compact text, for example:

```
Today is 2026-10-07. The user is logan.

## Projects (3)
- Ephrem Hymns (/project/ephrem-hymns/): 12 documents, owner logan, updated 2026-10-06, tags: Syriac

## Documents (newest first, 12)
- BL Add 14572 (/document/42/) in Ephrem Hymns: 40 pages, 40 segmented, 31 transcribed;
  editorial status: 9 not started, 22 in progress, 9 ready for TEI export;
  layers: manual, kraken; updated 2026-10-06 14:02

## Your tasks (running, or ended in the last 7 days)
- Transcribe, BL Add 14572: running, 12 of 40 pages done, started 2026-10-07 09:12
- Train recognizer syr_print_v3: crashed 2026-10-05 10:41, last message: CUDA out of memory

## Recent changes (7 days)
- 2026-10-07: 6 pages of BL Add 14572 edited
```

The system prompt explains the vocabulary (project → document → page →
regions and lines → transcription layers; the task types), tells the model to
answer only from the snapshot, to say when something is not in it, to refer
to projects and documents by name with their path, to keep answers short, and
to rank "what next" as crashed tasks first, then pages in progress, then
pages not started, then documents without a transcription. It also states
that it cannot perform actions yet.

Budget: the limits above keep the snapshot under roughly 4 000 tokens, which
matters for local prompt-processing speed. `context` counts in the response
let the UI show "based on 3 projects and 7 tasks" if wanted.

## UI

Layout follows the project dashboard: `EscrPage` with a single card.

- **Header**: "AI Chat", a muted "Qwen 3.6" label, a project-focus `<select>`
  ("All projects" plus the user's projects, from `/api/projects/`), and a
  "New conversation" text button that clears the history.
- **Message list**: scrolls, newest at the bottom, auto-scrolls on new
  messages. User messages right-aligned on `--secondary-hover`, assistant
  messages left-aligned on `--background2`, both using `--text1`. Works in
  both themes through the existing CSS variables.
- **Composer**: textarea and a primary "Send" button. Enter sends, Shift+Enter
  adds a line. Empty or whitespace-only input cannot be sent.
- **Empty state**: one welcome line and the four suggested questions.
- **Loading**: the send button and composer disable, and an assistant bubble
  with the `escr-spinner` and "Qwen 3.6 is thinking…" appears.
- **Error**: an inline `Alert color="danger"` under the last message with the
  server's message ("The assistant is not reachable right now.", "The
  assistant took too long to answer.", "The assistant returned no answer.")
  and a Retry button. Toasts are not used, so the error stays next to the
  message it belongs to.
- **Legacy mode**: the page shows the standard not-available text; the legacy
  navbar gets no link (same as the project dashboard).

## Testing

**Backend (`manage.py test assistant`, add to CI):**

- `test_client.py`: `OpenAICompatibleProvider` with the HTTP session mocked.
  Request body has model, messages, `max_tokens`, `temperature`,
  `stream: false`, and a Bearer header only when a key is set. A normal reply
  parses content, model and usage. Empty `content` (including
  `finish_reason: "length"` with reasoning only), HTTP 500, invalid JSON,
  `ConnectionError` and `Timeout` each raise `ProviderError` with the expected
  user-facing message and never include the base URL.
- `test_context.py`: with `CoreFactory`, a user sees their own and shared
  projects and documents but not others'; tasks are only theirs; hidden
  methods are excluded; limits hold; the rendered text contains the names,
  paths, page-status counts and the crashed task's last message; a project
  focus restricts documents.
- `test_views.py`: `ChatView` with `get_provider` patched to a fake that
  records what it receives. Anonymous → 401/403. Valid body → 200 with the
  fake's answer and the display name. The fake received exactly one system
  message, first, built by the server, even when the client sent one.
  Empty list, assistant as last message, unknown role, over-long content →
  400. Unreadable project → 404. `ProviderError` → 502 with the message.
  History is capped to `MAX_HISTORY`. `AssistantPage` requires login and
  renders the mount point and the display name.

**Frontend (`npm test` in `front/`):** `assistantChat.test.mjs` covers
`toApiMessages` (strips local fields, caps history, keeps order),
`parseChatResponse` (valid reply, missing or empty content throws
"empty response"), `errorMessage` (network error, timeout, 502 with server
message, 400, unknown), and `shouldSend` (Enter vs Shift+Enter vs other
keys). The store's `send` action is thin enough that these cover the
loading → success and loading → error transitions it performs.

**Unchanged behaviour:** run the full Django suite and `npm test`, plus
flake8, isort and eslint, before opening the PR. A manual check in the
browser against the real LM Studio: send each of the four suggested questions
and one unanswerable one, stop LM Studio and confirm the error state, set
`TIMEOUT` to 1 and confirm the timeout message.

## Concerns to settle before or during implementation

- **uwsgi concurrency** (decision 2). Needs a yes.
- **Reasoning tokens.** Qwen 3.6 reasons before answering and the reasoning
  counts against `max_tokens`. Start at 1 500 and treat an empty `content`
  as an error. During implementation, try `chat_template_kwargs:
  {"enable_thinking": false}` in the request; if LM Studio honours it, answers
  get faster and the budget can drop. Keep this as a provider option.
- **Latency.** Expect 5–40 s per answer on local hardware with a few
  thousand tokens of context. The UI must make waiting obvious. If it is
  too slow in practice, shrink the context limits first, then consider the
  Celery design.
- **Reachability from Docker.** The `web` container must reach
  `192.168.50.212:1234`. From this machine the server answers; from inside
  the container it should too, since it is the host's LAN address, but verify
  once with a one-line `urllib` call in `docker compose exec web`. LM Studio's
  "serve on local network" must stay on.
- **Throttling.** Add DRF's `ScopedRateThrottle` on `ChatView` at
  20 requests per minute per user. It uses the existing Redis cache; the test
  settings' dummy cache makes it a no-op in tests. Cheap insurance against a
  stuck client.
- **Privacy.** Document names, tags and task log lines go to the model.
  Today that stays on the LAN. If the provider ever becomes a cloud service,
  this needs a policy decision and probably a setting to limit the context.
- **Staff view.** v1 shows each user their own tasks, like `/api/tasks/`.
  Staff could later ask about everyone's tasks (the task monitoring page
  already allows that) by widening the query for `is_staff`.
- **Internationalisation.** The new Vue UI is English-only like the rest of
  the new UI; Django template strings use `{% trans %}`.

## Later (designed for, not built)

- **Change model or provider**: edit `ASSISTANT` or add a provider class
  implementing `complete()`; `get_provider()` dispatches on `PROVIDER`.
- **Environment variables**: wrap each `ASSISTANT` value in `os.getenv` and
  document them in `variables.env_example`.
- **Persistence**: `Conversation` and `Message` models in the `assistant`
  app, a `conversation` id in the request, and a list of past conversations
  on the page. The client already sends full history, so nothing in the
  protocol changes.
- **Streaming**: `stream: true` from the provider and a server-sent events
  response, or chunks over the notification websocket. Needs uwsgi/nginx
  buffering settings, so it is its own change.
- **More context**: document text through the existing Elasticsearch index
  when it is enabled, page metadata, the editor's line history. The LM Studio
  server already serves an embedding model if retrieval is ever wanted.
- **Tools and actions**: the endpoint returns `tool_calls`, so the provider
  can accept a `tools` list and the view can run allow-listed actions (queue
  a transcription, cancel a task) with the user's permissions, with
  confirmation in the UI.

## Suggested order of work

1. `assistant` app, settings, `client.py` with tests. Smoke-test against the
   real server from `manage.py shell`.
2. `context.py` and `prompts.py` with tests.
3. `ChatView`, `AssistantPage`, template, URL wiring, tests, uwsgi change.
4. Icon and nav link, webpack entry, export, store module, API client,
   pure helpers with tests.
5. Page and components, CSS, empty/loading/error states.
6. `npm run ui` against the running stack, manual checks, full test runs,
   lint, PR.

## Implemented (2026-10-07)

Everything above is in place, with these deviations found while building and
testing against the real LM Studio server:

- **Reasoning switched off by default.** The plan set `MAX_TOKENS` to 1 500
  and hoped `chat_template_kwargs` would disable the model's reasoning. In
  practice a typed question exhausted 1 500 tokens on reasoning alone and
  came back as an empty answer (handled as planned, but useless). LM Studio
  ignores `chat_template_kwargs` and `/no_think`, and honours the standard
  `reasoning_effort` parameter. So `ASSISTANT['REASONING_EFFORT']` is
  `'none'` (sent by the client when set; `'low'`, `'medium'`, `'high'` turn
  reasoning back on) and `MAX_TOKENS` is 4 000 as headroom. Answers then take
  one to two seconds instead of thirty.
- **Suggested questions send immediately** instead of filling the box; one
  click fewer, same result.
- **Projects list key.** `/api/projects/` names the key `id`, not `pk`; the
  focus menu reads it through `projectChoices()` in `front/src/assistant/chat.js`,
  which has its own test.
- **Validation errors** come back with a readable `error` string (the first
  message found) plus the full `errors` object.
- **Answers are plain text.** The model writes Markdown (bold, bullets),
  shown as written. A sanitised Markdown renderer is a natural next step.
- The `uwsgi.ini` change (2 processes, 4 threads) is included as the plan
  asked, pending the deployment decision.

Verified: `manage.py test assistant` (40 tests), the full existing suites,
`npm test` (241 tests), flake8, isort, eslint, the webpack build, and a
browser session against the dev server and the real model: navigation
entry, empty state, loading state, two answers, a follow-up that used the
history, the project focus, the empty-answer error with Retry, and New
conversation.
