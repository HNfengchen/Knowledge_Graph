from __future__ import annotations

import uvicorn

from kg_system.core.config import get_settings


def main() -> None:
    s = get_settings()
    uvicorn.run(
        "kg_system.main:app",
        host=s.APP_HOST,
        port=s.APP_PORT,
        reload=s.APP_DEBUG,
    )


if __name__ == "__main__":
    main()
