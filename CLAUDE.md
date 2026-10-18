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

### サイト名・一言（2026-10-17 本人決定）
- サイト名：「くらしノート｜藤沢・寒川」。旧名は表に出さない（本人の指示）。<title> の後ろは「くらしノート 藤沢・寒川」
- トップの一言：「暮らしの情報を、毎朝まとめて。」
- リポジトリ名は kurashi-note、公開アドレスは https://yokoyama-yumihiko.github.io/kurashi-note/（2026-10-17 変更）
