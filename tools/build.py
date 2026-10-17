"""data/news/*.json から「今朝のニュース」のページを作る。

使い方（リポジトリの一番上で）:
    python3 tools/build.py          # ページを作る
    python3 tools/build.py --check  # データの確認だけ（ファイルは書かない）

外部ライブラリは使わない（Python 3.9 標準のみ）。
データの形は docs/news-data.md を参照。
"""

import html
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEWS_DATA = ROOT / "data" / "news"
NEWS_OUT = ROOT / "news"
INDEX = ROOT / "index.html"

SITE_NAME = "Yokoyama Policy Lab"

# 表示順もこの順。茅ヶ崎市は載せない（2026-10-17 本人決定）
AREAS = ["藤沢市", "寒川町", "神奈川県", "全国", "海外"]
TOPICS = [
    "子育て・教育", "福祉・医療・介護", "防災・安全", "交通・まちづくり",
    "環境・エネルギー", "くらし・お金", "仕事・経済", "平和・人権", "その他",
]
WEEKDAYS = "月火水木金土日"

INDEX_START = "<!-- NEWS:START -->"
INDEX_END = "<!-- NEWS:END -->"
TOP_HEADLINES = 3


def esc(text):
    return html.escape(str(text), quote=True)


def jp_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.year}年{d.month}月{d.day}日（{WEEKDAYS[d.weekday()]}）"


# ---------- データの確認 ----------

def check_brief(path, brief):
    """問題を文字列のリストで返す。空なら OK。"""
    errors = []
    where = path.name

    if brief.get("date") != path.stem:
        errors.append(f"{where}: date がファイル名と違う（{brief.get('date')}）")
    try:
        date.fromisoformat(path.stem)
    except ValueError:
        errors.append(f"{where}: ファイル名が YYYY-MM-DD.json になっていない")

    items = brief.get("items")
    if not isinstance(items, list) or not items:
        errors.append(f"{where}: items が空")
        items = []

    for i, item in enumerate(items, 1):
        label = f"{where} items[{i}]"
        for key in ("title", "summary", "impact", "area", "topic", "source_name", "url"):
            if not str(item.get(key, "")).strip():
                errors.append(f"{label}: {key} が空")
        if item.get("area") and item["area"] not in AREAS:
            errors.append(f"{label}: area「{item['area']}」は使えない（{'／'.join(AREAS)}）")
        if item.get("topic") and item["topic"] not in TOPICS:
            errors.append(f"{label}: topic「{item['topic']}」は使えない")
        if item.get("url") and not str(item["url"]).startswith("https://"):
            errors.append(f"{label}: url が https:// で始まっていない")
        text = " ".join(str(item.get(k, "")) for k in ("title", "summary", "impact"))
        if "茅ヶ崎" in text or "茅ケ崎" in text:
            errors.append(f"{label}: 茅ヶ崎市の話題は載せない")

    day = brief.get("today_in_history")
    if day:
        for key in ("title", "note"):
            if not str(day.get(key, "")).strip():
                errors.append(f"{where} today_in_history: {key} が空")
        if day.get("url") and not str(day["url"]).startswith("https://"):
            errors.append(f"{where} today_in_history: url が https:// で始まっていない")

    return errors


def load_briefs():
    briefs, errors = [], []
    for path in sorted(NEWS_DATA.glob("*.json")):
        try:
            brief = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{path.name}: JSON の書き方が正しくない（{e}）")
            continue
        errors.extend(check_brief(path, brief))
        briefs.append(brief)
    briefs.sort(key=lambda b: b["date"], reverse=True)
    return briefs, errors


# ---------- ページの部品 ----------

def page(title, body, css="../css/style.css", description=""):
    meta = f'\n  <meta name="description" content="{esc(description)}">' if description else ""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}｜{SITE_NAME}</title>{meta}
  <link rel="stylesheet" href="{css}">
</head>

<body>
  <main>
{body}
  </main>
