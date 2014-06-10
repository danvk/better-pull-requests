from collections import defaultdict
import json
import urllib
import requests
import sys
import re
import os

from flask import Flask, url_for, render_template, request, jsonify, session, redirect
import github
import github_comments
import comment_db

if os.path.exists('secrets.json'):
    SECRETS = json.load(open('secrets.json'))
    CLIENT_SECRET = SECRETS['github_client_secret']
    Flask.secret_key = CLIENT_SECRET  # no need for multiple secrets
else:
    sys.stderr.write('''
You need to create a secrets.json file before running this server.
See README.md for details.\n
''')
    sys.exit(1)

app = Flask(__name__)

db = comment_db.CommentDb()

@app.route("/<owner>/<repo>/pulls")
def repo(owner, repo):
    token = session['token']
    pull_requests = github.get_pull_requests(token, owner, repo)

    for pr in pull_requests:
        pr['url'] = url_for('pull', owner=owner, repo=repo, number=pr['number'])

    return render_template('repo.html',
                           logged_in_user=session['login'],
                           pull_requests=pull_requests)


def _get_pr_info(session, owner, repo, number, sha1=None, sha2=None, path=None):
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
    github_comments.add_line_numbers_to_comments(token, owner, repo, pr['base']['sha'], comments['diff_level'])

    commits.reverse()
    # Add an entry for the base commit.
    commits.append({
        'sha': pr['base']['sha'],
        'commit': {
            'message': '(%s)' % pr['base']['ref'],
            'author': {'date': ''}
        },
        'author': {'login': ''}
    })

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
                '&sha1=' + urllib.quote(sha1) + '&sha2=' + urllib.quote(sha2))

    # TODO(danvk): store diffstats in here.
    files = [{
        'path': p,
        'link': diff_url(p),
        'comment_count': path_to_comments[p],
        'draft_comment_count': path_to_draft_comments[p],
        'total_comment_count': path_to_comments[p] + path_to_draft_comments[p]
        } for p in differing_files]

    return pr, commits, comments, files


@app.route("/<owner>/<repo>/pull/<number>")
def pull(owner, repo, number):
    sha1 = request.args.get('sha1', None)
    sha2 = request.args.get('sha2', None)
    token = session['token']

    pr, commits, comments, files = _get_pr_info(session, owner, repo, number, sha1=sha1, sha2=sha2)
    if not sha1:
        sha1 = [c['sha'] for c in commits if 'selected_left' in c][0]
    if not sha2:
        sha2 = [c['sha'] for c in commits if 'selected_right' in c][0]

    return render_template('pull_request.html',
                           logged_in_user=session['login'],
                           owner=owner, repo=repo,
                           commits=commits,
                           pull_request=pr,
                           comments=comments,
                           files=files)


@app.route("/<owner>/<repo>/pull/<number>/diff")
def file_diff(owner, repo, number):
    path = request.args.get('path', '')
    sha1 = request.args.get('sha1', '')
    sha2 = request.args.get('sha2', '')
    if not (path and sha1 and sha2):
        return "Incomplete request (need path, sha1, sha2)"

    token = session['token']
    pr, commits, comments, files = _get_pr_info(session, owner, repo, number, path=path, sha1=sha1, sha2=sha2)

    unified_diff = github.get_file_diff(token, owner, repo, path, sha1, sha2)
    if not unified_diff:
        return "Unable to get diff for %s..%s" % (sha1, sha2)

    # github excludes the first four header lines of "git diff"
    github_diff = '\n'.join(unified_diff.split('\n')[4:])

    github_comments.add_in_response_to(pr, comments['diff_level'])

    before = github.get_file_at_ref(token, owner, repo, path, sha1) or ''
    after = github.get_file_at_ref(token, owner, repo, path, sha2) or ''

    idxs = [i for (i, f) in enumerate(files) if f['path'] == path]

    if idxs:
        file_idx = idxs[0]
        prev_file = files[file_idx - 1] if file_idx > 0 else None
        next_file = files[file_idx + 1] if file_idx < len(files) - 1 else None
    else:
        # The current file is not part of this diff.
        # Just do something sensible.
        prev_file = None
        next_file = files[0] if len(files) > 0 else None

    pull_request_url = url_for('pull', owner=owner, repo=repo, number=number) + '?sha1=%s&sha2=%s' % (sha1, sha2)

    return render_template('file_diff.html',
                           logged_in_user=session['login'],
                           owner=owner, repo=repo,
                           pull_request=pr,
                           commits=commits,
                           comments=comments,
                           path=path, sha1=sha1, sha2=sha2,
                           before_contents=before, after_contents=after,
                           files=files,
                           prev_file=prev_file, next_file=next_file,
                           github_diff=github_diff,
                           pull_request_url=pull_request_url)


