import shutil
import tempfile
import unittest
from pathlib import Path

import versions

REPO = Path(__file__).resolve().parent.parent
FILES = (versions.SENTINEL, *set(versions.SOURCES.values()), "api/Dockerfile")


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

    def test_node_is_read_from_tool_versions(self):
        (self.root / versions.TOOL_VERSIONS).write_text("nodejs 24.99.1\n")
        self.assertEqual(versions.read_sources(self.root)["node"], "24.99.1")
        self.assertEqual(len(versions.check(self.root)), 1)

    def test_uv_is_read_from_the_lockfile_and_has_no_sentinel(self):
        (self.root / versions.UV_LOCK).write_text(
            '[[package]]\nname = "uvicorn"\nversion = "1.2.3"\n\n[[package]]\nname = "uv"\nversion = "0.99.1"\n'
            '\n[[package]]\nname = "rust-just"\nversion = "1.99.2"\n'
        )
        self.assertEqual(versions.locked(self.root, "uv"), "0.99.1")
        self.assertEqual(versions.locked(self.root, "just"), "1.99.2")
        self.assertNotIn("uv", versions.read_sources(self.root))
        self.assertNotIn("uv", versions.IMAGES)

    def test_lockfile_without_uv_is_an_error(self):
        (self.root / versions.UV_LOCK).write_text('[[package]]\nname = "uvicorn"\nversion = "1.2.3"\n')
        with self.assertRaises(versions.VersionError):
            versions.locked(self.root, "uv")

    def test_check_reports_sentinel_ahead_of_sources(self):
        self.bump_sentinel("python", "3.13.99")
        errors = versions.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("python", errors[0])

    def test_sync_copies_every_version(self):
        for name, new in {"python": "3.13.99", "node": "24.99.1", "terraform": "1.99.1"}.items():
            self.bump_sentinel(name, new)
        changed = versions.sync(self.root)
        self.assertEqual(
            sorted(changed),
            sorted([versions.PYTHON_VERSION_FILE, versions.TOOL_VERSIONS, versions.TERRAFORM_FILE]),
        )
        self.assertEqual(
            versions.read_sources(self.root),
            {"python": "3.13.99", "node": "24.99.1", "terraform": "1.99.1"},
        )
        self.assertEqual(versions.check(self.root), [])

    def test_sync_changes_nothing_else(self):
        before = (self.root / versions.TERRAFORM_FILE).read_text()
        old = self.bump_sentinel("terraform", "1.99.1")
        self.assertEqual(versions.sync(self.root), [versions.TERRAFORM_FILE])
        expected = before.replace(f'required_version = "= {old}"', 'required_version = "= 1.99.1"')
        self.assertEqual((self.root / versions.TERRAFORM_FILE).read_text(), expected)

    def test_align_copies_sources_to_sentinel(self):
        (self.root / versions.PYTHON_VERSION_FILE).write_text("3.13.99\n")
        self.edit(versions.TOOL_VERSIONS, f"nodejs {versions.read_sources(self.root)['node']}", "nodejs 24.99.1")
        self.assertEqual(len(versions.check(self.root)), 2)
        self.assertEqual(versions.align(self.root), ["python", "node"])
        self.assertEqual(versions.check(self.root), [])
        sentinel = versions.read_sentinel(self.root)
        self.assertEqual((sentinel["python"], sentinel["node"]), ("3.13.99", "24.99.1"))
        self.assertIn("FROM python:3.13.99-slim AS python", (self.root / versions.SENTINEL).read_text())

    def test_align_without_change_writes_nothing(self):
        self.assertEqual(versions.align(self.root), [])

    def test_sync_without_change_writes_nothing(self):
        self.assertEqual(versions.sync(self.root), [])

    def test_missing_source_fails(self):
        self.edit(versions.TERRAFORM_FILE, 'required_version = "= ', 'required_version = ">= ')
        with self.assertRaises(versions.VersionError):
            versions.read_sources(self.root)
        self.bump_sentinel("terraform", "1.99.1")
        with self.assertRaises(versions.VersionError):
            versions.sync(self.root)

    def test_version_without_patch_fails(self):
        (self.root / versions.PYTHON_VERSION_FILE).write_text("3.13\n")
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
        self.assertEqual(len(versions.check(self.root)), 1)

    def test_build_argument_images_are_docker_hub(self):
        self.assertEqual(versions.images_outside_docker_hub((REPO / "api/Dockerfile").read_text()), [])


if __name__ == "__main__":
    unittest.main()
