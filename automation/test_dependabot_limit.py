import unittest

from dependabot_limit import CONFIG, branch_prefix, count_open, issue_body, near_limit, read_entries

SAMPLE = """\
version: 2

updates:
  - package-ecosystem: uv
    directory: /
    open-pull-requests-limit: 10
  - package-ecosystem: uv
    directory: /api
    open-pull-requests-limit: 3
  - package-ecosystem: npm
    directory: /web
  - package-ecosystem: github-actions
    directory: /
    open-pull-requests-limit: 10
"""


class LimitTest(unittest.TestCase):
    def setUp(self):
        self.entries = read_entries(SAMPLE)

    def test_entries_are_read_with_limits(self):
        self.assertEqual([entry["limit"] for entry in self.entries], [10, 3, 5, 10])
        self.assertEqual(self.entries[1]["directory"], "/api")

    def test_real_config_has_a_limit_for_every_entry(self):
        entries = read_entries(CONFIG.read_text())
        self.assertGreaterEqual(len(entries), 6)
        self.assertTrue(all(entry["limit"] >= 1 for entry in entries))

    def test_branch_prefixes(self):
        prefixes = [branch_prefix(entry) for entry in self.entries]
        self.assertEqual(
            prefixes, ["dependabot/uv/", "dependabot/uv/api/", "dependabot/npm_and_yarn/web/", "dependabot/github_actions/"]
        )

    def test_pull_requests_are_counted_for_the_longest_matching_entry(self):
        branches = [
            "dependabot/uv/humanize-4.16.0",
            "dependabot/uv/api/pydantic-2.14.3",
            "dependabot/uv/api/pytest-9.2.0",
            "dependabot/npm_and_yarn/web/vitest-084c0aad97",
            "dependabot/github_actions/actions-cbea2a135e",
            "dependabot/docker/unknown/x-1.0.0",
            "feature/not-dependabot",
        ]
        self.assertEqual(count_open(self.entries, branches), [1, 2, 1, 1])

    def test_entries_within_the_margin_are_reported(self):
        near = near_limit(self.entries, [7, 1, 3, 8])
        self.assertEqual([(entry["ecosystem"], entry["directory"], count) for entry, count in near],
                         [("uv", "/api", 1), ("npm", "/web", 3), ("github-actions", "/", 8)])  # fmt: skip
        self.assertEqual(near_limit(self.entries, [7, 0, 2, 7]), [])

    def test_issue_body_lists_the_entries(self):
        body = issue_body(near_limit(self.entries, [0, 3, 0, 0]))
        self.assertIn("| uv | `/api` | 3 | 3 |", body)


if __name__ == "__main__":
    unittest.main()
