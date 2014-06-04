import sys
import logging
import json

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
                return cPickle.load(open(f))
            except:
                return None

    def set(self, k, v):
        f = self._file_for_key(k)
        cPickle.dump(v, open(f, 'wb'))


cache = SimpleCache()


def _fetch_url(token, url):
    cached = cache.get(url)
    if cached is not None:
        return cached
    sys.stderr.write('Uncached request for %s\n' % url)
    sys.stderr.write('Token=%s\n' % token)

    r = requests.get(url, headers={'Authorization': 'token ' + token})
    if not r.ok:
        sys.stderr.write('Request for %s failed.\n' % url)
        return False

    j = r.json()
    cache.set(url, j)
    return j


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
    return _fetch_url(token, url)


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


def post_comment(token, user, repo, pull_number, commit_id, path, position, body):
    post_path = '/repos/%(user)s/%(repo)s/pulls/%(pull_number)s/comments'

    return _post_api(token, post_path, {
        'commit_id': commit_id,
        'path': path,
        'position': position,
        'body': body
        }, user=user, repo=repo, pull_number=pull_number)
