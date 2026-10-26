"""ChatGPT の朝のブリーフの末尾にある「CLAUDE HANDOFF｜くらしノート」を取り込む。

使い方:
    python3 tools/import_handoff.py <貼り付けたテキストのファイル> [--no-fetch]

テキストの中の ```jsonl ... ``` の各行（1行1件のJSON）を読み、
- type "news"  → data/news/YYYY-MM-DD.json の items に足す（同じURLは上書き）
- type "event" / "food" → data/town.json に足す（同じURLがすでにあれば足さず、載っている文を残す）
- type "seido" → data/_candidates/YYYY-MM-DD.seido.jsonl に置くだけ（くらし制度ノートのDBには入れない。
  登録と3つの確認フラグは、タブ5で本人が確かめてから）
ChatGPT の書いたリンクが本当にあるか（存在しないURLを作っていないか）を、1件ずつ開いて確かめる。
開けない・見出しがページと合わないものは取り込まずに一覧で示す（--no-fetch で確認を省く）。
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import AREAS, TOPICS  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editorial  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (kurashi-note handoff check)"
NEWS_KEYS = ("title", "summary", "impact", "area", "topic", "source_name", "url")


def fetch_title(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as res:
        text = res.read(400000).decode(res.headers.get_content_charset() or "utf-8", errors="replace")
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S)
    og = re.search(r'<meta property="og:title" content="([^"]*)"', text)
    return " ".join(x for x in ((m.group(1) if m else ""), (og.group(1) if og else "")))


def norm(s):
    return re.sub(r"[\s　「」『』【】（）()・、。,.!！?？|｜:：\-ー〜~]", "", s)


def looks_same(title, page_title):
    """見出しのうち連続8文字以上（短ければ半分以上）がページのタイトルに含まれるか。"""
    a, b = norm(title), norm(page_title)
    n = min(8, max(4, len(a) // 2))
    return any(a[i:i + n] in b for i in range(0, max(1, len(a) - n + 1)))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    fetch = "--no-fetch" not in sys.argv
    block = re.search(r"```(?:jsonl|json)?\s*\n(.*?)```", text, re.S)
    lines = (block.group(1) if block else text).splitlines()

    day = datetime.now(JST).date().isoformat()
    excluded = editorial.excluded_urls()
    news, town, seido, rejected = [], [], [], []
    for n, line in enumerate(lines, 1):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            it = json.loads(line)
        except json.JSONDecodeError:
            rejected.append(f"{n}行目：JSONとして読めない")
            continue
        title, url, kind = it.get("title", ""), it.get("url", ""), it.get("type")
        why = []
        if not url.startswith("https://"):
            why.append("リンクが https:// で始まらない")
        if "茅ヶ崎" in title + it.get("summary", "") or "茅ケ崎" in title + it.get("summary", ""):
            why.append("茅ヶ崎市の話題")
        if editorial.is_excluded(url, excluded):
            why.append("掲載しないと決めた記事（data/excluded.json）")
        # 事件・事故・政治などの言葉は、ここでは一律に捨てない（2026-10-26）。
        # tools/verify.py が文脈（住民に必要な行動があるか）を見て HOLD か警告にする
        if kind == "news":
            why += [f"{k} が空" for k in NEWS_KEYS if not str(it.get(k, "")).strip()]
            if it.get("area") and it["area"] not in AREAS:
                why.append(f"area「{it['area']}」は使えない")
            if it.get("topic") and it["topic"] not in TOPICS:
                why.append(f"topic「{it['topic']}」は使えない")
        elif kind == "event" and not re.match(r"\d{4}-\d{2}-\d{2}$", it.get("date_start", "")):
            why.append("イベントの date_start がない")
        elif kind not in ("news", "event", "food", "seido"):
            why.append(f"type「{kind}」は使えない")
        if not why and fetch:
            try:
                if not looks_same(title, fetch_title(url)):
                    why.append("見出しがリンク先のページと合わない")
            except Exception as e:
                why.append(f"リンクが開けない（{e.__class__.__name__}）")
        if why:
            rejected.append(f"{title[:40]}：{'・'.join(why)}")
            continue
        if kind == "news":
            news.append({k: it.get(k, "") for k in NEWS_KEYS + ("published",)})
        elif kind in ("event", "food"):
            town.append({"kind": kind, "title": title, "when": it.get("when", ""),
                         "date_start": it.get("date_start", ""), "date_end": it.get("date_end", ""),
                         "place": it.get("place", ""), "area": it.get("area", ""),
                         "summary": it.get("summary", ""), "source_name": it.get("source_name", ""),
                         "url": url, "added": day})
        else:
            seido.append(it)

    if news:
        path = ROOT / "data" / "news" / f"{day}.json"
        brief = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"date": day, "keywords": [], "items": []}
        by_url = {i["url"]: i for i in brief["items"]}
        for i in news:
            by_url[i["url"]] = i
        brief["items"] = list(by_url.values())
        path.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    town_kept = []
    if town:
        path = ROOT / "data" / "town.json"
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        by_url = {t["url"]: t for t in old}
        town_kept = [t for t in town if t["url"] in by_url]
        town = [t for t in town if t["url"] not in by_url]
        for t in town:
            by_url[t["url"]] = t
        path.write_text(json.dumps(list(by_url.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if seido:
        path = ROOT / "data" / "_candidates" / f"{day}.seido.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in seido), encoding="utf-8")

    print(f"取り込み：ニュース{len(news)}件・イベント/グルメ{len(town)}件・制度の候補{len(seido)}件（制度はDBに入れず保留）")
    if town_kept:
        print(f"イベント/グルメ{len(town_kept)}件はすでに載っているので、前の文のままにしました：")
        for t in town_kept:
            print(f"  ・{t['title']}")
    if rejected:
        print("取り込まなかったもの：")
        for r in rejected:
            print("  -", r)
        # 取り込まなかった理由は公開しない記録に残す（data/_verify/ は .gitignore）
        log = ROOT / "data" / "_verify" / f"{day}.import.txt"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(f"# {datetime.now(JST).isoformat(timespec='seconds')} {sys.argv[1]}\n")
            f.write("".join(f"- {r}\n" for r in rejected))
    print("次は python3 tools/verify.py run（検証）→ python3 tools/verify.py show")
    return 0


if __name__ == "__main__":
    sys.exit(main())