@app.route("/check_for_updates", methods=['POST'])
def check_for_updates():
    owner = request.form['owner']
    repo = request.form['repo']
    pull_number = request.form['pull_number']
    updated_at = request.form['updated_at']
    token = session['token']

    pr = github.get_pull_request(token, owner, repo, pull_number, bust_cache=True)

    if pr['updated_at'] <= updated_at:
        return "OK"

    # Invalidate associated RPCs: commit list, comments
    github.expire_cache_for_pull_request_children(owner, repo, pull_number)
    return "Update"


@app.route("/save_draft", methods=['POST'])
def save_draft_comment():
    owner = request.form['owner']
    repo = request.form['repo']
    path = request.form['path']
    pull_number = request.form['pull_number']
    commit_id = request.form['commit_id']
    line_number = int(request.form['line_number'])
    in_reply_to = request.args.get('in_reply_to')
    comment = {
      'owner': owner,
      'repo': repo,
      'pull_number': pull_number,
      'path': path,
      'original_commit_id': commit_id,
      'body': request.form['body']
    }
    if in_reply_to:
      comment['in_reply_to'] = in_reply_to

    comment_id = request.form.get('id')
    if comment_id:
        comment['id'] = comment_id

    token = session['token']
    pr = github.get_pull_request(token, owner, repo, pull_number)
    base_sha = pr['base']['sha']

    position, hunk = github_comments.lineNumberToDiffPositionAndHunk(token, owner, repo, base_sha, path, commit_id, line_number, False)
    if not position:
        return "Unable to get diff position for %s:%s @%s" % (path, line_number, commit_id)

    comment['original_position'] = position
    comment['diff_hunk'] = hunk

    result = db.add_draft_comment(session['login'], comment)
    result = db.githubify_comment(result)
    # This is a bit roundabout, but more reliable!
    github_comments.add_line_number_to_comment(token, owner, repo, base_sha, result)
    return jsonify(result)


@app.route("/publish_draft_comments", methods=['POST'])
def publish_draft_comments():
    owner = request.form['owner']
    repo = request.form['repo']
    pull_number = request.form['pull_number']

    new_top_level = request.form['top_level_comment']

    if not owner:
        return "Incomplete post_comment request, missing owner"
    if not repo:
        return "Incomplete post_comment request, missing repo"
    if not pull_number:
        return "Incomplete post_comment request, missing pull_number"

    token = session['token']
    if not token:
        return "You must be signed in to publish comments."

    draft_comments = db.get_draft_comments(session['login'], owner, repo, pull_number)
    if not draft_comments and not new_top_level:
        return "No comments to publish!"

    # TODO(danvk): publish comments in parallel
    for comment in draft_comments:
        result = github.post_comment(token, owner, repo, pull_number, comment)
        if not result:
            return "Unable to publish comment: %s" % json.dumps(comment)
        db.delete_draft_comments([comment['id']])

    sys.stderr.write('Successfully published %d comments.\n' % len(draft_comments))

    if new_top_level:
        result = github.post_issue_comment(token, owner, repo, pull_number, new_top_level)
        if not result:
            return "Unable to publish comment: %s" % new_top_level

    github.expire_cache_for_pull_request(owner, repo, pull_number)
    github.expire_cache_for_pull_request_children(owner, repo, pull_number)
    return redirect(url_for('pull', owner=owner, repo=repo, number=pull_number))


@app.route("/discard_draft_comment", methods=['POST'])
def discard_draft_comment():
    comment_id = int(request.form['id'])
    if not comment_id:
        return "Missing 'id' parameter"

    if db.delete_draft_comments([comment_id]):
        return "OK"
    else:
        return "Error"


@app.route("/oauth_callback")
def oauth_callback():
    state = request.args.get('state', '')  # TODO(danvk): verify this
    code = request.args.get('code', '')
    if not code:
        return "Unable to authenticate"

    # Now we POST to github.com/login/oauth/access_token to get an access token.
    response = requests.post('https://github.com/login/oauth/access_token', data={
        'client_id': 'a9c607c208c3155a26dd',
        'client_secret': CLIENT_SECRET,
        'code': code,
        'redirect_uri': 'http://localhost:5000/oauth_callback'
        }, headers={'Accept': 'application/json'})

    if response.json() and 'access_token' in response.json():
        session['token'] = response.json()['access_token']
    else:
        return "Unable to authenticate."

    # Fetch basic user data to store in session state
    user_info = github.get_current_user_info(session['token'])
    if not user_info:
        return "Unable to get user info."
    session['login'] = user_info['login']

    return "Authenticated successfully!"


@app.route("/")
def hello():
    return render_template('index.html')


if __name__ == "__main__":
    app.run(debug=True)
