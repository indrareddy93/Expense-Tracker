# 💳 Expense Tracker

A production-grade, minimal expense tracking web app built with **FastAPI + Jinja2 templates + SQLite**. No separate frontend build step — one server, one deploy.

---

## Quick Start (Local)

```bash
# 1. Clone / unzip the project
cd expense-tracker

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
uvicorn main:app --reload --port 8000

# 5. Open your browser
open http://localhost:8000
```

That's it. SQLite creates `expenses.db` automatically on first run.

---

## Project Structure

```
expense-tracker/
├── main.py               # FastAPI app — routes, CORS, idempotency logic
├── models.py             # SQLAlchemy ORM models + DB engine setup
├── requirements.txt      # Python dependencies
├── render.yaml           # One-click Render.com deployment config
├── README.md
└── templates/
    └── index.html        # Full-featured UI (Tailwind CDN + vanilla JS)
```

---

## API Reference

| Method   | Endpoint              | Description                                      |
|----------|-----------------------|--------------------------------------------------|
| `GET`    | `/`                   | Serves the SPA shell (Jinja2)                    |
| `POST`   | `/expenses`           | Create expense (requires `Idempotency-Key` header) |
| `GET`    | `/expenses`           | List expenses (`?category=x&sort=date_desc`)     |
| `GET`    | `/categories`         | Distinct categories in use                       |
| `DELETE` | `/expenses/{id}`      | Remove an expense by UUID                        |

---

## Key Design Decisions

### 1. Integer Cents — Never Floats for Money
The `amount` column is stored as a **32-bit integer representing cents** (e.g. ₹12.50 → `1250`).

**Why?** IEEE-754 floating point cannot represent most decimal fractions exactly.
`0.1 + 0.2 === 0.30000000000000004` is a real, silent bug in financial software.
Storing cents as integers eliminates all rounding errors at the persistence layer.
The frontend converts: user types `12.50` → `Math.round(12.50 * 100) = 1250` before POSTing,
and `formatCents(cents)` divides back for display only.

### 2. Idempotency Keys — Safe Network Retries
Every `POST /expenses` request **must** include an `Idempotency-Key: <uuid>` header.

The server stores a mapping `idempotency_key → expense_id` in a dedicated
`idempotency_records` table. If the same key arrives again (network retry, browser
re-submit), the existing expense is returned with **HTTP 200** instead of inserting a
duplicate.

The frontend generates a fresh UUID4 per form submission using
`crypto.getRandomValues` (browser-native). The key is kept in the submission closure;
re-submitting the same form always generates a new key, meaning the idempotency
protection is specifically for **in-flight retries**, not accidental double-clicks
(which are prevented by disabling the submit button).

### 3. Single-Server Architecture (FastAPI + Jinja2)
Instead of a separate React app + API server, the HTML template is served directly
by FastAPI. This means:
- **Zero build step** — no `npm install`, no Vite, no dist folder
- **Single deployment target** — one service, one domain
- **Tailwind via CDN** — acceptable for a take-home; production would use PostCSS

### 4. UUID Primary Keys
Expenses use `uuid4` as primary keys instead of auto-increment integers to avoid
enumerable IDs and to make the data portable across environments.

---

## Trade-offs

| Decision | Benefit | Trade-off |
|---|---|---|
| **SQLite** | Zero infrastructure, instant setup | Not suitable for concurrent writes at scale; swap for PostgreSQL for production |
| **Tailwind CDN** | No build toolchain required | Downloads the full ~350 KB Tailwind CSS on every page load; purge/PostCSS for prod |
| **Vanilla JS** | No npm, no bundler | Manual DOM manipulation vs React's reactivity; fine for this scope |
| **In-process idempotency store** | Correct within a single server process | A multi-instance deployment needs a shared cache (Redis) for the idempotency table |
| **No auth** | Simpler demo | Real app needs JWT/session auth before any write endpoints |

---

## Deployment

### Option A — Render.com (Recommended, free tier)

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo.
3. Render auto-detects `render.yaml` and configures everything.
4. A persistent 1 GB disk is mounted at `/data` for SQLite. Update `DATABASE_URL` in `models.py` to:
   ```python
   DATABASE_URL = "sqlite:////data/expenses.db"
   ```
5. Click **Deploy** — live URL in ~90 seconds.

### Option B — Railway

```bash
# Install Railway CLI
npm i -g @railway/cli
railway login
railway init
railway up
```
Set `START_COMMAND` to `uvicorn main:app --host 0.0.0.0 --port $PORT`.

### Option C — Any VPS / Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t expense-tracker .
docker run -p 8000:8000 -v $(pwd)/data:/data expense-tracker
```

---

## Running Tests (Optional)

```bash
pip install httpx pytest pytest-asyncio
pytest tests/  # add tests/test_main.py to extend
```

---

*Built in < 1 hour as a take-home assignment. Stack: FastAPI 0.111, SQLAlchemy 2.0, SQLite, Jinja2, TailwindCSS CDN.*
