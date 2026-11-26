"""HTTP endpoints for form review: upload a filled-in form, list past reviews, open one, delete one."""
from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel

from immigration_helper.accounts import User
from immigration_helper.review import (
    MAX_UPLOAD_BYTES,
    Review,
    ReviewNotFoundError,
    ReviewService,
    ReviewSummary,
    UnreadableFormError,
)


class IssueResponse(BaseModel):
    severity: str  # error or warning
    location: str
    message: str
    source: str | None  # the instruction passage behind the check


class ReviewSummaryResponse(BaseModel):
    id: int
    form: str
    filename: str
    checked_at: datetime
    errors: int
    warnings: int

    @classmethod
    def of(cls, summary: ReviewSummary) -> "ReviewSummaryResponse":
        return cls(id=summary.review_id, form=str(summary.form), filename=summary.filename,
                   checked_at=summary.checked_at, errors=summary.errors, warnings=summary.warnings)


class ReviewResponse(ReviewSummaryResponse):
    issues: list[IssueResponse]

    @classmethod
    def of_review(cls, review: Review) -> "ReviewResponse":
        return cls(**ReviewSummaryResponse.of(review.summary).model_dump(), issues=[
            IssueResponse(severity=issue.severity.value, location=issue.location, message=issue.message,
                          source=issue.instruction_label)
            for issue in review.issues
        ])


def review_routes(reviews: ReviewService, current_user: Callable[..., User]) -> APIRouter:
    router = APIRouter(prefix="/api/reviews")
    LoggedIn = Annotated[User, Depends(current_user)]
    not_found = HTTPException(status_code=404, detail="Review not found.")

    @router.post("", status_code=201)
    def check_form(file: UploadFile, user: LoggedIn) -> ReviewResponse:
        data = file.file.read(MAX_UPLOAD_BYTES + 1)  # read one byte more than allowed to detect large files
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="The file is too large. Upload a PDF of 5 MB or less.")
        try:
            return ReviewResponse.of_review(reviews.check(user, file.filename or "form.pdf", data))
        except UnreadableFormError as error:  # messages written for the user, with no form values in them
            raise HTTPException(status_code=422, detail=str(error))

    @router.get("")
    def list_reviews(user: LoggedIn) -> list[ReviewSummaryResponse]:
        return [ReviewSummaryResponse.of(summary) for summary in reviews.reviews(user)]

    @router.get("/{review_id}")
    def get_review(review_id: int, user: LoggedIn) -> ReviewResponse:
        try:
            return ReviewResponse.of_review(reviews.review(user, review_id))
        except ReviewNotFoundError:
            raise not_found

    @router.delete("/{review_id}", status_code=204)
    def delete_review(review_id: int, user: LoggedIn) -> Response:
        try:
            reviews.delete(user, review_id)
        except ReviewNotFoundError:
            raise not_found
        return Response(status_code=204)

    return router
