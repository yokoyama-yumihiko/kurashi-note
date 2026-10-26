"""掲載候補を1件ずつ検証し、記録する（2026-10-26 本人決定。段階の意味は tools/gate.py）。

使い方（リポジトリの一番上で。D は YYYY-MM-DD、省略すると今日）:
    python3 tools/verify.py run [D]                 # 機械の検証（元ページを開いて本文・日付・根拠・重複・鮮度・編集方針）
    python3 tools/verify.py show [D]                # 一覧と、要約の各項目の根拠の箇所（Claude はこれを読んで照合する）
    python3 tools/verify.py review D --n 1,2 --fact ok --editorial ok [--note "..."]
                                                    # Claude が根拠の箇所を照合した結果を記録（警告があるときは --note 必須）
    python3 tools/verify.py approve D --all|--n 1,2 --note "本人の返事"
                                                    # 本人がOKと言ったときだけ実行（PUBLISH_APPROVED）
    python3 tools/verify.py hold [D]                # HOLD の一覧と理由
    python3 tools/verify.py release D --n 3 --note "本人が確かめた内容"
                                                    # HOLD を、Claude の本文照合を本人が見て確かめたときだけ戻す
    python3 tools/verify.py drop D --n 3 --reason "..." [--exclude]
                                                    # 載せないと決める（--exclude で data/excluded.json にも足す）

- 対象：data/news/D.json の記事と、data/town.json のうち added が D のイベント・グルメ。
  data/_candidates/D.seido.jsonl（制度の候補）は、期限とリンクを確かめて一覧に出すだけ（DBには入れない）
- 記録：data/_verify/D.json（公開しない。.gitignore）。取得日時・参照URL・HTTP・根拠の文・HOLDの理由・メモを残す
- 公開データには状態と日時とハッシュだけを "check" として書く（tools/gate.py）
- HOLD の記事は公開データから外し、data/_verify/D.json にだけ残す（公開リポジトリに出さない）
- 数字が本文に見つかっても、それだけで正確とはしない。FACT_VERIFIED には、根拠の箇所を Claude が読んで
  意味が合うと確かめた記録（review）が要る。根拠が見つからない・期限や曜日が合わないものは HOLD

外部ライブラリは使わない（Python 3.9 標準のみ）。
"""

import argparse
import difflib
import html
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editorial  # noqa: E402
import gate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NEWS = ROOT / "data" / "news"
TOWN = ROOT / "data" / "town.json"
KURASHI = ROOT / "data" / "kurashi.json"
SOURCES = ROOT / "data" / "sources.json"
CAND = ROOT / "data" / "_candidates"
VERIFY = ROOT / "data" / "_verify"
JST = timezone(timedelta(hours=9))
# 政府広報オンラインなど、ブラウザらしくない名乗りを断るサイトがあるため、ふつうのブラウザの名乗りにする
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
HISTORY_DAYS = 14
EVENT_AHEAD_DAYS = 30
STALE_DAYS = 7


def now():
    return datetime.now(JST).isoformat(timespec="seconds")


# ---------- 取得 ----------

def fetch(url):
    """元ページを1回開く。失敗しても例外にせず、HTTPの状態とエラーを返す。"""
    out = {"url": url, "fetched_at": now(), "http": None, "final_url": "", "ctype": "", "html": "", "error": ""}
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            out["http"], out["final_url"] = res.status, res.geturl()
            out["ctype"] = res.headers.get("Content-Type", "")
            raw = res.read(3_000_000)
            charset = res.headers.get_content_charset()
    except urllib.error.HTTPError as e:
        out["http"], out["error"] = e.code, f"HTTP {e.code}"
        return out
    except Exception as e:  # 名前解決・時間切れ・SSL など
        out["error"] = f"{e.__class__.__name__}: {str(e)[:80]}"
        return out
    if "html" not in out["ctype"] and "xml" not in out["ctype"]:
        return out
    if not charset:
        m = re.search(rb'charset=["\']?([\w-]+)', raw[:3000])
        charset = m.group(1).decode() if m else "utf-8"
    try:
        out["html"] = raw.decode(charset, errors="replace")
    except LookupError:
        out["html"] = raw.decode("utf-8", errors="replace")
    return out


# ---------- 文字の正規化 ----------

def nz(s):
    """全角→半角（NFKC）、令和→西暦、数字の桁区切りを外す、言い方のゆれをそろえる。"""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"令和\s*(元|\d+)\s*年", lambda m: f"{2018 + (1 if m.group(1) == '元' else int(m.group(1)))}年", s)
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)
    s = re.sub(r"(\d)\s+(?=[円人名件歳%時分月日年])", r"\1", s)
    s = re.sub(r"(?<=[年月日時])\s+(?=\d)", "", s)
    for a, b in (("申し込み", "申込"), ("申込み", "申込"), ("締め切り", "締切"), ("〆切", "締切"), ("〜", "~"), ("～", "~")):
        s = s.replace(a, b)
    return re.sub(r"[ \t　]+", " ", s)


