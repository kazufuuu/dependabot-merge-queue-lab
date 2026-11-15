import unittest

from security_release import (
    fixed_commits,
    node_security_release,
    pull_request_body,
    python_candidates,
    python_security_release,
    validate_target,
)
from version_sync import SyncError

CURRENT = {"python": "3.13.16", "node": "24.20.0", "uv": "0.13.5", "terraform": "1.16.5"}


def advisory(name: str, *commits: str, repo: str = "https://github.com/python/cpython") -> dict:
    events = [{"introduced": "0"}, *({"fixed": commit} for commit in commits)]
    return {"id": name, "affected": [{"ranges": [{"type": "GIT", "repo": repo, "events": events}]}]}


INDEX = [
    {"version": "v25.1.0", "security": True},
    {"version": "v24.22.3", "security": True},
    {"version": "v24.22.2", "security": False},
    {"version": "v24.22.1", "security": True},
    {"version": "v24.21.0", "security": False},
    {"version": "v24.20.0", "security": True},
    {"version": "v22.30.0", "security": True},
]


class NodeTest(unittest.TestCase):
    def test_newest_security_release_in_the_same_major_is_chosen(self):
        self.assertEqual(node_security_release((24, 20, 0), INDEX), (24, 22, 3))

    def test_release_after_the_last_security_release_is_not_chosen(self):
        index = [{"version": "v24.23.0", "security": False}, *INDEX]
        self.assertEqual(node_security_release((24, 20, 0), index), (24, 22, 3))

    def test_no_security_release_means_nothing_to_do(self):
        self.assertIsNone(node_security_release((24, 22, 3), INDEX))
        self.assertIsNone(node_security_release((24, 20, 0), [{"version": "v24.21.0", "security": False}]))

    def test_other_majors_are_ignored(self):
        self.assertIsNone(node_security_release((23, 0, 0), INDEX))

    def test_malformed_entries_are_ignored(self):
        index = [{"version": "v24.99.0-rc.1", "security": True}, {"security": True}, {"version": "v24.21.5", "security": "yes"}]
        self.assertIsNone(node_security_release((24, 20, 0), index))


class PythonTest(unittest.TestCase):
    def test_candidates_are_newer_versions_of_the_same_minor(self):
        tags = ["v3.13.15", "v3.13.16", "v3.13.18", "v3.13.17", "v3.14.0", "v3.13.19rc1", "3.13.20"]
        self.assertEqual(python_candidates((3, 13, 16), tags), [(3, 13, 17), (3, 13, 18)])

    def test_fixed_commits_of_other_repositories_are_ignored(self):
        self.assertEqual(fixed_commits(advisory("A", "aaa", "bbb")), {"aaa", "bbb"})
        self.assertEqual(fixed_commits(advisory("A", "aaa", repo="https://github.com/example/fork")), set())

    def test_release_that_contains_a_fix_is_chosen(self):
        candidates = [(3, 13, 17), (3, 13, 18)]
        commits = {(3, 13, 17): {"x1"}, (3, 13, 18): {"fix1", "x2"}}
        found = python_security_release(candidates, [advisory("PSF-1", "fix1", "other")], commits)
        self.assertEqual(found, ((3, 13, 18), ["PSF-1"]))

    def test_release_without_a_fix_is_not_chosen(self):
        commits = {(3, 13, 17): {"x1"}}
        self.assertIsNone(python_security_release([(3, 13, 17)], [advisory("PSF-1", "fix1")], commits))

    def test_release_after_the_last_fix_is_not_chosen(self):
        candidates = [(3, 13, 17), (3, 13, 18)]
        commits = {(3, 13, 17): {"fix1"}, (3, 13, 18): {"x2"}}
        found = python_security_release(candidates, [advisory("PSF-1", "fix1")], commits)
        self.assertEqual(found, ((3, 13, 17), ["PSF-1"]))


class TargetTest(unittest.TestCase):
    def test_newer_version_in_the_same_line_is_accepted(self):
        target = {"name": "python", "version": "3.13.18", "reasons": ["PSF-2026-42"]}
        self.assertEqual(validate_target(target, CURRENT), ("python", (3, 13, 18), ["PSF-2026-42"]))
        self.assertEqual(validate_target({"name": "node", "version": "24.22.3"}, CURRENT)[1], (24, 22, 3))

    def test_other_names_are_rejected(self):
        for name in ("uv", "terraform", "../x", None):
            with self.assertRaises(SyncError):
                validate_target({"name": name, "version": "9.9.9"}, CURRENT)

    def test_other_lines_and_older_versions_are_rejected(self):
        for name, version in (("python", "3.14.0"), ("python", "3.13.16"), ("python", "3.13.1"), ("node", "25.0.0")):
            with self.assertRaises(SyncError):
                validate_target({"name": name, "version": version}, CURRENT)

    def test_malformed_versions_are_rejected(self):
        for version in ("3.13.18-slim", "3.13", "3.13.18\nFROM evil", ""):
            with self.assertRaises(ValueError):
                validate_target({"name": "python", "version": version}, CURRENT)

    def test_malformed_advisory_ids_are_rejected(self):
        target = {"name": "python", "version": "3.13.18", "reasons": ["[x](https://example.com)"]}
        with self.assertRaises(SyncError):
            validate_target(target, CURRENT)

    def test_body_names_the_basis(self):
        self.assertIn("PSF-2026-42", pull_request_body("python", "3.13.16", "3.13.18", ["PSF-2026-42"]))
        self.assertIn("security", pull_request_body("node", "24.20.0", "24.22.3", []))


if __name__ == "__main__":
    unittest.main()
