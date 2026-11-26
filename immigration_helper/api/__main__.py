"""Start the API for the web chat page, from the project root (PostgreSQL must be running: docker compose up -d):

    python -m immigration_helper.api            # http://127.0.0.1:8000, used by the Next.js app in web/
"""
import argparse
import logging

import uvicorn

from immigration_helper import config
from immigration_helper.accounts import AccountService
from immigration_helper.answering.assistant import Assistant
from immigration_helper.api.app import create_app
from immigration_helper.history import ChatService
from immigration_helper.ingestion import ChunkStore
from immigration_helper.review import FormReviewer, ReviewService
from immigration_helper.storage import (
    Database,
    PostgresConversationStore,
    PostgresReviewStore,
    PostgresUserStore,
    sync_forms,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the ClearPath API.")
    parser.add_argument("--host", default="127.0.0.1", help="127.0.0.1 keeps it reachable from this computer only")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--secure-cookies", action="store_true", help="required when the site is served over HTTPS")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    database = Database(config.DATABASE_URL)
    chunks = ChunkStore(config.CHUNKS_PATH).load()
    forms = sync_forms(database, chunks)
    logging.getLogger(__name__).info("Database ready; %d forms in uscis_form", forms)

    accounts = AccountService(PostgresUserStore(database))
    chats = ChatService(Assistant.build(), PostgresConversationStore(database))
    reviews = ReviewService(FormReviewer(chunks), PostgresReviewStore(database))
    uvicorn.run(create_app(accounts, chats, reviews, args.secure_cookies), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
