"""ターミナルで使う AI 家庭教師。

使い方:
    python3 -m tutor                       # 質問モードで開始
    python3 -m tutor --mode 先生           # 先生モードで開始
    python3 -m tutor --resume last         # 前回のセッションを再開
    python3 -m tutor --learner 高橋        # 学習者名を指定(記録は名前ごと)
"""
import argparse
import sys
from typing import Callable

from .config import Config
from .llm import LLMError, OllamaBackend
from .modes import MODE_SPECS, parse_mode
from .profile import LEVEL_LABELS, parse_level
from .session import AssessmentOutcome, TutorSession
from .store import Repository, connect

HELP = """コマンド一覧:
  /mode <名前>    モードを切り替える(質問 / 解説 / 添削 / 先生 / ヒント)
  /modes          モードの一覧と説明
  /hint <1-3>     ヒントの段階を指定する(ヒントモード)
  /eval           これまでの会話で理解度を評価する
  /profile        理解度と苦手分野の記録を見る
  /level <段階>   説明のレベルを変える(初級 / 標準 / 上級)
  /style <希望>   説明の希望を伝える(例: /style 例えを多めに)
  /history        過去のセッション一覧
  /resume <番号>  過去のセッションを再開する
  /new            新しいセッションを始める(/reset でも可)
  /help           この一覧
  /exit           終了"""


class Cli:
    def __init__(self, session: TutorSession, write: Callable[[str], None] | None = None):
        self.session = session
        self._write = write or _stdout_write

    def say(self, text: str = "") -> None:
        self._write(text + "\n")

    def prompt_label(self) -> str:
        return f"\n[{MODE_SPECS[self.session.mode].label}] あなた> "

    # --- 入力1行の処理。False を返したら終了 -------------------------
    def handle(self, line: str) -> bool:
        line = line.strip()
        if not line:
            return True
        if line.startswith("/"):
            return self._command(line)
        self._chat(line)
        return True

    def _chat(self, text: str) -> None:
        self._write("AI> ")
        try:
            for chunk in self.session.ask(text):
                self._write(chunk)
            self.say()
        except LLMError as e:
            self.say(f"\n(エラー: {e})")
            return
        except KeyboardInterrupt:
            self.say("\n(中断しました。この発言は保存していません)")
            return
        if self.session.should_assess():
            self.say("(理解度を評価しています…)")
            self._show_outcome(self.session.maybe_assess())

    def _command(self, line: str) -> bool:
        name, _, arg = line.partition(" ")
        arg = arg.strip()
        s = self.session
        try:
            if name == "/exit":
                return False
            elif name == "/help":
                self.say(HELP)
            elif name == "/modes":
                for spec in MODE_SPECS.values():
                    mark = "*" if spec.mode is s.mode else " "
                    self.say(f" {mark} {spec.label}({spec.mode.value}): {spec.description}")
            elif name == "/mode":
                if not arg:
                    raise ValueError("使い方: /mode 先生")
                s.set_mode(parse_mode(arg))
                spec = MODE_SPECS[s.mode]
                self.say(f"({spec.label}モードにしました: {spec.description})")
            elif name == "/hint":
                if not arg.isdigit():
                    raise ValueError("使い方: /hint 2")
                s.set_hint_level(int(arg))
                self.say(f"(次のヒントは段階 {s.hint_level} です)")
            elif name == "/eval":
                self.say("(理解度を評価しています…)")
                outcome = s.evaluate()
                if outcome is None:
                    self.say("(評価できませんでした。もう少し会話してから試してください)")
                else:
                    self._show_outcome(outcome)
            elif name == "/profile":
                self._show_profile()
            elif name == "/level":
                learner = s.repo.update_learner(s.learner.id, level=parse_level(arg))
                s.refresh_learner(learner)
                self.say(f"(説明のレベルを「{LEVEL_LABELS[learner.level]}」にしました)")
            elif name == "/style":
                learner = s.repo.update_learner(s.learner.id, style=arg)
                s.refresh_learner(learner)
                self.say(f"(説明の希望を「{arg}」にしました)" if arg else "(説明の希望を消しました)")
            elif name == "/history":
                self._show_history()
            elif name == "/resume":
                if not arg.isdigit():
                    raise ValueError("使い方: /resume 3(番号は /history で確認)")
                s.resume(int(arg))
                self.say(f"(セッション {s.session_id} を再開しました。発言 {len(s.history)} 件)")
                self._show_recent()
            elif name in ("/new", "/reset"):
                s.new_session()
                self.say("(新しいセッションを始めました)")
            else:
                self.say(f"({name} というコマンドはありません。/help で一覧を表示します)")
        except ValueError as e:
            self.say(f"({e})")
        except LLMError as e:
            self.say(f"(エラー: {e})")
        return True

    # --- 表示 ---------------------------------------------------------
    def _show_outcome(self, outcome: AssessmentOutcome | None) -> None:
        if outcome is None:
            self.say("(今回は評価できませんでした)")
            return
        r = outcome.result
        self.say(f"[理解度] {r.subject} / {r.unit}: 今回 {r.score} 点 → 記録 {outcome.mastery_score:.0f} 点")
        if r.weaknesses:
            self.say(f"  つまずいた点: {'、'.join(r.weaknesses)}")
        if r.rationale:
            self.say(f"  理由: {r.rationale}")

    def _show_profile(self) -> None:
        s = self.session
        self.say(f"学習者: {s.learner.name} / レベル: {LEVEL_LABELS.get(s.learner.level, s.learner.level)}")
        if s.learner.style:
            self.say(f"説明の希望: {s.learner.style}")
        mastery = s.repo.get_mastery(s.learner.id)
        if mastery:
            self.say("理解度(低い順):")
            for m in mastery:
                self.say(f"  {m.subject} / {m.unit}: {m.score:.0f} 点({m.attempts} 回評価)")
        else:
            self.say("理解度の記録はまだありません(先生モードで会話すると記録されます)")
        weak = s.repo.get_weaknesses(s.learner.id)
        if weak:
            self.say("苦手分野:")
            for w in weak:
                self.say(f"  {w.note}({w.subject} / {w.unit}, {w.count} 回)")

    def _show_history(self) -> None:
        s = self.session
        sessions = s.repo.list_sessions(s.learner.id)
        if not sessions:
            self.say("(過去のセッションはありません)")
            return
        for info in sessions:
            mark = "*" if info.id == s.session_id else " "
            label = MODE_SPECS[parse_mode(info.mode)].label
            topic = f" {info.subject}/{info.unit}" if info.subject else ""
            title = info.title or "(発言なし)"
            self.say(f" {mark}{info.id:>4}  {info.updated_at[:16]}  [{label}]{topic}  {title}({info.message_count}件)")

    def _show_recent(self, n: int = 4) -> None:
        for m in self.session.history[-n:]:
            who = "あなた" if m["role"] == "user" else "AI"
            text = m["content"].replace("\n", " ")
            self.say(f"  {who}> {text[:80]}{'…' if len(text) > 80 else ''}")