def text_of(fragment):
    t = re.sub(r"(?i)<br\s*/?>|</(p|li|tr|h\d|div|dd|dt|th|td)>", "\n", fragment)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t　]+", " ", t)).strip()


# ---------- ページの読み取り ----------

MAIN_PATTERNS = (
    r'(?is)<main[^>]*>(.*?)</main>',
    r'(?is)<article[^>]*>(.*?)</article>',
    r'(?is)<div[^>]+id="(?:tmp_contents|contents|main|content|main_body|mainContents)"[^>]*>(.*)',
    r'(?is)<div[^>]+class="[^"]*(?:contents|main|article)[^"]*"[^>]*>(.*)',
)
LABEL_DATE = re.compile(r"(更新日|最終更新日|更新日時|最終更新|掲載日|公開日|発表日|報道発表日|登録日|作成日|配信日|発行日)"
                        r"\s*[:：]?\s*(\d{4})[年/.](\d{1,2})[月/.](\d{1,2})")
META_PUB = re.compile(r'(?:article:published_time|datePublished|dc\.date|pubdate|date)["\']?\s*(?:content=|:)\s*["\'](\d{4}-\d{2}-\d{2})(T\d{2}:\d{2})?')
META_MOD = re.compile(r'(?:article:modified_time|dateModified)["\']?\s*(?:content=|:)\s*["\'](\d{4}-\d{2}-\d{2})(T\d{2}:\d{2})?')
URL_DATE = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/|n-(20\d{2})(\d{2})(\d{2})|/(20\d{2})(\d{2})(\d{2})[_/.]")
LISTY = re.compile(r"/(news|shinchaku|pressreleases|press|list|search|category|tag|ichiran|new|index)(/index)?(\.html?)?/?$")


def page_info(got):
    raw = got["html"]
    clean = re.sub(r"(?is)<(script|style|noscript|svg|nav|header|footer|form)[^>]*>.*?</\1>", " ", raw)
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    og = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', raw)
    h1 = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", clean)
    body = ""
    for pat in MAIN_PATTERNS:
        m = re.search(pat, clean)
        if m and len(text_of(m.group(1))) >= 200:
            body = text_of(m.group(1))
            break
    if not body:
        m = re.search(r"(?is)<body[^>]*>(.*)", clean)
        body = text_of(m.group(1) if m else clean)
    body = nz(body)

    dates = {}  # "published"/"updated" → (YYYY-MM-DD, HH:MM or "", どこから)
    whole = nz(text_of(clean))
    for m in LABEL_DATE.finditer(whole):
        kind = "updated" if "更新" in m.group(1) else "published"
        dates.setdefault(kind, (f"{int(m.group(2)):04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}", "", m.group(1)))
    m = META_MOD.search(raw)
    if m:
        dates.setdefault("updated", (m.group(1), (m.group(2) or "")[1:], "ページの情報（modified）"))
    m = META_PUB.search(raw)
    if m:
        dates.setdefault("published", (m.group(1), (m.group(2) or "")[1:], "ページの情報（published）"))
    m = URL_DATE.search(got["final_url"] or got["url"])
    if m and "published" not in dates:
        y, mo, d = [g for g in m.groups() if g][:3]
        dates["published"] = (f"{y}-{mo}-{d}", "", "URLの日付")
    if not dates:
        m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", body[:400])
        if m:
            dates["published"] = (f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", "", "本文冒頭の日付（推定）")
    return {
        "title": nz(text_of(title.group(1))) if title else "",
        "og_title": nz(html.unescape(og.group(1))) if og else "",
        "h1": nz(text_of(h1.group(1))) if h1 else "",
        "body": body,
        "dates": dates,
    }


def norm_title(s):
    return re.sub(r"[\s「」『』【】()（）・、。,.!！?？|｜:：\-ー~〜]", "", nz(s))


def title_matches(title, *texts):
    """見出しのうち連続8文字以上（短ければ半分以上）が、ページのタイトル等に含まれるか。"""
    a = norm_title(title)
    b = norm_title(" ".join(texts))
    if not a:
        return False
    n = min(8, max(4, len(a) // 2))
    return any(a[i:i + n] in b for i in range(0, max(1, len(a) - n + 1)))


# ---------- 要約の中の「確かめるべき項目」と、本文の根拠 ----------

DATE_RE = re.compile(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日(?:\s*\(([月火水木金土日])(?:曜日?)?\))?")
RANGE_RE = re.compile(r"(\d{1,2})月(\d{1,2})日[^\d月\n]{0,8}?[~\-–][^\d\n]{0,3}(\d{1,2})日")
SLASH_RE = re.compile(r"(?<![\d/])(?:(\d{4})/)?(\d{1,2})/(\d{1,2})(?![\d/])")
ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
TIME_RE = re.compile(r"(午前|午後)?(\d{1,2})時(?:(\d{1,2})分|(半))?")
DAYONLY_RE = re.compile(r"(?<![\d月/])(\d{1,2})日\s*\(([月火水木金土日])")
CLOCK_RE = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])")
MONEY_RE = re.compile(r"((?:\d+(?:\.\d+)?[億万千]?)+)円")
COUNT_RE = re.compile(r"(\d+(?:\.\d+)?[万千]?)(人|名|件|世帯|か所|カ所|ヶ所|箇所|校|台|戸|店舗|店|組|団体|施設)")
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)(%|パーセント)")
AGE_RE = re.compile(r"(\d+)歳")
COND_WORDS = ("先着", "抽選", "無料", "要申込", "申込不要", "予約不要", "要予約", "在住", "在勤", "在学", "定員")
DEADLINE_CTX = re.compile(r"(まで|締切|必着|期限)")
WEEKDAYS = "月火水木金土日"
UNIT = {"名": "人", "カ所": "か所", "ヶ所": "か所", "箇所": "か所", "店舗": "店"}
TYPE_LABEL = {"dayonly": "日付", "date": "日付", "deadline": "期限", "time": "時刻", "money": "金額", "count": "人数・件数",
              "pct": "割合", "age": "年齢", "cond": "条件", "place": "場所"}


def jnum(s):
    total = 0.0
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)([億万千]?)", s):
        total += float(num) * {"億": 1e8, "万": 1e4, "千": 1e3, "": 1}[unit]
    return round(total, 2)


