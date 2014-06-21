'''Application logic and muxing'''

from collections import defaultdict
import json
import logging
import re
import sys
import json
import urllib

from flask import url_for, session, request
import github
import github_comments


class PullRequest(object):
    @staticmethod
    def from_github(db, token, login, owner, repo, number):
        pr = PullRequest()
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
        '''Helper to pass token, owner, and repo to github.py'''
        all_args = [self._token, self._owner, self._repo] + list(args)
        return fn(*all_args)

    def _get_outdated_commit_shas(self, commit_shas, comments):
        '''Outdated commit SHAs are known only from comments on them.'''
        known_shas = set(commit_shas)
        outdated_shas = set()
        for comment in comments['diff_level']:
            sha = comment['original_commit_id']
            if sha not in known_shas:
                outdated_shas.add(sha)

        return list(outdated_shas)

    def _attach_comments(self):
        '''Adds 'comments' fields commit, file and file/commit pair.'''
        sha_to_commit = {}
        for commit in self.commits:
          sha_to_commit[commit['sha']] = commit
        sha_file_map = {}
        for commit in self.commits:
            commit['comments'] = []
            for f in commit['files']:
                f['comments'] = []
                sha_file_map[(commit['sha'], f['filename'])] = f
        path_to_file = {}
        for f in self.files:
            f['comments'] = []
            path_to_file[f['filename']] = f

        for comment in self.comments['diff_level']:
            sha = comment['original_commit_id']
            if sha in sha_to_commit:
                sha_to_commit[sha]['comments'].append(comment)
            pair = (sha, comment['path'])
            if pair in sha_file_map:
                sha_file_map[pair]['comments'].append(comment)
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

        # NOTE: need to do some more thinking about outdated commits.
        # Since the PR's base sha sha may have changed since the commit, it
        # could be hard to show a meaningful diff.
        # outdated_commit_shas = self._get_outdated_commit_shas(commit_shas, comments)
        # commit_shas.extend(outdated_commit_shas)
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

        github_comments.add_line_numbers_to_comments(
                self._token, self._owner, self._repo,
                pr['base']['sha'], comments['diff_level'])
        github_comments.add_in_response_to(pr, comments['diff_level'])

        self.pull_request = pr
        self.commits = commits
        self.comments = comments
        self.files = files

        self._attach_comments()
        self.reverted_files = self._find_reverted_files()
        self._augment_commits()
        self._augment_files()

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

    def _augment_commits(self):
        for commit in self.commits:
            commit.update({
                'short_message':
                    re.sub(r'[\n\r].*', '', commit['commit']['message']),
            })
            if commit['sha'] == self.pull_request['base']['sha']:
                commit['short_message'] = '(base)'

    def _augment_files(self):
        pass

    def add_file_diff_links(self, sha1, sha2):
        for f in self.files:
            f.update({
                'link': url_for('file_diff', owner=self._owner, repo=self._repo, number=self._number) + '?path=' + urllib.quote(f['filename']) + '&sha1=' + urllib.quote(sha1) + '&sha2=' + urllib.quote(sha2) + '#diff'
            })




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
