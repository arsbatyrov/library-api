# Endless Library

[![CI](https://github.com/arsbatyrov/endless-library/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/arsbatyrov/endless-library/actions/workflows/ci.yml)
[![Security](https://github.com/arsbatyrov/endless-library/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/arsbatyrov/endless-library/actions/workflows/security.yml)
[![Publish images](https://github.com/arsbatyrov/endless-library/actions/workflows/publish.yml/badge.svg?branch=main)](https://github.com/arsbatyrov/endless-library/actions/workflows/publish.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Endless Library is a learning project: a library with a REST API (FastAPI + SQLAlchemy + PostgreSQL), a website
(React) and infrastructure (Docker, Kubernetes), built to practise testing on every level.

## Getting started

```powershell
# 1. Environment and dependencies (development: requirements-dev.txt, includes ruff)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 2. Settings (then change the password in .env)
copy .env.example .env

# 3. Database in Docker and table structure
docker compose up -d db
alembic upgrade head

# 4. Server
uvicorn app.main:app --reload
```

API documentation (Swagger): http://127.0.0.1:8000/docs

## Frontend

React + Vite + TypeScript in `frontend/`. Requests go to `/api/...`; the Vite dev server forwards them to FastAPI
(port 8000), so CORS is not needed.

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173 (the API must be running on :8000)
npm run build        # type check and build
```

### Signing in and out

Without a session the site shows only the sign-in page (no library data is requested). After a successful sign-in the
header shows the login and a **Sign out** button.

- The 15-minute **access token lives only in the memory of the page**: not in `localStorage`, not in `sessionStorage`,
  not in a readable cookie. The long-lived **refresh token is an `httpOnly` cookie** (path `/api/auth`) that scripts
  cannot read.
- A reload signs in silently through `POST /api/auth/refresh` (the browser attaches the cookie). While it runs the page
  shows "Checking your session...".
- When a request gets `401` (the token expired), the token is refreshed **once** and the request is repeated; several
  requests failing at the same moment share one refresh. If it cannot be refreshed, the sign-in page is shown with a
  note that the session ended.
- Sign out revokes the refresh token, clears the cookie, forgets the token and shows the sign-in page.
- Wrong credentials show the server's message as it is (not translated), keep the fields filled and put the focus back
  into the form. The page is available in Russian and English and works from the keyboard.
- The code: `frontend/src/auth.ts` (token and session), `api.ts` (the 401 handling), `LoginPage.tsx`.

### The interface by role

The site shows only what the role allows (the server still checks everything and answers `403` to a forbidden action):

| Role | Sections | In the catalogue |
|---|---|---|
| reader | Books (with the ranking), Loans (**only their own** books, read only, with **their own card** above them: name and email) | read only: no add, edit or delete buttons |
| librarian | Books, Readers, Loans (issue and return) | full |
| admin | Books, Readers, Loans, **Users** (the list of accounts) | full |

- A section is in the address (`/#books`, `/#readers`, `/#loans`, `/#users`): it can be opened by a link, survives a
  reload, and the Back button returns to the previous section. Asking for a section the role does not have (a reader
  opening `/#readers`) shows an allowed section and rewrites the address; the page of the forbidden section is never
  created, so **no request to the API is made for it**. A deep link survives signing in.
- When the server answers `403`, its message is shown as it is, the interface keeps working, and the profile is re-read
  (`GET /api/auth/me`): if the role was changed on the server after the page was opened, the sections and buttons adapt.
- The code: `roles.ts` (the matrix), `section.ts` (the address), `MyLoansPage.tsx`, `UsersPage.tsx`.

**Managing accounts on the site.** The admin works in *Users*: a table (login, role, reader card, status, last
sign-in) with **Create user**, **Disable / Enable**, **Change role** and **Reset password** per account. A librarian works in *Readers*:
a card without an account has **Create account** (only the role *reader* is offered, the card is fixed), a card with
one shows the login and the status with the same Disable/Enable and Reset password buttons (a librarian never sees
staff accounts). Disabling asks for confirmation (it ends the account's sessions); enabling and creating do not.
**Change role** (admin only, also on the Readers page) offers the three roles with the current one preselected; for the
reader role it asks for a free reader card, and leaving the reader role warns that the link to the card is removed. An
admin who changes their own role sees the admin screens disappear at once.
Errors from the server stand under the field they belong to as the server wrote them (a password shorter than 8
characters, a taken login, a reader without a card), the last active admin cannot be disabled (the server's message is
shown), and success messages follow the interface language. The code: `AccountForm.tsx`, `AccountActions.tsx`,
`UsersPage.tsx`, `ReadersPage.tsx`.

### Interface language (ru / en)

The RU | EN switch in the header changes the language of all interface texts: headings, labels, buttons, messages
and the date format (04.10.2026 or 04/10/2026). The choice is remembered in the browser (localStorage); until a
choice is made, the browser language is used (Russian or English, English otherwise). Texts live in
`frontend/src/i18n.ts` (`ru` and `en` dictionaries; a missing translation breaks the build). Messages that come
from the server (the `detail` field of error responses) are shown as they are and are not translated.

## Authentication settings

Login tokens (JWT) are signed with a secret that the application **requires at startup**: without a strong
`JWT_SECRET` (at least 32 bytes) it refuses to start and prints how to fix it. There is no default value.

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"   # generate a value
# put it into .env as JWT_SECRET=<value>   (see .env.example)
```

- Docker Compose reads `JWT_SECRET` from `.env`. In Kubernetes `k8s/deploy.sh` generates a random value once and
  keeps it in the Secret `endless-library-jwt`.
- Tests use a fixed test-only value that `tests/conftest.py` sets; a real secret is never used by tests.
- Replacing the secret logs everybody out: every issued token becomes invalid.

### The first administrator and the command line

There is no self-registration, so the first admin is created on the server:

```powershell
# password from an environment variable (or typed at a hidden prompt); it is NEVER a command-line argument
$env:LIBRARY_USER_PASSWORD = "<a password of 8 to 128 characters>"
.\.venv\Scripts\python.exe -m app.cli create-user --username admin --role admin
docker compose --profile full exec -e LIBRARY_USER_PASSWORD api python -m app.cli create-user --username admin --role admin
```

`create-user` takes `--role admin|librarian|reader`, `--reader-id N` (required for `reader`) and `--skip-if-exists`
(change nothing and succeed when the login exists, which makes it safe on every deploy). A repeated login is refused
with a clear message. It applies the same rules as the API (password policy, unique login ignoring case) and never
prints the password or its hash.

**Kubernetes:** `k8s/deploy.sh` creates the admin automatically. The password is random, stored only in the Secret
`endless-library-admin` and **shown once** at the end of the first deploy. A later deploy never overwrites the Secret
or the admin (and never shows a password again). To read it later:

```powershell
kubectl --context kind-endless-library -n endless-library get secret endless-library-admin -o jsonpath='{.data.password}'
# the value is base64: decode it (in Git Bash add  | base64 -d )
```

The JWT secret is a separate Secret (`endless-library-jwt`), also created once and never overwritten.

### Demo access (local machine only)

To sign in at once, without reading a generated password, three accounts with **public, well-known passwords** can be
created. They are **opt-in** and **insecure**: use them only on a local machine that nobody else can reach.

| Login / password | Role |
|---|---|
| admin / admin12345 | admin |
| librarian / librarian12345 | librarian |
| reader / reader12345 | reader (linked to the demo card "Demo Reader") |

The password policy forbids `admin / admin` (at least 8 characters, not equal to the login), hence `admin12345`.

```powershell
# kind cluster (Git Bash): creates or resets the three accounts; the Secret endless-library-admin gets the same
# password as the account, and the API logs a loud warning at startup
DEMO=1 bash k8s/deploy.sh

# Docker Compose: put DEMO_ACCOUNTS=true into .env, then
docker compose exec api python -m app.cli seed-demo

# development on one machine
$env:DEMO_ACCOUNTS = "true"
.\.venv\Scripts\python.exe -m app.cli seed-demo
```

`seed-demo` refuses to run unless `DEMO_ACCOUNTS=true` (only the word `true`), is safe to repeat (it resets the demo
passwords and reactivates the accounts, creating nothing twice), refuses to touch an existing account that has the demo
login but another role, and ends the sessions of the accounts it resets. Without `DEMO=1` a deploy creates nothing and
removes the API's demo flag. The command prints only the logins (a command never writes a password to a terminal or a log), and after `DEMO=1` the Secret `endless-library-admin` holds a note instead of a random password. **The accounts stay** after you stop using the flag: to go back to a secure setup, change the
passwords or disable the accounts (Users page), for example:

```powershell
$env:LIBRARY_USER_PASSWORD = "<a new strong password>"
.\.venv\Scripts\python.exe -m app.cli set-password --username admin    # also the way to regain access
```

`set-password` takes the password from `LIBRARY_USER_PASSWORD` or a hidden prompt (never an argument), applies the
password policy, ends every session of the account and does not reactivate a disabled one. CI never enables demo access
in its normal deploys; one separate job step deploys with `DEMO=1` to test it. Nothing about the demo logins is shown in
the application itself.

### Brute-force protection of the login

Five failed logins in a row for one login (counted over 15 minutes, ignoring case) lock that login for 15 minutes: the
next attempt gets `429` with a `Retry-After` header, even with the right password. A successful login resets the
count. The rule is per login, not per IP address, and is identical for logins that do not exist, so the answer never
reveals which logins exist. The counter lives in Redis (key = hash of the login, so no login is stored there).

The protection **fails open**: if Redis is unavailable or `REDIS_URL` is not set, signing in keeps working without the
lock, a warning is logged and the counter `endless_library_login_guard_failures_total{reason="redis_error|not_configured"}`
increases. A malformed request (`422`) does not count as a failed attempt.

### Roles and permissions

Books, readers and loans demand a login (`Authorization: Bearer <access token>`) and a role:

| Role | Allowed |
|---|---|
| `reader` | read the catalogue: `GET /books`, `GET /books/{id}`, `GET /books/popular`; their own reader card and its active loans: `GET /readers/{id}` and `GET /readers/{id}/loans` (another card gives `403`, whether or not it exists; creating, changing or listing readers stays staff-only, also for their own card) |
| `librarian`, `admin` | everything on books, readers and loans |
| `librarian` | additionally: create, list, disable/enable and reset the password of **reader** accounts (`/users`) |
| `admin` | additionally: all of that for every account, and change the role of any account to **any role** (reader, librarian, admin) |

User management (`/users`: create, list, `PATCH` to disable/enable or change a role, `reset-password`) is for staff only
and always needs a login. The system never loses its last active admin (`409`). A reader account is tied to a reader card:
becoming a reader needs a free card (`reader_id` in the `PATCH`: `422` if missing, `404` if the card does not exist, `409`
if it already has an account), leaving the reader role removes the link (the card itself stays). A librarian may not send a
`role` or a `reader_id` at all. A role change is immediate (the role is read from the database on every request) and does
not end the account's sessions. Disabling an account or resetting its password ends all its sessions.

No or a bad token gives `401` (with `WWW-Authenticate: Bearer`), a role that is not allowed gives `403`. `/health`,
`/ready`, `/docs` and `/openapi.json` stay open. A disabled or demoted user is refused at once, because the role and
the active flag are read from the database on every request.

There is no switch that turns the protection off: it is always on, in every environment. The web site shows a sign-in page
first; the access token (15 minutes) lives only in the memory of the page, the refresh token in an `httpOnly` cookie.

## Running in containers

The whole application (API, frontend, migrations) is built into images and started with the `full` profile:

```powershell
docker compose --profile full up -d --build   # http://127.0.0.1:8081
docker compose --profile full rm -sf api web migrate   # stop and remove only the application (the database stays)
```

- **`migrate`**: a one-off task that applies migrations and exits; `api` starts after it.
- **`api`**: image from `Dockerfile` (multi-stage build, non-root process, `/health` health check), not published
  outside Docker.
- **`web`**: image from `frontend/Dockerfile`: nginx serves the built interface and proxies `/api/...` to `api`
  (the address is set by the `API_UPSTREAM` variable).
- The usual `docker compose up -d db` still starts only the database.
- Runtime dependencies of the image: `requirements.txt` (direct dependencies are pinned); test and tooling
  dependencies: `requirements-dev.txt`.

### Published images

On every merge to `main`, the `publish.yml` workflow publishes images to the GitHub registry:

| Image | Tags |
|---|---|
| `ghcr.io/arsbatyrov/endless-library-api` | `latest`, `sha-<commit>` (and `X.Y.Z` for `vX.Y.Z` tags) |
| `ghcr.io/arsbatyrov/endless-library-web` | same |

```powershell
docker pull ghcr.io/arsbatyrov/endless-library-api:latest
```

Images are built from the same `Dockerfile`s that CI checks. For deployments, prefer the `sha-<commit>` tag (an exact
version) over `latest`.

## Kubernetes (local cluster)

The application can be deployed to a local [kind](https://kind.sigs.k8s.io/) cluster (Kubernetes inside Docker).
You need Docker, `kind` and `kubectl`; the script runs in Git Bash (on Windows) or in a regular Linux/macOS shell.

```bash
kind create cluster --config k8s/kind-config.yaml   # once: the endless-library cluster
bash k8s/deploy.sh                                   # build images, load them into the cluster, deploy
# Website: http://127.0.0.1:8080   API: http://127.0.0.1:8080/api/health
pytest tests/smoke -m smoke --no-cov                 # smoke and resilience tests
kind delete cluster --name endless-library           # remove everything
```

| File | What it is |
|---|---|
| `k8s/kind-config.yaml` | Cluster: node image v1.34.0, entry through port 8080 of your computer |
| `k8s/base/` | Namespace, ConfigMap, database (StatefulSet with a persistent volume), API and web (Deployments, 2 replicas, probes) |
| `k8s/migrate-job.yaml` | Migration Job (`alembic upgrade head`), a new one on every deploy |
| `k8s/ingress/` | Traefik ingress controller and the Ingress rule |
| `k8s/deploy.sh` | Full deployment; the database password is generated and stored only in a cluster Secret |

What `tests/smoke` checks: the application opens through the Ingress, data from the browser reaches the database,
a rolling update of the API loses no requests, data survives a database restart, and when the database is
unavailable the API is taken out of load balancing (readiness) but not restarted (liveness). In CI this is the
"Kubernetes (kind cluster smoke tests)" job.

## Cache and popular books (Redis)

Redis speeds up book reads (`GET /books`, `GET /books/{id}`, TTL 60 s) and stores loan counters for
`GET /books/popular?limit=5`. Postgres remains the source of truth: without Redis the application still works, just
slower.

```powershell
docker compose up -d redis                     # Redis on 127.0.0.1:6379
# add to .env: REDIS_URL=redis://127.0.0.1:6379/0   (see .env.example; without the variable the cache is off)
```

- The `X-Cache: HIT` or `MISS` response header shows whether the answer came from the cache or the database.
- Writes (creating, updating, deleting a book, issuing, returning) invalidate the affected cache entries.
- If Redis is unavailable, requests go to Postgres (short 0.5 s timeouts); API readiness (`/ready`) does not depend
  on Redis.
- Cache tests (the `redis` marker) use a separate Redis database, number 15, and clean it; the working one (number 0)
  is never touched. The address can be changed with `REDIS_TEST_URL`. Without Redis: `pytest -m "not redis"`.

## Observability: metrics, logs, Grafana

- **Metrics** (`GET /metrics` on every API pod, Prometheus format; nginx does not expose it outside): requests by
  method, route template and status code, response time (histogram), cache hits and misses, number of loans and
  returns, and the total amount of fines. The service paths `/health`, `/ready` and `/metrics` are not counted.
- **Logs**: every record is one JSON line on stdout; each request produces one record with `request_id`, `method`,
  `route`, `status` and `duration_ms`. The `X-Request-ID` header is accepted from the client (safe characters only)
  or generated, and returned in the response: it is the key for finding all records of one request.
- **Sign-in metrics and log** (AUTH-016). `endless_library_auth_logins_total{result}` counts login attempts as
  `success`, `failure` (wrong password, unknown or disabled login: indistinguishable on purpose) or `locked` (too many
  failures); `endless_library_auth_refresh_total{result}` counts token refreshes as `ok` or `rejected`. The only label is
  the result: never a login or a user, so the number of series stays small and no personal data reaches Prometheus. All
  series exist from the start at 0, so graphs have no gaps. The log has one line per event (`login`, `refresh`,
  `logout`, `password_changed`, `refresh_token_reuse`) with `request_id`, `result` and, for a success, `user_id`. It
  **never contains a password, a token, a cookie or a hash, and not even the login of a failed attempt** (people often
  type a password into the login field): a failure carries `login_hash`, the first 12 hex characters of a SHA-256 of
  the lower-cased login, which is enough to see many attempts on one login. The reuse of a replaced refresh token (a
  sign of theft) is logged at `WARNING` with the user id.
- **Prometheus and Grafana** are deployed to the cluster (`k8s/monitoring`, namespace `monitoring`) by
  `k8s/deploy.sh`. The dashboard has the panels **Входы по результатам** (logins by result), **Заблокированные входы**
  (locked logins in the last hour) and **Обновления токена** (refreshes):

```bash
# Grafana: http://grafana.localhost:8080 (the "Endless Library" dashboard, no port-forward needed)
kubectl --context kind-endless-library -n monitoring port-forward svc/prometheus 9090:9090   # http://127.0.0.1:9090
kubectl --context kind-endless-library -n endless-library logs deploy/api --tail=20          # JSON logs
```

Grafana opens without a login (view only); to edit, use the user `admin` and the password from the `grafana-admin`
Secret. Metric history is kept in the pod's memory (it is lost when the pod is recreated): this is a learning setup.

## Contract tests (OpenAPI)

The API contract is its OpenAPI schema (`/openapi.json`, `/docs`): the frontend and any other client rely on it.
There are three checks in `tests/contract` (the `contract` marker, not run by default; in CI this is the
"Contract tests (Schemathesis)" job):

```powershell
pytest tests/contract -m contract --no-cov                       # regular run, ~12 s, always the same result
SCHEMATHESIS_EXPLORE=600 pytest tests/contract/test_schemathesis.py -m contract --no-cov   # random search
UPDATE_OPENAPI_SNAPSHOT=1 pytest tests/contract/test_openapi_snapshot.py -m contract --no-cov   # after an intentional API change
```

- **Schemathesis** reads the schema and invents hundreds of requests for every operation (boundary numbers, empty
  and huge strings, wrong types, broken JSON) and checks the responses: the status code is described in the
  contract, the body matches the model, there are no 500s, bad requests are rejected and good ones are accepted.
  It has already found and helped to fix: `false` accepted as a number, ids above int32 (500), a NUL character in
  text (500), undocumented 400/404/409/503 codes, and field limits lost in the schema. Each finding is pinned by a
  regular test in `tests/api/test_contract_regressions_api.py`.
- **Schema snapshot** (`tests/contract/openapi.json`): any change of the contract turns the test red and shows which
  operations were added or removed. A snapshot update is visible in the pull request diff.
- **Security contract** (`test_security_contract.py`): closed by default. Every operation must be in an explicit
  list of open ones or declare the bearer scheme and `401`; against the running API every protected operation is
  called without a token, with a bad token and with a reader token, and `403` must appear exactly where the contract
  documents it. Schemathesis itself runs with the protection on, as an admin.

## Tests

1540 tests in total. A running database and Redis are required (`docker compose up -d db redis`). Tests use a
separate database `<name>_test` and Redis database number 15, create and clean them themselves; working data is not
touched.

```powershell
pytest                              # main suite + coverage (everything except ui, smoke, contract)
pytest -m "not db and not redis"    # only tests without infrastructure (fast, no Docker)
pytest tests/concurrency            # only race-condition tests
pytest -m ui --no-cov               # browser UI tests (see below)
pytest tests/contract -m contract --no-cov   # OpenAPI contract tests
pytest tests/smoke -m smoke --no-cov         # tests of the deployed cluster (after k8s/deploy.sh)
```

### What is tested where

| Folder | Tests | Level | What it checks | Where it runs in CI |
|---|---|---|---|---|
| `tests/unit` | 330 | unit | service logic, fines, log format, password hashing and policy, JWT tokens, the login guard, the command line, deployment files, the Qase reporting script and workflow | Tests |
| `tests/api` | 595 | API (in memory) | status codes, format, errors, Redis cache, ranking, metrics, contract regressions | Tests |
| `tests/db` | 42 | database | the database's own constraints (uniqueness, foreign keys, account rules), recovery after dropped connections | Tests |
| `tests/migrations` | 11 | migrations | apply from scratch, rollback, match with the models | Tests |
| `tests/concurrency` | 2 | race conditions | simultaneous requests to the same data | Tests |
| `tests/security` | 240 | security (negative) | forged and expired tokens, rights escalation, theft of a refresh token, cross-origin requests, indistinguishable sign-in failures, hostile input, secrets in responses and logs | Tests |
| `tests/contract` | 48 | contract | Schemathesis against OpenAPI and the schema snapshot | Contract tests |
| `tests/ui` | 227 | interface | scenarios in a real browser (Playwright), errors, network failures, signing in and out | UI tests |
| `tests/smoke` | 45 | deployed system | Ingress, sign-in, rights, refresh and sign-out, demo access, data all the way to the database, resilience (update without losses, database and Redis restart), Prometheus and Grafana | Kubernetes |

Other CI checks: linter and formatting (Lint), types and frontend build (Frontend), image build and a check through
nginx (Docker images), dependency and image vulnerabilities (Security), code analysis (CodeQL). Code coverage of the
main suite is about 97% (threshold 95%).

### Security tests

`tests/security` (marker `security`: `pytest -m security --no-cov`) is the attacker's view of the sign-in system:
automatic negative checks, written once and run on every change. They start without a login and try to break things.

- **Tokens** (`test_token_tampering.py`): about 50 forged, altered, unsigned (`alg: none` in every spelling),
  other-algorithm, other-key, expired and damaged access tokens are tried against **every protected operation** (the
  list comes from the OpenAPI schema, so a new endpoint that forgets the check is caught): always exactly `401`, never
  an accepted request and never a crash; also tokens in a query string, a cookie or a custom header.
- **Rights** (`test_privilege_escalation.py`): a reader asking for other cards' loans (id substitution and path tricks),
  creating accounts, changing roles (their own too) or books; a librarian creating staff, sending a higher role or extra
  fields (also duplicate JSON keys) while creating a reader, touching staff accounts: refused, the role is never raised.
- **Sessions** (`test_session_security.py`): reuse of a replaced refresh token ends every session of that user (and
  nobody else's); the cookie is `HttpOnly`, `SameSite=Lax`, scoped to its path, `Secure` behind HTTPS; **refresh and
  logout from another origin are refused and change nothing** (see below); responses with tokens are never cached.
- **Sign-in** (`test_login_hardening.py`): a wrong password, an unknown login and a disabled account give identical
  status, body, headers and, within a tolerance, time; about 35 injection payloads (SQL, LDAP, template, header
  injection, homoglyphs), mistyped, malformed and oversized bodies, wrong verbs, CORS. One test documents a **known
  limitation**: an already issued access token stays valid for up to 15 minutes after logout (refresh is revoked at once).
- **Secrets** (`test_secret_exposure.py`): a whole session runs while every response and every log line is collected,
  then every password, hash, token and the JWT secret is searched for everywhere.

**Cross-origin protection.** `/auth/refresh` and `/auth/logout` are authenticated by a cookie, which a browser attaches to
any request to our address. Besides `SameSite=Lax`, the server itself refuses a browser request that is not from its own
pages (`app/auth/origin.py`): `Sec-Fetch-Site` must be `same-origin` or `none`; without it, the host of `Origin` must be
the host the request was addressed to (`X-Forwarded-Host` behind the proxy). Requests with neither header (curl, tests,
a mobile app) are not browser pages and pass. Everything under `/auth/` is sent with `Cache-Control: no-store`.

### UI tests

Requirements: a running database, Node.js and `npm ci` in `frontend`, and the Chromium browser
(`python -m playwright install chromium`). The tests start the API (port 8100) and the frontend (port 5180) on a
separate database `<name>_e2e_test` themselves and stop them at the end (ports can be changed with the
`UI_API_PORT` and `UI_WEB_PORT` variables). Data is prepared through the API; checks go through the interface.

Every UI test starts **already signed in** as an administrator created in that database: the refresh cookie is put
into the browser as the server issues it, and the page restores the session silently (no clicking through the sign-in
page, no token in the test code). Data is prepared through the API with the administrator's token. Tests marked
`@pytest.mark.anonymous` (`tests/ui/test_login.py`) start without a session and go through the sign-in page.

Structure: `tests/ui/pages` (Page Objects: locators and actions), `tests/ui/test_*.py` (scenarios),
`tests/ui/network.py` (network control), `tests/ui/api_client.py` (data preparation).

What the scenarios cover: boundary values (title length 200/201, due date), an end-to-end journey through the
interface, API response substitution (`500`, dropped connection, a hanging request, a foreign error text), browser
clock substitution (overdue loans), and an example of an unstable wait (`test_waiting.py`).

**If a UI test fails**, a screenshot, a video and a trace remain in `test-results/artifacts/<test>/`. Open the trace
with this command (it shows actions, network, page snapshots and the DOM step by step):

```powershell
python -m playwright show-trace test-results/artifacts/<test-folder>/trace.zip
```

UI test server logs: `test-results/ui-servers/`.

### Reporting to Qase (CI)

The results of every **pull request to `main`** are reported to the Qase project `ELB` (TEST-004), so the cases, the runs and
their history can be seen there.

- **One Qase run per CI run.** The job "Qase test run" creates it (title `PR #<number>: <title>`, the description has the
  branch, the commit and a link to the GitHub Actions run); the jobs Tests, Contract tests, UI tests and Kubernetes report into it;
  the job "Qase complete run" closes it at the end. Both Qase jobs are not required checks.
- **Cases.** Every test function becomes an automated case (its title is the function name, the suite follows the folder
  and file); a parametrized test is one case with one result per parameter set. Re-runs add results to the same cases.
- **It can never turn CI red.** Without the token (pull requests from forks, Dependabot, or not configured), outside a pull
  request to `main`, or when Qase is unreachable or refuses the token, nothing is reported and the tests run as usual.
  The test jobs run even if the Qase job fails (`if: !cancelled()`), so a failed Qase job can not make a required check
  "skipped". `pull_request_target` is not used, so code from a fork never gets the secret.
- **Parameters of parametrized tests go to Qase too.** A very long value (the old malformed-body test used 100 000 characters)
  or a blank one (a single space: Qase trims it to nothing and answers "must be a string") makes Qase refuse the **whole batch of
  200 results**. `tests/conftest.py` therefore stops the collection with a clear message for such a parameter: build a long value
  inside the test and look it up by a short name, and give a blank one a readable id without a hyphen
  (`pytest.param(" ", id="single_space")`).
- **Settings in GitHub** (Settings, Secrets and variables, Actions): the secret `QASE_TESTOPS_API_TOKEN` and the variable
  `QASE_TESTOPS_PROJECT=ELB`. The token is passed only to the steps that run tests or the Qase script, never to a whole job.
  Rotate it in Qase if it ever leaks.
- **Locally** reporting is off. To report a local run on purpose, set the variables in the shell (never in a file in git):

```powershell
$env:QASE_MODE = "testops"; $env:QASE_TESTOPS_PROJECT = "ELB"; $env:QASE_TESTOPS_API_TOKEN = "<your token>"
pytest tests/unit/test_fines.py --no-cov
```

## Security and maintenance

- **Dependabot** (`.github/dependabot.yml`): once a week opens a pull request with dependency updates (Python, npm,
  GitHub Actions, Docker base images); minor updates are grouped into one PR per ecosystem.
- **Security checks** (`.github/workflows/security.yml`): `pip-audit`, `npm audit`, the Trivy image scanner. They run
  on every PR, on `main` and weekly; they are not required for merging (a new vulnerability in a third-party
  library must not block unrelated changes), and a red result is a signal to update the dependency.
- **CodeQL**: static code analysis for vulnerabilities (results on the repository's Security tab).
- **Secret scanning and push protection**: GitHub blocks pushes that contain recognised keys and tokens.
- All GitHub Actions are pinned by commit hash (with a version comment); Dependabot updates the hashes.
- OS packages are upgraded during image builds (`apt-get upgrade` / `apk upgrade`), which closes already fixed
  vulnerabilities of the base image.

## Agent team kit (not active)

A prepared set of role definitions (analyst, architect, developer, QA, reviewer) and process documents for building the
project with separate agents lives in [docs/agent-team/](docs/agent-team/README.md). It is stored as plain documentation
and is **not active**; see [docs/agent-team/activation.md](docs/agent-team/activation.md) for how to switch it on.

## Code checks

The same checks run in CI (GitHub Actions); you can run them locally before committing:

```powershell
ruff check .            # find issues (ruff check --fix . fixes the safe ones)
ruff format .           # formatting
```

## License

[MIT](LICENSE)

## Migrations

```powershell
alembic revision --autogenerate -m "description"   # create a migration from model changes
alembic upgrade head                               # apply
alembic downgrade -1                               # roll back the last one
alembic check                                      # are there differences between the models and the migrations
```