def minutes(ampm, h, m, half):
    v = int(h) * 60 + (30 if half else int(m or 0))
    return v + 720 if ampm == "午後" and int(h) < 12 else v


def keys_in(text, for_body=False):
    """文から (種類, キー, 位置, 表記) を取り出す。本文側は日付の書き方のゆれも拾う。"""
    out = []
    for m in DATE_RE.finditer(text):
        kind = "deadline" if not for_body and DEADLINE_CTX.search(text[m.end():m.end() + 8]) else "date"
        out.append((kind, (int(m.group(2)), int(m.group(3))), m.start(), m.group(0), m.group(1), m.group(4)))
    if for_body:
        for m in RANGE_RE.finditer(text):
            out.append(("date", (int(m.group(1)), int(m.group(3))), m.start(), m.group(0), None, None))
        for m in SLASH_RE.finditer(text):
            if 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31:
                out.append(("date", (int(m.group(2)), int(m.group(3))), m.start(), m.group(0), m.group(1), None))
        for m in ISO_RE.finditer(text):
            out.append(("date", (int(m.group(2)), int(m.group(3))), m.start(), m.group(0), m.group(1), None))
        for m in DAYONLY_RE.finditer(text):  # 記事でよくある「31日（土）」（月を書かない）
            out.append(("dayonly", (int(m.group(1)), m.group(2)), m.start(), m.group(0), None, None))
    for m in TIME_RE.finditer(text):
        out.append(("time", minutes(m.group(1), m.group(2), m.group(3), m.group(4)), m.start(), m.group(0), None, None))
        if for_body and not m.group(1) and int(m.group(2)) < 12 and "午後" in text[max(0, m.start() - 15):m.start()]:
            # 「午後1時半～4時」の「4時」は16時
            out.append(("time", minutes("午後", m.group(2), m.group(3), m.group(4)), m.start(), m.group(0), None, None))
    for m in CLOCK_RE.finditer(text):
        if int(m.group(1)) < 25:
            out.append(("time", int(m.group(1)) * 60 + int(m.group(2)), m.start(), m.group(0), None, None))
    for m in MONEY_RE.finditer(text):
        out.append(("money", jnum(m.group(1)), m.start(), m.group(0), None, None))
    for m in COUNT_RE.finditer(text):
        out.append(("count", (jnum(m.group(1)), UNIT.get(m.group(2), m.group(2))), m.start(), m.group(0), None, None))
    for m in PCT_RE.finditer(text):
        out.append(("pct", float(m.group(1)), m.start(), m.group(0), None, None))
    for m in AGE_RE.finditer(text):
        out.append(("age", int(m.group(1)), m.start(), m.group(0), None, None))
    for w in COND_WORDS:
        for m in re.finditer(w, text):
            out.append(("cond", w, m.start(), w, None, None))
    return out


def snippet(body, pos, width=36):
    return body[max(0, pos - width):pos + width + 10].replace("\n", " ")


def real_weekday(m, d, year_hint, day):
    """月日の曜日。年が書いていなければ、D の前後200日に入る年とみなす。"""
    years = [int(year_hint)] if year_hint else [day.year - 1, day.year, day.year + 1]
    for y in years:
        try:
            x = date(y, m, d)
        except ValueError:
            continue
        if year_hint or abs((x - day).days) <= 200:
            return WEEKDAYS[x.weekday()]
    return ""


