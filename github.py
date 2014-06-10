import sys
import logging
import json
import re

import os
import hashlib
import cPickle

import requests

GITHUB_API_ROOT = 'https://api.github.com'

WHITESPACE_RE = re.compile(r'^[ \t\n\r]*$')

# TODO(danvk): inject a cache from the server module
#from werkzeug.contrib.cache import SimpleCache
#cache = SimpleCache()
class SimpleCache(object):
    def __init__(self):
        self._cache_dir = '/tmp/better-git-pr/cache'
        if not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir)

    def _file_for_key(self, k):
        return os.path.join(self._cache_dir, hashlib.md5(k).hexdigest())

    def get(self, k):
        f = self._file_for_key(k)
        if os.path.exists(f):
            try:
                return open(f).read().decode('utf-8')
            except:
                return None

    def set(self, k, v):
        f = self._file_for_key(k)
        open(f, 'wb').write(v.encode('utf-8'))

    def delete_multi(self, ks):
        for k in ks:
            f = self._file_for_key(k)
            if os.path.exists(f):
                os.unlink(f)


cache = SimpleCache()


def _fetch_url(token, url, extra_headers=None, bust_cache=False):
    key = url + json.dumps(extra_headers)
    cached = cache.get(key)
    if cached is not None and not bust_cache:
        return cached
    sys.stderr.write('Uncached request for %s\n' % url)

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
        sys.stderr.write('%s\n' % r)
        sys.stderr.write('%s\n' % r.text)
        sys.stderr.write('Posted:\n%s\n' % json.dumps(obj))
        return False

    return r.json()


def _fetch_api(token, url, bust_cache=False):
    response = _fetch_url(token, url, bust_cache=bust_cache)
    if response is None:
        return None
    if WHITESPACE_RE.match(response):
        return None

    try:
        j = json.loads(response)
    except ValueError:
        sys.stderr.write('Failed to parse as JSON:\n%s\n' % response)
        raise
    return j


# caching: never
def get_current_user_info(token):
    """Returns information about the authenticated user."""
    return _fetch_api(token, GITHUB_API_ROOT + '/user', bust_cache=True)


# caching: should always check after calling
def get_pull_requests(token, owner, repo, bust_cache=False):
    url = (GITHUB_API_ROOT + '/repos/%(owner)s/%(repo)s/pulls') % {'owner': owner, 'repo': repo}
    return _fetch_api(token, url, bust_cache=bust_cache)


def _pull_request_url(owner, repo, pull_number):
    return (GITHUB_API_ROOT + '/repos/%(owner)s/%(repo)s/pulls/%(pull_number)s') % {'owner': owner, 'repo': repo, 'pull_number': pull_number}


# caching: should check after calling
def get_pull_request(token, owner, repo, pull_number, bust_cache=False):
    url = _pull_request_url(owner, repo, pull_number)
    return _fetch_api(token, url, bust_cache=bust_cache)


def _commits_url(owner, repo, pull_number):
    return (GITHUB_API_ROOT + '/repos/%(owner)s/%(repo)s/pulls/%(pull_number)s/commits') % {
            'owner': owner, 'repo': repo, 'pull_number': pull_number}

# caching: expires when pull_request's updated_at changes
def get_pull_request_commits(token, owner, repo, pull_number):
    """Returns commits from first to last."""
    commits = _fetch_api(token, _commits_url(owner, repo, pull_number))

    if not commits:
        return None

    # See https://developer.github.com/v3/pulls/#list-commits-on-a-pull-request
    commits.sort(key=lambda x: x['commit']['author']['date'])
    return commits


def _comments_urls(owner, repo, pull_number):
    issue_url = '/repos/%(owner)s/%(repo)s/issues/%(pull_number)s/comments' % {'owner': owner, 'repo': repo, 'pull_number': pull_number}
    diff_url = '/repos/%(owner)s/%(repo)s/pulls/%(pull_number)s/comments' % {'owner': owner, 'repo': repo, 'pull_number': pull_number}
    return GITHUB_API_ROOT + issue_url, GITHUB_API_ROOT + diff_url


