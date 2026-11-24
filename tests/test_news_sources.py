"""The extra headline feeds of trader-news: Google News and the market-wide feeds.

Fixtures are real feeds cut to four items, fetched on Tuesday November 24 2026.
"""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _load import FIX, load

news = load("trader-news", "news")
DIR = os.path.join(FIX, "trader-news-sources")
NOW = "2026-11-24T15:00:00+00:00"


def raw(name):
    with open(os.path.join(DIR, name), "rb") as fh:
        return fh.read()


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = news.main(args)
    return code, out.getvalue(), err.getvalue()


class Parsers(unittest.TestCase):
    def test_google_credits_the_outlet(self):
        items = news.parse_google(raw("google-TSLA.xml"), "TSLA")
        self.assertEqual(len(items), 4)
        first = items[0]
        self.assertEqual(first["source"], "Yahoo Finance")
        # the " - Yahoo Finance" suffix Google adds to every title is gone
        self.assertFalse(first["title"].endswith("Yahoo Finance"))
        self.assertTrue(first["title"].startswith("Tesla’s FSD v15"))
        self.assertTrue(first["id"].startswith("gnews:"))
        self.assertEqual(first["summary"], "")
        self.assertEqual(items[1]["source"], "Investor's Business Daily")

    def test_market_feed_text_is_cleaned(self):
        data = (b"<rss><channel><item><title>A &amp;quot;big&amp;quot; day</title>"
                b"<description>&lt;p&gt;Stocks   rose&lt;/p&gt;</description>"
                b"<guid>x1</guid><pubDate>Tue, 24 Nov 2026 14:00:00 +0000</pubDate>"
                b"</item></channel></rss>")
        it = news.parse_rss(data, "", source="MarketWatch", prefix="mkt-mw", kind="market")[0]
        self.assertEqual(it["title"], 'A "big" day')
        self.assertEqual(it["summary"], "Stocks rose")
        self.assertEqual(it["id"], "mkt-mw:x1")

    def test_market_feed(self):
        items = news.parse_rss(raw("market-fed.xml"), "", source="Federal Reserve",
                               prefix="mkt-fed", kind="market")
        self.assertEqual(items[3]["title"], "Minutes of the Federal Open Market Committee, "
                                            "October 27-28, 2026")
        self.assertEqual({i["kind"] for i in items}, {"market"})

    def test_google_query(self):
        url = news.google_query("TSLA", "Tesla")
        self.assertIn("q=%22Tesla%22+OR+TSLA+stock+when%3A2d", url)
        self.assertIn("q=TSLA+stock+when%3A2d", news.google_query("TSLA"))


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = os.path.join(self.tmp, "news.json")

    def base(self):
        return ["--offline", DIR, "--now", NOW, "--state", self.state, "--no-sec",
                "--no-moves", "--hours", "120"]

    def test_all_sources_merge(self):
        code, out, err = run(["--tickers", "TSLA", "--json"] + self.base())
        self.assertEqual(code, 0)
        doc = json.loads(out)
        sources = {i["source"] for i in doc["items"]}
        self.assertIn("Yahoo Finance", sources)  # via Google, credited to the outlet
        self.assertIn("Investor's Business Daily", sources)
        self.assertEqual(len(doc["items"]), 4)
        # no Yahoo file in this folder: that is a note, the other feeds still run
        self.assertTrue(any("headlines for TSLA" in n for n in doc["notes"]))

    def test_sources_filter(self):
        code, out, err = run(["--tickers", "TSLA", "--json", "--sources", "google"] + self.base())
        doc = json.loads(out)
        self.assertEqual(len(doc["items"]), 4)
        self.assertEqual(doc["notes"], [])  # Yahoo was not asked for, so no note about it

    def test_unknown_source(self):
        code, out, err = run(["--tickers", "TSLA", "--sources", "reuters"] + self.base())
        self.assertEqual(code, 2)
        self.assertIn("unknown source reuters", err)

    def test_market_only(self):
        code, out, err = run(["--market", "--sources", "google"] + self.base())
        self.assertEqual(code, 0)
        self.assertIn("MARKET", out)
        self.assertIn("Federal Reserve", out)
        self.assertIn("MarketWatch", out)
        self.assertIn("Federal Reserve announces College Fed Challenge winners", out)

    def test_seen_once(self):
        run(["--tickers", "TSLA", "--market"] + self.base())
        code, out, err = run(["--tickers", "TSLA", "--market"] + self.base())
        self.assertEqual(code, 1)
        self.assertIn("Nothing new.", out)


if __name__ == "__main__":
    unittest.main()