def item_texts(item):
    if item.get("kind") in ("event", "food"):
        parts = [item.get("when", ""), item.get("summary", "")]
        for k in ("date_start", "date_end"):
            if item.get(k):
                y, mo, d = item[k].split("-")
                parts.append(f"{int(mo)}月{int(d)}日")
        return nz(" ".join(parts))
    return nz(" ".join([item.get("summary", ""), item.get("impact", "")]))


def check_facts(item, body, day):
    """要約の各項目について本文の根拠を探す。(claims, holds)"""
    claims, holds = [], []
    if not body:
        return claims, ["本文がないため根拠を確かめられない"]
    index = {}
    for kind, key, pos, _, _, _ in keys_in(body, for_body=True):
        index.setdefault(("date" if kind == "deadline" else kind, key), []).append(pos)
    seen = set()
    for kind, key, pos, shown, year, wd in keys_in(item_texts(item)):
        if (kind, key) in seen:
            continue
        seen.add((kind, key))
        c = {"type": kind, "label": TYPE_LABEL[kind], "text": shown, "evidence": "", "ok": False}
        hits = index.get(("date" if kind == "deadline" else kind, key), [])
        if kind == "deadline":
            hits = [p for p in hits if DEADLINE_CTX.search(body[max(0, p - 10):p + 24])]
            if not hits and index.get(("date", key)):
                holds.append(f"期限として本文に書かれているか確かめられない：「{shown}」")
        if not hits and kind == "date" and wd and index.get(("dayonly", (key[1], wd))):
            hits = index[("dayonly", (key[1], wd))]
            c["note"] = f"本文は「{key[1]}日（{wd}）」で月の記載なし。記事の日付から月が合うか確かめる"
        if hits:
            c["evidence"], c["ok"] = snippet(body, hits[0]), True
        elif kind != "deadline" or not index.get(("date", key)):
            holds.append(f"{TYPE_LABEL[kind]}「{shown}」の根拠が本文に見つからない")
        if kind in ("date", "deadline") and wd:
            real = real_weekday(key[0], key[1], year, day)
            if real and real != wd:
                holds.append(f"曜日が合わない：「{shown}」は実際は{real}曜日")
                c["ok"] = False
        claims.append(c)
    place = item.get("place", "") if item.get("kind") == "event" else ""
    if place:
        p = nz(place)
        c = {"type": "place", "label": "場所", "text": place, "evidence": "", "ok": False}
        if p in body:
            c["evidence"], c["ok"] = snippet(body, body.index(p)), True
        else:
            parts = [x for x in re.split(r"[\s・、,/()]", p) if len(x) >= 3]
            hit = next((x for x in parts if x in body), "")
            if not hit:  # 「湘南モノレール湘南江の島駅ビル」→ 本文「湘南江の島駅」のような一部一致
                m = difflib.SequenceMatcher(None, p, body, autojunk=False).find_longest_match(0, len(p), 0, len(body))
                if m.size >= max(4, len(p) // 2):
                    hit = p[m.a:m.a + m.size]
            if hit:
                c["evidence"], c["ok"] = snippet(body, body.index(hit)), True
                c["note"] = f"一部「{hit}」で一致"
            else:
                holds.append(f"場所「{place}」の根拠が本文に見つからない")
        claims.append(c)
    if not claims:
        claims.append({"type": "lead", "label": "本文の冒頭", "text": "（数字・日付の項目なし）",
                       "evidence": body[:120].replace("\n", " "), "ok": True})
    return claims, holds


# ---------- 情報源・鮮度・重複 ----------

def tier_of(url, sources):
    host = urllib.parse.urlparse(url).netloc.lower()
    best = ""
    for dom in sources:
        if (host == dom or host.endswith("." + dom)) and len(dom) > len(best):
            best = dom
    return sources.get(best, "")


def page_date(dates):
    vals = [v for v in dates.values() if v and v[0]]
    return max(vals) if vals else None


def check_fresh(item, info, day):
    holds, warns = [], []
    if item.get("kind") == "event":
        last = item.get("date_end") or item.get("date_start")
        try:
            start, last = date.fromisoformat(item["date_start"]), date.fromisoformat(last)
        except (KeyError, ValueError):
            return ["イベントの日付（date_start）が読めない"], []
        if last < day:
            holds.append(f"終わったイベント（{last}）")
        elif start > day + timedelta(days=EVENT_AHEAD_DAYS):
            holds.append(f"開催が{EVENT_AHEAD_DAYS}日より先（{start}）：近づいてから載せる")
        return holds, warns
    if item.get("kind") == "food":
        return holds, warns
    pd = page_date(info["dates"])
    if not pd:
        return ["公開日・更新日をページから確かめられない"], []
    d = date.fromisoformat(pd[0])
    since = datetime.combine(day - timedelta(days=1), datetime.min.time(), JST).replace(hour=6)
    if pd[1]:
        at = datetime.fromisoformat(f"{pd[0]}T{pd[1]}").replace(tzinfo=JST)
        in_window = at >= since
    else:
        in_window = d >= since.date()
    if "推定" in pd[2]:
        warns.append(f"日付は{pd[2]}：{pd[0]}")
    if d < day - timedelta(days=STALE_DAYS):
        holds.append(f"古い情報（{pd[2]} {pd[0]}）")
    elif not in_window:
        warns.append(f"前日6時より前の情報（{pd[2]} {pd[0]}）：新しい動きがあるか確かめる")
    return holds, warns


def history(day):
    """過去14日の掲載（ニュース・イベント・グルメ）と、くらしの制度。"""
    past = []
    for path in sorted(NEWS.glob("*.json")):
        if path.stem >= day.isoformat() or path.stem < (day - timedelta(days=HISTORY_DAYS)).isoformat():
            continue
        for it in json.loads(path.read_text(encoding="utf-8")).get("items", []):
            past.append(("ニュース", path.stem, it))
    if TOWN.exists():
        for t in json.loads(TOWN.read_text(encoding="utf-8")):
            past.append(("イベント" if t.get("kind") == "event" else "グルメ", t.get("added", ""), t))
    seido = json.loads(KURASHI.read_text(encoding="utf-8")) if KURASHI.exists() else []
    if isinstance(seido, dict):
        seido = seido.get("cases", [])
    return past, seido


def similar(a, b):
    a, b = norm_title(a), norm_title(b)
    if not a or not b:
        return 0.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    m = difflib.SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b))
    return max(r, 0.8 if m.size >= 12 else 0)


