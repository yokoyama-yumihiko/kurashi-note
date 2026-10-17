# Yokoyama Policy Lab — Claude Code Instructions

## 1. Project

Yokoyama Policy Lab (YPL) is a public policy research and information platform.

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

YPL follows:

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

YPL should prioritize:

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

YPL may eventually include:

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
- YPL mobile applications
- AI Research Assistant

These are long-term directions.

Do not implement them prematurely unless requested.

---

## 11. Working With the User

The user is learning development while building YPL.

Therefore:

- explain commands before potentially destructive operations
- avoid unnecessary technical jargon
- break complicated work into manageable steps
- preserve working code whenever possible
- clearly distinguish required steps from optional improvements

The goal is not only to build YPL,
but also to create a development environment the user can understand and maintain.
---

## 12. Site Direction（2026-10-17 本人決定）

- 選挙・政治の発信はしない。「一市民が作る、藤沢・寒川の暮らしのお役立ちサイト」として作る
- 茅ヶ崎市の情報は載せない
- 2本柱：①今朝のニュース（毎朝の暮らしに関わるニュースのまとめ、`data/news/` → `tools/build.py`。形は `docs/news-data.md`）②蓄積された情報（地域・テーマのページ、藤沢くらし制度ノートの確認済み案件など）
- ニュース記事の本文・写真は転載しない。見出し・自分の言葉での短い要約・元記事へのリンクだけ
- 公開（push）の前に本人が確認する。毎朝のニュースは6時に下書き→本人OKで公開。自動公開への切り替えは本人が決める
- 配色・書体・既存のレイアウトは変えない（新しい部品は既存の5色の範囲で足す）
