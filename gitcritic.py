'''Application logic and muxing'''

from collections import defaultdict
import json
import logging
import re
import sys

from flask import url_for, session, request
import github
import github_comments
import urllib


class PullRequestCritic(object):
    def __init__(self, db, token, owner, repo, number):
        self._db = db
        self._token = token
        self._owner = owner
        self._repo = repo
        self._number = number

        self._get_pr_info()

    def _api(self, fn, *args):
        all_args = [self._token, self._owner, self._repo] + list(args)
        return fn(*all_args)

    def _get_outdated_commit_shas(self, commits, comments):
        known_shas = set([c['sha'] for c in commits])
        outdated_shas = set()
        for comment in comments['diff_level']:
            sha = comment['original_commit_id']
            if sha not in known_shas:
                outdated_shas.add(sha)

        return list(outdated_shas)

    def _reconstruct_commit(self, sha):
        commit = self._api(github.get_commit_info, sha)
        return {
            'commit': commit,
            'is_outdated': True,
            'author': {
                'login': ''
            },
            'parents': commit['parents'],
            'sha': commit['sha'],
            'html_url': commit['html_url']
        }

    def _get_outdated_commits(self, commits, comments):
        shas = self._get_outdated_commit_shas(commits, comments)
        return [self._reconstruct_commit(sha) for sha in shas]

    def _get_fake_head_commit(self, pr):
        return {
            'sha': pr['base']['sha'],
            'commit': {
                'message': '(%s)' % pr['base']['ref'],
                'author': {'date': ''},
                'committer': {'date': ''}  # sorts to the start
            },
            'author': pr['base']['user']
        }

    def _get_pr_info(self):
        '''Fill in basic information about a pull request.'''
        pr = self._api(github.get_pull_request, self._number)

        # get a list of files which have been affected by this PR, base to head.
        sha1 = pr['base']['sha']
        sha2 = pr['head']['sha']
        diff_info = self._api(github.get_diff_info, sha1, sha2)
        files = diff_info['files']

        # get a list of commits in the pull request.
        # We only know refs for outdated commits from the comments on them.
        commits = self._api(github.get_pull_request_commits, self._number)
        comments = self._api(github.get_pull_request_comments, self._number)
        outdated_commits = self._get_outdated_commits(commits, comments)
        commits.extend(outdated_commits)

        # Add an entry for the base commit.
        commits.append(self._get_fake_head_commit(pr))
        commits.sort(key=lambda c: c['commit']['committer']['date'])
        commits.reverse()

        # there may be additional files which were reverted. We need to query every
        # commit in the pull request to find these.
        sha_to_commit = {}
        for commit in commits:
            sha = commit['sha']
            sha_to_commit[sha] = self._api(github.get_commit_info, sha)

        self.pull_request = pr
        self.commits = commits
        self.comments = comments
        self.files = files
        self.sha_to_commit = sha_to_commit


def get_pr_info(db, session, owner, repo, number, sha1=None, sha2=None, path=None):
    '''Gets basic information about a pull request.
    
    This includes commits, comments, files affected and Pull Request info.
    '''
    token = session['token']
    login = session['login']
    commits = github.get_pull_request_commits(token, owner, repo, number)
    pr = github.get_pull_request(token, owner, repo, number)

    if not sha1:
        sha1 = pr['base']['sha']
    if not sha2:
        sha2 = commits[-1]['sha']

    comments = github.get_pull_request_comments(token, owner, repo, number)
    draft_comments = db.get_draft_comments(login, owner, repo, number)

    known_shas = set([c['sha'] for c in commits])
    outdated_shas = set()
    for comment in comments['diff_level']:
        sha = comment['original_commit_id']
        if sha not in known_shas:
            outdated_shas.add(sha)

    for sha in outdated_shas:
        commit = github.get_commit_info(token, owner, repo, sha)
        commits.append({
            'commit': commit,
            'is_outdated': True,
            'author': {
                'login': ''
            },
            'parents': commit['parents'],
            'sha': commit['sha'],
            'html_url': commit['html_url']
            })

    commit_to_comments = defaultdict(int)
    commit_to_draft_comments = defaultdict(int)
    for comment in comments['diff_level']:
        if path and comment['path'] != path: continue
        commit_to_comments[comment['original_commit_id']] += 1
    for comment in draft_comments:
        if path and comment['path'] != path: continue
        commit_to_draft_comments[comment['original_commit_id']] += 1
        comments['diff_level'].append(db.githubify_comment(comment))

    # TODO(danvk): only annotate comments on this file.
    github_comments.add_line_numbers_to_comments(token, owner, repo,
                                                 pr['base']['sha'],
                                                 comments['diff_level'])

    commits.reverse()
    # Add an entry for the base commit.
    commits.append({
        'sha': pr['base']['sha'],
        'commit': {
            'message': '(%s)' % pr['base']['ref'],
            'author': {'date': ''},
            'committer': {'date': ''}  # sorts to the start
        },
        'author': pr['base']['user']
    })

    commits.sort(key=lambda c: c['commit']['committer']['date'])
    commits.reverse()

    for commit in commits:
        sha = commit['sha']
        commit.update({
            'short_message': re.sub(r'[\n\r].*', '', commit['commit']['message']),
            'comment_count': commit_to_comments[sha],
            'draft_comment_count': commit_to_draft_comments[sha],
            'total_comment_count': commit_to_comments[sha] + commit_to_draft_comments[sha]
        })
        if sha1 == sha:
            commit['selected_left'] = True
        if sha2 == sha:
            commit['selected_right'] = True

    diff_info = github.get_diff_info(token, owner, repo, sha1, sha2)
    differing_files = [f['filename'] for f in diff_info['files']]

    path_to_comments = defaultdict(int)
    path_to_draft_comments = defaultdict(int)
    for comment in comments['diff_level']:
        path = comment.get('path')
        if comment.get('is_draft'):
            path_to_draft_comments[path] += 1
        else:
            path_to_comments[path] += 1

    def diff_url(path):
        return (url_for('file_diff', owner=owner, repo=repo, number=number) +
                '?path=' + urllib.quote(path) +
                '&sha1=' + urllib.quote(sha1) + '&sha2=' + urllib.quote(sha2) +
                '#diff')

    # TODO(danvk): store diffstats in here.
    files = [{
        'path': p,
        'link': diff_url(p),
        'comment_count': path_to_comments[p],
        'draft_comment_count': path_to_draft_comments[p],
        'total_comment_count': path_to_comments[p] + path_to_draft_comments[p]
        } for p in differing_files]

    return pr, commits, comments, files


def _add_urls_to_pull_requests(prs):
    for pr in prs:
        repo = pr['base']['repo']
        pr['url'] = url_for('pull', owner=repo['owner']['login'],
                repo=repo['name'], number=pr['number'])


def handle_get_pull_requests(owner, repo):
    '''Returns template vars for open pull requests for a repo.'''
    token = session['token']
    pull_requests = github.get_pull_requests(token, owner, repo,
                                             bust_cache=True)
    _add_urls_to_pull_requests(pull_requests)

    return {
            'logged_in_user': session['login'],
            'pull_requests': pull_requests
    }


def count_open_pull_requests(owner, repo):
    token = session['token']
    login = session['login']
    pull_requests = github.get_pull_requests(token, owner, repo,
                                             bust_cache=True)
    _add_urls_to_pull_requests(pull_requests)

    own_prs = filter(lambda pr: pr['user']['login'] == login, pull_requests)
    return {
            'count': len(pull_requests),
            'own': own_prs
    }
