"""Follow mixed Uvicorn/text logs with the bounded independent file follower."""

from follow_jsonl import main


if __name__ == "__main__":
    main(format="uvicorn")
