import re
import sys
import github
import itertools
from collections import defaultdict

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
    open('/tmp/diff.txt', 'wb').write(diff)

    # The first several lines are headers which github ignores in indexing.
    diff_lines = diff.split('\n')
    while diff_lines and not DIFF_HUNK_HEADER_RE.match(diff_lines[0]):
        del diff_lines[0]
    return diff_lines


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

    left_line_no = None
    right_line_no = None
    hunk_start = None
    for position, diff_line in enumerate(diff_lines):
        m = DIFF_HUNK_HEADER_RE.match(diff_line)
        if m:
            left_line_no = int(m.group(1)) - 1
            right_line_no = int(m.group(2)) - 1
            hunk_start = position
            continue
        assert left_line_no != None and right_line_no != None, ('%s, %s' % (position, diff_lines))

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


def _threadify(comments):
    """Adds 'reply_to' and 'is_addressed' fields where applicable."""
    # Assume each comment is a reply to the last comment by a different
    # user which hasn't already been replied to.
    has_reply = defaultdict(bool)
    for i, comment in enumerate(comments):
        # TODO(danvk): if comment.is_reply_to is set, use that.
        for j in xrange(i - 1, -1, -1):
            other_comment = comments[j]
            if has_reply[other_comment['id']]: continue
            if comment['by_owner'] != other_comment['by_owner']:
                comment['in_reply_to'] = other_comment['id']
                has_reply[other_comment['id']] = True
                if not other_comment['by_owner']:
                    other_comment['is_addressed'] = True


def add_in_response_to(pr, comments):
    """Adds 'reply_to' and 'is_addressed' fields where applicable."""
    # When the pull request owner replies to a comment, it's been addressed.
    pr_owner = pr['user']['login']
    def thread_key(c):
        return (c['path'], c['original_commit_id'], c['original_position'])
    def sort_key(c):
        t = None
        if 'created_at' in c: t = c['created_at']
        if 'updated_at' in c: t = c['updated_at']
        return (thread_key(c), t)  # earliest to latest

    comments.sort(key=sort_key)
    for comment in comments:
        if comment['user']['login'] == pr_owner:
            comment['by_owner'] = True
        else:
            comment['by_owner'] = False
            comment['is_addressed'] = False

    for _, grouped_comments in itertools.groupby(comments, thread_key):
        _threadify(list(grouped_comments))
