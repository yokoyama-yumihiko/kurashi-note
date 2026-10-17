"""AI が選んだ候補の番号と短い文から、data/news/YYYY-MM-DD.json を組み立てる。

使い方:
    python3 tools/make_brief.py            # 今日の data/_candidates/YYYY-MM-DD.picks.json を読む
    python3 tools/make_brief.py 2026-10-17 # 日付を指定

AI は見出し・URL・出典を書き写さず、候補の番号（collect_news.py の .txt の左端）だけを書く。
見出しは元のまま・リンクの写し間違いなし、になり、AI が書く文字数（利用枠）も減る。

picks.json の形:
{
  "keywords": ["...", "...", "..."],
  "picks": [{"n": 1, "topic": "防災・安全", "summary": "...", "impact": "..."}],
  "extra": [ data/news の items と同じ形（全国ニュースなど、候補にないもの） ],
  "today_in_history": { ... }   # なければ書かない
}
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "data" / "_candidates"
OUT = ROOT / "data" / "news"
JST = timezone(timedelta(hours=9))


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else datetime.now(JST).date().isoformat()
    candidates = json.loads((CAND / f"{day}.json").read_text(encoding="utf-8"))["candidates"]
    picks = json.loads((CAND / f"{day}.picks.json").read_text(encoding="utf-8"))

    items = []
    for p in picks["picks"]:
        n = int(p["n"])
        if not 1 <= n <= len(candidates):
            print(f"番号 {n} の候補はありません（1〜{len(candidates)}）")
            return 1
        c = candidates[n - 1]
        published = ""
        if c.get("date"):
            d = date.fromisoformat(c["date"])
            published = f"{d.month}月{d.day}日"
        items.append({
            "title": c["title"], "summary": p["summary"], "impact": p["impact"],
            "area": p.get("area", c["area"]), "topic": p["topic"],
            "source_name": c["source_name"], "url": c["url"], "published": published,
        })
    items += picks.get("extra", [])

    brief = {"date": day, "keywords": picks.get("keywords", []), "items": items}
    if picks.get("today_in_history"):
        brief["today_in_history"] = picks["today_in_history"]

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{day}.json"
    out.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(items)}本 → {out.relative_to(ROOT)}（次は python3 tools/build.py --check）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
