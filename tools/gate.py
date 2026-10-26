"""公開前の検証関門（2026-10-26 本人決定）。build.py と verify.py が共通で使う。

検証は4段階。上の段階に進むには、下の段階がすべて済んでいる必要がある。
  SOURCE_VERIFIED     個別ページを開けた・本文を取れた・見出しが合った（verify.py が機械で確認）
  FACT_VERIFIED       要約の金額・人数・日付・期限・対象条件の根拠が本文にあり（機械）、
                      Claude がその根拠の箇所を読んで意味が合うと確かめた（verify.py review）
  EDITORIAL_APPROVED  地域性・実用性・政治的中立・風評被害のおそれを確かめた（機械の警告を見たうえで review）
  PUBLISH_APPROVED    本人が最終OKを出した（verify.py approve。本人がOKと言ったときだけ実行する）
確かめられないものは HOLD として data/_verify/（公開しない）に移し、本人の確認に回す。

公開データ（data/news・data/town.json）の各記事には、状態と日時と内容のハッシュだけを
"check" として書く（根拠の文・HOLDの理由・メモは公開リポジトリに入れない）。
ハッシュが合わない＝承認のあとで内容が変わった、なので承認は無効になる。

関門をかけるのは GATE_START 以降のデータだけ。それより前のニュース・イベントは
これまでどおり表示する（過去データを一律エラーにしてサイトを止めないため）。
"""

import hashlib
import json

GATE_START = "2026-10-27"

STAGES = ("source", "fact", "editorial", "publish")
STATUSES = ("HOLD", "UNVERIFIED", "SOURCE_VERIFIED", "FACT_VERIFIED", "EDITORIAL_APPROVED", "PUBLISH_APPROVED")
STAGE_STATUS = dict(zip(STAGES, STATUSES[2:]))

NEWS_FIELDS = ("title", "summary", "impact", "area", "topic", "source_name", "url", "published")
TOWN_FIELDS = ("kind", "title", "when", "date_start", "date_end", "place", "area", "summary", "source_name", "url")


def content_hash(item):
    fields = TOWN_FIELDS if item.get("kind") in ("event", "food") else NEWS_FIELDS
    text = json.dumps([str(item.get(k, "")) for k in fields], ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def status_of(stages):
    """各段階の記録 {stage: {"ok": bool, ...}} から、いまの状態を返す。"""
    status = "UNVERIFIED"
    for s in STAGES:
        if not (stages.get(s) or {}).get("ok"):
            break
        status = STAGE_STATUS[s]
    return status


def rank(status):
    return STATUSES.index(status) if status in STATUSES else 0


def gated(day):
    return bool(day) and day >= GATE_START


def stamp_status(item):
    """公開データの記事についた "check" から状態を返す。(状態, 問題の説明 or "")"""
    check = item.get("check")
    if not isinstance(check, dict):
        return "UNVERIFIED", "検証記録がない（python3 tools/verify.py run）"
    if check.get("hash") != content_hash(item):
        return "UNVERIFIED", "検証のあとで内容が変わった（もう一度 verify.py run）"
    status = check.get("status", "UNVERIFIED")
    return (status if status in STATUSES else "UNVERIFIED"), ""
