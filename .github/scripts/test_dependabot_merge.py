import unittest

from dependabot_merge import (
    LABEL_AUTO,
    LABEL_HUMAN,
    Policy,
    classify,
    normalize,
    parse_updated_dependencies,
    plan_for,
)

POLICY = Policy(
    review_team="reviewers",
    review_count=1,
    required_check="all-green",
    ci_workflow="ci.yml",
    lockfiles=("uv.lock", "package-lock.json", ".terraform.lock.hcl"),
)
DEV_MINOR = Policy(**{**POLICY.__dict__, "dev_minor": True})


def message(*deps: dict) -> str:
    lines = ["deps: bump the patch group", "", "Bumps the patch group.", "", "---", "updated-dependencies:"]
    for dep in deps:
        first = True
        for key, value in dep.items():
            lines.append(("- " if first else "  ") + f"{key}: {value}")
            first = False
    return "\n".join([*lines, "...", "", "Signed-off-by: dependabot[bot] <support@github.com>"])


def dep(name="zod", update="patch", group="patch", kind="direct:production") -> dict:
    data = {
        "dependency-name": name,
        "dependency-version": "1.2.3",
        "dependency-type": kind,
        "update-type": f"version-update:semver-{update}",
    }
    if group:
        data["dependency-group"] = group
    return data


def pr(**overrides) -> dict:
    base = {
        "number": 1,
        "head": "aaa",
        "head_pushers": ["dependabot[bot]"],
        "labels": [],
        "commits": [
            {"message": message(dep()), "author": "dependabot[bot]", "signed_by_github": True, "pushers": ["dependabot[bot]"]}
        ],
        "files": ["web/package-lock.json"],
        "files_truncated": False,
        "approved_commits": [],
        "check": "success",
        "in_merge_queue": False,
        "auto_merge_enabled": False,
    }
    return {**base, **overrides}


def with_deps(*deps: dict, **overrides) -> dict:
    commit = {"message": message(*deps), "author": "dependabot[bot]", "signed_by_github": True}
    return pr(commits=[commit], **overrides)


class ParseTest(unittest.TestCase):
    def test_reads_every_dependency(self):
        deps = parse_updated_dependencies(message(dep("a"), dep("b", "minor", "minor")))
        self.assertEqual([d["dependency-name"] for d in deps], ["a", "b"])
        self.assertEqual(deps[1]["update-type"], "version-update:semver-minor")
        self.assertEqual(deps[1]["dependency-group"], "minor")

    def test_message_without_metadata(self):
        self.assertEqual(parse_updated_dependencies("fix: something"), [])