def check_dup(item, info, day, past, seido, same_day):
    holds, warns = [], []
    url, title = item["url"], item.get("title", "")
    pd = page_date(info["dates"]) if info else None
    for label, when, old in past + same_day:
        if old is item:
            continue
        if old.get("url") == url:
            if label == "ニュース":
                if pd and pd[0] > when:
                    warns.append(f"続報・更新の可能性：{when} にも掲載（ページの日付 {pd[0]}）。前回の要約「{old.get('summary', '')[:40]}」との違いを確かめる")
                else:
                    holds.append(f"既出：{when} に掲載済み（ページに新しい日付なし）")
            elif label != "ニュース" and item.get("kind") in ("event", "food") and when != day.isoformat():
                holds.append(f"既出：{label}として {when} から掲載中")
            continue
        s = similar(title, old.get("title", ""))
        same_event = (item.get("kind") == "event" and old.get("kind") == "event" and
                      item.get("date_start") and item.get("date_start") == old.get("date_start") and
                      (s >= 0.5 or (item.get("place") and item.get("place") == old.get("place"))))
        if same_event:
            warns.append(f"同じイベントの可能性：「{old.get('title', '')[:30]}」（{label} {when}・{old.get('url', '')}）")
        elif s >= 0.6:
            warns.append(f"似た見出し：「{old.get('title', '')[:30]}」（{label} {when}）。続報なら変わった点を要約に書く")
    for c in seido:
        if similar(title, c.get("title", "")) >= 0.6:
            warns.append(f"くらしの制度に同じ制度の可能性：「{c.get('title', '')[:30]}」")
    return holds, warns


def check_editorial(item, info, sources):
    holds, warns = [], []
    tier = tier_of(item["url"], sources)
    if not tier:
        holds.append(f"情報源リスト（data/sources.json）にないドメイン：{urllib.parse.urlparse(item['url']).netloc}")
    texts = [item.get("title", ""), item.get("summary", ""), item.get("impact", "")]
    h, w = editorial.assess(texts, info["body"] if info else "")
    holds += h
    warns += w
    if item.get("area") in ("藤沢市", "寒川町"):
        host = urllib.parse.urlparse(item["url"]).netloc
        official = host.endswith("city.fujisawa.kanagawa.jp") or host.endswith("town.samukawa.kanagawa.jp")
        if not official and not editorial.LOCAL.search(nz(" ".join(texts)) + (info["body"][:5000] if info else "")):
            warns.append(f"地域：{item['area']}としているが、本文に藤沢・寒川の地名が見当たらない")
    if not item.get("kind") and not str(item.get("impact", "")).strip():
        holds.append("暮らしへの影響（impact）がない")
    return holds, warns, tier


# ---------- 記録 ----------

def rec_path(day):
    return VERIFY / f"{day}.json"


def load_rec(day):
    p = rec_path(day)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"date": day, "entries": [], "seido": []}


def save_rec(day, rec):
    VERIFY.mkdir(parents=True, exist_ok=True)
    rec_path(day).write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def stamp(entry):
    st = entry["stages"]
    return {"status": entry["status"], "hash": entry["hash"],
            **{s: (st.get(s) or {}).get("at", "") for s in gate.STAGES if (st.get(s) or {}).get("ok")}}


