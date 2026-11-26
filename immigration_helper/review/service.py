"""Checking an uploaded form for a user and keeping the list of problems (never the form itself)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from immigration_helper.accounts import User
from immigration_helper.models import FormId
from immigration_helper.review.filled_form import Issue
from immigration_helper.review.pdf_form import read_filled_form
from immigration_helper.review.reviewer import FormReviewer

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # fillable USCIS forms are well under 1 MB


class ReviewNotFoundError(Exception):
    """The review doesn't exist or belongs to someone else (the caller can't tell which)."""


@dataclass(frozen=True)
class ReviewSummary:
    review_id: int
    form: FormId
    filename: str
    checked_at: datetime
    errors: int
    warnings: int


@dataclass(frozen=True)
class Review:
    summary: ReviewSummary
    issues: tuple[Issue, ...]


class ReviewStore(Protocol):
    def save(self, user_id: int, form: FormId, filename: str, issues: list[Issue]) -> ReviewSummary: ...

    def list_for(self, user_id: int) -> list[ReviewSummary]:
        """The user's reviews, newest first."""

    def load(self, user_id: int, review_id: int) -> Review | None: ...

    def delete(self, user_id: int, review_id: int) -> bool:
        """True if the review existed and belonged to the user."""


class ReviewService:
    def __init__(self, reviewer: FormReviewer, store: ReviewStore):
        self._reviewer = reviewer
        self._store = store

    def check(self, user: User, filename: str, data: bytes) -> Review:
        """Reads the PDF in memory and saves only the problems found; the file and its values are not kept.
        Raises UnreadableFormError (with a message for the user) for files it can't check."""
        form = read_filled_form(data)
        issues = self._reviewer.review(form)
        summary = self._store.save(user.user_id, form.form, _safe_name(filename), issues)
        return Review(summary, tuple(issues))

    def reviews(self, user: User) -> list[ReviewSummary]:
        return self._store.list_for(user.user_id)

    def review(self, user: User, review_id: int) -> Review:
        review = self._store.load(user.user_id, review_id)
        if review is None:
            raise ReviewNotFoundError()
        return review

    def delete(self, user: User, review_id: int) -> None:
        if not self._store.delete(user.user_id, review_id):
            raise ReviewNotFoundError()


def _safe_name(filename: str) -> str:
    """Only the file's own name, without folders, shortened; it's shown back to the user in their list."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip() or "form.pdf"
    return name[:120]
