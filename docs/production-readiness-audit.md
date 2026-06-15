# Thaqib Production Readiness Audit

Date: 2026-06-15
Last updated: 2026-06-16

Scope: repository-wide production deployment review for the FastAPI backend, React/Vite frontend, simulator, database migrations, AI video/audio runtime, Docker/CI, and end-to-end test coverage.

## Executive Summary

Thaqib is not ready for an unsupervised production rollout yet. The core app has real strengths: cookie-based JWT sessions, refresh rotation, CSRF middleware, tenant-aware API patterns in most CRUD routes, Alembic migrations, and meaningful pytest/Vitest coverage. The hidden risk is mostly at the deployment and runtime-boundary layer: WebSocket hall authorization, path/media authorization, first-run bootstrap control, heavyweight AI dependency reproducibility, stream process lifecycle, and operational observability.

This pass adds production deployment artifacts and a broad Playwright E2E test scaffold, and it clears the frontend npm advisories found during the audit. The remaining items below should be treated as launch blockers or explicit pilot risks.

## 1. Architecture And Security Audit

### Launch Blockers And Recently Closed Risks

1. Voice WebSocket authorization has now been hardened, but still needs staging verification against the real production origin.
   `src/thaqib/api/routes/voice.py` now rejects query-token auth, validates browser origins, authorizes hall access by tenant/admin assignment/invigilator assignment before joining, caps oversized frames, and tracks participants by connection ID.
   Remaining remediation: run the Playwright/WebSocket smoke tests against the on-prem staging origin and document the expected reverse-proxy `Origin`/cookie behavior.

2. Stream camera controls and alert media need DB-backed scope checks.
   Some stream endpoints are scoped for feed viewing, but camera-control helpers and path-based alert media reads still rely too much on runtime state/path safety rather than alert/session/device ownership.
   Remediation: resolve `Device -> Hall -> ExamSession -> ExamAdminAssignment/Assignment` on every control/media endpoint. Prefer `/alerts/{id}/media` endpoints over raw path endpoints.

3. Bootstrap setup is now token-gated, but the operational recovery path is still thin.
   `/api/setup/install` now requires `SETUP_BOOTSTRAP_TOKEN` when configured, production startup refuses to run without it, and production setup is limited to localhost/private-network callers by default.
   Remaining remediation: return explicit `uninstalled/installed/blocked` setup states, document the one-time bootstrap-token rotation/runbook, and add a repair path for partial setup.

4. Production safety depends on `APP_ENV=production`.
   `settings.py` rejects weak production secrets only in production mode. If a deploy forgets `APP_ENV`, the default JWT secret and insecure cookies can slip through.
   Remediation: fail startup when bound to public host with development defaults; require strong `SECRET_KEY`, `INTERNAL_EVENT_TOKEN`, `COOKIE_SECURE=true`, HTTPS CORS origins, non-SQLite DB, and `DEBUG=false`.

### Configuration Liabilities

- `.env` contains a dev-only secret and must remain ignored.
- `docker-compose.yml` is now marked development-only and pgAdmin is behind the `dev-tools` profile.
- `seed_demo.py` contains fixed demo passwords and wipes demo data; never run it against production.
- Runtime settings API writes to `.env`. This is convenient for demos but risky in immutable/container deployments.
  Remediation: disable settings writes in production or persist mutable settings in the database with audit logging.

### Memory And Performance Bottlenecks

- One camera pipeline thread per active camera, plus alert clip polling/writer work. Alert bursts can create many sleeping/writer tasks.
- AI dependency stack is heavyweight: Torch, Ultralytics, MediaPipe, BoxMOT, Faster Whisper. These should be capacity-planned separately from the API control plane.
- Browser dashboard auto-connects voice per hall and polls frequently. Under many halls/admin tabs this can become noisy.
- Audio playback currently creates many short `AudioBufferSourceNode`s; production voice should use an `AudioWorklet` with jitter buffering.

## 2. Environment And Dependency Check

### Changes Added

