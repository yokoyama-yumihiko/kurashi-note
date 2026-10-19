"""data/ から「今朝のニュース」と「くらしの制度」のページを作る。

使い方（リポジトリの一番上で）:
    python3 tools/build.py          # ページを作る
    python3 tools/build.py --check  # データの確認だけ（ファイルは書かない）

外部ライブラリは使わない（Python 3.9 標準のみ）。
データの形は docs/news-data.md を参照。data/kurashi.json は tools/export_kurashi.py が作る。
"""

import html
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editorial  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NEWS_DATA = ROOT / "data" / "news"
NEWS_OUT = ROOT / "news"
KURASHI_DATA = ROOT / "data" / "kurashi.json"
KURASHI_OUT = ROOT / "pages" / "kurashi.html"
TOWN_DATA = ROOT / "data" / "town.json"
TOWN_OUT = ROOT / "pages" / "town.html"
FOOD_DAYS = 60  # グルメを表示しておく日数
INDEX = ROOT / "index.html"
JST = timezone(timedelta(hours=9))

SITE_NAME = "くらしノート｜藤沢・寒川"  # 2026-10-17 本人決定
TITLE_SUFFIX = "くらしノート 藤沢・寒川"  # <title> では「｜」が重ならないように

# 表示順もこの順。茅ヶ崎市は載せない（2026-10-17 本人決定）
AREAS = ["藤沢市", "寒川町", "神奈川県", "全国", "海外"]
TOPICS = [
    "子育て・教育", "福祉・医療・介護", "防災・安全", "交通・まちづくり",
    "環境・エネルギー", "くらし・お金", "仕事・経済", "平和・人権", "その他",
]
WEEKDAYS = "月火水木金土日"

# 分野ごとのアイコン（assets/icons/。デジタル庁のアイコン素材を緑に色変更。leaf・bus は自作）
TOPIC_ICONS = {
    "子育て・教育": "child", "福祉・医療・介護": "health", "防災・安全": "attention",
    "交通・まちづくり": "bus", "環境・エネルギー": "leaf", "くらし・お金": "money",
    "仕事・経済": "work", "平和・人権": "family", "その他": "information",
}
# くらしの制度の分類（自由な文字）は、含まれる言葉で選ぶ
CASE_ICONS = [
    (("子育て", "保育", "教育", "学校", "不登校", "児童"), "child"),
    (("医療", "福祉", "介護", "健康", "障がい"), "health"),
    (("防災", "災害"), "attention"),
    (("物価", "生活", "給付", "お金", "税", "手当"), "money"),
    (("仕事", "就労", "雇用"), "work"),
]

INDEX_START = "<!-- NEWS:START -->"
INDEX_END = "<!-- NEWS:END -->"
KURASHI_START = "<!-- KURASHI:START -->"
KURASHI_END = "<!-- KURASHI:END -->"
TOWN_START = "<!-- TOWN:START -->"
TOWN_END = "<!-- TOWN:END -->"
TOP_HEADLINES = 3
# スマホが古い CSS を使い続けないよう、ページを作るたびに付ける目印
ASSET_VER = datetime.now(JST).strftime("%Y%m%d%H%M")
SITE_URL = "https://yokoyama-yumihiko.github.io/kurashi-note/"
FEED_DAYS = 14  # RSS に載せる日数


def esc(text):
    return html.escape(str(text), quote=True)


def icon(name, prefix="../"):
    """色はCSS（mask）で付ける。読み上げでは飛ばす。
    url はページからの相対パスにしたいので、CSS変数ではなく style に直接書く。"""
    url = f"url({prefix}assets/icons/{name}_line.svg)"
    return (f'<span class="topic-icon" style="-webkit-mask-image:{url};mask-image:{url}"'
            ' aria-hidden="true"></span>')


