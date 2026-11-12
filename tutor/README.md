# AI家庭教師(tutor)

担当: 高橋 / ブランチ: `feature/chat`

Ollama のローカル LLM で動く学習支援 AI です。Python の標準ライブラリだけで動きます(`pip install` 不要)。

## 起動

```
ollama pull qwen3:4b-instruct      # 初回のみ
python3 -m tutor                   # 質問モードで開始
python3 -m tutor --mode 先生       # 先生モードで開始
python3 -m tutor --learner 高橋    # 学習者名を指定(記録は名前ごとに分かれる)
python3 -m tutor --resume last     # 前回のセッションを再開
```

| 環境変数 | 意味 | 既定値 |
|---|---|---|
| `LLM_MODEL` | Ollama のモデル | `qwen3:4b-instruct` |
| `OLLAMA_URL` | Ollama の接続先 | `http://localhost:11434` |
| `TUTOR_DB` | 学習記録の保存先 | `data/tutor.db` |

## 5つのモード

| モード | 内容 |
|---|---|
| 質問 | 疑問に結論から簡潔に答える |
| 解説 | 段階を追って、例を使って丁寧に説明する |
| 添削 | 答案の良い点と直す点を指摘する(正解は書かない) |
| 先生 | 質問を1つずつ出して理解度を確かめ、3回答えるごとに自動で評価する |
| ヒント | 答えは言わず、段階1→3でヒントを出す |

## コマンド

`/mode <名前>` モード切替、`/modes` 一覧、`/hint <1-3>` ヒント段階、`/eval` 理解度評価、
`/profile` 理解度と苦手分野、`/level <初級|標準|上級>`、`/style <希望>`、
`/history` 過去のセッション、`/resume <番号>` 再開、`/new` 新しいセッション、`/help`、`/exit`

## しくみ

```
cli.py ──> session.py (TutorSession) ──> llm/ (OllamaBackend / FakeBackend)
                │
                ├─ modes.py + prompts/   モード別の指示
                ├─ profile.py            理解度・苦手分野から説明を調整
                ├─ assessment.py         JSON スキーマで採点 → 移動平均で理解度を更新
                ├─ retrieval.py          将来の RAG 用の差し込み口(今は空)
                └─ store/                SQLite に会話・理解度・苦手分野を保存
```

- **会話の保存**: 発言と返答は1組で保存します。途中でエラーや中断があれば、何も保存しません。
- **理解度**: 教科・単元ごとに 0〜100 点です。新しい評価を重めに反映します(移動平均、重み 0.6)。
- **説明の調整**: レベル、希望、理解が浅い単元、過去のつまずきを、毎回の指示に含めます。
- **モードの念押し**: 小さなモデルが指示を忘れないよう、最新の発言の直前にモードの要点を入れます。
- **画面と独立**: `TutorSession` は画面と独立しているので、他のメンバーの UI からも呼べます(`tutor/__init__.py` の例を参照)。
- **RAG**: `Retriever` を実装して `TutorSession(retriever=...)` に渡すと、参考資料がプロンプトに入ります。

## テスト

```
python3 -m unittest
```

LLM や Ollama がなくても動きます(偽の LLM と偽の HTTP サーバーを使います)。

## 既知の制約

- 4B モデルなので、添削モードで正しい式を書いてしまうことや、先生モードで質問が2つになることがあります。
  より大きいモデル(例: `qwen2.5:7b`)を `LLM_MODEL` で指定すると改善が見込めます。
- 単元名は LLM が決めるため、「二次関数」と「2次関数」が別の単元として記録されることがあります。