def refresh_status(entry):
    if entry["location"] == "hold":
        entry["status"] = "HOLD"
    elif entry["location"] == "dropped":
        entry["status"] = "DROPPED"
    else:
        entry["status"] = gate.status_of(entry["stages"])


def load_public(day):
    npath = NEWS / f"{day}.json"
    brief = json.loads(npath.read_text(encoding="utf-8")) if npath.exists() else None
    town = json.loads(TOWN.read_text(encoding="utf-8")) if TOWN.exists() else []
    return brief, town


def save_public(day, brief, town):
    if brief is not None:
        (NEWS / f"{day}.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TOWN.write_text(json.dumps(town, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_public(day, rec):
    """記録の状態を公開データに反映する：状態のスタンプを書き、HOLD・取りやめは公開データから外す。"""
    brief, town = load_public(day)
    by_url = {e["url"]: e for e in rec["entries"]}
    for items in ([brief["items"]] if brief else []) + [town]:
        keep = []
        for it in items:
            e = by_url.get(it.get("url"))
            if e and (items is town) == (e["kind"] != "news") and (items is not town or it.get("added") == day):
                if e["location"] in ("hold", "dropped"):
                    continue
                it["check"] = stamp(e)
            keep.append(it)
        items[:] = keep
    for e in rec["entries"]:  # 戻した（release）記事を公開データに入れる
        if e["location"] == "news" and brief is not None and not any(i["url"] == e["url"] for i in brief["items"]):
            brief["items"].append({**e["item"], "check": stamp(e)})
        elif e["location"] == "news" and brief is None:
            brief = {"date": day, "keywords": [], "items": [{**e["item"], "check": stamp(e)}]}
        elif e["location"] == "town" and not any(t["url"] == e["url"] for t in town):
            town.append({**e["item"], "check": stamp(e)})
    save_public(day, brief, town)


# ---------- コマンド ----------

def targets(day):
    brief, town = load_public(day)
    out = [("news", it) for it in (brief or {}).get("items", [])]
    out += [(t.get("kind"), t) for t in town if t.get("added") == day]
    return out


def verify_one(kind, item, d, sources, past, seido, same_day):
    got = fetch(item["url"])
    info = page_info(got) if got["html"] else None
    holds, warns = [], []
    page = {k: got[k] for k in ("url", "fetched_at", "http", "final_url", "ctype", "error")}
    # 1. SOURCE
    src_ok = False
    if got["error"] or not got["http"]:
        holds.append(f"リンクが開けない（{got['error'] or '応答なし'}）")
    elif not info:
        holds.append(f"本文を機械で読めない（{got['ctype'] or '種類不明'}）")
    else:
        page.update({"title": info["title"][:120], "h1": info["h1"][:120], "body_len": len(info["body"]),
                     "dates": info["dates"]})
        path = urllib.parse.urlparse(got["final_url"]).path
        if path in ("", "/") or LISTY.search(path) and path.count("/") <= 2:
            holds.append(f"個別記事ではなく一覧・トップのページらしい（{path or '/'}）")
        elif len(info["body"]) < 150:
            holds.append(f"本文が短すぎる（{len(info['body'])}文字）")
        elif not title_matches(item.get("title", ""), info["title"], info["og_title"], info["h1"]):
            if title_matches(item.get("title", ""), info["body"][:3000]):
                warns.append("見出しはページのタイトルではなく本文中で一致")
                src_ok = True
            else:
                holds.append("見出しがページのタイトル・本文と合わない")
        else:
            src_ok = True
    claims = []
    if src_ok:
        claims, h = check_facts(item, info["body"], d)
        holds += h
    h, w = check_fresh(item, info or {"dates": {}}, d) if (src_ok or item.get("kind") == "event") else ([], [])
    holds, warns = holds + h, warns + w
    h, w = check_dup(item, info, d, past, seido, same_day)
    holds, warns = holds + h, warns + w
    h, w, tier = check_editorial(item, info, sources)
    holds, warns = holds + h, warns + w
    stages = {"source": {"ok": src_ok, "at": got["fetched_at"], "by": "verify.py"},
              "fact": {"machine_ok": src_ok and all(c["ok"] for c in claims), "ok": False}}
    return {"kind": kind, "title": item.get("title", ""), "url": item["url"], "tier": tier,
            "hash": gate.content_hash(item), "item": {k: v for k, v in item.items() if k != "check"},
            "page": page, "claims": claims, "holds": holds, "warns": warns, "stages": stages,
            "location": "hold" if holds else ("news" if kind == "news" else "town")}


def cmd_run(day):
    d = date.fromisoformat(day)
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))["domains"]
    rec = load_rec(day)
    by_url = {e["url"]: e for e in rec["entries"]}
    past, seido = history(d)
    tg = targets(day)
    same_day = [("ニュース" if k == "news" else "イベント", day, it) for k, it in tg]
    for kind, item in tg:
        old = by_url.get(item["url"])
        h = gate.content_hash(item)
        if old and old["hash"] == h and old["location"] not in ("hold", "dropped"):
            continue  # 内容が変わっていなければ、前の検証と確認の記録をそのまま使う
        entry = verify_one(kind, item, d, sources, past, seido, same_day)
        if old:
            entry["n"] = old["n"]
            entry["previous"] = {"status": old["status"], "hash": old["hash"]}
            rec["entries"][rec["entries"].index(old)] = entry
        else:
            entry["n"] = len(rec["entries"]) + 1
            rec["entries"].append(entry)
        refresh_status(entry)
    rec["seido"] = check_seido(day, d)
    rec["run_at"] = now()
    save_rec(day, rec)
    sync_public(day, rec)
    print_summary(rec)
    return 0


