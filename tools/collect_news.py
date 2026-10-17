"""朝のニュースの「候補」を集める（AIは使わない）。

使い方:
    python3 tools/collect_news.py            # 今日の日付で data/_candidates/YYYY-MM-DD.json を作る
    python3 tools/collect_news.py --days 2   # 何日前までの記事を拾うか（初期値 2）

各サイトの一覧ページから見出し・リンク・日付だけを集め、暮らしに関わる言葉で並べ替えて
上位を残す。記事の中身は読まない（候補ごとの一言説明はページの description から取る）。
ここで作るのは下書きの材料で、公開用のデータ（data/news/）は AI が候補から選んで書き、
本人が確認してから公開する。data/_candidates/ は公開しない（.gitignore）。

外部ライブラリは使わない（Python 3.9 標準のみ）。サイトの作りが変わると拾えなくなるので、
0件のサイトがあれば最後に表示する。
全国は国（厚生労働省・デジタル庁・文部科学省）の発表、海外は BBCニュース Japan の見出しを少しだけ集める
（NHKのRSSは2026-08で更新停止のため使わない）。ふだんは ChatGPT の朝のブリーフ（import_handoff.py）が主で、これは予備。
"""

import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "_candidates"
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (YokoyamaPolicyLab news collector)"
MAX_PER_SOURCE = 12

# 暮らしに関わる度合いの目安。多く当たるほど上に並ぶ
KEYWORDS = [
    "子育て", "保育", "児童", "学校", "教育", "給付", "補助", "助成", "手当", "支援",
    "募集", "申請", "受付", "締切", "意見募集", "パブリックコメント", "防災", "災害", "避難",
    "地震", "台風", "大雨", "交通", "バス", "鉄道", "道路", "医療", "福祉", "介護", "健康",
    "感染", "ワクチン", "環境", "ごみ", "税", "料金", "物価", "雇用", "就労", "人権", "平和",
    "個人情報", "不正アクセス", "事故", "事件", "条例", "予算", "議会", "選挙",
]
# 一覧に混じる「暮らしのニュースではないページ」
SKIP_WORDS = ["お知らせ（news）", "通信", "マンホールカード", "フロアガイド", "職員採用", "入札", "落札",
              "市政報告", "県政報告", "議会報告", "議員"]  # 議員の活動報告（広告）は載せない
# まちの話題の振り分け（kind）。イベント・グルメは「まちのイベント・グルメ」ページの候補になる
EVENT_WORDS = re.compile(r"(まつり|祭|フェス|フェア|マルシェ|ライブ|コンサート|展示|個展|上映|講演|鑑賞会|体験|大会|ショー|"
                         r"盆踊り|花火|イベント|ワークショップ|開催|開幕)")
FOOD_WORDS = re.compile(r"(オープン|開店|新店|グルメ|カフェ|ラーメン|パン|ベーカリー|スイーツ|レストラン|食堂|ランチ|"
                        r"居酒屋|アイス|弁当|キッチン|ごはん|酒蔵|どぶろく|直売)")
# タウンニュースの記事の種類（ページ内の最初の <span class="tag">）。広告とコラムは使わない
TOWNNEWS_SKIP_TAGS = ("ピックアップ（PR）", "あっとほーむデスク")

# 部署名だけの見出し（例：「県土整備局 道路部道路管理課」）
DEPT_ONLY = re.compile(r"(局|部|課|室|センター|科)$")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as res:
        charset = res.headers.get_content_charset() or "utf-8"
        return res.read().decode(charset, errors="replace")


