# くらしノート｜藤沢・寒川 — Claude Code Instructions

## 1. Project

くらしノート｜藤沢・寒川 is a personal, non-partisan local information site for Fujisawa and Samukawa (see section 12).

The goal is to make public policy easier to understand and more accessible through:

- Evidence
- Data
- Visualization
- AI-assisted research
- Clear communication

Primary users include citizens, students, researchers, journalists,
public officials, and people interested in local communities.

---

## 2. Core Development Principle

くらしノート follows:

Small
→ Test
→ Learn
→ Improve
→ Scale

Do not build unnecessary large systems in the early stages.

Prefer simple, maintainable solutions.

---

## 3. Before Making Changes

Before modifying the project:

1. Understand the user's objective.
2. Inspect the relevant existing files.
3. Check the project documentation.
4. Explain significant changes before implementing them.
5. Prefer small, reversible changes.

Do not rewrite unrelated files unnecessarily.

---

## 4. Project Documentation

Always respect the following documents:

- `docs/architecture.md`
- `docs/coding-rules.md`
- `docs/design.md`
- `docs/roadmap.md`
- `PROJECT_PLAN.md`
- `README.md`

When implementation conflicts with these documents,
identify the conflict before proceeding.

---

## 5. Coding Rules

Follow `docs/coding-rules.md`.

Important principles:

- Keep code readable.
- Prefer simple implementations.
- Avoid unnecessary dependencies.
- Do not hide errors.
- Test changes before committing.
- Do not make large changes without explanation.

---

## 6. Design

Follow `docs/design.md`.

くらしノート should prioritize:

- readability
- accessibility
- mobile usability
- clear information hierarchy
- simple navigation
- evidence and source visibility

Policy information should generally follow:

Issue
→ Data
→ Impact on daily life
→ Policy
→ Evidence / Sources

---

## 7. Security

Never commit:

- passwords
- API keys
- access tokens
- credentials
- private personal information
- confidential documents

Use environment variables or appropriate secure storage.

If sensitive information is detected,
stop and warn the user before committing or pushing.

---

## 8. Git Workflow

Use:

Plan
→ Implement
→ Test
→ Review
→ Commit
→ Push

Keep commits small and understandable.

Before `git push`, confirm that:

- the intended files are included
- no secrets are included
- the application still works
- unrelated files were not accidentally modified

---

## 9. AI Development Policy

AI is a development assistant, not an unquestioned authority.

When generating or modifying code:

- explain important decisions
- verify assumptions
- check existing code first
- test whenever possible
- report errors clearly
- do not silently bypass failures

Never invent successful test results.

---

## 10. Future Direction

くらしノート may eventually include:

- Policy Dashboard
- Interactive Maps
- Data Visualization
- Policy Comparison
- Timeline
- Search
- Local Government Information
- Assembly / Parliamentary Document Search
- Public Transportation Information
- Disaster Information
- Education and Childcare Information
- くらしノート mobile applications
- AI Research Assistant

These are long-term directions.

Do not implement them prematurely unless requested.

---

## 11. Working With the User

The user is learning development while building くらしノート.

Therefore:

- explain commands before potentially destructive operations
- avoid unnecessary technical jargon
- break complicated work into manageable steps
- preserve working code whenever possible
- clearly distinguish required steps from optional improvements

The goal is not only to build くらしノート,
but also to create a development environment the user can understand and maintain.
---

## 12. Site Direction（2026-10-17 本人決定）

- 選挙・政治の発信はしない。「一市民が作る、藤沢・寒川の暮らしのお役立ちサイト」として作る
- 茅ヶ崎市の情報は載せない
- 2本柱：①今朝のニュース（毎朝の暮らしに関わるニュースのまとめ、`data/news/` → `tools/build.py`。形は `docs/news-data.md`）②蓄積された情報（地域・テーマのページ、藤沢くらし制度ノートの確認済み案件など）
- ニュース記事の本文・写真は転載しない。見出し・自分の言葉での短い要約・元記事へのリンクだけ
- 公開（push）の前に本人が確認する。毎朝のニュースは6時に下書き→本人OKで公開。自動公開への切り替えは本人が決める
- 配色・書体・既存のレイアウトは変えない（新しい部品は既存の5色の範囲で足す）

