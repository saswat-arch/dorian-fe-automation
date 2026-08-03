# Dorian FE Agent — Full Project Documentation

> **AI-powered frontend QA automation engine with self-healing selectors.**
> Built with Python (FastAPI + Playwright) backend and Next.js (React) frontend.

---

## Table of Contents

1. [What Is Dorian FE Agent?](#1-what-is-qa-autopilot)
2. [High-Level Architecture](#2-high-level-architecture)
3. [How a Test Run Works (End-to-End Flow)](#3-how-a-test-run-works-end-to-end-flow)
4. [The 3-Tier Self-Healing Selector System](#4-the-3-tier-self-healing-selector-system)
5. [Project Structure](#5-project-structure)
6. [Environment & Configuration](#6-environment--configuration)
7. [Python Engine — File-by-File Breakdown](#7-python-engine--file-by-file-breakdown)
8. [Next.js Web App — File-by-File Breakdown](#8-nextjs-web-app--file-by-file-breakdown)
9. [Key Concepts & Patterns](#9-key-concepts--patterns)
10. [How to Run the Project](#10-how-to-run-the-project)

---

## 1. What Is Dorian FE Agent?

Dorian FE Agent is an **AI-powered frontend testing tool** that:

- Lets you **import test flows from Jam recordings** (a browser recording tool) — paste a Jam URL and AI converts it into a structured test intent
- **Runs those tests with Playwright** (headless or headed Chromium browser automation)
- **Self-heals broken selectors** using a 3-tier system: cached selectors → 8 deterministic strategies → Claude Vision AI as the final fallback
- **Manages authentication** automatically — run a one-time auth setup, and every subsequent test reuses the saved login state
- **Learns your app** — builds a knowledgebase of pages, components, navigation, and API endpoints over time
- **Streams results in real-time** via Server-Sent Events (SSE) to a modern web UI

### Who Is It For?

QA engineers or developers who want to automate frontend testing without manually writing brittle CSS/XPath selectors. The AI handles selector resolution and heals them when the UI changes.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser (User)                    │
│                                                     │
│   Next.js UI (React)  ◄──── localhost:3000          │
│   ┌─────────────────────────────────────────────┐   │
│   │ Dashboard │ Intents │ Runner │ Reports │ ... │   │
│   └─────────────────────┬───────────────────────┘   │
│                         │ HTTP / SSE                 │
│   ┌─────────────────────▼───────────────────────┐   │
│   │         Next.js API Routes (Proxies)         │   │
│   │         /api/intents, /api/events, ...       │   │
│   └─────────────────────┬───────────────────────┘   │
└─────────────────────────┼───────────────────────────┘
                          │ HTTP / SSE
┌─────────────────────────▼───────────────────────────┐
│           Python FastAPI Engine (localhost:8000)      │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Routes   │  │  Schema   │  │  Converters       │  │
│  │ (FastAPI) │  │ (Pydantic)│  │ (Jam → Intent)    │  │
│  └────┬──────┘  └──────────┘  └───────────────────┘  │
│       │                                              │
│  ┌────▼──────────────────────────────────────────┐   │
│  │                  Core Engine                    │  │
│  │  ┌──────────┐ ┌────────────┐ ┌─────────────┐  │  │
│  │  │ Runner   │ │ Smart      │ │ AI Resolver  │  │  │
│  │  │          │ │ Selector   │ │ (Claude)     │  │  │
│  │  ├──────────┤ ├────────────┤ ├─────────────┤  │  │
│  │  │ Actions  │ │ Cache Mgr  │ │ Auth Setup   │  │  │
│  │  └──────────┘ └────────────┘ └─────────────┘  │  │
│  └───────────────────────────────────────────────┘   │
│       │                    │                         │
│  ┌────▼────┐         ┌────▼─────┐                    │
│  │Playwright│         │  SQLite  │ (Knowledgebase)    │
│  │(Browser) │         └──────────┘                    │
│  └──────────┘                                        │
└──────────────────────────────────────────────────────┘
```

### Communication Flow

1. **Browser** talks to **Next.js** (`localhost:3000`)
2. **Next.js API routes** are thin HTTP proxies that forward every request to the **Python FastAPI backend** (`localhost:8000`)
3. The **Python engine** does all the heavy lifting: running Playwright, calling Claude, managing files

This split exists so the frontend is a clean React app, and the engine has full access to Playwright and the filesystem.

---

## 3. How a Test Run Works (End-to-End Flow)

Here's what happens when you click "Run Tests" in the UI:

```
1. UI sends selected intent IDs via EventSource (SSE) to /api/events
2. Next.js proxy forwards the stream to Python's /api/events endpoint
3. For each intent:
   a. Python loads the intent JSON from the intents/ folder
   b. Launches Playwright Chromium (headed or headless)
   c. Injects saved auth state (cookies/localStorage from .auth/default.json)
   d. Navigates to the baseUrl
   e. For each step in the intent:
      i.   If step needs a target element → 3-tier resolution (see below)
      ii.  Execute the action (click, type, navigate, assert, etc.)
      iii. Stream the step result back to the UI via SSE
   f. After all steps: write a JSON report to reports/
   g. Stream "test:complete" event
4. After all intents: stream "run:complete" event
5. UI updates in real-time as events arrive
```

---

## 4. The 3-Tier Self-Healing Selector System

This is the core innovation. When the engine needs to find an element on a page:

### Tier 1: Cache (Fastest)

- Looks up a previously resolved selector string from a local JSON cache file
- Selector must be within TTL (not expired) and above minimum confidence
- If the cached locator still matches an element on the page → **use it**

### Tier 2: Smart Selector (Deterministic, 8 Strategies)

If cache misses, the engine tries these strategies in order:

1. **testId** — `page.getByTestId("submit-btn")`
2. **role + name** — `page.getByRole("button", name="Submit")`
3. **role + label** — `page.getByLabel("Email")`
4. **label** — `page.getByLabel("Password")`
5. **placeholder** — `page.getByPlaceholder("Enter email")`
6. **text** — `page.getByText("Sign In")`
7. **css** — `page.locator("#login-form input.email")`
8. **xpath** — `page.locator("xpath=//button[@type='submit']")`

Each strategy is tried, and if exactly one element matches → success. If multiple match, positional narrowing kicks in.

### Tier 3: AI Resolver (Claude Vision — Last Resort)

If Smart Selector fails:

1. Take a **screenshot** of the current viewport
2. Extract a **DOM snapshot** (simplified tree of the page's HTML structure)
3. Send both to **Claude (Anthropic)** with a prompt like "Find the element described as 'the email input field'"
4. Claude returns a Playwright locator string
5. The engine validates and executes it

**Self-healing**: If an AI-resolved selector works, the old broken one is "healed" — the new selector is cached, and the test continues instead of failing.

---

## 5. Project Structure

```
dorian-fe-automation/
│
├── .env                      # API keys and secrets
├── .env.example              # Template of required env vars
├── .auth/                    # Saved authentication state
│   ├── config.json           #   Auth flow configuration
│   ├── default.json          #   Browser storage state (cookies, localStorage)
│   └── meta.json             #   When auth was created, email used, etc.
│
├── engine/                   # Python backend (FastAPI + Playwright)
│   ├── pyproject.toml        #   Package config, dependencies
│   ├── logs/engine.log       #   Runtime logs
│   └── engine/               #   Python package
│       ├── main.py           #   FastAPI app entry point
│       ├── config.py         #   All paths, API keys, env vars
│       ├── schema/           #   Pydantic data models
│       ├── core/             #   The actual test engine
│       ├── converters/       #   Jam → Intent AI conversion
│       ├── routes/           #   FastAPI API endpoints
│       ├── knowledgebase/    #   SQLite-backed app knowledge
│       ├── reporters/        #   JSON and HTML report generation
│       └── utils/            #   Logging, screenshots, DOM, Mailosaur
│
├── web/                      # Next.js frontend
│   ├── package.json          #   Dependencies (Next 16, React 19, SWR)
│   ├── app/                  #   App Router pages and API routes
│   │   ├── layout.tsx        #     Root layout with sidebar
│   │   ├── page.tsx          #     Dashboard
│   │   ├── intents/          #     Intent management pages
│   │   ├── run/              #     Test runner with live SSE
│   │   ├── reports/          #     Report viewer
│   │   ├── auth/             #     Auth setup management
│   │   ├── knowledgebase/    #     App knowledge explorer
│   │   └── api/              #     Proxy routes → Python backend
│   ├── components/           #   Shared UI components
│   └── lib/                  #   TypeScript types and config
│
├── intents/                  # Stored test intent JSON files
├── reports/                  # Test run results (JSON + screenshots)
└── knowledgebase/            # SQLite database file
```

---

## 6. Environment & Configuration

### `.env` (Required Variables)

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | API key for Claude (AI resolver + Jam converter) |
| `JAM_ACCESS_TOKEN` | Personal access token for fetching Jam recordings via MCP API |
| `AUTH_EMAIL` | The email address used for OTP login (e.g. `you@yourapp.com`) |
| `AUTH_METHOD` | Auth method: `otp_manual` (default) or `interactive` |
| `PLAYWRIGHT_BROWSERS_PATH` | Path where Playwright browser binaries are installed |

### How Config Flows Through the System

```
.env file
  └→ engine/engine/config.py (loads with python-dotenv)
       └→ All Python modules import from config.py
            Paths: INTENTS_DIR, REPORTS_DIR, AUTH_DIR, DB_PATH, CACHE_DIR
            Keys: ANTHROPIC_API_KEY, JAM_ACCESS_TOKEN, AUTH_EMAIL, AUTH_METHOD

  └→ web/.env.local (optional, for BACKEND_URL override)
       └→ web/lib/engine-path.ts (defaults to http://localhost:8000)
```

---

## 7. Python Engine — File-by-File Breakdown

### `engine/pyproject.toml` — Package Definition

Declares the `qa-autopilot-engine` Python package. Key things:
- **Build system**: hatchling
- **Python**: >=3.9
- **Dependencies**: FastAPI, uvicorn, Playwright, Anthropic, Pydantic v2, aiosqlite, Mailosaur, httpx, sse-starlette, python-dotenv, loguru, jinja2
- **Console script**: `engine` command → runs `engine.main:run()`

---

### `engine/engine/main.py` — FastAPI App Entry Point

Creates the FastAPI application instance and wires everything together:
- Enables **CORS** for `localhost:3000` (the Next.js frontend)
- Registers all **routers** (intents, run, reports, stats, knowledgebase, auth, jam import)
- Exposes `GET /health` for health checks
- `run()` starts **uvicorn** on port 8000 with hot-reload

---

### `engine/engine/config.py` — Central Configuration

The single source of truth for all paths and secrets:
- Loads `.env` from the repo root using `python-dotenv`
- Sets `PLAYWRIGHT_BROWSERS_PATH` explicitly in `os.environ` so Playwright finds its binaries
- Defines directory paths: `INTENTS_DIR`, `REPORTS_DIR`, `KNOWLEDGEBASE_DIR`, `AUTH_DIR`, `CACHE_DIR`
- Creates directories automatically if they don't exist
- Exports all API keys as string constants

---

### Schema Layer (`engine/engine/schema/`)

These are **Pydantic v2 models** — the data contracts that define the shape of all data flowing through the system.

#### `schema/intent.py` — Test Intent Models

Defines what a "test" looks like:

- **`SelectorTarget`** — How to find an element: `testId`, `role`, `text`, `label`, `placeholder`, `css`, `xpath`
- **`StepIntent`** — One action in a test: type (click/type/navigate/etc.), human-readable intent description, target selector, value
- **`AssertionIntent`** — Verification after a step: visible, hidden, url, text content, count, enabled, checked
- **`IntentConfig`** — Test settings: timeout, retries, viewport dimensions, browsers list
- **`TestIntent`** — The complete test definition: id, name, baseUrl, tags, steps[], assertions[], config, metadata

Example intent JSON:
```json
{
  "id": "test-abc123",
  "name": "Create Business Profile",
  "baseUrl": "https://staging.app.com",
  "tags": ["smoke"],
  "steps": [
    { "id": "s1", "order": 1, "type": "navigate", "intent": "Go to homepage", "url": "/" },
    { "id": "s2", "order": 2, "type": "click", "intent": "Click Create Profile",
      "target": { "role": "button", "text": "Create Profile" } },
    { "id": "s3", "order": 3, "type": "type", "intent": "Enter business name",
      "target": { "css": "#business-name" }, "value": "Acme Corp" }
  ],
  "assertions": [
    { "id": "a1", "afterStep": "s3", "type": "url", "expected": "/profile/edit" }
  ],
  "config": { "timeout": 30000, "retries": 1, "viewport": { "width": 1280, "height": 720 }, "browsers": ["chromium"] }
}
```

#### `schema/result.py` — Run Result Models

Defines what a test **run output** looks like:

- **`StepResult`** — Per-step outcome: status (passed/failed/healed/skipped), which tier resolved it, strategy name, confidence score, duration, error message, screenshot path, healed-from/healed-to selectors
- **`RunResult`** — Full test outcome: testId, testName, passed boolean, all step results, total duration, browser, timestamp, healed count, environment info

#### `schema/knowledgebase.py` — Knowledge Models

Models for the app-knowledge database: pages visited, interactive components discovered, navigation paths, API endpoints observed.

---

### Core Engine (`engine/engine/core/`)

This is where the magic happens.

#### `core/runner.py` — The Test Runner (Heart of the Engine)

The `TestRunner` class orchestrates everything:

1. **`load_intent(path)`** — Reads and validates an intent JSON file using Pydantic
2. **`launch_browser()`** — Starts Playwright Chromium (headed or headless)
3. **`create_page()`** — Creates a browser page and **injects auth state** from `.auth/default.json` (cookies, localStorage saved from a previous login)
4. **`_resolve_element(page, step)`** — The 3-tier resolution:
   - Try **cached** selector (Tier 1)
   - Try **smart_selector** (Tier 2)
   - Try **ai_resolver** (Tier 3)
   - If AI resolves what cache/smart couldn't → mark as "healed"
5. **`run_intent_streaming(intent, headed)`** — The main loop:
   - Navigate to base URL
   - For each step: resolve target → execute action → check assertions → yield SSE event
   - Build the `RunResult` object
6. **`cleanup()`** — Close browser

#### `core/smart_selector.py` — Deterministic Selector Resolution (Tier 2)

`resolve_selector(page, target, intent_text)` tries 8 Playwright strategies in priority order:

| Priority | Strategy | Playwright Method |
|----------|----------|-------------------|
| 1 | testId | `page.getByTestId(value)` |
| 2 | role+name | `page.getByRole(role, name=text)` |
| 3 | role+label | `page.getByLabel(label)` |
| 4 | label | `page.getByLabel(label)` |
| 5 | placeholder | `page.getByPlaceholder(value)` |
| 6 | text | `page.getByText(text)` |
| 7 | css | `page.locator(css)` |
| 8 | xpath | `page.locator(xpath=...)` |

If a strategy finds **exactly 1** matching element → success (returns `SelectorResult` with the locator, strategy name, and confidence score).

If **multiple** elements match → tries positional narrowing (`.first`, `.last`, `.nth()`).

#### `core/ai_resolver.py` — Claude Vision Fallback (Tier 3)

When deterministic methods fail:

1. Takes a **screenshot** of the page
2. Extracts a **DOM snapshot** (simplified HTML tree)
3. Calls **Anthropic Claude** API with a system prompt + the screenshot + DOM + a description of what element to find
4. Claude returns a Playwright locator string like `page.getByRole("button", name="Submit")`
5. The engine **parses and validates** that locator string
6. If it works → returns the resolved element with confidence score

#### `core/action_executor.py` — Step Execution

Maps step types to Playwright actions:

| Step Type | What It Does |
|-----------|--------------|
| `navigate` | `page.goto(url)` |
| `click` | `locator.click()` |
| `type` | `locator.fill(value)` |
| `select` | `locator.selectOption(value)` |
| `hover` | `locator.hover()` |
| `wait` | `page.waitForTimeout(ms)` |
| `scroll` | `page.evaluate("window.scrollBy()")` |
| `assert` | Various assertion types |
| `screenshot` | `page.screenshot(path=...)` |
| `generate-email` | Creates a Mailosaur test email |
| `fetch-otp` | Fetches OTP code from Mailosaur inbox |

#### `core/auth_setup.py` — Global Authentication Manager

Handles the one-time login flow so every test starts already authenticated:

1. **`load_auth_config()`** — Reads `.auth/config.json` (or creates a default)
2. **`run_auth_setup()`** — The full login automation:
   - Clears the Mailosaur inbox (so we don't pick up old OTPs)
   - Launches a headed Chromium browser
   - Navigates to the app's login page
   - Enters the `AUTH_EMAIL` into the email field
   - Clicks submit
   - Waits for OTP email in Mailosaur (or magic link)
   - Enters the OTP / clicks the magic link
   - Waits for auth to complete
   - Saves the full browser state (cookies + localStorage) to `.auth/default.json`
   - Saves metadata (email, timestamp, expiry) to `.auth/meta.json`
3. **`get_auth_status()`** — Checks if saved state exists and whether it's still fresh (within `maxAgeHours`)
4. **`load_global_auth_state()`** — Reads the saved state for injection into test browser contexts
5. **`clear_auth_state()`** — Deletes saved state files

Auth config (`.auth/config.json`) is customizable:
```json
{
  "baseUrl": "https://staging-prism.upcover.com/",
  "method": "otp",
  "steps": {
    "loginButton": { "role": "button", "text": "Log In" },
    "emailField": { "role": "textbox", "label": "Email" },
    "submitButton": { "role": "button", "text": "Continue" },
    "otpField": { "role": "textbox", "label": "Enter the code" }
  },
  "waitAfterAuth": 5000,
  "maxAgeHours": 24
}
```

#### `core/cache_manager.py` — Selector Cache

Stores successfully resolved selectors so they can be reused instantly:

- **`get_cached_selector(intent_id, step_id)`** — Look up a cached locator string
- **`set_cached_selector(intent_id, step_id, ...)`** — Store a new resolution
- Cache entries include: locator string, strategy used, confidence, timestamp
- Entries expire after a configurable TTL
- Cache files are stored as `{intent_id}.cache.json` under `CACHE_DIR`

#### `core/locator_parser.py` — Playwright Locator Parser

Converts **string** locator expressions (from cache or AI) back into **Playwright Locator objects**:

- Parses patterns like `getByRole("button", name="Submit")`, `getByTestId("login")`, `locator("#my-id")`
- Includes `sanitize_ai_response()` to clean up raw AI output
- `is_valid_locator_string()` validates before execution

#### `core/errors.py` — Custom Exceptions

A clean error hierarchy:
- `QAAutopilotError` (base)
- `SelectorNotFoundError` — No strategy could find the element
- `StepExecutionError` — Action failed (timeout, wrong state, etc.)
- `AIResolverError` — Claude couldn't resolve the element
- `IntentValidationError` — Invalid intent JSON
- `BrowserLaunchError`, `CacheError`, `TimeoutError`

#### `core/auth_state.py` — Per-Intent Auth State (Legacy)

Provides per-intent storage state files. The current system uses **global** auth state (`auth_setup.py`) instead, but this module exists for potential future per-test auth flows.

---

### Converters (`engine/engine/converters/`)

#### `converters/jam_converter.py` — Jam Recording → Test Intent

The AI-powered converter that turns Jam recordings into structured test intents:

1. **`extract_jam_id(url)`** — Parses a Jam URL like `https://jam.dev/c/abc-123` into just `abc-123`
2. **`JamMCPClient`** — Manages communication with Jam's MCP API:
   - `initialize()` — Handshake to get a session ID
   - `call_tool(name, args)` — Calls MCP tools like `getDetails`, `getUserEvents`, `getConsoleLogs`, `getNetworkRequests`
   - Handles SSE response parsing
3. **`fetch_jam_recording(jam_url)`** — Fetches all data about a recording:
   - Details (title, URL, description)
   - User events (clicks, types, navigation)
   - Console logs
   - Network requests
   - Extracts the **base URL** from navigation events and network host data
4. **`convert_jam_recording(recording)`** — Sends the raw data to **Claude** with a detailed prompt (`STRUCTURING_PROMPT`) that instructs the AI to:
   - Convert events into ordered steps with proper targets
   - Extract element selectors from HTML snippets (id → css, data-testid → testId, role+text for buttons)
   - Generate meaningful assertions
   - **Skip any login/auth steps** (since auth is handled globally)
   - Use relative paths for URL assertions
5. **`save_intent(intent)`** — Writes the TestIntent JSON to `intents/`

#### `converters/prompt_converter.py` — Natural Language → Test Intent

Converts a plain English description into a test intent using Claude. Can incorporate knowledgebase context (known pages/components) for better results. Available for future use but not currently wired to a route.

---

### Routes (`engine/engine/routes/`)

These are the **FastAPI API endpoints** that the Next.js frontend talks to.

#### `routes/run.py` — Test Execution

- **`POST /api/run`** — Queue a run (returns metadata)
- **`GET /api/events`** — **SSE stream** that runs tests in real-time
  - Accepts: `intentIds` (comma-separated), `runId`, optional `headed` flag
  - For each intent: streams `test:start`, `step:result` (per step), `test:complete`
  - At the end: streams `run:complete`
  - Writes a JSON report for each completed intent

#### `routes/intents.py` — Intent CRUD

- **`GET /api/intents`** — List all intent JSON files from `intents/`
- **`POST /api/intents`** — Create a new intent
- **`GET /api/intents/{id}`** — Get one intent
- **`PUT /api/intents/{id}`** — Update an intent
- **`DELETE /api/intents/{id}`** — Delete an intent

#### `routes/jam_import.py` — Jam Import

- **`POST /api/intents/from-jam`** — Takes a Jam URL, fetches the recording, converts with AI, saves the intent, returns the result
  - If conversion fails, creates a **fallback minimal intent** with just a navigate step

#### `routes/reports.py` — Report Retrieval

- **`GET /api/reports`** — List all JSON report files from `reports/` with summary info
- **`GET /api/reports/{filename}`** — Get full report JSON

#### `routes/stats.py` — Dashboard Statistics

- **`GET /api/stats`** — Returns: intent count, report count, pass rate (last 10), last run info, total healed selectors

#### `routes/knowledgebase_routes.py` — Knowledgebase API

- **`GET /api/knowledgebase`** — Stats + pages + endpoints overview
- **`GET /api/knowledgebase?page=/path`** — Drill-down: page details + components + navigation

#### `routes/auth_state_routes.py` — Auth Management

- **`GET /api/auth/status`** — Is auth state saved? Is it fresh or expired?
- **`GET /api/auth/config`** — Get the auth flow configuration
- **`PUT /api/auth/config`** — Update the auth flow configuration
- **`POST /api/auth/setup`** — Run the full Playwright+Mailosaur auth flow
- **`DELETE /api/auth/state`** — Clear saved auth state

---

### Knowledgebase (`engine/engine/knowledgebase/`)

A SQLite-backed learning system that remembers your app's structure.

#### `knowledgebase/db.py` — Database Layer

- Uses **aiosqlite** for async SQLite access
- Schema: 4 tables — `pages`, `components`, `navigation`, `api_endpoints`
- **Upsert** operations: if a page/component was seen before, update it; otherwise insert
- Singleton pattern: `get_database()` returns one shared connection

#### `knowledgebase/collector.py` — Data Collection

- **`collect_page_structure(page)`** — Runs JavaScript in the browser to discover all interactive elements (buttons, inputs, links, selects, textareas) and their attributes
- **`track_navigation(from, to, trigger)`** — Records navigation between pages
- **`track_api_call(method, url, status)`** — Records API calls (normalizes URL patterns by replacing IDs with `:id` placeholders)

#### `knowledgebase/query.py` — Data Retrieval

- **`get_all_pages()`** — All discovered pages
- **`get_components_on_page(path)`** — Interactive elements on a page
- **`get_stats()`** — Aggregate counts
- **`serialize_knowledgebase_context()`** — Text summary for LLM prompts (used by prompt converter)

---

### Reporters (`engine/engine/reporters/`)

#### `reporters/json_reporter.py` — JSON Reports

Writes the `RunResult` (plus metadata like version and Python version) to a timestamped JSON file in `reports/`. This is the primary report format used by the UI.

#### `reporters/html_reporter.py` — HTML Reports

Generates a self-contained HTML file with embedded CSS, expandable step details, and optional base64-encoded screenshots. Available but not currently invoked by the routes.

---

### Utils (`engine/engine/utils/`)

#### `utils/logger.py` — Logging

Uses **loguru** for structured logging:
- File output → `engine/../../logs/engine.log` (with rotation)
- Colored console output
- `create_logger("module-name")` creates a scoped logger

#### `utils/screenshot.py` — Screenshots

- **`capture_screenshot(page, path)`** — Full-page or viewport screenshot
- **`capture_failure_screenshot(page, test_id, step_id)`** — Auto-named failure screenshot saved to `reports/`
- Returns both file path and optional base64 encoding

#### `utils/dom_snapshot.py` — DOM Extraction

- **`extract_dom_snapshot(page)`** — Serializes the page's `<body>` into a simplified text tree
- Filters to meaningful HTML tags/attributes
- Caps depth and total length to stay within AI context limits
- Used by `ai_resolver.py` to give Claude structural context

---

## 8. Next.js Web App — File-by-File Breakdown

### Configuration Files

#### `web/package.json`
- **Next.js 16.2.4**, **React 19**, **SWR** (data fetching with caching), **lucide-react** (icons)
- Dev: Tailwind CSS 4, TypeScript 5, ESLint

#### `web/next.config.ts`
Default empty config. No rewrites — all API proxying is done explicitly in route handlers.

#### `web/tsconfig.json`
Strict TypeScript with `@/*` path alias for imports. Uses `moduleResolution: bundler`.

#### `web/postcss.config.mjs`
Wires `@tailwindcss/postcss` for Tailwind v4.

---

### Shared Code (`web/lib/`)

#### `lib/engine-path.ts` — Backend URL

One line: exports `BACKEND_URL` (defaults to `http://localhost:8000`). Every API route imports this.

#### `lib/types.ts` — TypeScript Type Definitions

Mirrors the Python Pydantic schemas exactly:
- `SelectorTarget`, `StepIntent`, `AssertionIntent`, `TestIntent` — Intent shape
- `StepResult`, `RunResult`, `JsonReport` — Run output shape
- `PageRecord`, `ComponentRecord`, `NavigationRecord`, `ApiEndpointRecord`, `KnowledgebaseStats` — Knowledgebase shape

---

### App Shell

#### `app/layout.tsx` — Root Layout

- Loads **Space Grotesk** font from Google Fonts via `next/font/google`
- Applies the font globally via CSS variable
- Renders a fixed-height flex container: `<Sidebar />` + scrollable `<main>`
- Sets page metadata (title, description)

#### `app/globals.css` — Global Styles

- Tailwind v4 via `@import "tailwindcss"`
- CSS custom properties for a warm stone/neutral color palette
- Custom scrollbar styling (thin, rounded)
- Focus-visible reset for clean form inputs

#### `components/sidebar.tsx` — Navigation Sidebar

- Client component using `usePathname()` for active route highlighting
- Dark sidebar (#111110) with amber logo accent
- Links: Dashboard, Intents, Test Runner, Reports, Auth Setup, Knowledgebase
- Icons from lucide-react

---

### Pages

#### `app/page.tsx` — Dashboard (Server Component)

- Fetches stats from `/api/stats` on the server
- Displays: last run status banner, 4 stat cards (intents, pass rate, runs, healed), quick action links, 3-tier self-healing explainer
- **Server component** — renders on the server, no client JS needed

#### `app/intents/page.tsx` — Intent List

- Client component with **SWR** for data fetching + automatic revalidation
- Search/filter by name or tag
- Table with columns: name, tags (auth/uses-auth badges), step count, base URL, actions (run/edit/delete)
- Empty state with "Create Intent" CTA

#### `app/intents/new/page.tsx` — Create Intent

Two tabs:
1. **Jam Import** — Paste a Jam URL, optionally set test name and base URL override, click "Import & Convert" → AI generates the intent
2. **JSON Editor** — Raw JSON textarea with a template

Shows success result with data source badges (details, userEvents, consoleLogs, networkRequests), JSON preview, and links to edit or run.

#### `app/intents/[id]/page.tsx` — Edit Intent

- Loads intent by ID, displays as editable JSON textarea
- Info chips (base URL, step count, tags)
- Save, Delete, and Run buttons

#### `app/run/page.tsx` — Test Runner

The most interactive page:
1. **Selection phase** — Checkboxes to pick which intents to run (auth intents auto-run first)
2. **Running phase** — Opens an `EventSource` (SSE) connection to `/api/events`
3. **Live results** — Test cards update in real-time as events arrive:
   - `test:start` → card becomes "running"
   - `step:result` → new step row appears with pass/fail/healed icon
   - `test:complete` → card shows final status
   - `run:complete` → summary bar (X passed, Y failed, Z healed)
4. **Stop button** — Can abort a running test

#### `app/reports/page.tsx` — Reports List

- SWR-fetched list of all JSON reports
- Aggregate pass rate display
- Table: test name, status (passed/failed), steps, duration, healed count, time ago
- Links to detail page

#### `app/reports/[id]/page.tsx` — Report Detail

- Full report viewer: pass/fail banner, environment info (browser, viewport, URL, timestamp)
- Expandable step rows showing: tier, confidence %, duration, healed-from/to, errors

#### `app/auth/page.tsx` — Auth Setup

- **Status card** — Shows: Authenticated (green) / Expired (amber) / Not Authenticated (gray), email, age, max age
- **Run Auth Setup** button — Triggers the Playwright+Mailosaur login flow
- **Clear State** button — Deletes saved auth
- **How It Works** — 5-step explainer
- **Config Editor** — View/edit the auth config JSON (base URL, method, selectors, timing)

#### `app/knowledgebase/page.tsx` — Knowledgebase Explorer

- Stat chips: pages, components, navigation, API endpoints
- Two-panel layout:
  - Left: discovered pages (click to drill down → components + navigation)
  - Right: observed API endpoints with method badges and status codes

---

### API Routes (`web/app/api/`)

These are **thin HTTP proxies** — they receive requests from the browser and forward them to the Python backend. This pattern exists because:
1. The browser can only talk to the same origin (Next.js on port 3000)
2. The Python engine runs on port 8000
3. The proxy layer handles the cross-origin forwarding

Every route uses `BACKEND_URL` from `lib/engine-path.ts`.

| Route | Methods | Forwards To |
|-------|---------|-------------|
| `/api/stats` | GET | `GET /api/stats` |
| `/api/intents` | GET, POST | `/api/intents` |
| `/api/intents/[id]` | GET, PUT, DELETE | `/api/intents/{id}` |
| `/api/intents/from-jam` | POST | `POST /api/intents/from-jam` |
| `/api/run` | POST | `POST /api/run` |
| `/api/events` | GET (SSE) | `GET /api/events` (streaming) |
| `/api/reports` | GET | `GET /api/reports` |
| `/api/reports/[filename]` | GET | `GET /api/reports/{filename}` |
| `/api/knowledgebase` | GET | `GET /api/knowledgebase` |
| `/api/auth/status` | GET | `GET /api/auth/status` |
| `/api/auth/config` | GET, PUT | `/api/auth/config` |
| `/api/auth/setup` | POST | `POST /api/auth/setup` |
| `/api/auth/state` | DELETE | `DELETE /api/auth/state` |

**Special case: `/api/events`** — This is an SSE proxy. It opens a streaming connection to the Python backend and pipes the event stream directly to the browser. It also adds `headed=true` to the query string so tests run in visible browser mode.

---

## 9. Key Concepts & Patterns

### Intent-Based Testing

Instead of writing code like traditional test frameworks, tests are defined as **JSON documents** called "intents." Each intent describes:
- **What** to do (steps: navigate, click, type)
- **What** to verify (assertions: URL changed, element visible, text present)
- **Where** to find elements (targets: by role, testId, CSS, text)

This makes tests readable, portable, and AI-convertible.

### Server-Sent Events (SSE)

The test runner uses SSE for real-time streaming:
- The browser opens an `EventSource` connection
- The server sends named events as they happen (`test:start`, `step:result`, etc.)
- Each event carries a JSON payload
- This gives instant UI updates without polling

### Pydantic v2 (Python Data Validation)

All data models use Pydantic:
- Automatic **validation** when loading intent JSON files
- Automatic **serialization** to JSON for API responses
- Type safety with IDE autocompletion
- Default values for optional fields

### SWR (Stale-While-Revalidate)

The frontend uses SWR for data fetching:
- Shows **cached data immediately** while refetching in the background
- Automatic revalidation on window focus
- Deduplicated requests
- Used for: intents list, reports list, knowledgebase data

### Playwright Browser Automation

Playwright drives the actual browser:
- Launches Chromium (headed for debugging, headless for CI)
- Supports `storage_state` injection (how we skip re-authentication)
- Rich locator API (getByRole, getByTestId, getByLabel, etc.)
- Screenshots, network interception, page evaluation

### Mailosaur Email Testing

For apps that use email-based authentication:
- Mailosaur provides a virtual email inbox
- Real emails forwarded from `AUTH_EMAIL` arrive in Mailosaur
- The engine polls Mailosaur API for new messages
- Extracts OTP codes or magic links from email content
- Fully automated: clear inbox → trigger login → wait for email → extract code → complete auth

---

## 10. How to Run the Project

### Prerequisites

- **Python 3.9+** with pip
- **Node.js 18+** with pnpm
- API keys in `.env` (see `.env.example`)

### Start the Python Engine

```bash
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium

# Run the engine
python -m engine.main
# → FastAPI server on http://localhost:8000
```

### Start the Next.js Frontend

```bash
cd web
pnpm install
pnpm dev
# → Next.js dev server on http://localhost:3000
```

### Using the App

1. **Auth Setup** — Go to `/auth`, click "Run Auth Setup" to save login state
2. **Import a Test** — Go to `/intents/new`, paste a Jam URL, click "Import & Convert"
3. **Run Tests** — Go to `/run`, select intents, click "Run Selected"
4. **View Results** — Go to `/reports` to see historical results
5. **Explore Knowledge** — Go to `/knowledgebase` to see what the engine has learned

---

*Built with FastAPI, Playwright, Anthropic Claude, Next.js 16, React 19, Tailwind CSS 4.*
