(function readDocument(kind, limit) {
  const text = (root, selector) => root.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim() || null;
  const attr = (root, selector, name) => root.querySelector(selector)?.getAttribute(name) || null;
  const shopId = value => value?.match(/\/shop\/([A-Za-z0-9_-]+)/)?.[1] || null;
  const canonical = href => {
    if (!href) return null;
    try {
      const url = new URL(href, 'https://www.dianping.com');
      const id = shopId(url.pathname);
      // Do not return tracking parameters, query signatures or foreign URLs.
      return url.hostname === 'www.dianping.com' && id ? `https://www.dianping.com/shop/${id}` : null;
    } catch { return null; }
  };
  if (kind === 'search') {
    const seen = new Set();
    const items = [...document.querySelectorAll('#shop-all-list li, .shop-list li')].map(item => {
      const url = canonical(attr(item, '.tit a, a[data-click-name="shop_title_click"], a[href*="/shop/"]', 'href'));
      return {
        id: shopId(url), name: text(item, '.tit h4, h4'), url,
        address: text(item, '.tag-addr .addr, .addr'), category: text(item, '.tag-addr a'),
        reviewCount: text(item, '.review-num'), averagePrice: text(item, '.mean-price'),
        rating: attr(item, '[class*="rank-stars"]', 'title')
      };
    }).filter(item => {
      if (!item.id || !item.name || seen.has(item.id)) return false;
      seen.add(item.id); return true;
    }).slice(0, limit);
    const visibleText = (document.body?.innerText || '').replace(/\s+/g, ' ');
    const empty = Boolean(document.querySelector('.shop-list-empty, .search-empty, .not-found')) || /没有找到相关商户|未找到相关商户|没有找到符合条件的商户/.test(visibleText);
    return {items, emptyState: empty};
  }
  const reviews = [...document.querySelectorAll('.reviews-items > ul > li, .review-list > ul > li')]
    .slice(0, limit).map(item => ({
      content: text(item, '.review-words'), author: text(item, '.name'),
      publishedAt: text(item, '.time')
    })).filter(item => item.content);
  return {
    id: shopId(location.pathname), url: canonical(location.href),
    name: text(document, '.shopName, h1.shop-name, .shop-name, h1'),
    address: text(document, '.addressText, .expand-info.address .item, .shop-addr'),
    rating: text(document, '.star-score') || attr(document, '[class*="rank-stars"]', 'title'),
    reviewCount: text(document, '.reviews, #reviewCount, .review-count'),
    averagePrice: text(document, 'span.price, #avgPriceTitle, .average'),
    openingHours: text(document, '.biz-time, [itemprop="openingHours"]'),
    businessStatus: text(document, '.biz-txt'), category: text(document, '.category'),
    region: text(document, '.region'), reviews,
    reviewsStatus: reviews.length ? 'available' : 'not_visible_on_page'
  };
})