</body>
</html>
"""


NOTICE = """    <p class="news-notice">
      要約はAIを使って作り、運営者が確認してから載せています。
      正確な内容は、必ずリンク先の記事や公式の発表で確かめてください。
      <a href="../pages/about.html">このサイトについて</a>
    </p>"""


def render_item(item):
    published = f"・{esc(item['published'])}" if item.get("published") else ""
    return f"""        <article class="news-item">
          <p class="news-tag">{esc(item['topic'])}</p>
          <h3><a href="{esc(item['url'])}" target="_blank" rel="noopener">{esc(item['title'])}</a></h3>
          <p>{esc(item['summary'])}</p>
          <p class="news-impact"><span>暮らしへの影響</span>{esc(item['impact'])}</p>
          <p class="news-source">出典：{esc(item['source_name'])}{published}</p>
        </article>"""


def render_brief_body(brief, newer=None, older=None):
    parts = [
        '    <a class="back-link" href="../index.html">← トップページに戻る</a>',
        "",
        "    <section>",
        "      <p>今朝のニュース</p>",
        f"      <h1>{jp_date(brief['date'])}</h1>",
    ]
    if brief.get("keywords"):
        chips = "".join(f'<li>{esc(k)}</li>' for k in brief["keywords"])
        parts.append(f'      <ul class="news-keywords" aria-label="今日のキーワード">{chips}</ul>')
    parts.append("    </section>")

    for area in AREAS:
        items = [it for it in brief["items"] if it["area"] == area]
        if not items:
            continue
        parts += [
            "",
            '    <section class="news-section">',
            f"      <h2>{esc(area)}</h2>",
            '      <div class="news-list">',
            "\n".join(render_item(it) for it in items),
            "      </div>",
            "    </section>",
        ]

    day = brief.get("today_in_history")
    if day:
        link = ""
        if day.get("url"):
            name = esc(day.get("source_name") or "出典")
            link = f'\n        <p class="news-source">出典：<a href="{esc(day["url"])}" target="_blank" rel="noopener">{name}</a></p>'
        parts += [
            "",
            '    <section class="news-section">',
            "      <h2>今日は何の日</h2>",
            '      <div class="news-day">',
            f"        <h3>{esc(day['title'])}</h3>",
            f"        <p>{esc(day['note'])}</p>{link}",
            "      </div>",
            "    </section>",
        ]

    nav = []
    if older:
        nav.append(f'<a href="{older["date"]}.html">← {jp_date(older["date"])}</a>')
    nav.append('<a href="archive.html">過去のニュース一覧</a>')
    if newer:
        nav.append(f'<a href="{newer["date"]}.html">{jp_date(newer["date"])} →</a>')
    parts += ["", f'    <nav class="news-nav">{" ".join(nav)}</nav>', "", NOTICE]
    return "\n".join(parts)


def render_archive_body(briefs):
    rows = "\n".join(
        f'        <li><a href="{b["date"]}.html">{jp_date(b["date"])}</a>'
        f'<span>{len(b["items"])}本</span></li>'
        for b in briefs
    )
    return f"""    <a class="back-link" href="../index.html">← トップページに戻る</a>

    <section>
      <p>今朝のニュース</p>
      <h1>過去のニュース一覧</h1>
    </section>

    <section class="news-section">
      <ul class="news-archive">
{rows}
      </ul>
    </section>
"""


def render_empty_body():
    return """    <a class="back-link" href="../index.html">← トップページに戻る</a>

    <section>
      <p>今朝のニュース</p>
      <h1>準備中です</h1>
      <p>毎朝、藤沢・寒川・神奈川の暮らしに関わるニュースをまとめてお届けする予定です。</p>
    </section>
"""


def render_index_block(latest):
    if not latest:
        return f"""{INDEX_START}
    <section class="news-home">
      <h2>今朝のニュース</h2>
      <p>準備中です。毎朝、暮らしに関わるニュースをまとめてお届けする予定です。</p>
    </section>
    {INDEX_END}"""
    heads = "\n".join(
        f'        <li><span>{esc(it["area"])}</span>{esc(it["title"])}</li>'
        for it in latest["items"][:TOP_HEADLINES]
    )
    return f"""{INDEX_START}
    <section class="news-home">
      <h2>今朝のニュース</h2>
      <p class="news-home-date">{jp_date(latest['date'])}</p>
      <ul class="news-home-list">
{heads}
      </ul>
      <a class="news-home-more" href="news/index.html">今朝のニュースを読む（{len(latest['items'])}本）→</a>
    </section>
    {INDEX_END}"""


# ---------- 書き出し ----------

def build():
    briefs, errors = load_briefs()
    if errors:
        print("データに問題があります。ページは作りませんでした。")
        for e in errors:
            print("  -", e)
        return 1
    if "--check" in sys.argv:
        print(f"OK：{len(briefs)}日分のデータに問題はありません。")
        return 0

    NEWS_OUT.mkdir(exist_ok=True)
    outputs = {}
    for i, brief in enumerate(briefs):
        newer = briefs[i - 1] if i > 0 else None
        older = briefs[i + 1] if i + 1 < len(briefs) else None
        title = f"今朝のニュース {jp_date(brief['date'])}"
        outputs[f"{brief['date']}.html"] = page(title, render_brief_body(brief, newer, older))

    if briefs:
        latest = briefs[0]
        outputs["index.html"] = page(
            "今朝のニュース",
            render_brief_body(latest, older=briefs[1] if len(briefs) > 1 else None),
            description="藤沢・寒川・神奈川の暮らしに関わる今朝のニュースのまとめ",
        )
        outputs["archive.html"] = page("過去のニュース一覧", render_archive_body(briefs))
    else:
        outputs["index.html"] = page("今朝のニュース", render_empty_body())

    # 消えたデータのページを残さない
    for old in NEWS_OUT.glob("*.html"):
        if old.name not in outputs:
            old.unlink()
    for name, text in outputs.items():
        (NEWS_OUT / name).write_text(text, encoding="utf-8")

    index_html = INDEX.read_text(encoding="utf-8")
    start, end = index_html.find(INDEX_START), index_html.find(INDEX_END)
    if start == -1 or end == -1:
        print("index.html に NEWS:START / NEWS:END の目印がありません。")
        return 1
    block = render_index_block(briefs[0] if briefs else None)
    index_html = index_html[:start] + block + index_html[end + len(INDEX_END):]
    INDEX.write_text(index_html, encoding="utf-8")

    print(f"作成：news/ に {len(outputs)} ページ、トップページの「今朝のニュース」を更新")
    return 0


if __name__ == "__main__":
    sys.exit(build())
