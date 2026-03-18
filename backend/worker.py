"""Worker RQ.

Execute em um processo separado:
  python worker.py
"""

from __future__ import annotations

from rq import Worker

from services.queue_service import get_redis


def main() -> None:
    conn = get_redis()
    Worker(["default"], connection=conn).work()


if __name__ == "__main__":
    main()

