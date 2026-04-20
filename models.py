from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./expenses.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(String, primary_key=True, index=True)
    amount = Column(Integer, nullable=False)          # stored in CENTS — never float
    category = Column(String, nullable=False)
    description = Column(String, nullable=False)
    date = Column(String, nullable=False)             # ISO string YYYY-MM-DD
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class IdempotencyRecord(Base):
    """Maps a client-supplied Idempotency-Key → the expense it created."""
    __tablename__ = "idempotency_records"

    key = Column(String, primary_key=True)
    expense_id = Column(String, nullable=False)
