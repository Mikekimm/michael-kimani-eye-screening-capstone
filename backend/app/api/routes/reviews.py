from typing import Annotated

from fastapi import APIRouter, Depends, status

from ...schemas import QueueItemOut, ReviewRequest, ScreeningOut
from ...services.reviews import ReviewService
from ..deps import Presenter, Specialist, get_review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])
Reviews = Annotated[ReviewService, Depends(get_review_service)]


@router.get("/queue", response_model=list[QueueItemOut])
def review_queue(user: Specialist, reviews: Reviews):
    return reviews.queue(user)


@router.post("/{screening_id}/take", response_model=ScreeningOut)
def take_case(screening_id: str, user: Specialist, reviews: Reviews, presenter: Presenter):
    """Assigns a queued case to this specialist; other specialists see it as taken."""
    return presenter.screening(reviews.take(user, screening_id))


@router.post("/{screening_id}", response_model=ScreeningOut, status_code=status.HTTP_201_CREATED)
def review_screening(screening_id: str, body: ReviewRequest, user: Specialist, reviews: Reviews, presenter: Presenter):
    """Appends a review event (approve / override / request_retake / comment). History is never edited."""
    return presenter.screening(reviews.review(user, screening_id, body))