def clean(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def md_to_date(md, today):
    """「10月16日」→ 日付。年またぎ（1月に12月の記事）も考える。"""
    m = re.match(r"(\d+)月(\d+)日", md)
    if not m:
        return None
    d = today.replace(month=int(m.group(1)), day=int(m.group(2)))
    return d if d <= today else d.replace(year=d.year - 1)


# ---------- サイトごとの読み方 ----------

def fujisawa(url, source_name, today):
    base = "https://www.city.fujisawa.kanagawa.jp"
    text = fetch(url)
    rows = re.findall(r'news_date">([^<]+)</td>\s*<td class="news_link"><a href="([^"]+)">(.*?)</a>', text, re.S)
    for md, href, title in rows:
        yield {"source_name": source_name, "area": "藤沢市", "title": clean(title),
               "url": href if href.startswith("http") else base + href, "date": md_to_date(md, today)}


def kanagawa(today):
    base = "https://www.pref.kanagawa.jp"
    text = fetch(base + "/news/index.html")
    for y, mo, d, href, title in re.findall(
            r'<dt>(\d{4})年(\d+)月(\d+)日</dt><dd><a href="([^"]+)">(.*?)</a>', text, re.S):
        yield {"source_name": "神奈川県", "area": "神奈川県", "title": clean(title),
               "url": href if href.startswith("http") else base + href,
               "date": datetime(int(y), int(mo), int(d)).date()}


def townnews(edition, area, must, source_name, today):
    base = "https://www.townnews.co.jp"
    text = fetch(f"{base}/{edition}/")
    seen = set()
    for m in re.finditer(rf'(?:{base})?/{edition}/(\d{{4}})/(\d{{2}})/(\d{{2}})/(\d+)\.html', text):
        url = f"{base}/{edition}/{m.group(1)}/{m.group(2)}/{m.group(3)}/{m.group(4)}.html"
        if url in seen or len(seen) >= 45:  # 記事ページを読みすぎない（1週間分でおよそ50本、うち広告が2割ほど）
            continue
        seen.add(url)
        day = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        if (today - day).days > 6:  # タウンニュースは週刊なので少し長めに見る
            continue
        page = fetch(url)
        tag = re.search(r'<span class="tag">([^<]+)<', page)
        if tag and tag.group(1).strip() in TOWNNEWS_SKIP_TAGS:  # 広告（PR）・編集後記は載せない
            continue
        t = re.search(r"<title>([^<|]+)", page)
        desc = re.search(r'<meta property="og:description" content="([^"]*)"', page)
        title = clean(t.group(1)) if t else ""
        excerpt = clean(desc.group(1))[:160] if desc else ""
        if must and must not in title + excerpt:
            continue
        yield {"source_name": source_name, "area": area, "title": title, "url": url,
               "date": day, "excerpt": excerpt, "weekly": True}


def kanko(today):
    """藤沢市観光協会のトップにあるイベント一覧（開催期間つき）。"""
    text = fetch("https://www.fujisawa-kanko.jp/")
    rows = re.findall(r'<p class="extCatList5Txt">(.*?)</p>\s*<strong>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', text, re.S)
    for period, href, title in rows:
        period = clean(period).split("\n")[0].strip()
        yield {"source_name": "藤沢市観光協会", "area": "藤沢市", "title": clean(title),
               "url": href, "date": None, "excerpt": period, "kind": "event"}


# 国の発表は会議の開催告知や会見録が多いので、暮らしに直接関わらないものを外す
NATIONAL_SKIP = ("審議会", "部会", "検討会", "委員会", "会見", "懇談会", "研究会", "分科会", "協議会",
                 "民間事業者向け", "調達", "入札", "人事", "叙勲", "表彰", "採用", "職員", "業務説明会",
                 "ダッシュボード", "病院報告", "事例集", "統計表")


def rss(url, source_name, area, today, skip=(), limit=None):
    """RSS 2.0 / RDF の一覧（見出し・リンク・日付）。"""
    text = fetch(url)
    n = 0
    for block in re.findall(r"<item[ >].*?</item>", text, re.S):
        title = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.S)
        link = re.search(r"<link>(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?</link>", block, re.S)
        when = re.search(r"<(?:pubDate|dc:date)>([^<]+)<", block)
        if not title or not link:
            continue
        title = clean(title.group(1))
        if any(w in title for w in skip):
            continue
        day = None
        if when:
            w = when.group(1).strip()
            try:
                day = datetime.fromisoformat(w[:19]).date() if w[:4].isdigit() else \
                    datetime.strptime(w[5:16], "%d %b %Y").date()
            except ValueError:
                day = None
        yield {"source_name": source_name, "area": area, "title": title, "url": link.group(1), "date": day}
        n += 1
        if limit and n >= limit:
            return


# ---------- まとめ ----------

def kind_of(c):
    if c.get("kind"):
        return c["kind"]
    text = c["title"] + c.get("excerpt", "")
    if FOOD_WORDS.search(c["title"]):
        return "food"
    if EVENT_WORDS.search(text):
        return "event"
    return "news"


def score(c):
    text = c["title"] + c.get("excerpt", "")
    return sum(1 for k in KEYWORDS if k in text)