class ClassifyTest(unittest.TestCase):
    def test_patch_group_with_lockfile_only_is_auto(self):
        self.assertTrue(classify(pr(), POLICY).auto)

    def test_nested_lockfiles_are_lockfiles(self):
        files = ["uv.lock", "api/uv.lock", "infra/.terraform.lock.hcl"]
        self.assertTrue(classify(pr(files=files), POLICY).auto)

    def test_manifest_change_is_human(self):
        decision = classify(pr(files=["web/package-lock.json", "web/package.json"]), POLICY)
        self.assertFalse(decision.auto)
        self.assertIn("web/package.json", decision.reasons[0])

    def test_minor_is_human(self):
        self.assertFalse(classify(with_deps(dep(update="minor", group="minor")), POLICY).auto)

    def test_minor_inside_patch_group_is_human(self):
        self.assertFalse(classify(with_deps(dep(), dep("b", update="minor")), POLICY).auto)

    def test_ungrouped_patch_with_update_type_is_auto(self):
        self.assertTrue(classify(with_deps(dep(group=None)), POLICY).auto)

    def test_ungrouped_major_is_human(self):
        self.assertFalse(classify(with_deps(dep(update="major", group=None)), POLICY).auto)

    def test_group_name_does_not_decide(self):
        # グループは PR のまとめ方。範囲は、種別と依存の種類で決める。
        self.assertTrue(classify(with_deps(dep(group="everything")), POLICY).auto)
        self.assertFalse(classify(with_deps(dep(update="minor", group="patch")), POLICY).auto)

    def test_dev_minor_is_human_by_default(self):
        target = with_deps(dep(update="minor", group=None, kind="direct:development"))
        self.assertFalse(classify(target, POLICY).auto)

    def test_dev_minor_is_auto_when_enabled(self):
        target = with_deps(dep(update="minor", group=None, kind="direct:development"))
        self.assertTrue(classify(target, DEV_MINOR).auto)

    def test_production_minor_is_human_even_when_dev_minor_enabled(self):
        target = with_deps(dep(update="minor", group=None, kind="direct:production"))
        self.assertFalse(classify(target, DEV_MINOR).auto)

    def test_indirect_minor_is_human_even_when_dev_minor_enabled(self):
        target = with_deps(dep(update="minor", group=None, kind="indirect"))
        self.assertFalse(classify(target, DEV_MINOR).auto)

    def test_major_is_human_even_when_dev_minor_enabled(self):
        target = with_deps(dep(update="major", group=None, kind="direct:development"))
        self.assertFalse(classify(target, DEV_MINOR).auto)

    def test_dev_minor_with_manifest_change_is_human(self):
        target = with_deps(dep(update="minor", group=None, kind="direct:development"))
        target["files"] = ["web/package.json", "web/package-lock.json"]
        self.assertFalse(classify(target, DEV_MINOR).auto)

    def test_dev_minor_metadata_in_an_unsigned_commit_is_human(self):
        target = with_deps(dep(update="minor", group=None, kind="direct:development"))
        target["commits"][0].update(author="mallory", signed_by_github=False)
        self.assertFalse(classify(target, DEV_MINOR).auto)

    def test_dev_minor_metadata_pushed_by_a_person_is_human(self):
        target = with_deps(dep(update="minor", group=None, kind="direct:development"))
        target["head_pushers"] = ["mallory"]
        self.assertFalse(classify(target, DEV_MINOR).auto)

    def test_dev_minor_with_a_second_commit_is_human(self):
        target = with_deps(dep(update="minor", group=None, kind="direct:development"))
        target["commits"].append({"message": "", "author": "mallory", "signed_by_github": False, "pushers": ["mallory"]})
        self.assertFalse(classify(target, DEV_MINOR).auto)

    def test_commit_by_someone_else_is_human(self):
        commit = {"message": message(dep()), "author": "mallory", "signed_by_github": True}
        self.assertFalse(classify(pr(commits=[commit]), POLICY).auto)

    def test_unsigned_commit_is_human(self):
        commit = {"message": message(dep()), "author": "dependabot[bot]", "signed_by_github": False}
        self.assertFalse(classify(pr(commits=[commit]), POLICY).auto)

    def test_extra_commit_is_human(self):
        good = {"message": message(dep()), "author": "dependabot[bot]", "signed_by_github": True}
        self.assertFalse(classify(pr(commits=[good, good]), POLICY).auto)

    def test_dependabot_commit_pushed_by_human_is_human(self):
        decision = classify(pr(head_pushers=["mallory"]), POLICY)
        self.assertFalse(decision.auto)
        self.assertIn("mallory", decision.reasons[0])

    def test_reopened_by_human_is_human(self):
        self.assertFalse(classify(pr(head_pushers=["dependabot[bot]", "mallory"]), POLICY).auto)

    def test_unknown_pusher_with_finished_check_is_human(self):
        self.assertFalse(classify(pr(head_pushers=[]), POLICY).auto)

    def test_unknown_pusher_while_check_is_pending_waits(self):
        self.assertTrue(classify(pr(head_pushers=[], check="pending"), POLICY).auto)

    def test_missing_metadata_is_human(self):
        commit = {"message": "bump", "author": "dependabot[bot]", "signed_by_github": True}
        self.assertFalse(classify(pr(commits=[commit]), POLICY).auto)

    def test_too_many_files_is_human(self):
        self.assertFalse(classify(pr(files_truncated=True), POLICY).auto)


def node(author: str, signature: dict | None) -> dict:
    """GraphQL が返す PR の形。コミットの作者と署名だけを変えられる。"""
    commit = {"oid": "aaa", "message": message(dep()), "author": {"user": {"login": author}}, "signature": signature}
    return {
        "number": 1,
        "headRefOid": "aaa",
        "labels": {"nodes": []},
        "reviewRequests": {"nodes": []},
        "latestReviews": {"nodes": []},
        "commits": {"totalCount": 1, "nodes": [{"commit": commit}]},
        "statusCheckRollup": None,
        "files": {"totalCount": 1, "nodes": [{"path": "uv.lock"}]},
        "mergeQueueEntry": None,
        "autoMergeRequest": None,
    }