def check_seido(day, d):
    path = CAND / f"{day}.seido.jsonl"
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("{"):
            continue
        s = json.loads(line)
        url = s.get("primary_source") or s.get("url", "")
        got = fetch(url) if url.startswith("https://") else {"http": None, "error": "URLなし", "fetched_at": now()}
        dl = nz(str(s.get("deadline", "")))
        m = re.search(r"(\d{4})[-年](\d{1,2})[-月](\d{1,2})", dl)
        if m:
            when = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            state = "期限切れ" if when < d else f"期限内（{when}）"
        else:
            state = "期限の日付がない（本人確認）"
        out.append({"title": s.get("title", ""), "url": url, "http": got.get("http"), "error": got.get("error", ""),
                    "fetched_at": got.get("fetched_at"), "deadline": state})
    return out


def print_summary(rec):
    print(f"検証 {rec['date']}（{rec.get('run_at', '')}）")
    for e in rec["entries"]:
        print(f"{e['n']:>2}｜{e['kind']}｜{e['status']}｜{e['title'][:34]}")
        for h in e["holds"]:
            print(f"     × {h}")
        for w in e["warns"]:
            print(f"     ! {w}")
    for s in rec.get("seido", []):
        print(f"制度の候補｜{s['title'][:30]}｜{s['deadline']}｜リンク {s['http'] or s['error']}")
    counts = {}
    for e in rec["entries"]:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    print("状態：" + "・".join(f"{k} {v}" for k, v in counts.items()))


def cmd_show(day):
    rec = load_rec(day)
    for e in rec["entries"]:
        if e["location"] in ("dropped",):
            continue
        print(f"{e['n']:>2}｜{e['kind']}｜{e['status']}｜{e['title'][:40]}｜{e['url']}")
        it = e["item"]
        text = it.get("summary", "") + (" / " + it.get("impact", "") if it.get("impact") else "")
        if e["kind"] == "event":
            text = f"{it.get('when', '')}｜{it.get('place', '')}｜{it.get('summary', '')}"
        print(f"     要約：{text[:160]}")
        for c in e["claims"]:
            mark = "○" if c["ok"] else "×"
            print(f"     {mark} {c['label']}「{c['text']}」→ {c['evidence'] or '（根拠なし）'}"
                  + (f"　※{c['note']}" if c.get("note") else ""))
        for h in e["holds"]:
            print(f"     × {h}")
        for w in e["warns"]:
            print(f"     ! {w}")
    return 0


def pick(rec, ns):
    want = {int(x) for x in ns.split(",") if x.strip()}
    got = [e for e in rec["entries"] if e["n"] in want]
    missing = want - {e["n"] for e in got}
    if missing:
        raise SystemExit(f"番号 {sorted(missing)} はありません")
    return got


def check_current(day, entries):
    """公開データの内容が、検証したときから変わっていないか。"""
    brief, town = load_public(day)
    now_items = {i["url"]: i for i in (brief or {}).get("items", []) + town}
    for e in entries:
        it = now_items.get(e["url"])
        if e["location"] in ("news", "town") and (not it or gate.content_hash(it) != e["hash"]):
            raise SystemExit(f"{e['n']}「{e['title'][:30]}」は検証のあとで内容が変わっています。先に verify.py run")


def cmd_review(day, ns, fact, edit, note):
    rec = load_rec(day)
    entries = pick(rec, ns)
    check_current(day, entries)
    for e in entries:
        if e["location"] == "hold":
            raise SystemExit(f"{e['n']} は HOLD です。HOLD は Claude の確認だけでは戻せません（本人確認のうえ release）")
        if fact:
            if not e["stages"]["fact"].get("machine_ok"):
                raise SystemExit(f"{e['n']} は根拠が揃っていません")
            if fact == "ok":
                e["stages"]["fact"].update({"ok": True, "at": now(), "by": "Claude（根拠の箇所を照合）", "note": note})
            else:
                e["location"], e["holds"] = "hold", e["holds"] + [f"Claude の照合で不一致：{note}"]
        if edit and e["location"] != "hold":
            if not e["stages"]["fact"].get("ok"):
                raise SystemExit(f"{e['n']} は FACT_VERIFIED になっていません")
            if edit == "ok":
                if e["warns"] and not note:
                    raise SystemExit(f"{e['n']} には警告があります。確かめた内容を --note に書いてください")
                e["stages"]["editorial"] = {"ok": True, "at": now(), "by": "Claude（編集方針で確認）", "note": note}
            else:
                e["location"], e["holds"] = "hold", e["holds"] + [f"編集方針で見送り：{note}"]
        refresh_status(e)
        print(f"{e['n']}｜{e['status']}｜{e['title'][:40]}")
    save_rec(day, rec)
    sync_public(day, rec)
    return 0