def case_icon(text):
    for words, name in CASE_ICONS:
        if any(w in text for w in words):
            return name
    return "information"


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
        if editorial.is_excluded(item.get("url", "")):
            errors.append(f"{label}: 掲載しないと決めた記事（data/excluded.json）")

    day = brief.get("today_in_history")
    if day:
        for key in ("title", "note"):
            if not str(day.get(key, "")).strip():
                errors.append(f"{where} today_in_history: {key} が空")
        if day.get("url") and not str(day["url"]).startswith("https://"):
            errors.append(f"{where} today_in_history: url が https:// で始まっていない")

    return errors


def alarm_notes(briefs):
    """編集方針（tools/editorial.py）に当たりそうな記事を「注意」として返す。
    具体的な危険や行政が対応を求める情報なら載せてよいので、エラーにはしない（公開前に本人が確かめる）。"""
    notes = []
    for brief in briefs:
        for item in brief.get("items", []):
            why = editorial.alarm_reason(item.get("title", ""), item.get("summary", ""), item.get("impact", ""))
            if why:
                notes.append(f"{brief['date']}: 「{item.get('title', '')}」は{why}です。不安をあおらないか確かめてください")
    return notes


def repeated_urls(briefs):
    """前の日にも載せたリンクを「注意」として返す（エラーにはしない）。"""
    seen, notes = {}, []
    for brief in sorted(briefs, key=lambda b: b["date"]):
        for item in brief.get("items", []):
            url = item.get("url")
            if url in seen:
                notes.append(f"{brief['date']}: 「{item.get('title')}」は {seen[url]} にも載せています")
            else:
                seen[url] = brief["date"]
    return notes


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

# 全ページ共通のメニュー（上に固定。スマホは横にスライドできるタブ）
NAV_START = "<!-- NAV:START -->"
NAV_END = "<!-- NAV:END -->"
FOOTER_START = "<!-- FOOTER:START -->"
FOOTER_END = "<!-- FOOTER:END -->"
# お問い合わせ（Googleフォーム、2026-10-18 本人決定）。空のあいだはフッターに出さない
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSfKwRwbf1iX7zSeb_OOZTekVoDZOfABKhSrxkV2KA-8U_Gp6Q/viewform"
# 書体（Noto Sans JP）。どの端末でも同じ字形で見えるように Google Fonts から読む
FONT_LINKS = """<link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap">"""
NAV_ITEMS = [  # (key, パス, パソコンでの表示, スマホでの表示)
    ("home", "index.html", "ホーム", "ホーム"),
    ("news", "news/index.html", "今朝のニュース", "ニュース"),
    ("kurashi", "pages/kurashi.html", "くらしの制度", "制度"),
    ("town", "pages/town.html", "イベント・グルメ", "イベント"),
    ("fujisawa", "pages/fujisawa.html", "藤沢市", "藤沢"),
    ("samukawa", "pages/samukawa.html", "寒川町", "寒川"),
    ("about", "pages/about.html", "このサイトについて", "サイトについて"),
]
# 静的ページ（build.py が作らないページ）と、そのメニューの場所
STATIC_PAGES = {
    "index.html": ("", "home"), "pages/about.html": ("../", "about"),
    "pages/fujisawa.html": ("../", "fujisawa"), "pages/fujisawa-education.html": ("../", "fujisawa"),
    "pages/fujisawa-school.html": ("../", "fujisawa"), "pages/samukawa.html": ("../", "samukawa"),
}


def nav(prefix="../", active=""):
    """パソコン：右上に横並び。スマホ：名前・「今朝のニュース」ボタン・≡（押すと一覧）。
    ≡ は <details> なので JavaScript なしで開け閉めできる。"""
    current = ' aria-current="page"'
    links = "".join(
        f'<a href="{prefix}{path}"{current if key == active else ""}>{long}</a>'
        for key, path, long, _ in NAV_ITEMS)
    return f"""{NAV_START}
  <div class="site-nav">
    <a class="site-brand" href="{prefix}index.html"><img src="{prefix}assets/favicon.png" alt="" width="24" height="24">くらしノート<small>藤沢・寒川</small></a>
    <nav class="site-links" aria-label="サイト内のページ">{links}</nav>
    <a class="nav-cta" href="{prefix}news/index.html">今朝のニュース</a>
    <details class="site-menu">
      <summary aria-label="メニュー"><span></span></summary>
      <nav class="menu-list" aria-label="メニュー">{links}</nav>
    </details>
  </div>
  {NAV_END}"""


