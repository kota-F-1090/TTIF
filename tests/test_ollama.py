"""OllamaBackend を、手元で立てた偽の HTTP サーバーに対して試す(本物の Ollama は不要)。"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tutor.llm import LLMError, OllamaBackend


class FakeOllama(BaseHTTPRequestHandler):
    requests: list[dict] = []
    json_content = '{"ok": true}'

    def log_message(self, *args):
        pass

    def _send(self, status: int, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, json.dumps({"models": [{"name": "qwen3:4b-instruct"}]}).encode())

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.requests.append(payload)
        if payload["model"] == "broken":
            self._send(404, json.dumps({"error": "model not found"}).encode())
        elif payload["stream"]:
            lines = [{"message": {"content": "こん"}}, {"message": {"content": "にちは"}}, {"done": True}]
            self._send(200, "\n".join(json.dumps(l) for l in lines).encode())
        else:
            self._send(200, json.dumps({"message": {"content": FakeOllama.json_content}}).encode())


class OllamaBackendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeOllama.requests.clear()
        FakeOllama.json_content = '{"ok": true}'
        self.backend = OllamaBackend("qwen3:4b-instruct", self.url)

    def test_check(self):
        self.backend.check()
        with self.assertRaisesRegex(LLMError, "ollama pull"):
            OllamaBackend("missing:1b", self.url).check()

    def test_chat_stream(self):
        chunks = list(self.backend.chat_stream([{"role": "user", "content": "hi"}], temperature=0.2))
        self.assertEqual(chunks, ["こん", "にちは", ""])
        self.assertEqual(self.backend.chat([{"role": "user", "content": "hi"}]), "こんにちは")
        self.assertEqual(FakeOllama.requests[0]["options"], {"temperature": 0.2})
        self.assertNotIn("options", FakeOllama.requests[1])

    def test_chat_json_sends_schema(self):
        schema = {"type": "object"}
        self.assertEqual(self.backend.chat_json([], schema, temperature=0), {"ok": True})
        req = FakeOllama.requests[0]
        self.assertEqual((req["format"], req["stream"]), (schema, False))

    def test_chat_json_rejects_non_json_and_non_object(self):
        for content in ["not json", "[1, 2]"]:
            FakeOllama.json_content = content
            with self.subTest(content=content), self.assertRaises(LLMError):
                self.backend.chat_json([], {})

    def test_http_error_message_is_readable(self):
        with self.assertRaisesRegex(LLMError, "model not found"):
            list(OllamaBackend("broken", self.url).chat_stream([]))

    def test_connection_refused(self):
        backend = OllamaBackend("x", "http://127.0.0.1:9", timeout=2)
        with self.assertRaisesRegex(LLMError, "接続できません"):
            backend.check()


if __name__ == "__main__":
    unittest.main()
