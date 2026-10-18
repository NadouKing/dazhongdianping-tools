"""Actual packaged JavaScript against synthetic HTML, with no platform/account access."""

import asyncio
import json
from importlib.resources import files

import pytest

from dazhongdianping_tools.browser import ChromeBrowser, chrome_executable
from dazhongdianping_tools.errors import DianpingError


def test_dom_reader_and_canonical_urls_in_temporary_chrome(tmp_path):
    try:
        chrome_executable(None)
    except DianpingError:
        pytest.skip("Chrome unavailable; CDP contract tests remain browser-independent")

    async def run():
        browser = ChromeBrowser(profile_dir=tmp_path / "test-profile")
        try:
            await browser.start()
            target = await browser.cdp.send("Target.createTarget", {"url": "about:blank"})
            attached = await browser.cdp.send(
                "Target.attachToTarget", {"targetId": target["targetId"], "flatten": True}
            )
            session = attached["sessionId"]
            reader = files("dazhongdianping_tools").joinpath("page_reader.js").read_text("utf-8")

            async def read(html, kind, path="/shop/shop123"):
                expression = (
                    "(()=>{const document=new DOMParser().parseFromString("
                    + json.dumps(html)
                    + ",'text/html');const location={pathname:"
                    + json.dumps(path)
                    + ",href:"
                    + json.dumps("https://www.dianping.com" + path)
                    + "};return "
                    + reader
                    + "("
                    + json.dumps(kind)
                    + ",5);})()"
                )
                return await browser.cdp.evaluate(expression, session)

            detail = await read(
                '<h1 class="shopName">测试咖啡</h1><div class="addressText">示例路1号</div>'
                '<span class="star-score">4.4</span><span class="reviews">84条</span>'
                '<span class="price">¥22/人</span><span class="biz-txt">休息中</span>'
                '<span class="biz-time">次日07:30开始营业</span>'
                '<div class="reviews-items"><ul><li><div class="review-words">安静</div>'
                '<span class="name">匿名</span><span class="time">2026-10-18</span>'
                "</li></ul></div>",
                "detail",
            )
            assert detail["id"] == "shop123"
            assert detail["address"] == "示例路1号"
            assert detail["rating"] == "4.4"
            assert detail["averagePrice"] == "¥22/人"
            assert detail["businessStatus"] == "休息中"
            assert detail["openingHours"] == "次日07:30开始营业"
            assert detail["reviewsStatus"] == "available"
            assert detail["reviews"][0]["content"] == "安静"
            no_reviews = await read('<h1 class="shopName">测试咖啡</h1>', "detail")
            assert no_reviews["reviewsStatus"] == "not_visible_on_page"
            assert no_reviews["address"] is None

            search = await read(
                '<div id="shop-all-list"><ul><li><div class="tit">'
                '<a href="/shop/shop123?signature=never-export"><h4>测试咖啡</h4></a>'
                '</div><span class="mean-price">人均 ￥22</span></li>'
                '<li><div class="tit"><a href="/shop/shop123"><h4>重复</h4></a></div></li>'
                '<li><div class="tit"><a href="https://evil.test/shop/foreign">'
                "<h4>外链</h4></a></div></li></ul></div>",
                "search",
                "/search/keyword/4/0_test",
            )
            assert len(search["items"]) == 1
            assert search["items"][0]["url"] == "https://www.dianping.com/shop/shop123"
            assert "never-export" not in json.dumps(search)
            empty = await read('<div class="shop-list-empty">没有找到相关商户</div>', "search")
            assert empty == {"items": [], "emptyState": True}
        finally:
            await browser.close()
            await browser.close()
            assert not browser.lock.path.exists()

    asyncio.run(run())