def footer(prefix="../"):
    """全ページ共通のいちばん下（お問い合わせ・このサイトについて・RSS）。"""
    contact = ""
    if FORM_URL:
        contact = f"""
    <section class="contact" id="contact" aria-labelledby="contact-title">
      <h2 id="contact-title">お問い合わせ</h2>
      <p>情報の誤りのご指摘、情報の提供、ご意見はこちらからお寄せください。返信が必要な方は、フォームにメールアドレスをお書きください。</p>
      <a class="contact-button" href="{FORM_URL}" target="_blank" rel="noopener">お問い合わせフォームを開く</a>
      <p class="contact-note">Googleフォームが開きます。市役所・町役場への申請や相談はできません。手続きは各窓口へお問い合わせください。</p>
    </section>"""
    return f"""{FOOTER_START}
  <footer class="site-footer">{contact}
    <nav class="footer-links" aria-label="このサイトについて"><a href="{prefix}pages/about.html">このサイトについて</a><a href="{prefix}news/feed.xml">RSS（今朝のニュース）</a></nav>
    <p class="footer-note">市や町の公式サイトではありません。内容は必ず公式の案内で確かめてください。</p>
    <p class="footer-copy">© くらしノート｜藤沢・寒川</p>
  </footer>
  {FOOTER_END}"""


def head_extras(title, description, prefix="../"):
    """SNS・LINEで共有されたときのカード（OGP）と、ブラウザのアイコン。"""
    desc = description or "藤沢・寒川の暮らしの情報を毎朝まとめて。今朝のニュース・くらしの制度・イベント・グルメ"
    return f"""
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta property="og:image" content="{SITE_URL}assets/ogp.png">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="{prefix}assets/favicon.png">
  <link rel="apple-touch-icon" href="{prefix}assets/apple-touch-icon.png">"""


def share_links(url, text):
    """LINE・X で送るためのリンク（外部のスクリプトは読み込まない）。"""
    from urllib.parse import quote
    u, t = quote(url, safe=""), quote(text, safe="")
    return (f'    <p class="share">このページを送る：'
            f'<a href="https://social-plugins.line.me/lineit/share?url={u}" target="_blank" rel="noopener">LINE</a>'
            f'<a href="https://x.com/intent/post?url={u}&amp;text={t}" target="_blank" rel="noopener">X</a></p>')


def page(title, body, css="../css/style.css", description="", feed=False, script="", active=""):
    meta = f'\n  <meta name="description" content="{esc(description)}">' if description else ""
    meta += head_extras(f"{title}｜{SITE_NAME}", description)
    if script:
        meta += f'\n  <script src="{script}?v={ASSET_VER}" defer></script>'
    if feed:
        meta += f'\n  <link rel="alternate" type="application/rss+xml" title="今朝のニュース｜{SITE_NAME}" href="feed.xml">'
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}｜{TITLE_SUFFIX}</title>{meta}
  {FONT_LINKS}
  <link rel="stylesheet" href="{css}?v={ASSET_VER}">
  <script type="module" src="{css.replace('css/style.css', 'js/linebreak.js')}?v={ASSET_VER}"></script>
</head>

<body>
  {nav("../", active)}
  <main>
{body}
  </main>
  {footer(css.replace("css/style.css", ""))}
