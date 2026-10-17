# 今朝のニュース データの形

1日分を `data/news/YYYY-MM-DD.json` に1ファイルで置き、`python3 tools/build.py` を実行すると
`news/` のページとトップページの「今朝のニュース」欄ができる。
`python3 tools/build.py --check` はデータの確認だけを行う（ファイルは書かない）。

```json
{
  "date": "2026-10-17",
  "keywords": ["キーワード1", "キーワード2", "キーワード3"],
  "items": [
    {
      "title": "元記事の見出し（そのまま）",
      "summary": "自分の言葉での要約（2〜3文）",
      "impact": "暮らしへの影響（1文）",
      "area": "藤沢市",
      "topic": "子育て・教育",
      "source_name": "媒体名",
      "url": "https://...",
      "published": "10月17日"
    }
  ],
  "today_in_history": {
    "title": "今日は何の日",
    "note": "説明（1〜2文）",
    "source_name": "出典名",
    "url": "https://..."
  }
}
```

- `area`：藤沢市／寒川町／神奈川県／全国／海外（茅ヶ崎市は載せない）
- `topic`：子育て・教育／福祉・医療・介護／防災・安全／交通・まちづくり／環境・エネルギー／くらし・お金／仕事・経済／平和・人権／その他
- `keywords`・`today_in_history`・`published` は省略できる
- 記事の本文・写真は転載しない。見出し・短い要約・リンクだけにする
- 記念日など出典が確かめられないものは載せない
