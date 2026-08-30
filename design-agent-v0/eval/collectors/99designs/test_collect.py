import json
import unittest

import collect


class CollectTests(unittest.TestCase):
    def test_robots_wildcard_query_rule(self):
        policy = collect.RobotsPolicy.parse(
            """
            User-agent: *
            Disallow: /contests?*entry-level=
            Disallow: /*/contests/*/brief
            Allow: /*/contests/*$
            """
        )
        self.assertFalse(
            policy.can_fetch(
                "CurifyDesignResearch/0.1",
                "https://99designs.hk/contests?industry=art&entry-level=0",
            )
        )
        self.assertTrue(
            policy.can_fetch(
                "CurifyDesignResearch/0.1",
                "https://99designs.hk/logo-design/contests/example-123",
            )
        )
        self.assertFalse(
            policy.can_fetch(
                "CurifyDesignResearch/0.1",
                "https://99designs.hk/logo-design/contests/example-123/brief",
            )
        )

    def test_page_url_preserves_filters(self):
        url = collect.page_url(collect.DEFAULT_LIST_URL, 3)
        self.assertIn("industry=art", url)
        self.assertIn("status=won", url)
        self.assertIn("page=3", url)

    def test_extract_contest_links(self):
        document = """
        <a href="/logo-design/contests/a-winner-123">one</a>
        <a href="/logo-design/contests/a-winner-123?x=1">duplicate</a>
        <a href="/contests?page=2">next</a>
        <a href="https://example.com/logo-design/contests/no-456">external</a>
        """
        self.assertEqual(
            collect.contest_urls_from_html(document, "https://99designs.hk/contests"),
            ["https://99designs.hk/logo-design/contests/a-winner-123"],
        )

    def test_extract_brief_and_winner_from_next_data(self):
        payload = {
            "props": {
                "pageProps": {
                    "contestOverviewResult": {
                        "resp": {
                            "id": "123",
                            "title": "Art poster",
                            "designerCount": 8,
                            "entryCount": 42,
                            "winningEntryCount": 1,
                            "deliverableFileTypes": ["PNG", "JPG"],
                            "industry": {"key": "art", "title": "Art & Design"},
                            "category": {"key": "poster-design", "title": "Poster"},
                            "isUnlisted": False,
                            "isRobotsNoIndex": False,
                            "isCompleted": True,
                            "brief": {
                                "elements": [
                                    {
                                        "__typename": "ContestOverviewChoiceElement",
                                        "key": "industry",
                                        "title": "Industry",
                                        "choiceValue": "art",
                                        "choices": [
                                            {"key": "art", "value": "Art & Design"}
                                        ],
                                    },
                                    {
                                        "__typename": "ContestOverviewTextAreaElement",
                                        "key": "about",
                                        "title": "About us",
                                        "textAreaValue": "Independent art gallery",
                                    },
                                ]
                            },
                            "winningEntries": [
                                {
                                    "designer": {
                                        "id": "d1",
                                        "designerLevel": "TOP",
                                        "user": {"displayName": "Designer One"},
                                    },
                                    "designUrl": "https://images.example/winner.png",
                                }
                            ],
                        }
                    }
                }
            }
        }
        document = (
            '<html><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(payload)
            + "</script></html>"
        )
        authorization = collect.Authorization("abc", "/permission.txt")
        record = collect.extract_contest(
            document,
            "https://99designs.hk/poster-design/contests/art-poster-123",
            authorization,
        )
        self.assertEqual(record["contest_id"], "123")
        self.assertEqual(record["industry"]["key"], "art")
        self.assertIn("Independent art gallery", record["brief"]["text"])
        self.assertEqual(record["winners"][0]["designer_name"], "Designer One")
        self.assertEqual(record["rights"]["status"], "permission_required")


if __name__ == "__main__":
    unittest.main()
