'''Application logic and muxing'''

from collections import defaultdict
import re

from flask import url_for, session, request
import github
import github_comments
import urllib

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


def handle_get_pull_requests(owner, repo):
    '''Returns template vars for open pull requests for a repo.'''
    token = session['token']
    pull_requests = github.get_pull_requests(token, owner, repo,
                                             bust_cache=True)

    for pr in pull_requests:
        pr['url'] = url_for('pull', owner=owner,
                            repo=repo, number=pr['number'])

    return {
            'logged_in_user': session['login'],
            'pull_requests': pull_requests
    }


def count_open_pull_requests(owner, repo):
    token = session['token']
    login = session['login']
    pull_requests = github.get_pull_requests(token, owner, repo,
                                             bust_cache=True)

    own_prs = filter(lambda pr: pr['user']['login'] == login, pull_requests)
    return {
            'count': len(pull_requests),
            'own': own_prs
    }
