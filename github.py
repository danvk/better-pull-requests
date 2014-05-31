import sys

import requests


def extract_path(json, path):
    parts = path.split('.')
    try:
        for part in parts:
            json = json[part]
        return json
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

# TODO(danvk): only use this in debug mode.
API_CACHE = {}
TOKEN = '59c0f1b073b84f91b43c6e3182a2bcc078afc90a'

def _fetch_api(url):
    if url in API_CACHE:
        return API_CACHE[url]

    r = requests.get(url, headers={'Authorization': 'token ' + TOKEN})
    if not r.ok:
        sys.stderr.write('Request for %s failed.\n' % url)
        return False

    j = r.json()
    API_CACHE[url] = j
    return j


def get_pull_requests(user, repo):
    url = 'https://api.github.com/repos/%s/%s/pulls' % (user, repo)
    pull_requests = _fetch_api(url)
    if not pull_requests:
        return None

    # See https://developer.github.com/v3/pulls/
    paths = PR_paths
    return [{x: extract_path(p, x) for x in paths} for p in pull_requests]


def get_pull_request(user, repo, pull_number):
    url = 'https://api.github.com/repos/%s/%s/pulls/%s' % (user, repo, pull_number)
    pr = _fetch_api(url)
    if not pr:
        return None

    paths = PR_paths
    return {x: extract_path(pr, x) for x in paths}


def get_pull_request_commits(user, repo, pull_number):
    """Returns commits from first to last."""
    url = 'https://api.github.com/repos/%s/%s/pulls/%s/commits' % (user, repo, pull_number)
    commits = _fetch_api(url)

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


def get_pull_request_comments(user, repo, pull_number):
    # There are two types of comments:
    # 1. top level (these are issue comments)
    # 2. diff-level (these are pull requests comments)
    issue_url = 'https://api.github.com/repos/%s/%s/issues/%s/comments' % (user, repo, pull_number)
    pr_url = 'https://api.github.com/repos/%s/%s/pulls/%s/comments' % (user, repo, pull_number)

    issue_comments = _fetch_api(issue_url) or []
    pr_comments = _fetch_api(pr_url) or []

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
