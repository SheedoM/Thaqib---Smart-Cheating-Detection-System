# Thaqib End-to-End Suite

These Playwright tests exercise the real browser, FastAPI API, cookies, CSRF, RBAC, seeded demo data, stream lifecycle endpoints, alert/report APIs, voice WebSockets, and simulator health.

## Expected Environment

Run migrations and seed a disposable database first:

```bash
python -m alembic upgrade head
python seed_demo.py college
python -m uvicorn src.thaqib.main:app --host 127.0.0.1 --port 8001
cd frontend
npm run dev -- --host 127.0.0.1
npm run e2e
```

Defaults match the college seed:

```bash
E2E_WEB_URL=http://127.0.0.1:5173
E2E_API_URL=http://127.0.0.1:8001
E2E_ADMIN_USERNAME=admin
E2E_ADMIN_PASSWORD=Admin12345!
E2E_INVIGILATOR_USERNAME=invigilator
E2E_INVIGILATOR_PASSWORD=Demo12345!
E2E_INTERNAL_EVENT_TOKEN=test-internal-event-token
E2E_SIMULATOR_URL=http://127.0.0.1:8000
```

Set `E2E_START_SERVERS=true` only for local smoke runs where the database is already migrated and seeded. CI should start services explicitly so migrations, seeding, and simulator setup are visible.

These tests intentionally create uniquely named records. Do not run them against production data.
