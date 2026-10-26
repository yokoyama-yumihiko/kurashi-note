"""朝のニュースの「候補」を集める（AIは使わない）。

使い方:
    python3 tools/collect_news.py            # 今日の日付で data/_candidates/YYYY-MM-DD.json と .txt を作る
    python3 tools/collect_news.py --days 2   # 何日前までの記事を拾うか（初期値 2）

各サイトの一覧ページから見出し・リンク・日付だけを集め、暮らしに関わる言葉で並べ替えて
上位を残す。記事の中身は読まない（候補ごとの一言説明はページの description から取る）。
ここで作るのは下書きの材料で、公開用のデータ（data/news/）は AI が候補から選んで書き、
本人が確認してから公開する。data/_candidates/ は公開しない（.gitignore）。

外部ライブラリは使わない（Python 3.9 標準のみ）。サイトの作りが変わると拾えなくなるので、
0件のサイトがあれば最後に表示する。
全国は国（厚生労働省・デジタル庁・文部科学省・消費者庁・政府広報・気象庁・国民生活センター）の発表、
海外は BBCニュース Japan の見出しを少しだけ集める（NHKのRSSは2026-08で更新停止のため使わない）。
寒川町は町の公式サイトの新着（2026-10-26 追加）。

前日6:00〜当日6:00（日本時間）の更新を優先する。時刻がわかる情報源は時刻で、日付だけのものは日付で判定し、
一覧の日付の横に「◎」を付けて上に並べる。

情報源ごとの取得ログ（最終取得日時・成功/失敗・HTTP・取得件数・エラー）を
data/_logs/sources.jsonl に追記し、その日の分を data/_candidates/YYYY-MM-DD.sources.json に置く。
「0件」（読めたが該当なし）と「失敗」（読めなかった）は分けて表示する。

事件・事故や政治の言葉が当たった候補は、一律には捨てず、一覧の最後の「編集方針の確認が必要」に理由つきで出す
（判断は tools/verify.py と本人。2026-10-26）。掲載しないと決めた記事（data/excluded.json）は出さない。
"""

import email.utils
import html
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editorial  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "_candidates"
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (kurashi-note news collector)"
# 政府広報オンラインは上の名乗りを断る（403）ため、ふつうのブラウザの名乗りで読む
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
LOG_DIR = ROOT / "data" / "_logs"
MAX_PER_SOURCE = 12

# 暮らしに関わる度合いの目安。多く当たるほど上に並ぶ
KEYWORDS = [
    "子育て", "保育", "児童", "学校", "教育", "給付", "補助", "助成", "手当", "支援",
    "募集", "申請", "受付", "締切", "意見募集", "パブリックコメント", "防災", "災害", "避難",
    "地震", "台風", "大雨", "交通", "バス", "鉄道", "道路", "医療", "福祉", "介護", "健康",
    "感染", "ワクチン", "環境", "ごみ", "税", "料金", "物価", "雇用", "就労", "人権", "平和",
    "個人情報", "不正アクセス", "事故", "事件", "条例", "予算", "リコール", "回収", "注意喚起",
]  # 「議会」「選挙」は政治を扱わない方針のため外した（2026-10-26）
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


# いま読んでいる情報源の取得結果（main が情報源ごとに入れ替える）
TRACE = {"http": [], "errors": []}


def fetch(url, ua=UA):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            TRACE["http"].append(res.status)
            charset = res.headers.get_content_charset() or "utf-8"
            return res.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        TRACE["http"].append(e.code)
        TRACE["errors"].append(f"HTTP {e.code} {url}")
        raise
    except Exception as e:
        TRACE["errors"].append(f"{e.__class__.__name__} {url}")
        raise


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


# 藤沢市の13地区の市民センター（地区の行事・地域回覧・自治会連合会などの新着）
CENTERS = {"kata-c": "片瀬", "kuge-c": "鵠沼", "tsuji-c": "辻堂", "mura-c": "村岡", "fuji-c": "藤沢",
           "meiji-c": "明治", "zengyo-c": "善行", "snooba-c": "湘南大庭", "mutsu-c": "六会",
           "sndai-c": "湘南台", "endou-c": "遠藤", "chougo-c": "長後", "gosho-c": "御所見"}


