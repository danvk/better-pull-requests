import sys
import logging
import json
import re

import os
import hashlib
import cPickle

import requests

GITHUB_API_ROOT = 'https://api.github.com'

# TODO(danvk): inject a cache from the server module
#from werkzeug.contrib.cache import SimpleCache
#cache = SimpleCache()
class SimpleCache(object):
    def __init__(self):
        self._cache_dir = '/tmp/better-git-pr/cache'
        if not os.path.exists(self._cache_dir):
            os.mkdir(self._cache_dir)

    def _file_for_key(self, k):
        return os.path.join(self._cache_dir, hashlib.md5(k).hexdigest())

    def get(self, k):
        f = self._file_for_key(k)
        if os.path.exists(f):
            try:
                return open(f).read()
            except:
                return None

    def set(self, k, v):
        f = self._file_for_key(k)
        open(f, 'wb').write(v)


cache = SimpleCache()


def _fetch_url(token, url, extra_headers=None):
    key = url + json.dumps(extra_headers)
    cached = cache.get(key)
    if cached is not None:
        return cached
    sys.stderr.write('Uncached request for %s\n' % url)
    sys.stderr.write('Token=%s\n' % token)

    headers = {'Authorization': 'token ' + token}
    if extra_headers:
        headers.update(extra_headers)
    r = requests.get(url, headers=headers)
    if not r.ok:
        sys.stderr.write('Request for %s failed.\n' % url)
        return False

    response = r.text
    cache.set(key, response)
    return response


def _post_api(token, path, obj, **kwargs):
    url = (GITHUB_API_ROOT + path) % kwargs
    assert '%' not in url
    sys.stderr.write('Posting to %s\n' % url)
    r = requests.post(url, headers={'Authorization': 'token ' + token, 'Content-type': 'application/json'}, data=json.dumps(obj))
    if not r.ok:
        sys.stderr.write('Request for %s failed.\n' % url)
        return False

    return r.json()


def _fetch_api(token, path, **kwargs):
    url = (GITHUB_API_ROOT + path) % kwargs
    assert '%' not in url

    response = _fetch_url(token, url)
    if response is None:
        return None

    try:
        j = json.loads(response)
    except ValueError:
        sys.stderr.write('Failed to parse as JSON:\n%s\n' % response)
        raise
    return j


def get_pull_requests(token, user, repo):
    return _fetch_api(token, '/repos/%(user)s/%(repo)s/pulls', user=user, repo=repo)


def get_pull_request(token, user, repo, pull_number):
    return _fetch_api(token, '/repos/%(user)s/%(repo)s/pulls/%(pull_number)s', user=user, repo=repo, pull_number=pull_number)


def get_pull_request_commits(token, user, repo, pull_number):
    """Returns commits from first to last."""
    commits = _fetch_api(token, '/repos/%(user)s/%(repo)s/pulls/%(pull_number)s/commits', user=user, repo=repo, pull_number=pull_number)

    if not commits:
        return None

    # See https://developer.github.com/v3/pulls/#list-commits-on-a-pull-request
    commits.sort(key=lambda x: x['commit']['author']['date'])
    return commits


def get_pull_request_comments(token, user, repo, pull_number):
    # There are two types of comments:
    # 1. top level (these are issue comments)
    # 2. diff-level (these are pull requests comments)
    # TODO(danvk): are there also file-level comments?

    issue_comments = _fetch_api(token, '/repos/%(user)s/%(repo)s/issues/%(pull_number)s/comments', user=user, repo=repo, pull_number=pull_number) or []
    pr_comments = _fetch_api(token, '/repos/%(user)s/%(repo)s/pulls/%(pull_number)s/comments', user=user, repo=repo, pull_number=pull_number) or []

    return {'top_level': issue_comments, 'diff_level': pr_comments}


def get_diff_info(token, user, repo, sha1, sha2):
    # https://developer.github.com/v3/repos/commits/#compare-two-commits
    # Highlights include files.{filename,additions,deletions,changes}
    return _fetch_api(token, '/repos/%(user)s/%(repo)s/compare/%(sha1)s...%(sha2)s', user=user, repo=repo, sha1=sha1, sha2=sha2)


def get_file_diff(token, user, repo, path, sha1, sha2):
    # https://developer.github.com/v3/repos/commits/#compare-two-commits
    # Highlights include files.{filename,additions,deletions,changes}
    url = (GITHUB_API_ROOT + '/repos/%(user)s/%(repo)s/compare/%(sha1)s...%(sha2)s') % {'user': user, 'repo': repo, 'sha1': sha1, 'sha2': sha2}
    unified_diff = _fetch_url(token, url, extra_headers={'Accept': 'application/vnd.github.3.diff'})
    if not unified_diff:
        sys.stderr.write('Unable to get unified diff %s\n' % url)
        return None

    # Parse out the bit that's relevant to the file 
    diff_start_re = re.compile(r'^diff --git a/(.*?) b/(.*?)$', re.MULTILINE)
    ms = [m for m in diff_start_re.finditer(unified_diff)]
    file_idx = -1
    for idx, m in enumerate(ms):
        # is it possible that m.group(1) != m.group(2)
        if m.group(1) == path and m.group(2) == path:
            file_idx = idx
            break

    if file_idx == -1:
        sys.stderr.write('Unable to find diff for %s in %s\n' % (path, url))
        return None

    start = ms[file_idx].start()
    if file_idx < len(ms) - 1:
        limit = ms[file_idx + 1].start()
    else:
        limit = len(unified_diff)
    return unified_diff[start:limit]


def get_file_at_ref(token, user, repo, path, sha):
    url = (GITHUB_API_ROOT + '/repos/%(user)s/%(repo)s/contents/%(path)s?ref=%(sha)s') % {'user': user, 'repo': repo, 'path': path, 'sha': sha}
    return _fetch_url(token, url, extra_headers={'Accept': 'application/vnd.github.3.raw'})


def post_comment(token, user, repo, pull_number, commit_id, path, position, body):
    post_path = '/repos/%(user)s/%(repo)s/pulls/%(pull_number)s/comments'

    return _post_api(token, post_path, {
        'commit_id': commit_id,
        'path': path,
        'position': position,
        'body': body
        }, user=user, repo=repo, pull_number=pull_number)
