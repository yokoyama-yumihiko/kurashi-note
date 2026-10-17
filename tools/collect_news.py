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
全国ニュースは機械で読める安定した一覧が見つからなかった（NHKのRSSは2026-08で更新停止）ため、
下書きを作るAIが1〜2本だけ調べて足す。
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


def townnews(edition, area, must, today):
    base = "https://www.townnews.co.jp"
    text = fetch(f"{base}/{edition}/")
    seen = set()
    for m in re.finditer(rf'(?:{base})?/{edition}/(\d{{4}})/(\d{{2}})/(\d{{2}})/(\d+)\.html', text):
        url = f"{base}/{edition}/{m.group(1)}/{m.group(2)}/{m.group(3)}/{m.group(4)}.html"
        if url in seen or len(seen) >= 20:  # 記事ページを読みすぎない
            continue
        seen.add(url)
        day = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        if (today - day).days > 6:  # タウンニュースは週刊なので少し長めに見る
            continue
        page = fetch(url)
        t = re.search(r"<title>([^<|]+)", page)
        desc = re.search(r'<meta property="og:description" content="([^"]*)"', page)
        title = clean(t.group(1)) if t else ""
        excerpt = clean(desc.group(1))[:160] if desc else ""
        if must and must not in title + excerpt:
            continue
        yield {"source_name": "タウンニュース", "area": area, "title": title, "url": url,
               "date": day, "excerpt": excerpt, "weekly": True}


# ---------- まとめ ----------

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
        "タウンニュース藤沢": lambda: townnews("0601", "藤沢市", None, today),
        "タウンニュース寒川": lambda: townnews("0603", "寒川町", "寒川", today),
    }

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
                got.append(c)
            got.sort(key=lambda c: (c["score"], str(c["date"])), reverse=True)
            got = got[:MAX_PER_SOURCE]
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
    print(f"候補 {len(candidates)}件 → {out.relative_to(ROOT)}")
    for line in report:
        print("  -", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
