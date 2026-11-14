import unittest

import version_sync
import versions


def pr(**overrides) -> dict:
    base = {
        "number": 1,
        "head": "aaa",
        "head_pushers": ["dependabot[bot]"],
        "commits": [{"message": "", "author": "dependabot[bot]", "signed_by_github": True}],
        "files": [versions.SENTINEL],
        "files_truncated": False,
    }
    return {**base, **overrides}


class CandidateTest(unittest.TestCase):
    def test_sentinel_only_pr_from_dependabot_is_a_candidate(self):
        self.assertTrue(version_sync.is_candidate(pr()))

    def test_pr_touching_other_files_is_not(self):
        self.assertFalse(version_sync.is_candidate(pr(files=[versions.SENTINEL, ".python-version"])))
        self.assertFalse(version_sync.is_candidate(pr(files=["api/Dockerfile"])))

    def test_pr_already_synced_is_not(self):
        commit = {"message": "", "author": "dependabot[bot]", "signed_by_github": True}
        self.assertFalse(version_sync.is_candidate(pr(commits=[commit, commit])))

    def test_pr_pushed_by_human_is_not(self):
        self.assertFalse(version_sync.is_candidate(pr(head_pushers=["mallory"])))
        self.assertFalse(version_sync.is_candidate(pr(head_pushers=[])))

    def test_unsigned_commit_is_not(self):
        commit = {"message": "", "author": "dependabot[bot]", "signed_by_github": False}
        self.assertFalse(version_sync.is_candidate(pr(commits=[commit])))


class PayloadTest(unittest.TestCase):
    def test_payload_survives_the_round_trip(self):
        payload = {"number": 3, "head": "abc", "files": {".python-version": "3.13.99\n"}}
        self.assertEqual(version_sync.decode(version_sync.encode(payload)), payload)

    def test_allowed_files_pass(self):
        version_sync.validate_paths(sorted(version_sync.ALLOWED))

    def test_other_files_are_refused(self):
        for path in (".github/workflows/ci.yml", "pyproject.toml", "uv.lock", versions.SENTINEL, "automation/versions.py"):
            with self.assertRaises(version_sync.SyncError):
                version_sync.validate_paths([".python-version", path])


if __name__ == "__main__":
    unittest.main()
