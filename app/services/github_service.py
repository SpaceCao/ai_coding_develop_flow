"""GitHub 服务 - PR/分支/文件操作"""

from __future__ import annotations

import logging
import re

from github import Auth, Github
from github.Repository import Repository

from config.settings import settings

logger = logging.getLogger(__name__)


def _get_repo() -> Repository:
    auth = Auth.Token(settings.github_token)
    g = Github(auth=auth)
    return g.get_repo(settings.github_repo)


def create_branch(branch_name: str, base: str = "main") -> str:
    """从 base 创建新分支，返回分支名"""
    repo = _get_repo()
    base_ref = repo.get_branch(base)
    repo.create_git_ref(f"refs/heads/{branch_name}", base_ref.commit.sha)
    logger.info("Created branch %s from %s", branch_name, base)
    return branch_name


def commit_files(branch: str, files: dict[str, str], message: str) -> str:
    """批量提交文件到指定分支，返回 commit sha

    Args:
        branch: 目标分支
        files: {文件路径: 文件内容}
        message: commit message
    """
    repo = _get_repo()
    for path, content in files.items():
        try:
            existing = repo.get_contents(path, ref=branch)
            repo.update_file(path, message, content, existing.sha, branch=branch)
        except Exception:
            repo.create_file(path, message, content, branch=branch)
    ref = repo.get_git_ref(f"heads/{branch}")
    logger.info("Committed %d files to %s", len(files), branch)
    return ref.object.sha


def create_pull_request(
    branch: str,
    title: str,
    body: str,
    base: str = "main",
) -> tuple[int, str]:
    """创建 PR，返回 (pr_number, pr_url)"""
    repo = _get_repo()
    pr = repo.create_pull(title=title, body=body, head=branch, base=base)
    logger.info("Created PR #%d: %s", pr.number, pr.html_url)
    return pr.number, pr.html_url


def add_pr_comment(pr_number: int, body: str) -> None:
    """给 PR 添加评论"""
    repo = _get_repo()
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(body)
    logger.info("Added comment to PR #%d", pr_number)


def merge_pull_request(pr_number: int, merge_method: str = "squash") -> bool:
    """合并 PR"""
    repo = _get_repo()
    pr = repo.get_pull(pr_number)
    result = pr.merge(merge_method=merge_method)
    logger.info("Merged PR #%d: %s", pr_number, result.merged)
    return result.merged


def get_pr_diff(pr_number: int) -> str:
    """获取 PR 的 diff 内容"""
    repo = _get_repo()
    pr = repo.get_pull(pr_number)
    files = pr.get_files()
    diff_parts = []
    for f in files:
        diff_parts.append(f"--- {f.filename}\n{f.patch or ''}")
    return "\n\n".join(diff_parts)


def parse_code_blocks(ai_output: str) -> dict[str, str]:
    """从 AI 输出中解析 ```filepath:path 格式的代码块"""
    pattern = r"```filepath:(.+?)\n(.*?)```"
    matches = re.findall(pattern, ai_output, re.DOTALL)
    return {path.strip(): content.strip() for path, content in matches}
