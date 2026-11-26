"""HTTP API for the web app. It only translates between HTTP/JSON and the account, chat and review services."""
import logging
from datetime import datetime
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from openai import OpenAIError
from pydantic import BaseModel, Field, field_validator

from immigration_helper.accounts import (
    AccountService,
    EmailAddress,
    EmailTakenError,
    InvalidCredentialsError,
    LoginSession,
    User,
)
from immigration_helper.accounts.passwords import MAX_PASSWORD_LENGTH
from immigration_helper.accounts.service import SESSION_LIFETIME
from immigration_helper.api.reviews import review_routes
from immigration_helper.history import ChatService, ChatTurn, Conversation, ConversationNotFoundError, ConversationSummary
from immigration_helper.review import ReviewService

SESSION_COOKIE = "clearpath_session"
_MAX_QUESTION_CHARS = 1000
logger = logging.getLogger(__name__)


class CredentialsRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


class UserResponse(BaseModel):
    email: str

    @classmethod
    def of(cls, user: User) -> "UserResponse":
        return cls(email=str(user.email))


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=_MAX_QUESTION_CHARS)
    conversation_id: int | None = None  # leave out to start a new conversation

    @field_validator("question")
    @classmethod
    def _not_blank(cls, question: str) -> str:
        if not question.strip():
            raise ValueError("question must not be blank")
        return question.strip()


class AskResponse(BaseModel):
    conversation_id: int
    reply_type: str  # answer, not_covered or conversation
    answer: str
    sources: list[str]
    warnings: list[str]
    cost_usd: float

    @classmethod
    def of(cls, turn: ChatTurn) -> "AskResponse":
        answer = turn.reply.answer
        return cls(
            conversation_id=turn.conversation_id,
            reply_type=answer.kind.value,
            answer=answer.text,
            sources=[citation.label for citation in answer.citations],
            warnings=turn.reply.warnings(),
            cost_usd=turn.reply.cost_usd,
        )


class ConversationSummaryResponse(BaseModel):
    id: int
    title: str
    updated_at: datetime

    @classmethod
    def of(cls, summary: ConversationSummary) -> "ConversationSummaryResponse":
        return cls(id=summary.conversation_id, title=summary.title, updated_at=summary.updated_at)


class MessageResponse(BaseModel):
    role: str
    content: str
    reply_type: str | None  # assistant messages only
    sources: list[str]
    cost_usd: float | None


class ConversationResponse(BaseModel):
    id: int
    title: str
    messages: list[MessageResponse]

    @classmethod
    def of(cls, conversation: Conversation) -> "ConversationResponse":
        return cls(id=conversation.conversation_id, title=conversation.title, messages=[
            MessageResponse(role=message.role.value, content=message.content,
                            reply_type=message.kind.value if message.kind else None,
                            sources=list(message.sources), cost_usd=message.cost_usd)
            for message in conversation.messages
        ])


def create_app(accounts: AccountService, chats: ChatService, reviews: ReviewService,
               secure_cookies: bool = False) -> FastAPI:
    """``secure_cookies`` must be True when the site is served over HTTPS (anything beyond localhost)."""
    app = FastAPI(title="ClearPath API")

    def current_user(clearpath_session: Annotated[str | None, Cookie()] = None) -> User:
        user = accounts.user_for(clearpath_session) if clearpath_session else None
        if user is None:
            raise HTTPException(status_code=401, detail="Please log in.")
        return user

    LoggedIn = Annotated[User, Depends(current_user)]

    def start_session(response: Response, session: LoginSession) -> UserResponse:
        response.set_cookie(SESSION_COOKIE, session.token, max_age=int(SESSION_LIFETIME.total_seconds()),
                            httponly=True, samesite="lax", secure=secure_cookies, path="/")
        return UserResponse.of(session.user)

    @app.post("/api/auth/signup", status_code=201)
    def sign_up(request: CredentialsRequest, response: Response) -> UserResponse:
        try:
            session = accounts.sign_up(EmailAddress(request.email), request.password)
        except ValueError as error:  # invalid email or a password that breaks the rules
            raise HTTPException(status_code=422, detail=str(error))
        except EmailTakenError:
            raise HTTPException(status_code=409, detail="An account with this email already exists. Log in instead.")
        return start_session(response, session)

    @app.post("/api/auth/login")
    def log_in(request: CredentialsRequest, response: Response) -> UserResponse:
        try:
            session = accounts.log_in(EmailAddress(request.email), request.password)
        except (ValueError, InvalidCredentialsError):
            raise HTTPException(status_code=401, detail="Wrong email or password.")
        return start_session(response, session)

    @app.post("/api/auth/logout", status_code=204)
    def log_out(clearpath_session: Annotated[str | None, Cookie()] = None) -> Response:
        if clearpath_session:
            accounts.log_out(clearpath_session)
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=secure_cookies)
        return response

    @app.get("/api/auth/me")
    def me(user: LoggedIn) -> UserResponse:
        return UserResponse.of(user)

    @app.get("/api/conversations")
    def list_conversations(user: LoggedIn) -> list[ConversationSummaryResponse]:
        return [ConversationSummaryResponse.of(summary) for summary in chats.conversations(user)]

    @app.get("/api/conversations/{conversation_id}")
    def get_conversation(conversation_id: int, user: LoggedIn) -> ConversationResponse:
        try:
            return ConversationResponse.of(chats.conversation(user, conversation_id))
        except ConversationNotFoundError:
            raise HTTPException(status_code=404, detail="Conversation not found.")

    @app.post("/api/ask")
    def ask(request: AskRequest, user: LoggedIn) -> AskResponse:
        # A plain (non-async) handler: FastAPI runs it in a worker thread, so a slow answer doesn't block the server.
        try:
            return AskResponse.of(chats.ask(user, request.question, request.conversation_id))
        except ConversationNotFoundError:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        except (OpenAIError, RuntimeError):
            logger.exception("Answering failed for a question")
            raise HTTPException(status_code=502, detail="The assistant could not answer right now. Please try again.")

    app.include_router(review_routes(reviews, current_user))
    return app
