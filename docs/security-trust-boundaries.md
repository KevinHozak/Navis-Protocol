# 🛡️ Navis-Protocol Security & Trust Boundaries

This document defines the runtime access models, server-side authorization enforcement, web origin constraints, and deployment boundary disclosures governing the `Navis-Protocol` ecosystem across native desktop, local development, and hosted environments.

---

## 1. Runtime Access Models & Trust Boundaries

The system supports three distinct operational tiers, each with differing transport mechanisms, trust assumptions, and security gates:

| Access Model | Primary Transport | Security Boundary & Trust Mechanism | Role of Hosted Cloud IAM |
| :--- | :--- | :--- | :--- |
| **Native Desktop** (Production) | Local IPC (`tauri-apps/api`) | **OS User Isolation.** The native Tauri v2 application does not spawn an HTTP listener. All commands execute via in-process Rust handlers and local Python worker subprocesses constrained to the authenticated Windows user session and `NAVIS_ROOT`. | None. Runs fully offline/local-first. |
| **Local Web / Dev Compatibility** | HTTP (`127.0.0.1:8000`, `127.0.0.1:3000`) | **Loopback & CORS Constraint.** Bound to local loopback adapters. Requests from untrusted web origins are rejected. When `NAVIS_API_KEY` is unset, loopback connections are permitted for development convenience, but cross-origin web access remains blocked. | None. Intended for development only. |
| **Hosted Web Portal** (Cloud Run) | Public/Private HTTPS (`run.app`) | **Layered IAM & Server-Side Token Authorization.** Infrastructure boundary is governed by Cloud Run Service IAM / Cloud Armor. Application boundary is enforced via `NAVIS_API_KEY` token matching on all protected endpoints. | Cloud Run IAM enforces transport and service invocation access; application authorization validates request-level authority. |

---

## 2. Server-Side Authorization Enforcement

### Token Authentication Contract
- Protected routes (reads, writes, tasks, combat, sync, biometrics, neural endpoints, and `/api/vault/*`) require a valid authorization token when `NAVIS_API_KEY` or `NAVIS_REQUIRE_AUTH` is configured:
  - Header: `Authorization: Bearer <key>` or `X-Vanguard-Key: <key>`
  - Comparison: Constant-time comparison (`hmac.compare_digest`) to prevent timing attacks.
- **Fail-Closed Behavior**: Requests without credentials or with invalid credentials are rejected with **HTTP 401 Unauthorized** before any file, database, or state mutation is performed.
- **Exempt Routes**:
  - `GET /` (Root ping)
  - `GET /health`, `GET /api/health`
  - `GET /api/auth/status` (Public status check indicating whether authentication is currently required)
  - `POST /api/auth/verify` (Endpoint used by clients to validate credentials and authorize terminals)
  - `OPTIONS` (CORS preflight requests)
  - `/docs`, `/openapi.json`, `/redoc` (API schema exploration)

---

## 3. Web Origin Constraints (CORS)

- Prior configurations permitted unrestricted wildcards (`allow_origins=["*"]`) combined with credentials, which created an application-level gap against malicious websites.
- **Constrained Default Origins**:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
  - `http://localhost:8000`
  - `http://127.0.0.1:8000`
  - `tauri://localhost`
  - `http://vault.localhost`
  - `https://vault.localhost`
- **Configurable Origins**:
  - Additional trusted web origins may be supplied via the `NAVIS_ALLOWED_ORIGINS` environment variable (comma-separated).
  - Cross-origin requests from origins outside this allowlist do not receive CORS headers and are rejected by browsers.

---

## 4. Frontend Terminal Gate (`SecurityGuard.js`)

- **Removal of Static Secrets**:
  - The hardcoded client-side constant (`NAVIS-ALPHA-9`) has been completely removed from frontend bundles.
  - Client bundles and public assets advertise no static credentials.
- **Dynamic Terminal Authorization**:
  - The frontend queries `/api/auth/status`. If authentication is not required (e.g. local loopback dev mode), the terminal unlocks automatically.
  - If authentication is required, the user enters their Vanguard Key, which is verified dynamically against `/api/auth/verify`.
  - Upon successful verification, the key is stored in browser session storage and attached automatically to subsequent API requests via the `X-Vanguard-Key` header in `desktopApi.js`.

---

## 5. Deployed Boundary & Unverified Exposure Status

- **Verification Scope**:
  - All automated tests in `backend/tests/test_api_authorization.py` verify the application-level boundary in synthetic and loopback test environments.
  - Tested: unauthenticated rejections, invalid tokens, valid tokens, allowed and disallowed CORS origins, preflight handling, and fail-closed behavior when `NAVIS_REQUIRE_AUTH` is set.
- **Report of Unverified Deployed Exposure**:
  - The live GCP Cloud Run deployment (`<configured backend URL>`) has **not** been directly accessed, probed, or modified during this local development task, in adherence to strict project testing boundaries.
  - **Operational Requirement for Hosted Production**: When deploying the backend to Cloud Run, operators must:
    1. Set the `NAVIS_API_KEY` secret in Google Cloud Secret Manager / Cloud Run environment variables.
    2. Set `NAVIS_ALLOWED_ORIGINS` to the exact production frontend custom domain or Vercel/Firebase URL.
    3. Ensure Cloud Run ingress settings are configured appropriately (e.g., restricted to internal/load-balancer if using Cloud Armor or Identity-Aware Proxy).