- `requirements.txt`: pinned API/control-plane runtime.
- `requirements-ai.txt`: pinned AI/audio runtime extras, including BoxMOT's `yacs` runtime dependency.
- `requirements-dev.txt`: pinned dev/test tools.
- `frontend/package-lock.json`: updated; `npm audit` now reports zero vulnerabilities after remediation.
- `frontend/package.json`: adds `packageManager`, Node/npm engines, Playwright scripts.
- `.python-version`, `.node-version`, `frontend/.nvmrc`: explicit runtime contracts.
- `simulator/requirements.txt`: updated, including `requests` for its healthcheck, a patched `python-multipart`, and a NumPy-1.26-compatible OpenCV pin.

### Remaining Dependency Risks

- Python requirements are direct-pinned but not hash-locked. For stronger supply-chain control, generate `uv.lock` or hash-locked `requirements.lock` and install with `uv sync --locked` or `pip install --require-hashes`.
- `pyproject.toml` and `requirements*.txt` can drift. Pick one source of truth before release.
- The AI stack is sensitive to NumPy/Pandas/Torch/TorchVision/BoxMOT/OpenCV compatibility. Do not casually upgrade those pins without running the video tracker tests, Docker builds, and at least one real stream smoke test.

## 3. CI/CD And Deployment Plan

### Added Deployment Files

- `Dockerfile`: backend image with non-root user, healthcheck, optional AI extras.
- `frontend/Dockerfile`: static SPA build served by Nginx.
- `frontend/nginx.conf`: SPA routing, API/WS reverse proxy, security headers, CSP.
- `docker-compose.prod.yml`: Postgres, one-shot migration service, backend, frontend, optional simulator profile.
- `.env.production.example`: production environment template.
- `.github/workflows/ci.yml`: backend tests, frontend lint/test/build/audit, Docker builds, compose validation.
- `.github/workflows/security.yml`: pip/npm audits, compose validation, image scans.
- `.github/dependabot.yml`: scheduled npm/pip/actions updates.

### Deployment Strategy

Chosen target: on-prem university server.

- Put Nginx/frontend at the public edge and proxy `/api` and `/api/v1/voice/ws` to the backend on the private network. Same-origin deployment avoids split-domain CSRF failures.
- Run the FastAPI API/control plane as a lean service with `INSTALL_AI=false` and `STREAM_MANAGER_ENABLED=false`.
- Split real-time AI pipelines into a dedicated worker service. The worker should own camera capture, model inference, alert snapshot/clip writing, and pipeline health metrics. The API should own auth, roles, assignments, reports, and configuration.
- Run Postgres on the same on-prem host only for a pilot. For production, prefer a separate university-managed database VM/server with scheduled backups and restricted network access.
- Run migrations as a release step or one-shot job, not inside every backend process.
- Mount `models/`, `alerts/`, `archive/`, `uploads/`, and `logs/` as durable volumes or object-storage-backed paths.
- Put the AI worker on the GPU-capable server or GPU node. Keep the API responsive even when inference is overloaded.
- Keep the simulator disabled in production unless explicitly running a demo profile.

Capacity planning note: the "cap" is not meant to restrict the product. It is the tested operating envelope for a given server: concurrent exams, halls, cameras per hall, input resolution, FPS, model size, alert retention, and acceptable latency. Without that envelope, overload becomes silent: frame drops, delayed alerts, missed detections, full disks, or API timeouts. Raise the supported envelope after load tests on the actual university hardware.

### Environment Variable Management

Use a secret manager, not committed `.env` files:

- AWS: Secrets Manager/SSM Parameter Store + ECS task secrets.
- DigitalOcean: App Platform encrypted envs or Droplet secrets provisioned by Ansible/SOPS.
- Docker Compose pilot: `.env.production` on the host with strict file permissions, then migrate to Docker secrets.

Required production secrets:

- `SECRET_KEY`
- `INTERNAL_EVENT_TOKEN`
- `SETUP_BOOTSTRAP_TOKEN`
- `POSTGRES_PASSWORD`
- RTSP camera credentials stored by Thaqib
- Sentry/Datadog tokens if enabled

