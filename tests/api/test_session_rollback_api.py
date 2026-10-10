"""TEST-005: work that a request did not commit must not survive into the next request.

In production every request gets its own session, closed after the response. The test fixture shares one session, so it
rolls back after each request; these tests check that the fixture really does it.
"""

from sqlalchemy import func, select

from app.database import get_db
from app.main import app
from app.models import Book


def run_one_request(work) -> None:
    """Does what FastAPI does for a request: take the session from the override, work with it, finish the generator."""
    generator = app.dependency_overrides[get_db]()
    session = next(generator)
    work(session)
    generator.close()


def book_count(db) -> int:
    return db.scalar(select(func.count()).select_from(Book))


def test_work_that_was_not_committed_is_gone_after_the_request(anonymous_client, db):
    def work(session):
        session.add(Book(title="Unsaved", author="Nobody", copies_available=1))
        session.flush()

    run_one_request(work)

    assert book_count(db) == 0


def test_committed_work_survives_the_request(anonymous_client, db):
    def work(session):
        session.add(Book(title="Saved", author="Somebody", copies_available=1))
        session.commit()

    run_one_request(work)

    assert book_count(db) == 1
