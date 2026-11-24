"""trader-notify: WhatsApp (CallMeBot) and Telegram, with the network replaced."""
import io
import json
import os
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout

from _load import load

notify = load(os.path.join(".claude", "skills", "trader-notify"), "notify")

ENV = {"CALLMEBOT_PHONE": "+33600000000", "CALLMEBOT_APIKEY": "123456",
       "TELEGRAM_BOT_TOKEN": "111:abc", "TELEGRAM_CHAT_ID": "42"}


class FakeHttp(object):
    def __init__(self, replies=None):
        self.calls = []
        self.replies = replies or {}

    def __call__(self, req, timeout=20):
        self.calls.append(req)
        host = urllib.parse.urlsplit(req.full_url).hostname
        return self.replies.get(host, (200, "Message queued." if "callmebot" in host
                                       else '{"ok":true,"result":{}}'))


def run(argv, env=ENV, http=None):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = notify.main(argv, env=env, http=http or FakeHttp())
    return code, out.getvalue(), err.getvalue()


class Chunks(unittest.TestCase):
    def test_short_text_is_one_part(self):
        self.assertEqual(notify.chunks("  hello \n", 100), ["hello"])
        self.assertEqual(notify.chunks("", 100), [])

    def test_long_text_splits_on_lines_and_numbers_parts(self):
        text = "\n".join("line %02d %s" % (i, "x" * 20) for i in range(10))
        parts = notify.chunks(text, 80)
        self.assertGreater(len(parts), 1)
        self.assertTrue(parts[0].startswith("(1/%d) " % len(parts)))
        joined = "\n".join(p.split(") ", 1)[1] for p in parts)
        self.assertEqual(joined, text)

    def test_one_huge_line_is_cut(self):
        parts = notify.chunks("y" * 250, 100)
        self.assertEqual(len(parts), 3)


class Send(unittest.TestCase):
    def setUp(self):
        self.state = os.path.join(tempfile.mkdtemp(), "notify.json")

    def test_status(self):
        code, out, _ = run(["status"], env={"CALLMEBOT_PHONE": "+33", "CALLMEBOT_APIKEY": "k"})
        self.assertEqual(code, 0)
        self.assertIn("whatsapp  ready", out)
        self.assertIn("telegram  not set up", out)
        code, out, _ = run(["status"], env={})
        self.assertEqual(code, 3)

    def test_both_channels(self):
        http = FakeHttp()
        code, out, _ = run(["send", "TSLA", "hit", "the", "target", "--title", "Day Trader"],
                           http=http)
        self.assertEqual(code, 0)
        self.assertEqual(len(http.calls), 2)
        wa = urllib.parse.parse_qs(urllib.parse.urlsplit(http.calls[0].full_url).query)
        self.assertEqual(wa["text"], ["Day Trader\nTSLA hit the target"])
        self.assertEqual(wa["phone"], ["+33600000000"])
        tg = json.loads(http.calls[1].data.decode("utf-8"))
        self.assertEqual(tg["chat_id"], "42")
        self.assertIn("/bot111:abc/sendMessage", http.calls[1].full_url)
        self.assertIn("whatsapp  sent (1 part)", out)

    def test_secrets_never_printed_on_failure(self):
        http = FakeHttp({"api.callmebot.com": (200, "APIKey is invalid"),
                         "api.telegram.org": (401, '{"ok":false}')})
        code, out, err = run(["send", "hi"], http=http)
        self.assertEqual(code, 1)
        for secret in ENV.values():
            self.assertNotIn(secret, out + err)
        self.assertIn("CallMeBot refused", out)
        self.assertIn("Telegram: the API refused", out)

    def test_only_configured_channels(self):
        env = {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"}
        http = FakeHttp()
        code, out, _ = run(["send", "hi"], env=env, http=http)
        self.assertEqual(code, 0)
        self.assertEqual(len(http.calls), 1)
        self.assertIn("whatsapp  not set up, skipped", out)

    def test_nothing_set_up(self):
        code, out, err = run(["send", "hi"], env={})
        self.assertEqual(code, 3)
        self.assertIn("no channel set up", err)

    def test_key_sends_once(self):
        http = FakeHttp()
        args = ["send", "stop hit", "--key", "stop-TSLA", "--state", self.state]
        self.assertEqual(run(args, http=http)[0], 0)
        code, out, _ = run(args, http=http)
        self.assertEqual(code, 0)
        self.assertIn("already sent", out)
        self.assertEqual(len(http.calls), 2)  # two channels, the first time only

    def test_dry_run_sends_nothing(self):
        http = FakeHttp()
        code, out, _ = run(["send", "hello", "--dry-run", "--channels", "whatsapp"], http=http)
        self.assertEqual(code, 0)
        self.assertEqual(http.calls, [])
        self.assertIn("[dry run] whatsapp", out)

    def test_bad_channel(self):
        code, _, err = run(["send", "hi", "--channels", "sms"])
        self.assertEqual(code, 2)
        self.assertIn("unknown channel sms", err)

    def test_file_input(self):
        path = os.path.join(tempfile.mkdtemp(), "brief.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("NVDA oversold bounce\n")
        http = FakeHttp()
        run(["send", "--file", path, "--channels", "telegram"], http=http)
        self.assertEqual(json.loads(http.calls[0].data.decode())["text"], "NVDA oversold bounce")


if __name__ == "__main__":
    unittest.main()