RTSP credential storage decision: Thaqib will store camera credentials. Treat this as a privileged secret-management feature, not ordinary configuration. Store RTSP URLs encrypted at rest, redact them from logs/API responses, restrict read/update permissions to admins, rotate credentials when staff leave, and never expose full URLs to browser clients.

### Evidence Retention Policy

Default production policy: balanced retention.

- Full-session video archives: disabled by default for production. If explicitly enabled for an exam, retain for 14 days, then delete automatically unless the exam is under dispute.
- Full-session audio recordings: disabled by default and should remain disabled unless the institution explicitly approves them for a specific exam.
- Alert snapshots, short video clips, and short audio episode clips: retain for 180 days for normal review, reporting, and appeals.
- Confirmed cheating incidents: retain for 3 academic years, then delete or export to the university's formal records system.
- Cancelled or false-positive alerts: retain for 30 days, then delete automatically.
- User uploads/profile images: retain while the user account exists; delete or anonymize when the account is removed.
- Operational logs: retain application logs for 30 days and security/audit logs for 1 year.
- Legal hold/dispute hold: suspend deletion for the affected exam/session/alert until an admin removes the hold.
- Encryption/access: store evidence on encrypted server storage, restrict download/view to authorized admins and assigned invigilators, and log every evidence view/export/delete action.

## 4. Testing And Observability Protocol

### Critical Unit/Contract Tests Before Production

Backend:

- `pytest tests/test_auth.py tests/test_auth_advanced.py`
- `pytest tests/test_tenant_isolation.py tests/test_scoping.py tests/test_role_merge.py`
- `pytest tests/test_setup_security.py`
- `pytest tests/test_exams.py tests/test_invigilator_feed.py tests/test_alert_lifecycle.py`
- `pytest tests/test_voice_incident.py`
- `pytest tests/test_stream_composer_attach.py tests/test_video_pipeline_startup.py tests/test_tracker_import.py`
- `pytest tests/test_simulator_config.py tests/test_seed_demo.py`

Frontend:

- `npm run lint`
- `npm run test:run`
- `npm run build`
- `npm audit --audit-level=moderate`

Deployment:

- `docker compose -f docker-compose.prod.yml config`
- `docker build --build-arg INSTALL_AI=false -t thaqib-backend:ci .`
- `docker build -t thaqib-frontend:ci ./frontend`

### Comprehensive E2E Suite Added

Playwright files are under `frontend/e2e/`:

- `00-setup-auth.spec.ts`: setup status, setup re-entry, cookie login, refresh, CSRF, logout.
- `01-tenant-rbac.spec.ts`: admin vs invigilator access and CSRF on mutating APIs.
- `02-admin-config.spec.ts`: hall, devices, mic placement, user, exam, assignment, report.
- `03-exam-stream-lifecycle.spec.ts`: invigilator readiness, feeds, start/stop/status.
- `04-alert-review-report.spec.ts`: internal event token gate, report visibility, fake alert rejection.
- `05-browser-roles.spec.ts`: browser login/routing for admin and invigilator.
- `06-voice-websocket.spec.ts`: two-browser voice presence/talk events.
- `07-negative-security.spec.ts`: stream CSRF, media traversal rejection, fake hall denial.
- `08-simulator-media.spec.ts`: simulator health/readiness/camera/mic endpoints.

Run with:

```bash
cd frontend
npm run e2e
```

### Observability Baseline

Add before launch:

- Structured JSON logs with request ID, user ID, role, institution ID, route, status, latency, and camera/session IDs where applicable.
- Sentry for backend exceptions and frontend errors. Scrub passwords, tokens, cookies, RTSP URLs, student media paths, and transcripts.
- Metrics: request latency/error rate, DB pool usage, active sessions, active camera pipelines, frame FPS, frame drops, alert queue depth, writer queue depth, stream reconnects, WebSocket participants, voice reconnects.
- Health endpoints:
  - `/health`: process liveness.
  - `/ready`: DB reachable, migrations at head, model artifacts present, writable media dirs.
  - `/metrics`: Prometheus/OpenTelemetry metrics.
