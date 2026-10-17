"""藤沢くらし制度ノートのDBの写しから、サイトに載せてよい案件だけを data/kurashi.json に書き出す。

使い方:
    python3 tools/export_kurashi.py <casesフォルダ>

<casesフォルダ> は、くらし制度ノートの Artifact DB（cases）を ArtifactData の list で
ファイルに保存したもの（1案件1ファイルのJSON）。DB本体には読み書きしない。

載せる条件（どれか1つでも欠けたら載せない）:
- 3つの確認フラグ（still_valid_confirmed・duplicate_checked・recent_change_checked）が
  すべて true。フラグを true にするのは本人だけ（くらし制度ノートの決まり）
- status が POST か PUBLISHED（HOLD・EXPIRED などは載せない）
- lifecycle_status が ARCHIVED でない
- 期限が日付で書かれていれば、今日（日本時間）以降。過ぎたものは build.py も表示しない
- 期限が日付で書かれていない案件は、最終確認から STALE_DAYS 日以内のものだけ
  （日程の変わる相談会などが、古いまま残らないようにするため）

書き出すのは市民向けの項目だけ。内部の採点・メモ・変更履歴などは出さない。
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "kurashi.json"
JST = timezone(timedelta(hours=9))

STALE_DAYS = 30
FLAGS = ("still_valid_confirmed", "duplicate_checked", "recent_change_checked")
PUBLIC_STATUSES = ("POST", "PUBLISHED")
FIELDS = (
    "title", "summary", "benefit", "amount", "target_user", "how_to_apply",
    "deadline", "department", "contact", "primary_source", "category", "area",
)


def deadline_date(text):
    """期限の先頭が YYYY-MM-DD なら その日付、そうでなければ None。"""
    m = re.match(r"\s*(\d{4}-\d{2}-\d{2})", str(text or ""))
    return m.group(1) if m else None


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    src = Path(sys.argv[1])
    today = datetime.now(JST).date().isoformat()

    cases, skipped = [], []
    for path in sorted(src.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        case = doc.get("data", doc)
        title = case.get("title") or path.stem
        if not all(case.get(f) is True for f in FLAGS):
            continue
        if case.get("status") not in PUBLIC_STATUSES:
            skipped.append(f"{title}（status {case.get('status')}）")
            continue
        if case.get("lifecycle_status") == "ARCHIVED":
            skipped.append(f"{title}（アーカイブ済み）")
            continue
        until = deadline_date(case.get("deadline"))
        if until and until < today:
            skipped.append(f"{title}（期限 {until} を過ぎた）")
            continue
        checked = str(case.get("last_verified") or "")[:10]
        if not until:
            limit = (datetime.now(JST).date() - timedelta(days=STALE_DAYS)).isoformat()
            if not checked or checked < limit:
                skipped.append(f"{title}（期限の日付がなく、最終確認 {checked or 'なし'} から{STALE_DAYS}日を過ぎた）")
                continue
        if not str(case.get("primary_source", "")).strip().startswith("https://"):
            skipped.append(f"{title}（一次情報のリンクがない）")
            continue

        item = {k: str(case.get(k) or "").strip() for k in FIELDS}
        item["id"] = path.stem
        item["deadline_date"] = until or ""
        item["last_verified"] = checked
        cases.append(item)

    # 期限が近いものを先に、期限のないものは後ろに
    cases.sort(key=lambda c: (c["deadline_date"] or "9999-99-99", c["title"]))
    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"書き出し：{len(cases)}件 → data/kurashi.json")
    for c in cases:
        print(f"  - {c['title']}（期限 {c['deadline'] or 'なし'}／最終確認 {c['last_verified']}）")
    if skipped:
        print("確認済みだが載せなかったもの：")
        for s in skipped:
            print("  -", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