class SignatureTest(unittest.TestCase):
    def signed(self, author: str, signature: dict | None) -> bool:
        return normalize(node(author, signature), POLICY, {"aaa": ["dependabot[bot]"]})["commits"][0]["signed_by_github"]

    def test_commit_signed_by_github_counts(self):
        self.assertTrue(self.signed("dependabot[bot]", {"isValid": True, "wasSignedByGitHub": True}))

    def test_commit_signed_with_a_personal_key_does_not_count(self):
        # 作者を Dependabot と偽り、人が自分の鍵で署名したコミット。署名は有効でも対象にしない。
        self.assertFalse(self.signed("dependabot[bot]", {"isValid": True, "wasSignedByGitHub": False}))

    def test_unsigned_commit_does_not_count(self):
        self.assertFalse(self.signed("dependabot[bot]", None))


def runtime_pr(**overrides) -> dict:
    """Dependabot が Dependabot 用の Dockerfile の python を上げ、バージョンの同期が管理場所を積んだ PR。"""
    first = {
        "message": message(dep("python")),
        "author": "dependabot[bot]",
        "signed_by_github": True,
        "pushers": ["dependabot[bot]"],
    }
    second = {"message": "バージョンの管理場所を合わせる", "author": "sync-app[bot]", "signed_by_github": True, "pushers": ["sync-app[bot]"]}
    base = {
        "commits": [first, second],
        "head_pushers": ["sync-app[bot]"],
        "files": [".github/dependabot/Dockerfile", ".python-version"],
    }
    return pr(**{**base, **overrides})


class RuntimeTest(unittest.TestCase):
    """Python と Node のランタイムの更新は、patch でも人が判断する。"""

    def test_patch_with_sync_commit_is_human(self):
        self.assertFalse(classify(runtime_pr(), POLICY).auto)

    def test_patch_before_sync_is_human(self):
        target = runtime_pr()
        target["commits"] = target["commits"][:1]
        target["files"] = [".github/dependabot/Dockerfile"]
        target["head_pushers"] = ["dependabot[bot]"]
        self.assertFalse(classify(target, POLICY).auto)


def security_message(*changes: tuple[str, str, str], kind="direct:production") -> str:
    """セキュリティアップデートのコミットメッセージ。グループも種別も書かれない。"""
    if len(changes) == 1:
        name, old, new = changes[0]
        prose = [f"Bumps [{name}](https://github.com/example/{name}) from {old} to {new}."]
    else:
        prose = ["Bumps several dependencies. These dependencies need to be updated together.", ""]
        for name, old, new in changes:
            prose += [f"Updates `{name}` from {old} to {new}", "- [Release notes](https://example.com)", ""]
    lines = ["Bump something", "", *prose, "", "---", "updated-dependencies:"]
    for name, _, new in changes:
        lines += [f'- dependency-name: "{name}"', f"  dependency-version: {new}", f"  dependency-type: {kind}"]
    return "\n".join([*lines, "...", "", "Signed-off-by: dependabot[bot] <support@github.com>"])


def security_pr(*changes: tuple[str, str, str], **overrides) -> dict:
    target = pr(**overrides)
    target["commits"][0]["message"] = security_message(*changes)
    return target


