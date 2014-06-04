import git
import re

DIFF_HUNK_HEADER_RE = re.compile(r'^@@ -([0-9]+),[0-9]+ \+([0-9]+),[0-9]+ @@')

def _find_position_in_diff_hunk(diff_lines, position):
    idx = position
    while idx >= 0 and not DIFF_HUNK_HEADER_RE.match(diff_lines[idx]):
        idx -= 1
    return position - idx


def add_line_number_to_comment(pr, comment):
    base_sha = pr['base.sha']
    path = comment['path']
    comment_sha = comment['original_commit_id']
    position = comment['original_position']

    head_repo = pr['head.repo.full_name']
    clone_url = 'https://github.com/%s.git' % head_repo

    diff = git.get_file_diff(clone_url, path, base_sha, comment_sha)
    if not diff:
        return False

    # The first four lines are headers which github ignores in indexing.
    diff_lines = diff.split('\n')[4:]
    diff_line = diff_lines[position]

    comment['diff_line'] = diff_line
    comment['position_in_diff_hunk'] = _find_position_in_diff_hunk(diff_lines, position)
    # TODO(danvk): compute line numbers here (instead of in JS)



def add_line_numbers_to_comments(pr, comments):
    for comment in comments:
        add_line_number_to_comment(pr, comment)
