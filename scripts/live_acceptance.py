"""Opt-in read-only acceptance. Credentials/profile contents are never exported."""

import argparse
import asyncio
import json
from pathlib import Path

from dazhongdianping_tools import DianpingClient


async def run(args):
    async with DianpingClient(profile_dir=args.profile_dir, chrome_path=args.chrome_path) as client:
        session = await client.check_session()
        search = await client.search(args.keyword, city=args.city, limit=5)
        selected = args.shop_id or search["data"]["items"][0]["id"]
        detail = await client.detail(selected)
    return {
        "type": "read-only-live-acceptance",
        "notAnOfficialApi": True,
        "session": session,
        "search": search,
        "detail": detail,
        "limits": [
            "One search and one exact shop detail; this is not a platform-wide reliability claim.",
            "Only current rendered page data is read; missing reviews are not zero reviews.",
            "No private profile path, cookies, request headers or signatures are exported.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-dir", required=True)
    parser.add_argument("--chrome-path")
    parser.add_argument("--keyword", default="咖啡")
    parser.add_argument("--city", default="广州")
    parser.add_argument("--shop-id")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "count": result["search"]["data"]["count"],
                "shop": result["detail"]["data"]["name"],
                "reviewsStatus": result["detail"]["data"]["reviewsStatus"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