def centers(today):
    """各市民センターのトップにある「新着情報」（日付つき、5件ずつ）。地区レベルの話題を拾う。"""
    base = "https://www.city.fujisawa.kanagawa.jp"
    for code, name in CENTERS.items():
        try:
            text = fetch(f"{base}/{code}/index.html")
        except Exception:
            continue
        rows = re.findall(r'class="date"><p>([^<]+)</p></td><td><p><a href="([^"]+)">(.*?)</a>', text, re.S)
        for md, href, title in rows:
            day = md_to_date(md, today)
            if not day or (today - day).days > 30:  # 地区の行事は早めに載るので1か月分を見る
                continue
            yield {"source_name": f"{name}市民センター", "area": "藤沢市", "title": f"【{name}地区】{clean(title)}",
                   "url": href if href.startswith("http") else base + href,
                   "date": day, "weekly": True}


def kanko(today):
    """藤沢市観光協会のトップにあるイベント一覧（開催期間つき）。"""
    text = fetch("https://www.fujisawa-kanko.jp/")
    rows = re.findall(r'<p class="extCatList5Txt">(.*?)</p>\s*<strong>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', text, re.S)
    for period, href, title in rows:
        period = clean(period).split("\n")[0].strip()
        yield {"source_name": "藤沢市観光協会", "area": "藤沢市", "title": clean(title),
               "url": href, "date": None, "excerpt": period, "kind": "event"}


# 国の発表は会議の開催告知や会見録が多いので、暮らしに直接関わらないものを外す
NATIONAL_SKIP = ("審議会", "会議", "部会", "検討会", "委員会", "会見", "懇談会", "研究会", "分科会", "協議会",
                 "民間事業者向け", "調達", "入札", "人事", "叙勲", "表彰", "採用", "職員", "業務説明会",
                 "ダッシュボード", "病院報告", "事例集", "統計表")


def rss(url, source_name, area, today, skip=(), limit=None, ua=UA):
    """RSS 2.0 / RDF の一覧（見出し・リンク・日付と、わかれば時刻）。"""
    text = fetch(url, ua)
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
        day = at = None
        if when:
            w = when.group(1).strip()
            try:
                if w[:4].isdigit():
                    at = datetime.fromisoformat(w[:25]) if len(w) >= 25 else None
                    day = datetime.fromisoformat(w[:19]).date()
                else:
                    at = email.utils.parsedate_to_datetime(w).astimezone(JST)
                    day = at.date()
            except (ValueError, TypeError):
                day = at = None
        if at is not None and at.tzinfo is None:
            at = at.replace(tzinfo=JST)
        yield {"source_name": source_name, "area": area, "title": title, "url": html.unescape(link.group(1)),
               "date": at.astimezone(JST).date() if at else day, "at": at}
        n += 1
        if limit and n >= limit:
            return


def samukawa(today):
    """寒川町の新着（町のサイトのトップが読み込んでいる index.update.json。公開日時つき、新しい順に100件）。"""
    for x in json.loads(fetch("https://www.town.samukawa.kanagawa.jp/index.update.json")):
        at = datetime.fromisoformat(x["publish_datetime"]).astimezone(JST)
        title = clean(x.get("page_name", ""))
        if any(w in title for w in NATIONAL_SKIP + ("会議",)):
            continue
        yield {"source_name": "寒川町", "area": "寒川町", "title": title, "url": x["url"],
               "date": at.date(), "at": at, "excerpt": clean(x.get("description") or "")[:160]}


