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
  "today_in_history": { ... },  # なければ書かない
  "town": [                       # まちのイベント・グルメ（なければ書かない）
    {"n": 48, "kind": "event", "date_start": "2026-10-18", "date_end": "", "when": "10月18日（日）",
     "place": "秋葉台公園", "summary": "..."},
    {"n": 12, "kind": "food", "place": "辻堂", "summary": "..."}
  ]
}
town は data/town.json に足す（同じリンクは上書き）。終わって7日たったイベントと、
載せて90日たったグルメはここで消す（表示は build.py が日付で絞る）。
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOWN = ROOT / "data" / "town.json"
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

    if picks.get("town"):
        town = json.loads(TOWN.read_text(encoding="utf-8")) if TOWN.exists() else []
        by_url = {t["url"]: t for t in town}
        for p in picks["town"]:
            c = candidates[int(p["n"]) - 1]
            entry = {"kind": p["kind"], "title": c["title"], "when": p.get("when", ""),
                     "date_start": p.get("date_start", ""), "date_end": p.get("date_end", ""),
                     "place": p.get("place", ""), "area": p.get("area", c["area"]),
                     "summary": p["summary"], "source_name": c["source_name"], "url": c["url"],
                     "added": day}
            by_url[c["url"]] = entry
        today = date.fromisoformat(day)
        keep = []
        for t in by_url.values():
            if t["kind"] == "event":
                last = t.get("date_end") or t.get("date_start")
                if last and (today - date.fromisoformat(last)).days > 7:
                    continue
            elif (today - date.fromisoformat(t["added"])).days > 90:
                continue
            keep.append(t)
        TOWN.write_text(json.dumps(keep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"まちのイベント・グルメ：{len(picks['town'])}件を追加・更新（全部で{len(keep)}件）")

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{day}.json"
    out.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(items)}本 → {out.relative_to(ROOT)}（次は python3 tools/build.py --check）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
