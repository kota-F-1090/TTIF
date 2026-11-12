"""ターミナルで動く対話チャット。

使い方:
    python chat.py                 # 既定モデル (qwen2.5:3b)
    python chat.py --model gemma3:4b
コマンド: /reset で履歴クリア, /exit で終了
"""
import argparse
import sys
import urllib.error

from local_llm import DEFAULT_MODEL, chat_stream, list_models

SYSTEM_PROMPT = "あなたは親切で簡潔な日本語アシスタントです。"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args()

    try:
        models = list_models()
    except urllib.error.URLError:
        sys.exit("Ollama に接続できません。Ollama を起動してください (ollama serve)。")
    if args.model not in models:
        sys.exit(f"モデル {args.model} がありません。`ollama pull {args.model}` を実行してください。\n"
                 f"インストール済み: {models}")

    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    print(f"[{args.model}] /reset で履歴クリア, /exit で終了")
    while True:
        try:
            user = input("\nあなた> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        if user == "/exit":
            break
        if user == "/reset":
            history = history[:1]
            print("(履歴をクリアしました)")
            continue

        history.append({"role": "user", "content": user})
        print("AI> ", end="", flush=True)
        reply = ""
        for chunk in chat_stream(history, args.model, temperature=args.temperature):
            print(chunk, end="", flush=True)
            reply += chunk
        print()
        history.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
