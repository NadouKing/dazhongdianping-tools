"""JSON-first CLI; errors are machine-readable and do not expose browser internals."""

import argparse
import asyncio
import json
import sys

from . import __version__
from .client import DianpingClient
from .errors import DianpingError


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        raise DianpingError("invalid_arguments", "命令参数不正确，请运行 dp --help。")


def parser() -> argparse.ArgumentParser:
    root = JsonArgumentParser(description="大众点评只读工具（本机 Chrome / CDP）")
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--profile-dir", help="专用 Chrome 用户目录；也可设置 DP_PROFILE_DIR")
    root.add_argument("--chrome-path", help="Chrome 可执行文件；也可设置 DP_CHROME_PATH")
    root.add_argument("--timeout", type=float, default=30, help="浏览器/页面超时秒数")
    root.add_argument("--visible", action="store_true", help="显示专用浏览器窗口")
    root.add_argument(
        "--verification-wait",
        type=float,
        default=0,
        help="遇人工验证时在原页面等待的秒数（0–600，须 --visible）",
    )
    commands = root.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="按城市、关键词搜索商家")
    search.add_argument("keyword")
    search.add_argument("--city", default="广州")
    search.add_argument("--limit", type=int, default=20)
    detail = commands.add_parser("detail", help="按精确商家 ID 读取详情")
    detail.add_argument("item_id")
    detail.add_argument("--limit", type=int, default=10, help="最多读取当前页面可见评论数")
    commands.add_parser("session", help="检查登录/人工验证状态")
    login = commands.add_parser("login", help="打开可见专用浏览器，等待人工登录")
    login.add_argument("--wait", type=float, default=180)
    return root


async def run(args):
    async with DianpingClient(
        profile_dir=args.profile_dir,
        chrome_path=args.chrome_path,
        headless=not (args.visible or args.command == "login"),
        timeout=args.timeout,
        verification_wait=args.verification_wait,
    ) as client:
        if args.command == "search":
            return await client.search(args.keyword, city=args.city, limit=args.limit)
        if args.command == "detail":
            return await client.detail(args.item_id, limit=args.limit)
        if args.command == "login":
            return await client.login(wait=args.wait)
        return await client.check_session()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        args = parser().parse_args()
        result = asyncio.run(run(args))
    except DianpingError as error:
        print(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "status": "error",
                    "source": "dianping",
                    "error": error.as_dict(),
                },
                ensure_ascii=False,
            )
        )
        return 1
    except KeyboardInterrupt:
        print(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "status": "error",
                    "source": "dianping",
                    "error": {"code": "interrupted", "message": "操作已取消。"},
                },
                ensure_ascii=False,
            )
        )
        return 130
    except Exception:
        print(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "status": "error",
                    "source": "dianping",
                    "error": {
                        "code": "internal_error",
                        "message": "工具发生内部错误，请检查浏览器配置或提交脱敏诊断。",
                    },
                },
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
