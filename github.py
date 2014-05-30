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


def get_pull_requests(user, repo):
    url = 'https://api.github.com/repos/%s/%s/pulls' % (user, repo)
    r = requests.get(url)
    if not r.ok:
        # TODO(danvk): print error
        sys.stderr.write('Request for %s failed.\n' % url)
        return None

    # See https://developer.github.com/v3/pulls/
    pull_requests = r.json()
    paths = ['number',
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
    return [{x: extract_path(p, x) for x in paths} for p in pull_requests]


def get_pull_request(user, repo, pull_number):



def get_pull_request_commits(user, repo, pull_number):
    url = 'https://api.github.com/repos/%s/%s/pulls/%s/commits' % (user, repo, pull_number)

    r = requests.get(url)
    if not r.ok:
        # TODO(danvk): print error
        sys.stderr.write('Request for %s failed.\n' % url)
        return None

    # See https://developer.github.com/v3/pulls/#list-commits-on-a-pull-request
    commits = r.json()
    paths = ['sha',
            'commit.author.date',
            'commit.message',
            'commit.comment_count',
            'author.login'
            ]
    return [{x: extract_path(p, x) for x in paths} for p in commits]
