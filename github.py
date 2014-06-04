import sys
import logging
import json

import os
import hashlib
import cPickle

import requests

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


def extract_path(json_data, path):
    parts = path.split('.')
    try:
        for part in parts:
            json_data = json_data[part]
        return json_data
    except KeyError:
        return None

PR_paths = ['number',
             'state',
             'title',
             'body',
             'created_at',  # ISO
             'modified_at',
             'user.login',  # sender of the pull request
             'head.label',  # e.g. 'kylebaggott:master'
             'head.ref',  # e.g. 'master'
             'head.sha',  # sha for ref
             'head.repo.full_name',  # e.g. kylebaggott/dygraphs
             'head.repo.clone_url',  # repo for pull request
             'base.ref',  # e.g. master
             'base.sha'
            ]

def _fetch_api(token, url):
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


def _post_api(token, url, obj):
    sys.stderr.write('Posting to %s\n' % url)
    r = requests.post(url, headers={'Authorization': 'token ' + token, 'Content-type': 'application/json'}, data=json.dumps(obj))
    if not r.ok:
        sys.stderr.write('Request for %s failed.\n' % url)
        return False

    return r.json()


def get_pull_requests(token, user, repo):
    url = 'https://api.github.com/repos/%s/%s/pulls' % (user, repo)
    pull_requests = _fetch_api(token, url)
    if not pull_requests:
        return None

    # See https://developer.github.com/v3/pulls/
    paths = PR_paths
    return [{x: extract_path(p, x) for x in paths} for p in pull_requests]


def get_pull_request(token, user, repo, pull_number):
    url = 'https://api.github.com/repos/%s/%s/pulls/%s' % (user, repo, pull_number)
    pr = _fetch_api(token, url)
    if not pr:
        return None

    paths = PR_paths
    return {x: extract_path(pr, x) for x in paths}


def get_pull_request_commits(token, user, repo, pull_number):
    """Returns commits from first to last."""
    url = 'https://api.github.com/repos/%s/%s/pulls/%s/commits' % (user, repo, pull_number)
    commits = _fetch_api(token, url)

    if not commits:
        return None

    # See https://developer.github.com/v3/pulls/#list-commits-on-a-pull-request
    paths = ['sha',
             'commit.author.date',
             'commit.message',
             'commit.comment_count',
             'author.login'
            ]
    commits = [{x: extract_path(p, x) for x in paths} for p in commits]
    commits.sort(key=lambda x: x['commit.author.date'])
    return commits


def get_pull_request_comments(token, user, repo, pull_number):
    # There are two types of comments:
    # 1. top level (these are issue comments)
    # 2. diff-level (these are pull requests comments)
    issue_url = 'https://api.github.com/repos/%s/%s/issues/%s/comments' % (user, repo, pull_number)
    pr_url = 'https://api.github.com/repos/%s/%s/pulls/%s/comments' % (user, repo, pull_number)

    issue_comments = _fetch_api(token, issue_url) or []
    pr_comments = _fetch_api(token, pr_url) or []

    issue_paths = {'id': 'id', 'user.login': 'user', 'updated_at': 'time', 'body': 'body'}
    pr_paths = {
            'path': 'path',
            'position': 'position',
            'original_position': 'original_position',
            'commit_id': 'commit_id',
            'original_commit_id': 'original_commit_id',
            'diff_hunk': 'diff_hunk'}
    pr_paths.update(issue_paths)

    return {
        'top_level': issue_comments,
        'diff_level': [{n: extract_path(comment, p) for p, n in pr_paths.iteritems()} for comment in pr_comments]
            }


def post_comment(token, user, repo, pull_number, commit_id, path, position, body):
    post_url = 'https://api.github.com/repos/%s/%s/pulls/%s/comments' % (user, repo, pull_number)

    return _post_api(token, post_url, {
        'commit_id': commit_id,
        'path': path,
        'position': position,
        'body': body
        })
