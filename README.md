# cstudy — ローカルLLM

[Ollama](https://ollama.com) で小型の LLM を手元の PC (CPU) で動かし、Python から使います。
Python 側は標準ライブラリだけで動きます（`pip install` 不要）。

## セットアップ

1. Ollama をインストール: `winget install Ollama.Ollama`（インストール後は常駐アプリとして自動起動）
2. モデルを取得:
   ```
   ollama pull qwen2.5:3b
   ```
3. チャットを起動:
   ```
   python chat.py
   python chat.py --model gemma3:4b   # 別モデルを使う場合
   ```

## モデルの目安（RAM 16GB・GPUなし）

| モデル | サイズ | 備考 |
|---|---|---|
| `qwen2.5:1.5b` | 約1GB | 最速、品質は控えめ |
| `qwen2.5:3b` | 約2GB | **既定**。速度と日本語品質のバランス |
| `gemma3:4b` | 約3GB | 日本語も比較的得意 |
| `qwen2.5:7b` | 約5GB | 高品質だが CPU では遅め |

## Python から使う

```python
from local_llm import chat

print(chat([{"role": "user", "content": "高専とは何ですか？"}]))
```

環境変数 `LLM_MODEL` で既定モデル、`OLLAMA_URL` で接続先を変更できます。
