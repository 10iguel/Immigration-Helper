"""Start the API for the web chat page, from the project root:

    python -m immigration_helper.api            # http://127.0.0.1:8000, used by the Next.js app in web/
"""
import argparse
import logging

import uvicorn

from immigration_helper.answering.assistant import Assistant
from immigration_helper.api.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the USCIS Form Helper API.")
    parser.add_argument("--host", default="127.0.0.1", help="127.0.0.1 keeps it reachable from this computer only")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(Assistant.build()), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
