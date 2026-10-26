"""編集方針（2026-10-18 本人決定、2026-10-26 見直し）を各ツールで共通に使う。

- 市民の不安を不必要にあおらない・風評被害を防ぐ
- 藤沢市・寒川町に直接関係しない局地的な事件・事故・食中毒などは、原則として載せない
  （市民に具体的な危険が及ぶ情報や、行政が対応を求める情報は載せてよい）
- 政治家・政党・選挙活動・政治的な評価は扱わない
- 掲載しないと決めた記事は data/excluded.json に入れ、翌日以降も再び載らないようにする

2026-10-26 から、言葉が当たっただけで一律に消さない。assess() が
  HOLD（そのままでは載せない。本人の判断に回す）／WARN（載せる前に確かめる）
を返し、最終的な掲載判断は編集方針に沿って Claude と本人が行う（tools/verify.py）。
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = ROOT / "data" / "excluded.json"

ALARM = re.compile(r"(食中毒|ノロウイルス|事件|事故|逮捕|容疑|殺人|殺害|強盗|窃盗|放火|火災|火事|死亡|遺体|不審者|わいせつ|暴行|傷害|"
                   r"感染症|集団感染|クラスター)")
# 地名。「明治」「遠藤」「一色」など、ほかの意味でも使う言葉は地区名の形のときだけ数える
LOCAL = re.compile(r"(藤沢|寒川|湘南台|辻堂|江の島|江ノ島|鵠沼|片瀬|善行|長後|六会|御所見|湘南大庭|村岡|"
                   r"(?:明治|遠藤|大庭|一色)(?:地区|市民センター|公民館))")
# 政治家・政党・選挙活動（2026-10-17 本人決定「選挙・政治の発信はしない」）
POLITICS = re.compile(r"(議員|政党|自民党|立憲|公明党|維新|国民民主|共産党|れいわ|参政党|社民党|選挙|立候補|公認候補|候補予定者|後援会|"
                      r"街頭演説|市政報告|県政報告|国政報告|総理|首相|大臣|首脳会談|内閣支持)")
# 住民に必要な行動・具体的な影響（事件・事故などの話題でも、これがあれば載せる候補になる）
ACTION = re.compile(r"(回収|リコール|返金|交換|使用を中止|使用中止|運休|運転見合わせ|通行止め|交通規制|規制|迂回|避難|"
                    r"注意報|警報|注意喚起|呼びかけ|相談窓口|問い合わせ|連絡してください|確認してください|"
                    r"接種|検査|受診|休校|休園|断水|停電|給水|閉鎖|中止|延期|対象の方|登録者|パスワード)")


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


def politics_reason(*texts):
    m = POLITICS.search(" ".join(t for t in texts if t))
    return f"政治（扱わない）：「{m.group(1)}」" if m else ""


def assess(texts, body=""):
    """記事の文（見出し・要約など）と元ページの本文から、(holds, warns) を返す。

    - 政治家・政党・選挙活動 → HOLD（除外基準は維持。行政の手続きの話もあり得るので最後は本人が決める）
    - 事件・事故・感染症など：住民に必要な行動・具体的な影響が見当たらない → HOLD
                             見当たる → WARN（あおる言葉・不要な施設名や企業名がないか確かめる）
    """
    text = " ".join(t for t in texts if t)
    holds, warns = [], []
    why = politics_reason(text)
    if why:
        holds.append(why)
    m = ALARM.search(text)
    if m:
        action = ACTION.search(text)  # 必要な行動は、載せる文（見出し・要約・影響）に書いてあるかで見る
        if not action:
            holds.append(f"事件・事故など（{m.group(1)}）：住民への具体的な影響・必要な行動が見当たらない")
        else:
            local = "藤沢・寒川に関係" if LOCAL.search(text + body[:3000]) else "藤沢・寒川の記載なし"
            warns.append(f"事件・事故など（{m.group(1)}、行動「{action.group(1)}」あり、{local}）："
                         "あおる言葉・不要な施設名や企業名がないか確かめる")
    return holds, warns
