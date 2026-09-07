# AI Assistant Hub — Antigravity Project Memory & Guidelines

## 1. Project Overview & Current Architecture
- **Product**: Telegram Mini App (TMA) for interacting with AI models (OpenRouter, Gemini, Venice, etc.).
- **Active Production Path**:
  - **Frontend**: Located in `gh-pages/` (repository: `ThreepleS/ai-app-frontend`, branch: `gh-pages`), deployed to GitHub Pages at `https://threeples.github.io/ai-app-frontend/`.
  - **Backend**: Supabase Edge Functions in `supabase/functions/` (project ref: `amhszfvqruzpydqyjlya`).
- **Inactive / Legacy**:
  - Python Telegram bot in root (`main.py`, `src/`) is NOT active or running. The bot only serves as the entrypoint button in Telegram to open the Mini App. Do not spend time maintaining the Python server unless explicitly requested.

## 2. Frontend Conventions & Critical Rules (`gh-pages/`)
1. **Single Monolith File**:
   - The frontend logic lives primarily in `gh-pages/app.js`.
2. **Strict CSP (No CDNs, No Inline Scripts)**:
   - Content Security Policy forbids inline scripts and remote CDN scripts (except telegram-web-app and lucide).
   - Dependencies like `marked.min.js`, `dompurify.min.js`, and `eruda.min.js` MUST remain local files within `gh-pages/`.
3. **Android WebView & DOM Compatibility**:
   - Old Android Telegram WebViews crash when calling `.forEach` on a `NodeList`.
   - **RULE**: NEVER use `querySelectorAll(...).forEach(...)`. ALWAYS use `aiHubQueryAll(...)` which guarantees returning a standard JavaScript `Array`.
   - Preserve `Array.prototype.forEach` polyfills and safety guards.
4. **Deploy Process for Frontend**:
   - From directory `gh-pages/`:
     ```powershell
     powershell -ExecutionPolicy Bypass -File deploy.ps1
     ```
   - This bumps the timestamp version (`app_<YYYYMMDD_HHMM>.js`), updates `version.json` and `index.html` cache-busting queries (`?v=...`), commits, and pushes to `origin/gh-pages`.
   - **CRITICAL RULE (Post-Deploy Version Reporting)**: After EVERY frontend deploy, the agent MUST explicitly state the new version string (e.g. `vYYYYMMDD_HHMM`) to the user in the chat, so the user can immediately compare and verify it in the app's settings ("Настройки -> Ещё").
5. **Fixed Syntax Traps**:
   - `aiHubQueryAll(...).forEach(...) is not a function`: Caused when `aiHubQueryAll(...).forEach((tab) => { tab.addEventListener(...); });` had an unclosed callback (`forEach` wasn't closed with a second `});`), trapping subsequent code until a dangling `})();` at the end of the file invoked the `undefined` return value of `forEach(...)`.
6. **NO EMOJIS — USE ONLY ICONS (Lucide) & CUSTOM UI**:
   - **CRITICAL**: NEVER use emojis in the UI (no 🧠, ⚠️, ⚙️, 🔄, ▼, etc.).
   - Exclusively use the project icon library: Lucide Icons (`<i data-lucide="..."></i>` or Lucide SVG icons).
   - Ensure newly added dynamic DOM nodes trigger `if (window.lucide) lucide.createIcons(...)`.
   - Never rely on default/native browser controls (like unstyled details/summary markers or native dialogs) — always build custom styled UI components.


## 3. Backend Conventions & Critical Rules (`supabase/functions/`)
1. **Edge Functions**:
   - Stack: Deno / TypeScript.
   - Core functions: `chat` (SSE streaming, Gemini prompt caching, context compression), `auth`, `dialogs`, `settings`, `models`, `admin`, `keyinfo`, `favorites`, `img-proxy`.
2. **Authentication**:
   - Authenticated via Telegram `initData` HMAC verification in `_shared/shared.ts` (`verifyInitData`).
   - Standard Supabase JWT verification is disabled for these endpoints (`--no-verify-jwt`).
3. **Data Security**:
   - Sensitive fields (messages content, dialogs, system prompts) are encrypted with AES-256-GCM (`encryptField` / `decryptField`).
4. **Deploy Process for Supabase Functions**:
   ```powershell
   supabase functions deploy <function_names...> --no-verify-jwt
   ```

## 4. Documentation References
- Comprehensive documentation map: `docs/PROJECT_DOCUMENTATION.md`
- DB Migrations: `supabase/migrations/`