def _stdout_write(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> None:
    config = Config.from_env()
    parser = argparse.ArgumentParser(prog="python3 -m tutor", description="AI家庭教師")
    parser.add_argument("--model", default=config.model, help=f"Ollama のモデル(既定: {config.model})")
    parser.add_argument("--mode", default="質問", help="開始モード(質問/解説/添削/先生/ヒント)")
    parser.add_argument("--learner", default="default", help="学習者名(記録は名前ごとに分かれる)")
    parser.add_argument("--resume", metavar="ID", help="再開するセッション番号、または last")
    parser.add_argument("--db", default=config.db_path, help="保存先の SQLite ファイル")
    args = parser.parse_args(argv)

    try:
        mode = parse_mode(args.mode)
    except ValueError as e:
        sys.exit(str(e))

    backend = OllamaBackend(args.model, config.ollama_url)
    try:
        backend.check()
    except LLMError as e:
        sys.exit(str(e))

    repo = Repository(connect(args.db))
    learner = repo.get_or_create_learner(args.learner)

    session_id = None
    if args.resume:
        session_id = repo.latest_session_id(learner.id) if args.resume == "last" else _to_int(args.resume)
        if session_id is None:
            sys.exit("再開できるセッションがありません。")
    try:
        session = TutorSession(backend, repo, learner, mode=mode, session_id=session_id)
    except ValueError as e:
        sys.exit(str(e))

    cli = Cli(session)
    cli.say(f"AI家庭教師 [{args.model}] 学習者: {learner.name} / /help でコマンド一覧、/exit で終了")
    if session_id is not None:
        cli.say(f"(セッション {session_id} を再開しました。発言 {len(session.history)} 件)")
        cli._show_recent()
    while True:
        try:
            line = input(cli.prompt_label())
        except (EOFError, KeyboardInterrupt):
            cli.say()
            break
        if not cli.handle(line):
            break


def _to_int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        sys.exit("--resume にはセッション番号か last を指定してください。")