def jma(today):
    """気象庁の報道発表（press_list.js の一覧。種類1＝報道発表だけ。年は令和）。"""
    text = fetch("https://www.jma.go.jp/jma/press_list.js")
    for kind, href, y, mo, d, title in re.findall(
            r"array\[num\+\+\] = \['(\d)','([^']+)','(\d+)','(\d+)','(\d+)','([^']*)'\]", text):
        if kind != "1":
            continue
        yield {"source_name": "気象庁", "area": "全国", "title": clean(title),
               "url": "https://www.jma.go.jp" + href, "date": date(2018 + int(y), int(mo), int(d))}


def kokusen(today):
    """国民生活センターの報道発表一覧。"""
    text = fetch("https://www.kokusen.go.jp/news/news.html")
    for href, title, y, mo, d in re.findall(
            r'<a href="(data/[^"]+)">(.*?)</a>\s*（(\d{4})年(\d+)月(\d+)日）', text, re.S):
        yield {"source_name": "国民生活センター", "area": "全国", "title": clean(title),
               "url": "https://www.kokusen.go.jp/news/" + href, "date": date(int(y), int(mo), int(d))}


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


def in_window(c, since):
    """前日6:00〜当日6:00（日本時間）の更新か。時刻がわかれば時刻で、日付だけなら日付で判定する。"""
    if c.get("at"):
        return since <= c["at"] < since + timedelta(days=1)
    return bool(c.get("date")) and c["date"] >= since.date()


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
        "藤沢市 地区の市民センター": lambda: centers(today),
        # 全国（国の発表）と海外は、暮らしに関わるものを少しだけ
        "寒川町 新着": lambda: samukawa(today),
        "厚生労働省": lambda: rss("https://www.mhlw.go.jp/stf/news.rdf", "厚生労働省", "全国", today, NATIONAL_SKIP),
        "デジタル庁": lambda: rss("https://www.digital.go.jp/rss/news.xml", "デジタル庁", "全国", today, NATIONAL_SKIP),
        "文部科学省": lambda: rss("https://www.mext.go.jp/b_menu/news/index.rdf", "文部科学省", "全国", today, NATIONAL_SKIP),
        "消費者庁": lambda: rss("https://www.caa.go.jp/news.rss", "消費者庁", "全国", today, NATIONAL_SKIP),
        "政府広報オンライン": lambda: rss("https://www.gov-online.go.jp/rss/index.rdf", "政府広報オンライン", "全国", today,
                                   NATIONAL_SKIP + ("総理", "首脳", "会談", "ビデオメッセージ", "くにおとたみよ"), ua=BROWSER_UA),
        "気象庁": lambda: jma(today),
        "国民生活センター": lambda: kokusen(today),
        "BBCニュース Japan": lambda: rss("https://feeds.bbci.co.uk/japanese/rss.xml", "BBCニュース Japan", "海外", today),
    }
    # 出典ごとの上限（全国・海外は少なめ）
    caps = {"藤沢市 地区の市民センター": 20, "厚生労働省": 5, "デジタル庁": 3, "文部科学省": 3, "BBCニュース Japan": 4,
            "消費者庁": 4, "政府広報オンライン": 3, "気象庁": 3, "国民生活センター": 3}
    since = datetime.combine(today - timedelta(days=1), datetime.min.time(), JST).replace(hour=6)

    candidates, review, report, logs, seen = [], [], [], [], set()
    excluded, held = editorial.excluded_urls(), 0
    for name, read in sources.items():
        TRACE["http"], TRACE["errors"] = [], []
        log = {"source": name, "fetched_at": datetime.now(JST).isoformat(timespec="seconds"),
               "ok": False, "http": None, "raw_count": 0, "count": 0, "error": ""}
        try:
            got = []
            for c in read():
                log["raw_count"] += 1
                if not c["title"] or not c["url"].startswith("https://") or c["url"] in seen:
                    continue
                if "茅ヶ崎" in c["title"] or "茅ケ崎" in c["title"]:
                    continue
                if any(w in c["title"] for w in SKIP_WORDS) or DEPT_ONLY.search(c["title"]):
                    continue
                if editorial.is_excluded(c["url"], excluded):
                    held += 1
                    continue
                if c["date"] and not c.get("weekly") and (today - c["date"]).days > days:
                    continue
                c["score"] = score(c)
                c["kind"] = kind_of(c)
                c["fresh"] = in_window(c, since)
                # 事件・事故・政治などは一律に捨てず、理由をつけて「確認が必要」に回す（2026-10-26）
                holds, warns = editorial.assess([c["title"], c.get("excerpt", "")])
                if holds:
                    c["review"] = holds[0]
                    seen.add(c["url"])
                    review.append(c)
                    continue
                got.append(c)
            # 前日6時〜当日6時のものを先に、そのなかで点の高い順
            got.sort(key=lambda c: (c["fresh"], c["score"], str(c["date"])), reverse=True)
            # 種類（ニュース・イベント・グルメ）ごとに上限を数える
            cap = caps.get(name, MAX_PER_SOURCE)
            got = [c for k in ("news", "event", "food")
                   for c in [c for c in got if c["kind"] == k][:cap]]
            for c in got:
                seen.add(c["url"])
                if not c.get("excerpt") and c["score"] > 0:
                    describe(c)
            candidates += got
            log.update({"ok": True, "count": len(got)})
            report.append(f"{name}: {len(got)}件" + ("（読めたが該当なし）" if not got else ""))
        except Exception as e:
            log["error"] = f"{e.__class__.__name__}: {str(e)[:120]}"
            report.append(f"{name}: 失敗（{log['error']}）")
        codes = TRACE["http"]
        log["http"] = codes[0] if len(set(codes)) == 1 else (codes[:5] or None)
        if TRACE["errors"] and log["ok"]:  # 一覧は読めたが、一部のページで失敗（地区の市民センターなど）
            log["error"] = f"一部失敗 {len(TRACE['errors'])}件：" + "／".join(TRACE["errors"][:3])
        logs.append(log)

    candidates += review
    for c in candidates:
        c["date"] = c["date"].isoformat() if c["date"] else ""
        c["at"] = c["at"].isoformat() if c.get("at") else ""
        c.pop("weekly", None)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / "sources.jsonl").open("a", encoding="utf-8") as f:
        f.write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in logs))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{today.isoformat()}.json"
    out.write_text(json.dumps({"date": today.isoformat(), "candidates": candidates},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # AI が読む用の短い一覧（JSON より文字数が少なく、利用枠を節約できる）
    # URL・出典は tools/make_brief.py が番号から埋めるので載せない。種類ごとにまとめる
    lines = [f"{today.isoformat()} 候補 {len(candidates)}件（番号｜地域｜日付｜点｜見出し｜説明）"
             "　日付の◎＝前日6時〜当日6時の更新"]
    for kind, label in (("news", "ニュース"), ("event", "イベント"), ("food", "グルメ")):
        lines.append(f"## {label}")
        for i, c in enumerate(candidates, 1):
            if c["kind"] == kind and not c.get("review"):
                lines.append("｜".join([str(i), c["area"], c["date"][5:] + ("◎" if c["fresh"] else ""), str(c["score"]),
                                       c["title"], c.get("excerpt", "")[:100]]))
    lines.append("## 編集方針の確認が必要（そのままでは載せない。住民への具体的な影響・必要な行動があるときだけ）")
    for i, c in enumerate(candidates, 1):
        if c.get("review"):
            lines.append("｜".join([str(i), c["area"], c["date"][5:], c["title"][:50], c["review"]]))
    brief_out = OUT_DIR / f"{today.isoformat()}.txt"
    brief_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"候補 {len(candidates)}件 → {out.relative_to(ROOT)}（AI用の短い一覧：{brief_out.relative_to(ROOT)}）")
    (OUT_DIR / f"{today.isoformat()}.sources.json").write_text(
        json.dumps(logs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for line in report:
        print("  -", line)
    if review:
        print(f"  - 編集方針の確認が必要（事件・事故・政治など）：{len(review)}件（一覧の最後）")
    if held:
        print(f"  - 掲載しないと決めた記事（data/excluded.json）として外したもの：{held}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