# caching: expires when pull_request's updated_at changes
def get_pull_request_comments(token, owner, repo, pull_number):
    # There are two types of comments:
    # 1. top level (these are issue comments)
    # 2. diff-level (these are pull requests comments)
    # TODO(danvk): are there also file-level comments?
    issue_url, diff_url = _comments_urls(owner, repo, pull_number)
    issue_comments = _fetch_api(token, issue_url) or []
    pr_comments = _fetch_api(token, diff_url) or []

    return {'top_level': issue_comments, 'diff_level': pr_comments}


# caching: never expires
def get_diff_info(token, owner, repo, sha1, sha2):
    # https://developer.github.com/v3/repos/commits/#compare-two-commits
    # Highlights include files.{filename,additions,deletions,changes}
    url = (GITHUB_API_ROOT + '/repos/%(owner)s/%(repo)s/compare/%(sha1)s...%(sha2)s') % {'owner': owner, 'repo': repo, 'sha1': sha1, 'sha2': sha2}
    return _fetch_api(token, url)


# caching: never expires
def get_file_diff(token, owner, repo, path, sha1, sha2):
    # https://developer.github.com/v3/repos/commits/#compare-two-commits
    # Highlights include files.{filename,additions,deletions,changes}
    url = (GITHUB_API_ROOT + '/repos/%(owner)s/%(repo)s/compare/%(sha1)s...%(sha2)s') % {'owner': owner, 'repo': repo, 'sha1': sha1, 'sha2': sha2}
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


# caching: never expires
def get_file_at_ref(token, owner, repo, path, sha):
    url = (GITHUB_API_ROOT + '/repos/%(owner)s/%(repo)s/contents/%(path)s?ref=%(sha)s') % {'owner': owner, 'repo': repo, 'path': path, 'sha': sha}
    return _fetch_url(token, url, extra_headers={'Accept': 'application/vnd.github.3.raw'})


# caching: n/a
def post_comment(token, owner, repo, pull_number, comment):
    # Have to have 'body', then either 'in_reply_to' or a full position spec.
    if not 'body' in comment and (
            ('in_reply_to' in comment) or
            ('commit_id' in comment and
             'path' in comment and
             'position' in comment)):
        return None
    post_path = '/repos/%(owner)s/%(repo)s/pulls/%(pull_number)s/comments'

    filtered_comment = {'body': comment['body']}
    if 'in_reply_to' in comment:
        filtered_comment['in_reply_to'] = comment['in_reply_to']
    else:
        filtered_comment['commit_id'] = comment['original_commit_id']
        filtered_comment['position'] = comment['original_position']
        filtered_comment['path'] = comment['path']

    return _post_api(token, post_path, filtered_comment,
                     owner=owner, repo=repo, pull_number=pull_number)


# caching: n/a
def post_issue_comment(token, owner, repo, issue_number, body):
    post_path = '/repos/%(owner)s/%(repo)s/issues/%(issue_number)s/comments'

    return _post_api(token, post_path, {
        'body': body
        }, owner=owner, repo=repo, issue_number=issue_number)


def _expire_urls(urls):
    keys = [url + json.dumps(None) for url in urls]
    cache.delete_multi(keys)


def expire_cache_for_pull_request_children(owner, repo, pull_number):
    """Delete all non-permanent cache entries relating to this PR."""
    urls = (list(_comments_urls(owner, repo, pull_number)) +
            [_commits_url(owner, repo, pull_number)])
    _expire_urls(urls)


def expire_cache_for_pull_request(owner, repo, pull_number):
    """Delete the Pull Request RPC itself from the cache."""
    _expire_urls([_pull_request_url(owner, repo, pull_number)])
