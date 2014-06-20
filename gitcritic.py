'''Application logic and muxing'''

from collections import defaultdict
import json
import logging
import re
import sys
import json

from flask import url_for, session, request
import github
import github_comments
import urllib


class PullRequestCritic(object):
    @staticmethod
    def from_github(db, token, login, owner, repo, number):
        pr = PullRequestCritic()
        pr._db = db
        pr._token = token
        pr._login = login
        pr._owner = owner
        pr._repo = repo
        pr._number = number

        pr._get_pr_info()
        return pr

    def __init__(self):
        pass

    def _api(self, fn, *args):
        all_args = [self._token, self._owner, self._repo] + list(args)
        return fn(*all_args)

    def _get_outdated_commit_shas(self, commit_shas, comments):
        known_shas = set(commit_shas)
        outdated_shas = set()
        for comment in comments['diff_level']:
            sha = comment['original_commit_id']
            if sha not in known_shas:
                outdated_shas.add(sha)

        return list(outdated_shas)

    def _attach_comments(self):
        '''Adds 'comments' fields commit, file and file/commit pair.'''
        sha_to_commit = {commit['sha']: commit for commit in self.commits}
        sha_file_map = {}
        for commit in self.commits:
            commit['comments'] = []
            for f in commit['files']:
                f['comments'] = []
                sha_file_map[(commit['sha'], f['filename'])] = f
        path_to_file = {f['filename']: f for f in self.files}
        for f in self.files:
            f['comments'] = []

        for comment in self.comments['diff_level']:
            sha = comment['original_commit_id']
            sha_to_commit[sha]['comments'].append(comment)
            sha_file_map[(sha, comment['path'])]['comments'].append(comment)
            path_to_file[comment['path']]['comments'].append(comment)


    def _get_pr_info(self):
        '''Fill in basic information about a pull request.'''
        pr = self._api(github.get_pull_request, self._number)

        # get a list of files which have been affected by this PR, base to
        # head.
        sha1 = pr['base']['sha']
        sha2 = pr['head']['sha']
        diff_info = self._api(github.get_diff_info, sha1, sha2)
        files = diff_info['files']

        # get a list of commits in the pull request. The API does not return
        # "outdated" commits or the base commit. We add these using auxiliary
        # data.
        commit_shas = [c['sha'] for c in self._api(github.get_pull_request_commits, self._number)]
        comments = self._api(github.get_pull_request_comments, self._number)
        outdated_commit_shas = self._get_outdated_commit_shas(commit_shas, comments)
        commit_shas.extend(outdated_commit_shas)
        commit_shas.append(pr['base']['sha'])

        # Get "thick" commit data.
        # This includes a list of modified files, whereas
        # get_pull_request_commits does not. This gives us information about
        # reverted files.
        commits = []
        for sha in commit_shas:
            commits.append(self._api(github.get_commit_info, sha))
        commits.sort(key=lambda c: c['commit']['committer']['date'])
        commits.reverse()

        # Merge draft and published comments.
        draft_comments = self._db.get_draft_comments(
                self._login, self._owner, self._repo, self._number)
        for comment in draft_comments:
            comments['diff_level'].append(self._db.githubify_comment(comment))

        self.pull_request = pr
        self.commits = commits
        self.comments = comments
        self.files = files

        self._attach_comments()
        self.reverted_files = self._find_reverted_files()

    def _find_reverted_files(self):
        '''Look for files appearing only in intermediate commits.'''
        files = set([f['filename'] for f in self.files])
        reverted_files = set()
        for commit in self.commits[:-1]:
            if len(commit['parents']) >= 2:
                # ignore merge commits.
                # See http://stackoverflow.com/questions/6713652/git-diff-unique-to-merge-commit
                continue
            for f in commit['files']:
                path = f['filename']
                if path not in files:
                    reverted_files.add(path)
        return list(reverted_files)


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
