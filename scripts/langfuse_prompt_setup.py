"""Quản lý prompt `day13-chat` trên project Langfuse cá nhân (đọc key từ .env).

    python scripts/langfuse_prompt_setup.py status     # in version + labels hiện tại
    python scripts/langfuse_prompt_setup.py create     # tạo v1 (baseline, production) và v2 (candidate) nếu chưa có
    python scripts/langfuse_prompt_setup.py promote    # production -> version mới nhất (v2)
    python scripts/langfuse_prompt_setup.py rollback   # production -> version đầu (v1)

Code của app không đổi khi đổi version: app chỉ hỏi Langfuse theo LANGFUSE_PROMPT_NAME/LABEL.
Sau promote/rollback, cache prompt của API là 60 giây; khởi động lại API để thấy ngay.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio

PROMPT_V1 = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
PROMPT_V2 = (
    "You are a concise support assistant. Answer in at most 3 short bullet points "
    "using only the docs.\nFeature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
)


def versions(client, name: str) -> list:
    found = []
    version = 1
    while True:
        try:
            prompt = client.get_prompt(name, version=version, type="text", cache_ttl_seconds=0, max_retries=0)
        except Exception:
            return found
        found.append(prompt)
        version += 1


def print_status(client, name: str) -> None:
    items = versions(client, name)
    print(f"[{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}] prompt '{name}': {len(items)} version(s)")
    for prompt in items:
        print(f"  v{prompt.version}: labels={sorted(prompt.labels)} | {prompt.prompt.splitlines()[0][:70]}")


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["status", "create", "promote", "rollback"])
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        print("Thiếu LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY trong .env")
        return 1

    from langfuse import get_client

    client = get_client()
    if not client.auth_check():
        print("Langfuse auth_check thất bại: kiểm tra key và LANGFUSE_BASE_URL")
        return 1
    name = os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    existing = versions(client, name)

    if args.action == "create":
        if not existing:
            client.create_prompt(name=name, prompt=PROMPT_V1, labels=["baseline", "production"], type="text")
            print("Đã tạo v1 với labels baseline, production")
        if len(versions(client, name)) < 2:
            client.create_prompt(name=name, prompt=PROMPT_V2, labels=["candidate"], type="text")
            print("Đã tạo v2 với label candidate")
    elif args.action in {"promote", "rollback"}:
        if len(existing) < 2:
            print("Cần ít nhất 2 version; chạy 'create' trước")
            return 1
        print("Trước:")
        print_status(client, name)
        if args.action == "promote":
            target = existing[-1]
            client.update_prompt(name=name, version=target.version, new_labels=["candidate", "production"])
        else:
            target = existing[0]
            client.update_prompt(name=name, version=target.version, new_labels=["baseline", "production"])
        print(f"Đã chuyển label production -> v{target.version}. Sau:")

    print_status(client, name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