- Audit events: setup run, login failures, password changes, user CRUD, role changes, exam assignment changes, alert confirm/cancel, settings changes, stream start/stop.

## 5. Final Review Checklist

Do not launch until each item is explicitly answered:

- Voice WS origin and hall authorization are fixed and covered by negative tests.
- Stream controls and alert media are scoped through DB ownership, not only runtime/path checks.
- Setup requires a one-time bootstrap token and localhost/VPN/private-network restriction.
- Production startup fails closed for unsafe secrets, SQLite DB, debug mode, insecure cookies, wildcard CORS, and writable `.env` settings.
- The production Python install is lockfile/hash reproducible.
- AI runtime has a tested operating envelope for the on-prem server: CPU/GPU, max concurrent exams, max halls, max cameras, expected FPS, and disk retention.
- Migrations run as one release job and are rollback-tested on a production-like clone.
- RTSP credentials are encrypted at rest, redacted from logs/API responses, and rotated through an admin-only workflow.
- Balanced evidence retention policy is approved by the institution and implemented with automated cleanup plus legal-hold exceptions.
- E2E suite runs against staging with seeded disposable data.
- Observability dashboards and alerts exist before the first pilot exam.

## Verification Performed

- Frontend lint: `npm run lint` passed with zero warnings.
- Frontend unit tests: `npm run test:run` passed, 6 files and 14 tests.
- Frontend production build: `npm run build` passed.
- Frontend dependency audit: `npm audit --audit-level=moderate` reported zero vulnerabilities.
- Playwright E2E discovery: `npm run e2e -- --list` found 17 tests across 9 files.
- Production Compose validation: `$env:THAQIB_ENV_FILE='.env.production.example'; docker compose --env-file .env.production.example -f docker-compose.prod.yml config --quiet` passed.
- Lean backend image build: `docker build --build-arg INSTALL_AI=false -t thaqib-backend:verify .` passed after pinning OpenCV to the NumPy-1.26-compatible 4.10 line.
- Frontend image build: `docker build -t thaqib-frontend:verify ./frontend` passed after installing the declared npm version in the build image and adding `frontend/.dockerignore`.
- Backend tests: `pytest -q` passed, 112 tests.

Known verification caveat: the current local Python environment still fails `python -m pip check` because BoxMOT is installed beside incompatible AI packages (`gdown`, `lapx`, `numpy`, `pandas`, `regex`, `torchvision`) and missing `yacs`. The pinned `requirements-ai.txt` resolves the intended version set, but production should install it in a clean venv/container rather than relying on this workstation environment.

Remaining non-security npm drift from `npm outdated`: React/React DOM/router and several lint/test tools have patch/minor updates available, while ESLint, TypeScript, `lucide-react`, and some globals/tooling packages have major releases. Do not take those major upgrades during release hardening without visual regression and full E2E runs.

## Product Decisions Captured

1. Real-time AI pipelines may be split into a dedicated worker service.
2. Target deployment is an on-prem university server.
3. Capacity planning is still required, but it should be framed as a tested operating envelope, not an arbitrary product limit.
4. RTSP camera credentials will be stored by Thaqib.
5. Invigilators must not access halls outside their explicit assignments.
6. Setup must require both a one-time bootstrap token and localhost/VPN/private-network access where possible.
7. Evidence retention defaults to the balanced production policy.

## Remaining Policy Choices

1. On-prem capacity baseline: choose a first pilot target such as number of concurrent exams, halls per exam, cameras per hall, resolution, FPS, and expected retention window. Then load-test that exact target before the first real exam.
2. Legal-hold authority: decide which role can place/remove a legal hold on an exam, session, or alert.
3. Formal-record export: decide whether confirmed incidents are kept inside Thaqib for 3 academic years or exported to the university's official record system and deleted from Thaqib sooner.
