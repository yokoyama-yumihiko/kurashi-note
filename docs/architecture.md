# くらしノート Architecture

## 1. Purpose

くらしノートは、公共政策に関する情報を、
市民・行政・研究者・学生・報道関係者などが
分かりやすく利用できる形で提供するための
公共政策研究・情報発信プラットフォームです。

## 2. Core Principles

くらしノートの開発では、以下を基本原則とします。

1. Evidence First
   - 根拠・一次資料を重視する

2. Citizen First
   - 市民にとって分かりやすい設計を優先する

3. Simple First
   - 不必要に複雑な技術構成にしない

4. Open Architecture
   - 将来の機能追加・データ連携を容易にする

5. AI Assisted
   - AIを調査・分析・開発支援に活用する

6. Human Review
   - AIの出力をそのまま採用せず、人間が確認する

## 3. System Structure

くらしノートは段階的に以下の構成へ発展させます。

### Web
- HTML
- CSS
- JavaScript
- GitHub Pages

### Application
- Flutter
- iOS
- Android

### Data
- 公開統計
- 自治体オープンデータ
- 政策資料
- 議会資料

### AI
- ChatGPT
- Claude / Claude Code

## 4. Development Policy

開発は、

Plan
→ Design
→ Implement
→ Test
→ Review
→ Commit
→ Push

の順序を基本とします。

大規模な変更を一度に行わず、
小さな変更単位でGitに記録します。

## 5. Long-Term Architecture

将来的には、

くらしノート Web
↓
Policy Data Platform
↓
API / Database
↓
くらしノート Applications
↓
AI Research Assistant

という構成を目指します。

ただし、初期段階では過剰なシステム構築を避け、
必要になった機能から段階的に追加します。