def describe(c):
    """一覧に説明がないものだけ、ページの description を1回読む。"""
    if c.get("excerpt"):
        return
    try:
        page = fetch(c["url"])
    except Exception:
        return
    m = re.search(r'<meta name="description" content="([^"]*)"', page)
    if m and clean(m.group(1)):
        c["excerpt"] = clean(m.group(1))[:160]


def main():
    days = 2
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    today = datetime.now(JST).date()

    sources = {
        "藤沢市 記者発表": lambda: fujisawa("https://www.city.fujisawa.kanagawa.jp/pressreleases/index.html", "藤沢市（記者発表）", today),
        "藤沢市 新着": lambda: fujisawa("https://www.city.fujisawa.kanagawa.jp/shinchaku/index.html", "藤沢市", today),
        "神奈川県 新着": lambda: kanagawa(today),
        "タウンニュース藤沢": lambda: townnews("0601", "藤沢市", None, "タウンニュース藤沢版", today),
        "タウンニュース寒川": lambda: townnews("0603", "寒川町", "寒川", "タウンニュース茅ヶ崎・寒川版", today),
        "藤沢市観光協会 イベント": lambda: kanko(today),
        # 全国（国の発表）と海外は、暮らしに関わるものを少しだけ
        "厚生労働省": lambda: rss("https://www.mhlw.go.jp/stf/news.rdf", "厚生労働省", "全国", today, NATIONAL_SKIP),
        "デジタル庁": lambda: rss("https://www.digital.go.jp/rss/news.xml", "デジタル庁", "全国", today, NATIONAL_SKIP),
        "文部科学省": lambda: rss("https://www.mext.go.jp/b_menu/news/index.rdf", "文部科学省", "全国", today, NATIONAL_SKIP),
        "BBCニュース Japan": lambda: rss("https://feeds.bbci.co.uk/japanese/rss.xml", "BBCニュース Japan", "海外", today),
    }
    # 出典ごとの上限（全国・海外は少なめ）
    caps = {"厚生労働省": 5, "デジタル庁": 3, "文部科学省": 3, "BBCニュース Japan": 4}

    candidates, report, seen = [], [], set()
    for name, read in sources.items():
        try:
            got = []
            for c in read():
                if not c["title"] or not c["url"].startswith("https://") or c["url"] in seen:
                    continue
                if "茅ヶ崎" in c["title"] or "茅ケ崎" in c["title"]:
                    continue
                if any(w in c["title"] for w in SKIP_WORDS) or DEPT_ONLY.search(c["title"]):
                    continue
                if c["date"] and not c.get("weekly") and (today - c["date"]).days > days:
                    continue
                c["score"] = score(c)
                c["kind"] = kind_of(c)
                got.append(c)
            got.sort(key=lambda c: (c["score"], str(c["date"])), reverse=True)
            # 種類（ニュース・イベント・グルメ）ごとに上限を数える
            cap = caps.get(name, MAX_PER_SOURCE)
            got = [c for k in ("news", "event", "food")
                   for c in [c for c in got if c["kind"] == k][:cap]]
            for c in got:
                seen.add(c["url"])
                if not c.get("excerpt") and c["score"] > 0:
                    describe(c)
            candidates += got
            report.append(f"{name}: {len(got)}件")
        except Exception as e:
            report.append(f"{name}: 読めませんでした（{e.__class__.__name__}）")

    for c in candidates:
        c["date"] = c["date"].isoformat() if c["date"] else ""
        c.pop("weekly", None)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{today.isoformat()}.json"
    out.write_text(json.dumps({"date": today.isoformat(), "candidates": candidates},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # AI が読む用の短い一覧（JSON より文字数が少なく、利用枠を節約できる）
    # URL・出典は tools/make_brief.py が番号から埋めるので載せない。種類ごとにまとめる
    lines = [f"{today.isoformat()} 候補 {len(candidates)}件（番号｜地域｜日付｜点｜見出し｜説明）"]
    for kind, label in (("news", "ニュース"), ("event", "イベント"), ("food", "グルメ")):
        lines.append(f"## {label}")
        for i, c in enumerate(candidates, 1):
            if c["kind"] == kind:
                lines.append("｜".join([str(i), c["area"], c["date"][5:], str(c["score"]),
                                       c["title"], c.get("excerpt", "")[:100]]))
    brief_out = OUT_DIR / f"{today.isoformat()}.txt"
    brief_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"候補 {len(candidates)}件 → {out.relative_to(ROOT)}（AI用の短い一覧：{brief_out.relative_to(ROOT)}）")
    for line in report:
        print("  -", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
