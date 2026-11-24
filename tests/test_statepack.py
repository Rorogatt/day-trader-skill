"""statepack: the trader/ memory as one JSON text, for the scheduled cloud runs."""
import json
import os
import tempfile
import unittest

from _load import load

sp = load(os.path.join(".claude", "skills", "trader-notify"), "statepack")


def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


class StatePack(unittest.TestCase):
    def test_round_trip(self):
        src = os.path.join(tempfile.mkdtemp(), "trader")
        write(os.path.join(src, "config.json"), {"paper": True})
        write(os.path.join(src, "state", "news.json"), {"seen": {"a": "2026-11-24"}})
        with open(os.path.join(src, "universe.txt"), "w") as fh:
            fh.write("TSLA|Tesla\n")
        doc = sp.pack(src)
        self.assertEqual(sorted(doc["files"]), ["config.json", "state/news.json"])
        dst = os.path.join(tempfile.mkdtemp(), "trader")
        self.assertEqual(sp.unpack(doc, dst), ["config.json", "state/news.json"])
        with open(os.path.join(dst, "state", "news.json")) as fh:
            self.assertEqual(json.load(fh)["seen"], {"a": "2026-11-24"})
        # the same pack again is not newer: nothing is rewritten
        self.assertEqual(sp.unpack(doc, dst), [])
        self.assertEqual(len(sp.unpack(doc, dst, force=True)), 2)

    def test_never_writes_outside_trader(self):
        dst = os.path.join(tempfile.mkdtemp(), "trader")
        doc = {"format": "day-trader-state/1", "packed_at": "2026-11-24T00:00:00+00:00",
               "files": {"../evil.json": {}, "/etc/x.json": {}, "state/ok.json": {}}}
        self.assertEqual(sp.unpack(doc, dst), ["state/ok.json"])
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(dst), "evil.json")))

    def test_rejects_other_json(self):
        with self.assertRaises(ValueError):
            sp.unpack({"hello": 1}, tempfile.mkdtemp())


if __name__ == "__main__":
    unittest.main()