class SecurityUpdateTest(unittest.TestCase):
    """セキュリティアップデートは、通常の更新と同じ条件で扱う。違いは cooldown だけ。"""

    def test_patch_is_auto(self):
        self.assertTrue(classify(security_pr(("jinja2", "3.1.4", "3.1.6")), POLICY).auto)

    def test_several_patches_are_auto(self):
        target = security_pr(("@vitest/mocker", "5.0.0", "5.0.3"), ("vitest", "5.0.0", "5.0.3"))
        self.assertTrue(classify(target, POLICY).auto)

    def test_minor_is_human(self):
        self.assertFalse(classify(security_pr(("vitest", "5.0.0", "5.1.0")), POLICY).auto)

    def test_major_is_human(self):
        self.assertFalse(classify(security_pr(("vitest", "5.0.9", "6.0.0")), POLICY).auto)

    def test_one_minor_among_patches_is_human(self):
        target = security_pr(("a", "1.0.0", "1.0.1"), ("b", "1.0.0", "1.1.0"))
        self.assertFalse(classify(target, POLICY).auto)

    def test_downgrade_is_human(self):
        self.assertFalse(classify(security_pr(("jinja2", "3.1.6", "3.1.4")), POLICY).auto)

    def test_version_that_is_not_three_numbers_is_human(self):
        self.assertFalse(classify(security_pr(("a", "1.0.0", "1.0.1rc1")), POLICY).auto)
        self.assertFalse(classify(security_pr(("a", "1.0", "1.0.1")), POLICY).auto)

    def test_prose_that_disagrees_with_metadata_is_human(self):
        target = security_pr(("jinja2", "3.1.4", "3.1.6"))
        target["commits"][0]["message"] = target["commits"][0]["message"].replace(
            "dependency-version: 3.1.6", "dependency-version: 4.0.0"
        )
        self.assertFalse(classify(target, POLICY).auto)

    def test_missing_prose_is_human(self):
        target = security_pr(("jinja2", "3.1.4", "3.1.6"))
        target["commits"][0]["message"] = target["commits"][0]["message"].replace("Bumps [jinja2]", "Raises [jinja2]")
        self.assertFalse(classify(target, POLICY).auto)

    def test_manifest_change_is_human(self):
        target = security_pr(("jinja2", "3.1.4", "3.1.6"), files=["api/pyproject.toml", "api/uv.lock"])
        self.assertFalse(classify(target, POLICY).auto)

    def test_message_copied_into_an_unsigned_commit_is_human(self):
        target = security_pr(("jinja2", "3.1.4", "3.1.6"))
        target["commits"][0].update(author="mallory", signed_by_github=False)
        self.assertFalse(classify(target, POLICY).auto)

    def test_message_copied_and_pushed_by_a_person_is_human(self):
        target = security_pr(("jinja2", "3.1.4", "3.1.6"), head_pushers=["mallory"])
        self.assertFalse(classify(target, POLICY).auto)

    def test_failed_check_goes_to_human(self):
        plan = plan_for(security_pr(("jinja2", "3.1.4", "3.1.6"), check="failure"), POLICY)
        self.assertFalse(plan.approve or plan.enqueue)


class PlanTest(unittest.TestCase):
    def test_auto_with_green_check_is_approved_labeled_and_enqueued(self):
        plan = plan_for(pr(), POLICY)
        self.assertTrue(plan.approve and plan.enqueue)
        self.assertEqual(plan.add_labels, [LABEL_AUTO])

    def test_auto_with_pending_check_waits(self):
        self.assertTrue(plan_for(pr(check="pending"), POLICY).is_noop())

    def test_auto_with_failed_check_goes_to_human(self):
        plan = plan_for(pr(check="failure"), POLICY)
        self.assertFalse(plan.approve or plan.enqueue)
        self.assertEqual(plan.add_labels, [LABEL_HUMAN])
        self.assertIn("必須のチェックが落ちました", plan.comment)

    def test_queued_pr_is_left_alone(self):
        target = pr(labels=[LABEL_AUTO], approved_commits=["aaa"], in_merge_queue=True)
        self.assertTrue(plan_for(target, POLICY).is_noop())

    def test_pr_removed_from_queue_goes_to_human(self):
        plan = plan_for(pr(labels=[LABEL_AUTO], approved_commits=["aaa"]), POLICY)
        self.assertFalse(plan.approve or plan.enqueue)
        self.assertEqual(plan.remove_labels, [LABEL_AUTO])
        self.assertEqual(plan.add_labels, [LABEL_HUMAN])

    def test_removed_pr_is_not_requeued_on_later_runs(self):
        target = pr(labels=[LABEL_HUMAN], approved_commits=["aaa"])
        self.assertTrue(plan_for(target, POLICY).is_noop())

    def test_new_head_after_rebase_starts_over(self):
        target = pr(head="bbb", labels=[LABEL_HUMAN], approved_commits=["aaa"])
        plan = plan_for(target, POLICY)
        self.assertTrue(plan.approve and plan.enqueue)
        self.assertEqual(plan.remove_labels, [LABEL_HUMAN])

    def test_human_pr_gets_label_and_comment_once(self):
        target = with_deps(dep(update="minor", group="minor"))
        plan = plan_for(target, POLICY)
        self.assertEqual(plan.add_labels, [LABEL_HUMAN])
        self.assertIsNotNone(plan.comment)
        again = with_deps(dep(update="minor", group="minor"), labels=[LABEL_HUMAN])
        self.assertTrue(plan_for(again, POLICY).is_noop())

    def test_push_by_human_cancels_reserved_merge(self):
        commit = {"message": message(dep()), "author": "mallory", "signed_by_github": False}
        target = pr(commits=[commit], labels=[LABEL_AUTO], auto_merge_enabled=True)
        plan = plan_for(target, POLICY)
        self.assertTrue(plan.disable_auto_merge)
        self.assertEqual(plan.remove_labels, [LABEL_AUTO])
        self.assertFalse(plan.approve or plan.enqueue)


if __name__ == "__main__":
    unittest.main()
