"""編集方針（2026-10-18 本人決定）を各ツールで共通に使う。

- 市民の不安を不必要にあおらない・風評被害を防ぐ
- 藤沢市・寒川町に直接関係しない局地的な事件・事故・食中毒などは、原則として載せない
  （市民に具体的な危険が及ぶ情報や、行政が対応を求める情報は載せてよい → 本人が確かめて手で入れる）
- 掲載しないと決めた記事は data/excluded.json に入れ、翌日以降も再び載らないようにする
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = ROOT / "data" / "excluded.json"

ALARM = re.compile(r"(食中毒|ノロウイルス|事件|事故|逮捕|容疑|殺人|殺害|強盗|窃盗|放火|火災|火事|死亡|遺体|不審者|わいせつ|暴行|傷害)")
LOCAL = re.compile(r"(藤沢|寒川|湘南台|辻堂|江の島|江ノ島|鵠沼|片瀬|善行|長後|六会|御所見|遠藤|村岡|明治|大庭|一色)")


def excluded_urls():
    if not EXCLUDED.exists():
        return set()
    return {e["url"] for e in json.loads(EXCLUDED.read_text(encoding="utf-8"))}


def is_excluded(url, urls=None):
    return url in (excluded_urls() if urls is None else urls)


def alarm_reason(*texts):
    """藤沢・寒川に関係しない事件・事故・食中毒などなら理由を返す（なければ空文字）。"""
    text = " ".join(t for t in texts if t)
    m = ALARM.search(text)
    if m and not LOCAL.search(text):
        return f"編集方針：藤沢・寒川に直接関係しない「{m.group(1)}」の話題"
    return ""