</body>
</html>
"""


NOTICE = """    <p class="news-notice">
      要約はAIを使って作り、運営者が確認してから載せています。
      正確な内容は、必ずリンク先の記事や公式の発表で確かめてください。
      <a href="../pages/about.html">このサイトについて</a>
    </p>"""


def source_link(url):
    """出典の行の終わりに付ける、元の記事へのリンク。"""
    return f'<br><a href="{esc(url)}" target="_blank" rel="noopener">元の記事を読む（{esc(url_host(url))}）</a>'


def url_host(url):
    from urllib.parse import urlparse
    return urlparse(url).netloc.removeprefix("www.")


def render_item(item, n=0):
    published = f"・{esc(item['published'])}" if item.get("published") else ""
    anchor = f' id="item-{n}"' if n else ""
    return f"""        <article class="news-item"{anchor}>
          <p class="news-tag">{icon(TOPIC_ICONS.get(item['topic'], 'information'))}{esc(item['topic'])}</p>
          <h3><a href="{esc(item['url'])}" target="_blank" rel="noopener">{esc(item['title'])}</a></h3>
          <p>{esc(item['summary'])}</p>
          <p class="news-impact"><span>暮らしへの影響</span>{esc(item['impact'])}</p>
          <p class="news-source">出典：{esc(item['source_name'])}{published}{source_link(item['url'])}</p>
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
            "\n".join(render_item(it, brief["items"].index(it) + 1) for it in items),
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
    parts += ["", share_links(f"{SITE_URL}news/{brief['date']}.html", f"今朝のニュース {jp_date(brief['date'])}｜{SITE_NAME}"),
              "", f'    <nav class="news-nav">{" ".join(nav)}</nav>',
              '    <p class="news-notice">毎朝のニュースは <a href="feed.xml">RSS（フィード）</a> でも受け取れます。</p>',
              "", NOTICE]
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
    page_url = f"news/{latest['date']}.html"
    heads = "\n".join(
        f'          <li><a href="{page_url}#item-{i}"><span>{esc(it["area"])}</span>{esc(it["title"])}</a></li>'
        for i, it in enumerate(latest["items"][:TOP_HEADLINES], 1)
    )
    return f"""{INDEX_START}
    <section class="news-home has-illust">
      <div>
        <h2>今朝のニュース</h2>
        <p class="news-home-date">{jp_date(latest['date'])}</p>
        <ul class="news-home-list">
{heads}
        </ul>
        <a class="news-home-more" href="news/index.html">今朝のニュースを読む（{len(latest['items'])}本）→</a>
      </div>
      <img class="news-home-illust" src="assets/illust/phone.png" alt="" width="551" height="600">
    </section>
    {INDEX_END}"""


