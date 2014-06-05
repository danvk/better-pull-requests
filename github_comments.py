import re
import sys
import github

DIFF_HUNK_HEADER_RE = re.compile(r'^@@ -([0-9]+),[0-9]+ \+([0-9]+),[0-9]+ @@')

def _find_position_in_diff_hunk(diff_lines, position):
    idx = position
    while idx >= 0 and not DIFF_HUNK_HEADER_RE.match(diff_lines[idx]):
        idx -= 1
    return position - idx


def _get_github_diff_lines(token, owner, repo, path, sha1, sha2):
    diff = github.get_file_diff(token, owner, repo, path, sha1, sha2)
    if not diff:
        return False

    # The first four lines are headers which github ignores in indexing.
    return diff.split('\n')[4:]


def add_line_number_to_comment(token, owner, repo, base_sha, comment):
    path = comment['path']
    comment_sha = comment['original_commit_id']
    position = comment['original_position']

    diff_lines = _get_github_diff_lines(token, owner, repo, path, base_sha, comment_sha)
    if not diff_lines:
        return False
    diff_line = diff_lines[position]

    comment['diff_line'] = diff_line
    comment['position_in_diff_hunk'] = _find_position_in_diff_hunk(diff_lines, position)
    # TODO(danvk): compute line numbers here (instead of in JS)


def add_line_numbers_to_comments(token, owner, repo, base_sha, comments):
    for comment in comments:
        add_line_number_to_comment(token, owner, repo, base_sha, comment)


def lineNumberToDiffPositionAndHunk(token, owner, repo, base_sha, path, commit_id, line_number, on_left):
    diff_lines = _get_github_diff_lines(token, owner, repo, path, base_sha, commit_id)
    if not diff_lines:
        sys.stderr.write('Unable to get diff\n')
        return False

    left_line_no = -1
    right_line_no = -1
    hunk_start = -1
    for position, diff_line in enumerate(diff_lines):
        m = DIFF_HUNK_HEADER_RE.match(diff_line)
        if m:
            left_line_no = int(m.group(1)) - 1
            right_line_no = int(m.group(2)) - 1
            hunk_start = position
            continue
        assert left_line_no >= 0 and right_line_no >= 0

        if len(diff_line) > 0:
            sign = diff_line[0]
        else:
            sign = ''

        if sign == '-':
            left_line_no += 1
        elif sign == '+':
            right_line_no += 1
        else:
            left_line_no += 1
            right_line_no += 1

        # sys.stderr.write('%d/%d (want %d) %s\n' % (left_line_no, right_line_no, line_number, diff_line))
        if ((on_left and left_line_no == line_number) or
            (not on_left and right_line_no == line_number)):
            return (position, '\n'.join(diff_lines[hunk_start:1+position]))

    return False, None
