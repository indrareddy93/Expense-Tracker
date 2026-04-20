import uuid
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from models import Base, Expense, IdempotencyRecord, SessionLocal, engine

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="Expense Tracker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# Create tables on startup
Base.metadata.create_all(bind=engine)


# ── Dependency ─────────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ────────────────────────────────────────────────────────────────────
class ExpenseIn(BaseModel):
    amount: int          # MUST be integer (cents)
    category: str
    description: str
    date: str            # YYYY-MM-DD

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount must be a positive integer (cents)")
        return v

    @field_validator("date")
    @classmethod
    def date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be YYYY-MM-DD")
        return v


def expense_to_dict(e: Expense) -> dict:
    return {
        "id": e.id,
        "amount": e.amount,
        "category": e.category,
        "description": e.description,
        "date": e.date,
        "created_at": e.created_at.isoformat(),
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
def index(request: Request):
    """Serve the SPA shell."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/expenses", status_code=201)
def create_expense(
    payload: ExpenseIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """
    Create an expense.

    Idempotency: if we've seen this Idempotency-Key before, return the
    previously stored expense (HTTP 200) instead of inserting a duplicate.
    This makes the endpoint safe for client retries on network failure.
    """
    # ── Idempotency check ──────────────────────────────────────────────────
    existing_record = (
        db.query(IdempotencyRecord)
        .filter(IdempotencyRecord.key == idempotency_key)
        .first()
    )
    if existing_record:
        expense = (
            db.query(Expense)
            .filter(Expense.id == existing_record.expense_id)
            .first()
        )
        if expense:
            return JSONResponse(status_code=200, content=expense_to_dict(expense))
        # Edge-case: record exists but expense was somehow deleted — fall through

    # ── Create new expense ─────────────────────────────────────────────────
    new_expense = Expense(
        id=str(uuid.uuid4()),
        amount=payload.amount,
        category=payload.category.strip(),
        description=payload.description.strip(),
        date=payload.date,
        created_at=datetime.utcnow(),
    )
    db.add(new_expense)

    idem_record = IdempotencyRecord(
        key=idempotency_key,
        expense_id=new_expense.id,
    )
    db.add(idem_record)

    db.commit()
    db.refresh(new_expense)
    return JSONResponse(status_code=201, content=expense_to_dict(new_expense))


@app.get("/expenses")
def list_expenses(
    category: Optional[str] = Query(None, description="Filter by category"),
    sort: Optional[str] = Query(None, description="date_asc | date_desc"),
    db: Session = Depends(get_db),
):
    """Return expenses with optional category filter and date sort."""
    q = db.query(Expense)

    if category:
        q = q.filter(Expense.category == category)

    if sort == "date_desc":
        q = q.order_by(Expense.date.desc(), Expense.created_at.desc())
    else:
        q = q.order_by(Expense.date.asc(), Expense.created_at.asc())

    return [expense_to_dict(e) for e in q.all()]


@app.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """Return the distinct categories currently in use."""
    rows = db.query(Expense.category).distinct().all()
    return sorted([r[0] for r in rows])


@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: str, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    # Remove idempotency record too so retried creates don't ghost-return deleted data
    db.query(IdempotencyRecord).filter(
        IdempotencyRecord.expense_id == expense_id
    ).delete()
    db.delete(expense)
    db.commit()