def cmd_approve(day, ns, all_, note):
    if not note:
        raise SystemExit("本人の返事（例：「OK」）を --note に書いてください。本人がOKと言っていなければ実行しない")
    rec = load_rec(day)
    entries = [e for e in rec["entries"] if e["status"] == "EDITORIAL_APPROVED"] if all_ else pick(rec, ns)
    check_current(day, entries)
    for e in entries:
        if e["status"] != "EDITORIAL_APPROVED":
            raise SystemExit(f"{e['n']} は {e['status']} です（EDITORIAL_APPROVED のものだけ承認できます）")
        e["stages"]["publish"] = {"ok": True, "at": now(), "by": "本人", "note": note}
        refresh_status(e)
        print(f"{e['n']}｜{e['status']}｜{e['title'][:40]}")
    save_rec(day, rec)
    sync_public(day, rec)
    return 0


def cmd_hold(day):
    rec = load_rec(day)
    for e in rec["entries"]:
        if e["location"] == "hold":
            print(f"{e['n']:>2}｜{e['kind']}｜{e['title'][:40]}｜{e['url']}")
            for h in e["holds"]:
                print(f"     × {h}")
    return 0


def cmd_release(day, ns, note):
    if not note:
        raise SystemExit("本人が確かめた内容を --note に書いてください（Claude の判断だけでは戻さない）")
    rec = load_rec(day)
    for e in pick(rec, ns):
        if e["location"] != "hold":
            raise SystemExit(f"{e['n']} は HOLD ではありません")
        t = now()
        e["released_holds"] = e["holds"]
        e["holds"] = []
        for s in ("source", "fact", "editorial"):
            if not (e["stages"].get(s) or {}).get("ok"):
                e["stages"][s] = {"ok": True, "at": t, "by": "本人（Claude の本文照合を見て確認）", "note": note}
        e["location"] = "news" if e["kind"] == "news" else "town"
        refresh_status(e)
        print(f"{e['n']}｜{e['status']}｜{e['title'][:40]}（公開には approve が別に必要）")
    save_rec(day, rec)
    sync_public(day, rec)
    return 0


def cmd_drop(day, ns, reason, exclude):
    rec = load_rec(day)
    entries = pick(rec, ns)
    for e in entries:
        e["location"], e["dropped"] = "dropped", {"at": now(), "reason": reason}
        refresh_status(e)
        print(f"{e['n']}｜取りやめ｜{e['title'][:40]}")
    if exclude:
        ex = json.loads(editorial.EXCLUDED.read_text(encoding="utf-8")) if editorial.EXCLUDED.exists() else []
        have = {x["url"] for x in ex}
        ex += [{"url": e["url"], "title": e["title"], "reason": reason, "decided": day} for e in entries if e["url"] not in have]
        editorial.EXCLUDED.write_text(json.dumps(ex, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save_rec(day, rec)
    sync_public(day, rec)
    return 0


def main():
    ap = argparse.ArgumentParser(description="掲載候補の検証（tools/verify.py の先頭の説明を参照）")
    ap.add_argument("cmd", choices=["run", "show", "review", "approve", "hold", "release", "drop"])
    ap.add_argument("day", nargs="?", default=datetime.now(JST).date().isoformat())
    ap.add_argument("--n", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--fact", choices=["ok", "ng"])
    ap.add_argument("--editorial", choices=["ok", "ng"])
    ap.add_argument("--note", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--exclude", action="store_true")
    a = ap.parse_args()
    date.fromisoformat(a.day)
    if a.cmd == "run":
        return cmd_run(a.day)
    if a.cmd == "show":
        return cmd_show(a.day)
    if a.cmd == "hold":
        return cmd_hold(a.day)
    if a.cmd == "review":
        return cmd_review(a.day, a.n, a.fact, a.editorial, a.note)
    if a.cmd == "approve":
        return cmd_approve(a.day, a.n, a.all, a.note)
    if a.cmd == "release":
        return cmd_release(a.day, a.n, a.note)
    return cmd_drop(a.day, a.n, a.reason or "（理由なし）", a.exclude)


if __name__ == "__main__":
    sys.exit(main())