def render_feed(briefs):
    """今朝のニュースの RSS 2.0。1本ずつ記事として流す。"""
    entries = []
    for brief in briefs[:FEED_DAYS]:
        d = date.fromisoformat(brief["date"])
        pub = datetime(d.year, d.month, d.day, 7, 0, tzinfo=JST).strftime("%a, %d %b %Y %H:%M:%S +0900")
        page_url = f"{SITE_URL}news/{brief['date']}.html"
        for i, it in enumerate(brief["items"], 1):
            entries.append(f"""    <item>
      <title>{esc(f"［{it['area']}］{it['title']}")}</title>
      <link>{esc(it['url'])}</link>
      <guid isPermaLink="false">{esc(page_url)}#{i}</guid>
      <description>{esc(it['summary'] + ' ' + it['impact'] + '（出典：' + it['source_name'] + '）')}</description>
      <pubDate>{pub}</pubDate>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>今朝のニュース｜{SITE_NAME}</title>
    <link>{SITE_URL}news/index.html</link>
    <description>藤沢・寒川・神奈川の暮らしに関わるニュースのまとめ（要約はAIを使い、運営者が確認しています）</description>
    <language>ja</language>
{chr(10).join(entries)}
  </channel>
</rss>
"""


# ---------- くらしの制度 ----------

def load_kurashi(today):
    """期限が過ぎたものを除いて返す。export 後に日がたっても古い案件を出さないため。"""
    if not KURASHI_DATA.exists():
        return [], []
    try:
        cases = json.loads(KURASHI_DATA.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [], [f"kurashi.json: JSON の書き方が正しくない（{e}）"]
    errors = []
    for c in cases:
        for key in ("title", "primary_source", "last_verified"):
            if not c.get(key):
                errors.append(f"kurashi.json「{c.get('title', '?')}」: {key} が空")
        if c.get("primary_source") and not c["primary_source"].startswith("https://"):
            errors.append(f"kurashi.json「{c.get('title')}」: 一次情報が https:// で始まっていない")
    shown = [c for c in cases if not c.get("deadline_date") or c["deadline_date"] >= today]
    return shown, errors


def render_case(c):
    rows = []
    for label, key in (("対象", "target_user"), ("内容", "benefit"), ("金額", "amount"),
                       ("期限", "deadline"), ("申し込み方法", "how_to_apply"),
                       ("担当", "department"), ("問い合わせ", "contact")):
        if c.get(key):
            rows.append(f"            <dt>{label}</dt><dd>{esc(c[key])}</dd>")
    deadline = ""
    if c.get("deadline"):
        until = f' data-deadline="{esc(c["deadline_date"])}"' if c.get("deadline_date") else ""
        deadline = f'<p class="kurashi-deadline"{until}>期限：{esc(c["deadline"])}</p>'
    tag = c.get('category') or c.get('area') or ''
    lead = c.get("summary") or c.get("benefit") or ""
    rows_html = "\n".join(rows)
    return f"""        <article class="news-item" id="{esc(c['id'])}">
          <p class="news-tag">{icon(case_icon(tag))}{esc(tag)}</p>
          <h3>{esc(c['title'])}</h3>
          {deadline}
          <p>{esc(lead)}</p>
          <details class="kurashi-details">
            <summary>くわしく見る</summary>
            <dl>
{rows_html}
            </dl>
          </details>
          <p class="news-source"><a href="{esc(c['primary_source'])}" target="_blank" rel="noopener">公式の案内を見る</a>・最終確認 {esc(c['last_verified'])}</p>
        </article>"""


def render_kurashi_body(cases):
    if cases:
        items = "\n".join(render_case(c) for c in cases)
        listing = f'      <div class="news-list">\n{items}\n      </div>'
    else:
        listing = "      <p>今、載せている制度はありません。</p>"
    return f"""    <a class="back-link" href="../index.html">← トップページに戻る</a>

    <section>
      <p>藤沢くらし制度ノート</p>
      <h1>くらしの制度</h1>
      <p>藤沢市・神奈川県の給付・補助・申し込みなどのうち、公式の案内を確認したものを、期限の近い順に載せています。期限が過ぎたものは自動で外れます。</p>
    </section>

    <section class="news-section">
{listing}
    </section>

    <p class="news-notice">
      市や県の公式の発信ではありません。内容は「最終確認」の日の時点のものです。
      申し込みの前に、必ず公式の案内で最新の情報を確かめてください。
      <a href="about.html">このサイトについて</a>
    </p>"""


def render_kurashi_block(cases):
    if cases:
        today = datetime.now(JST).date()
        rows = []
        for c in cases[:3]:
            label, soon = "随時", ""
            if c.get("deadline_date"):
                left = (date.fromisoformat(c["deadline_date"]) - today).days
                label = "期限 " + esc(c["deadline_date"][5:].replace("-", "/"))
                if left <= 7:  # 1週間以内の期限は目立たせる
                    soon = f'<em class="soon">{"あと" + str(left) + "日" if left > 0 else "今日まで"}</em>'
            rows.append(f'          <li><a href="pages/kurashi.html#{esc(c["id"])}"><span>{label}{soon}</span>{esc(c["title"])}</a></li>')
        rows = "\n".join(rows)
        text = f'<p class="news-home-date">期限の近い順・{len(cases)}件</p>\n        <ul class="news-home-list">\n{rows}\n        </ul>'
    else:
        text = "<p>準備中です。</p>"
    return f"""{KURASHI_START}
    <section class="news-home has-illust">
      <div>
        <h2>くらしの制度</h2>
        {text}
        <a class="news-home-more" href="pages/kurashi.html">くらしの制度を見る →</a>
      </div>
      <img class="news-home-illust" src="assets/illust/counter.png" alt="" width="600" height="387">
    </section>
    {KURASHI_END}"""


# ---------- まちのイベント・グルメ ----------

def load_town(today):
    """表示するイベント（終わっていないもの、日付順）とグルメ（新しい順）を返す。"""
    if not TOWN_DATA.exists():
        return [], [], []
    try:
        items = json.loads(TOWN_DATA.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [], [], [f"town.json: JSON の書き方が正しくない（{e}）"]
    errors, events, foods = [], [], []
    for t in items:
        label = f"town.json「{t.get('title', '?')}」"
        for key in ("kind", "title", "summary", "source_name", "url", "added"):
            if not str(t.get(key, "")).strip():
                errors.append(f"{label}: {key} が空")
        if t.get("kind") not in ("event", "food"):
            errors.append(f"{label}: kind は event か food")
        if t.get("url") and not t["url"].startswith("https://"):
            errors.append(f"{label}: url が https:// で始まっていない")
        text = " ".join(str(t.get(k, "")) for k in ("title", "summary", "place"))
        if "茅ヶ崎" in text or "茅ケ崎" in text:
            errors.append(f"{label}: 茅ヶ崎市の話題は載せない")
        if editorial.is_excluded(t.get("url", "")):
            errors.append(f"{label}: 掲載しないと決めた記事（data/excluded.json）")
        if t.get("kind") == "event":
            try:
                date.fromisoformat(t.get("date_start", ""))
            except ValueError:
                errors.append(f"{label}: イベントには date_start（YYYY-MM-DD）が必要")
                continue
            if (t.get("date_end") or t["date_start"]) >= today:
                events.append(t)
        elif t.get("kind") == "food" and t.get("added", "") >= (
                date.fromisoformat(today) - timedelta(days=FOOD_DAYS)).isoformat():
            foods.append(t)
    events.sort(key=lambda t: (t["date_start"], t["title"]))
    foods.sort(key=lambda t: t["added"], reverse=True)
    return events, foods, errors


def date_badge(t, today):
    d = date.fromisoformat(t["date_start"])
    if t["date_start"] < today:
        return '<p class="town-date is-open"><span>開催中</span></p>'
    return (f'<p class="town-date"><span>{d.month}/{d.day}</span>'
            f'<small>{WEEKDAYS[d.weekday()]}</small></p>')


def render_event(t, today, n=0):
    place = f"・{esc(t['place'])}" if t.get("place") else ""
    return f"""        <article class="town-event" id="ev-{n}">
          {date_badge(t, today)}
          <div>
            <h3><a href="{esc(t['url'])}" target="_blank" rel="noopener">{esc(t['title'])}</a></h3>
            <p class="town-when">{esc(t.get('when') or '')}{place}</p>
            <p>{esc(t['summary'])}</p>
            <p class="news-source">出典：{esc(t['source_name'])}{source_link(t['url'])}</p>
          </div>
        </article>"""


def render_food(t):
    place = f'<p class="town-when">{esc(t["area"])}・{esc(t["place"])}</p>' if t.get("place") else ""
    return f"""        <article class="news-item">
          <p class="news-tag">{icon('food')}グルメ</p>
          <h3><a href="{esc(t['url'])}" target="_blank" rel="noopener">{esc(t['title'])}</a></h3>
          {place}
          <p>{esc(t['summary'])}</p>
          <p class="news-source">出典：{esc(t['source_name'])}・{esc(t['added'])} 掲載{source_link(t['url'])}</p>
        </article>"""


def render_town_body(events, foods, today):
    ev = "\n".join(render_event(t, today, i) for i, t in enumerate(events, 1)) or \
        '        <p>いまは載せているイベントがありません。</p>'
    fd = "\n".join(render_food(t) for t in foods) or \
        '        <p>新しいお店の話題が見つかったら、ここに載せます。</p>'
    return f"""    <a class="back-link" href="../index.html">← トップページに戻る</a>

    <section class="hero">
      <div class="hero-text">
        <p>藤沢・寒川</p>
        <h1>まちのイベント・グルメ</h1>
        <p>お祭りや催し、新しいお店の話題を集めています。日付が過ぎたイベントは自動で外れます。</p>
      </div>
      <img class="page-illust" src="../assets/illust/community.png" alt="" width="1000" height="832">
    </section>

    <section class="news-section">
      <h2>これからのイベント</h2>
      <div class="town-events">
{ev}
      </div>
    </section>

    <section class="news-section">
      <h2>グルメ・新しいお店</h2>
      <div class="news-list">
{fd}
      </div>
    </section>

{share_links(SITE_URL + "pages/town.html", "まちのイベント・グルメ｜" + SITE_NAME)}

    <p class="news-notice">
      地域の新聞や観光協会などの発表をもとに、見出し・日時・短い紹介とリンクを載せています。
      お店やイベントの評価はしていません。広告（PR）記事は載せていません。
      日時や中止の情報は、必ずリンク先で確かめてください。
      <a href="about.html">このサイトについて</a>
    </p>"""


def render_town_block(events, foods, today):
    if events:
        rows = "\n".join(
            f'          <li><a href="pages/town.html#ev-{i}"><span>{"開催中" if t["date_start"] < today else esc(date.fromisoformat(t["date_start"]).month) + "/" + esc(date.fromisoformat(t["date_start"]).day)}</span>{esc(t["title"])}</a></li>'
            for i, t in enumerate(events[:3], 1))
        body = f"""        <ul class="news-home-list">
{rows}
        </ul>"""
    else:
        body = "        <p>お祭りや催し、新しいお店の話題を集めていきます。</p>"
    return f"""{TOWN_START}
    <section class="news-home has-illust">
      <div>
        <h2>まちのイベント・グルメ</h2>
{body}
        <a class="news-home-more" href="pages/town.html">イベント・グルメを見る（{len(events) + len(foods)}件）→</a>
      </div>
      <img class="news-home-illust" src="assets/illust/community.png" alt="" width="1000" height="832">
    </section>
    {TOWN_END}"""


def replace_block(text, start_mark, end_mark, block):
    start, end = text.find(start_mark), text.find(end_mark)
    if start == -1 or end == -1:
        raise ValueError(f"index.html に {start_mark} / {end_mark} の目印がありません。")
    return text[:start] + block + text[end + len(end_mark):]


# ---------- 書き出し ----------

def build():
    today = datetime.now(JST).date().isoformat()
    briefs, errors = load_briefs()
    kurashi, kurashi_errors = load_kurashi(today)
    errors += kurashi_errors
    events, foods, town_errors = load_town(today)
    errors += town_errors
    if errors:
        print("データに問題があります。ページは作りませんでした。")
        for e in errors:
            print("  -", e)
        return 1
    for note in repeated_urls(briefs):
        print("注意：", note)
    for note in alarm_notes(briefs):
        print("注意：", note)
    if "--check" in sys.argv:
        print(f"OK：ニュース{len(briefs)}日分・くらしの制度{len(kurashi)}件・イベント{len(events)}件・グルメ{len(foods)}件のデータに問題はありません。")
        return 0

    NEWS_OUT.mkdir(exist_ok=True)
    outputs = {}
    for i, brief in enumerate(briefs):
        newer = briefs[i - 1] if i > 0 else None
        older = briefs[i + 1] if i + 1 < len(briefs) else None
        title = f"今朝のニュース {jp_date(brief['date'])}"
        outputs[f"{brief['date']}.html"] = page(title, render_brief_body(brief, newer, older), feed=True, active="news")

    if briefs:
        latest = briefs[0]
        outputs["index.html"] = page(
            "今朝のニュース",
            render_brief_body(latest, older=briefs[1] if len(briefs) > 1 else None),
            description="藤沢・寒川・神奈川の暮らしに関わる今朝のニュースのまとめ",
            feed=True, active="news",
        )
        outputs["archive.html"] = page("過去のニュース一覧", render_archive_body(briefs), active="news")
    else:
        outputs["index.html"] = page("今朝のニュース", render_empty_body(), active="news")

    feed_path = NEWS_OUT / "feed.xml"
    if briefs:
        feed_path.write_text(render_feed(briefs), encoding="utf-8")
    elif feed_path.exists():
        feed_path.unlink()

    # 消えたデータのページを残さない
    for old in NEWS_OUT.glob("*.html"):
        if old.name not in outputs:
            old.unlink()
    for name, text in outputs.items():
        (NEWS_OUT / name).write_text(text, encoding="utf-8")

    TOWN_OUT.write_text(page("まちのイベント・グルメ", render_town_body(events, foods, today),
                             description="藤沢・寒川のお祭りや催し、新しいお店の話題", active="town"), encoding="utf-8")
    KURASHI_OUT.write_text(page("くらしの制度", render_kurashi_body(kurashi), script="../js/deadline.js", active="kurashi"), encoding="utf-8")

    index_html = INDEX.read_text(encoding="utf-8")
    try:
        index_html = replace_block(index_html, INDEX_START, INDEX_END,
                                   render_index_block(briefs[0] if briefs else None))
        index_html = replace_block(index_html, KURASHI_START, KURASHI_END,
                                   render_kurashi_block(kurashi))
        index_html = replace_block(index_html, TOWN_START, TOWN_END,
                                   render_town_block(events, foods, today))
    except ValueError as e:
        print(e)
        return 1
    INDEX.write_text(index_html, encoding="utf-8")

    # 静的ページのメニューを入れ替える（目印がなければ <body> の直後に入れる）
    for rel, (prefix, active) in STATIC_PAGES.items():
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        block = nav(prefix, active)
        text = re.sub(r'href="((?:\.\./)?css/style\.css)(?:\?v=\d+)?"', rf'href="\1?v={ASSET_VER}"', text)
        text = re.sub(r'src="((?:\.\./)?js/[a-z]+\.js)(?:\?v=\d+)?"', rf'src="\1?v={ASSET_VER}"', text)
        if "fonts.googleapis.com" not in text:
            text = re.sub(r'(\n\s*)(<link rel="stylesheet" href="(?:\.\./)?css/style\.css)', rf"\1{FONT_LINKS}\1\2", text, count=1)
        if FOOTER_START in text:
            text = replace_block(text, FOOTER_START, FOOTER_END, footer(prefix))
        else:
            text = re.sub(r"\s*<footer>.*?</footer>", "", text, flags=re.S)
            text = text.replace("</body>", f"  {footer(prefix)}\n</body>", 1)
        if "js/linebreak.js" not in text:  # 日本語の改行を文節で（全ページ共通）
            text = text.replace("</head>", f'  <script type="module" src="{prefix}js/linebreak.js?v={ASSET_VER}"></script>\n</head>', 1)
        if NAV_START in text:
            text = replace_block(text, NAV_START, NAV_END, block)
        else:
            text = text.replace("<body>", "<body>\n  " + block, 1)
        path.write_text(text, encoding="utf-8")

    print(f"作成：news/ に {len(outputs)} ページ、くらしの制度 {len(kurashi)}件、トップページを更新")
    return 0


if __name__ == "__main__":
    sys.exit(build())
