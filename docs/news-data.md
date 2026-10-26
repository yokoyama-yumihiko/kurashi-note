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
- `check`：検証の状態（tools/verify.py が書く。手で書かない）。`{"status": "PUBLISH_APPROVED", "hash": "...", "source": 日時, "fact": 日時, "editorial": 日時, "publish": 日時}`。2026-10-27 以降のデータは、これが PUBLISH_APPROVED で内容のハッシュが合う記事だけ公開できる（data/town.json のうち added が 2026-10-27 以降のイベント・グルメも同じ）。根拠の文・HOLDの理由は公開しない data/_verify/ にだけ置く
- 記事の本文・写真は転載しない。見出し・短い要約・リンクだけにする
- 記念日など出典が確かめられないものは載せない