### 編集方針：不安をあおらない（2026-10-18 本人決定）
- 市民の不安を不必要にあおらない。風評被害を防ぐ
- 藤沢市・寒川町に直接関係しない局地的な事件・事故・食中毒などは、原則として載せない
- ただし、市民に具体的な危険が及ぶ情報（リコール・注意報・広域の感染症など）や、行政が対応を求める情報（個人情報漏えいで登録者に注意を求める等）は載せる。その場合も事実と「何をすればよいか」だけを書き、あおる言葉を使わない
- 仕組み：`tools/editorial.py` が判定（候補集め・HANDOFF取り込みで自動的に外し、`build.py --check` が「注意」を出す）。掲載しないと決めた記事は `data/excluded.json` に入れ、翌日以降も載らないようにする（取り込み・make_brief・build のどこでも止まる）
- 初回の適用：2026-10-16 神奈川県発表「食中毒の発生について」（綾瀬市内の社員食堂）を10/18のニュースから取り下げ
- 2026-10-26 見直し：言葉が当たっただけで一律に消さない。政治家・政党・選挙活動は HOLD（除外基準は維持）、事件・事故・感染症は載せる文に住民の行動（回収・運休・通行止め・注意報など）がなければ HOLD、あれば警告。最終判断は編集方針に沿って Claude と本人が行う（`editorial.assess()`）

### 公開前の検証関門（2026-10-26 本人決定）
- 2026-10-27 以降のニュース・イベント・グルメは、4段階（SOURCE_VERIFIED → FACT_VERIFIED → EDITORIAL_APPROVED → PUBLISH_APPROVED）を通ったものだけ公開する。手順は `docs/morning-brief.md`「公開前の検証」、仕組みは `tools/gate.py`・`tools/verify.py`
- AI の「確認しました」だけで検証済みにしない。根拠の箇所（本文の該当部分）を機械で記録し、Claude はそれを照合する。確かめられないものは HOLD にして本人に回す。推測で補わない
- `verify.py approve`（PUBLISH_APPROVED）は、本人が OK と言ったときだけ実行する。`check` を手で書き換えない
- 検証記録・HOLD の理由・未公開の記事は `data/_verify/`、取得ログは `data/_logs/`（どちらも .gitignore。公開リポジトリに入れない）。公開データには状態・日時・ハッシュだけ
- 情報源は `data/sources.json` のドメインだけ。足すときは本人が確かめてから。候補集めに情報源を足すときは、実際に取得テストをして成功したものだけ

### サイト名・一言（2026-10-17 本人決定）
- サイト名：「くらしノート｜藤沢・寒川」。旧名は表に出さない（本人の指示）。<title> の後ろは「くらしノート 藤沢・寒川」
- トップの一言：「暮らしの情報を、毎朝まとめて。」
- リポジトリ名は kurashi-note、公開アドレスは https://yokoyama-yumihiko.github.io/kurashi-note/（2026-10-17 変更）

## 13. Macのターミナルとクラウド（スマホ）の両方から作業する（2026-10-19 本人決定）

本人はMacのターミナルでも、スマホのClaudeアプリ（Claude Code のクラウド版）でもこのサイトを触る。どちらで作業しても次を守る。

- **作業の最初に `git pull`**（もう一方が先に公開していることがある）。続けて `git log --oneline -5` で、前回からの変更を確かめる。作業の記録は**コミットメッセージ**に残す（クラウドからはMac側のログを読み書きできないため、コミットがそのまま両方の記録になる）
- 毎朝のニュースは `docs/morning-brief.md` の「まずはこちら」の手順。本人がHANDOFFを貼ったら取り込み → `python3 tools/build.py --check` → `python3 tools/build.py` → 何が載るか（ニュース・イベントの見出しと、取り込まなかったもの・その理由）を短く示して**本人OKを待つ**
- 公開は本人OKの後で、`main` に push する（GitHub Pages は main から公開）。クラウドで main に直接 push できないときは、作業ブランチを push してプルリクエストを作り、マージは本人に頼む（GitHubアプリの「Merge」1回）。公開後1〜10分で反映される
- 編集方針（12章）と `data/excluded.json`、公開前の検証関門はどちらでも同じように効く。消さない・ゆるめない
- クラウドでは `data/_verify/`（検証記録）が残らない。verify.py の run〜approve は1回の作業の中で行い、push 前に `python3 tools/build.py --check` を必ず手で実行する（Mac は pre-push フックが自動で実行）
- リンク確認（import_handoff.py）が**ネットワーク制限で開けない**ときは、黙って `--no-fetch` にしない。本人に伝え、クラウドの環境設定でネットワークを許可してもらうか、本人OKのうえで `--no-fetch` にして WebFetch で各リンクを確かめる
- 制度の候補（type "seido"）は `data/_candidates/`（gitの対象外）に置かれる。クラウドでは消えてしまうので、件名とURLを返事の中に一覧で示す（くらし制度ノートのDBへの登録はMacのタブ4で本人が確かめてから）
- **クラウドではできないこと**（Macで行う）：写真の取り込み（元の写真はMac内）、くらしの制度の書き出し（`tools/export_kurashi.py`、DBの写しはMac内）、ChatGPTの指示文の更新。頼まれたら「Macのターミナルで行います」と伝える
- デザイン・仕組みの改修は、クラウドでは小さな文言修正まで。大きな改修はMacで、変更前の控えを取ってから行う（クラウドで直した場合も、gitの履歴から戻せる）
