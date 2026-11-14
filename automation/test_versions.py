import shutil
import tempfile
import unittest
from pathlib import Path

import versions

REPO = Path(__file__).resolve().parent.parent
FILES = (
    versions.SENTINEL,
    *versions.PYPROJECTS,
    *versions.LOCKFILES,
    versions.NODE_VERSION_FILE,
    versions.TERRAFORM_FILE,
    "api/Dockerfile",
)


class VersionsTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        for path in FILES:
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO / path, self.root / path)

    def edit(self, path: str, old: str, new: str) -> None:
        file = self.root / path
        text = file.read_text()
        self.assertIn(old, text)
        file.write_text(text.replace(old, new))

    def bump_sentinel(self, name: str, new: str) -> str:
        old = versions.read_sentinel(self.root)[name]
        self.edit(versions.SENTINEL, f":{old}", f":{new}")
        return old

    def test_repository_is_consistent(self):
        self.assertEqual(versions.check(REPO), [])

    def test_sources_and_sentinel_agree(self):
        actual = versions.read_sources(self.root)
        self.assertEqual({name: actual[name] for name in versions.IMAGES}, versions.read_sentinel(self.root))

    def test_uv_is_read_from_the_dev_dependency(self):
        self.edit("pyproject.toml", f'"uv=={versions.read_sources(self.root)["uv"]}"', '"uv==0.99.1"')
        self.assertEqual(versions.read_sources(self.root)["uv"], "0.99.1")
        # uv は Dependabot が直接上げるので、見張り役とは比べない。
        self.assertTrue(all("uv:" not in error for error in versions.check(self.root)))

    def test_check_reports_sentinel_ahead_of_sources(self):
        self.bump_sentinel("python", "3.13.99")
        errors = versions.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("python", errors[0])

    def test_sync_copies_every_version(self):
        uv = versions.read_sources(self.root)["uv"]
        for name, new in {"python": "3.13.99", "node": "24.99.1", "terraform": "1.99.1"}.items():
            self.bump_sentinel(name, new)
        changed = versions.sync(self.root)
        self.assertEqual(
            sorted(changed), sorted([*versions.PYPROJECTS, versions.NODE_VERSION_FILE, versions.TERRAFORM_FILE])
        )
        self.assertEqual(
            versions.read_sources(self.root),
            {"python": "3.13.99", "uv": uv, "node": "24.99.1", "terraform": "1.99.1"},
        )

    def test_sync_changes_nothing_else(self):
        before = {path: (self.root / path).read_text() for path in versions.PYPROJECTS}
        old = self.bump_sentinel("python", "3.13.99")
        versions.sync(self.root)
        for path, text in before.items():
            expected = text.replace(f'requires-python = "=={old}"', 'requires-python = "==3.13.99"')
            self.assertEqual((self.root / path).read_text(), expected)

    def test_sync_without_change_writes_nothing(self):
        self.assertEqual(versions.sync(self.root), [])

    def test_after_sync_only_the_lockfiles_are_stale(self):
        self.bump_sentinel("python", "3.13.99")
        versions.sync(self.root)
        errors = versions.check(self.root)
        self.assertEqual(len(errors), len(versions.LOCKFILES))
        self.assertTrue(all("uv lock" in error for error in errors))

    def test_missing_source_fails(self):
        self.edit("pyproject.toml", 'requires-python = "==', 'requires-python = ">=')
        with self.assertRaises(versions.VersionError):
            versions.read_sources(self.root)
        with self.assertRaises(versions.VersionError):
            versions.sync(self.root)

    def test_disagreeing_sources_fail(self):
        python = versions.read_sources(self.root)["python"]
        self.edit("api/pyproject.toml", f'requires-python = "=={python}"', 'requires-python = "==3.13.1"')
        with self.assertRaises(versions.VersionError):
            versions.read_sources(self.root)

    def test_missing_sentinel_stage_fails(self):
        self.edit(versions.SENTINEL, " AS node", " AS tool")
        with self.assertRaises(versions.VersionError):
            versions.read_sentinel(self.root)

    def test_duplicated_sentinel_stage_fails(self):
        file = self.root / versions.SENTINEL
        file.write_text(file.read_text() + "FROM node:24.1.0-slim AS node\n")
        with self.assertRaises(versions.VersionError):
            versions.read_sentinel(self.root)

    def test_image_outside_docker_hub_is_reported(self):
        self.edit(versions.SENTINEL, "FROM hashicorp/terraform:", "FROM ghcr.io/hashicorp/terraform:")
        text = (self.root / versions.SENTINEL).read_text()
        self.assertEqual(len(versions.images_outside_docker_hub(text)), 1)

    def test_build_argument_images_are_docker_hub(self):
        self.assertEqual(versions.images_outside_docker_hub((REPO / "api/Dockerfile").read_text()), [])


if __name__ == "__main__":
    unittest.main()
