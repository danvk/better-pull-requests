from collections import defaultdict
import json
import urllib
import requests
import sys

from flask import Flask, url_for, render_template, request, jsonify, session
import github
import git
import github_comments

SECRETS = json.load(open('secrets.json'))
CLIENT_SECRET = SECRETS['github_client_secret']
Flask.secret_key = SECRETS['flask_secret_key']

app = Flask(__name__)

@app.route("/repo/<user>/<repo>")
def repo(user, repo):
    token = session['token']
    pull_requests = github.get_pull_requests(token, user, repo)
    sys.stderr.write('Found %d pull requests in %s/%s\n' % (
        len(pull_requests), user, repo))

    format_pull_requests = [{
        'url': url_for('pull', user=user, repo=repo, number=pr['number']),
        'number': pr['number'],
        'title': pr['title'],
        'user': pr['user.login']
        } for pr in pull_requests]

    return render_template('repo.html', pull_requests=format_pull_requests)


@app.route("/pull/<user>/<repo>/<number>")
def pull(user, repo, number):
    token = session['token']
    commits = github.get_pull_request_commits(token, user, repo, number)
    pr = github.get_pull_request(token, user, repo, number)
    comments = github.get_pull_request_comments(token, user, repo, number)

    commit_to_comments = defaultdict(int)
    for comment in comments['diff_level']:
        commit_to_comments[comment['original_commit_id']] += 1

    commits.reverse()
    commits.append({
        'sha': pr['base.sha'],
        'commit.message': '(%s)' % pr['base.ref'],
        'commit.author.date': '',
        'author.login': ''
    })

    format_commits = [{
        'sha': commit['sha'],
        'message': commit['commit.message'],
        'author': commit['author.login'],
        'time': commit['commit.author.date'],
        'comment_count': commit_to_comments[commit['sha']]
        } for commit in commits]

    return render_template('pull_request.html', commits=format_commits, user=user, repo=repo, head_repo=pr['head.repo.full_name'], pull_request=pr, comments=comments)


@app.route("/pull/<user>/<repo>/<number>/diff")
def file_diff(user, repo, number):
    path = request.args.get('path', '')
    sha1 = request.args.get('sha1', '')
    sha2 = request.args.get('sha2', '')
    if not (path and sha1 and sha2):
        return "Incomplete request (need path, sha1, sha2)"

    # TODO(danvk): consolidate this code with the pull route
    token = session['token']
    commits = github.get_pull_request_commits(token, user, repo, number)
    pr = github.get_pull_request(token, user, repo, number)
    comments = github.get_pull_request_comments(token, user, repo, number)

    commit_to_comments = defaultdict(int)
    for comment in comments['diff_level']:
        commit_to_comments[comment['original_commit_id']] += 1

    commits.reverse()
    commits.append({
        'sha': pr['base.sha'],
        'commit.message': '(%s)' % pr['base.ref'],
        'commit.author.date': '',
        'author.login': ''
    })

    format_commits = [{
        'sha': commit['sha'],
        'message': commit['commit.message'],
        'author': commit['author.login'],
        'time': commit['commit.author.date'],
        'comment_count': commit_to_comments[commit['sha']]
        } for commit in commits]

    head_repo = pr['head.repo.full_name']
    clone_url = 'https://github.com/%s.git' % head_repo

    # github excludes the first four header lines of "git diff"
    github_diff = '\n'.join(git.get_file_diff(clone_url, path, sha1, sha2).split('\n')[4:])

    # TODO(danvk): only annotate comments on this file.
    github_comments.add_line_numbers_to_comments(pr, comments['diff_level'])

    differing_files = git.get_differing_files(clone_url, sha1, sha2)
    before = git.get_file_at_ref(clone_url, path, sha1)
    after = git.get_file_at_ref(clone_url, path, sha2)

    def diff_url(path):
        return (url_for('file_diff', user=user, repo=repo, number=number) +
                '?path=' + urllib.quote(path) +
                '&sha1=' + urllib.quote(sha1) + '&sha2=' + urllib.quote(sha2))

    linked_files = [{'path':p, 'link': diff_url(p)} for p in differing_files]

    if path in differing_files:
        file_idx = differing_files.index(path)
        prev_file = linked_files[file_idx - 1] if file_idx > 0 else None
        next_file = linked_files[file_idx + 1] if file_idx < len(linked_files) - 1 else None
    else:
        # The current file is not part of this diff.
        # Just do something sensible.
        prev_file = None
        next_file = linked_files[0] if len(linked_files) > 0 else None

    return render_template('file_diff.html', commits=format_commits, user=user, repo=repo, head_repo=pr['head.repo.full_name'], pull_request=pr, comments=comments, path=path, sha1=sha1, sha2=sha2, before_contents=before, after_contents=after, differing_files=linked_files, prev_file=prev_file, next_file=next_file, github_diff=github_diff)


# TODO(danvk): eliminate this request -- should all be done server-side
@app.route("/diff", methods=["GET", "POST"])
def diff():
    repo = request.args.get('repo', '')
    sha1 = request.args.get('sha1', '')
    sha2 = request.args.get('sha2', '')
    if not (repo and sha1 and sha2):
        return "Incomplete request (need repo, sha1, sha2)"

    clone_url = 'https://github.com/%s.git' % repo
    differing_files = git.get_differing_files(clone_url, sha1, sha2)
    before = {p: git.get_file_at_ref(clone_url, p, sha1) for p in differing_files}
    after = {p: git.get_file_at_ref(clone_url, p, sha2) for p in differing_files}

    return jsonify(files=differing_files, before=before, after=after)


@app.route("/post_comment", methods=['POST'])
def post_comment():
    owner = request.form['owner']
    repo = request.form['repo']
    pull_number = request.form['pull_number']
    path = request.form['path']
    commit_id = request.form['commit_id']
    line_number = int(request.form['line_number'])
    body = request.form['body']

    if not owner:
        return "Incomplete post_comment request, missing owner"
    if not repo:
        return "Incomplete post_comment request, missing repo"
    if not pull_number:
        return "Incomplete post_comment request, missing pull_number"
    if not path:
        return "Incomplete post_comment request, missing path"
    if not commit_id:
        return "Incomplete post_comment request, missing commit_id"
    if not line_number:
        return "Incomplete post_comment request, missing line_number"
    if not body:
        return "Incomplete post_comment request, missing body"

    token = session['token']
    if not token:
        return "You must be oauthed to post a comment."

    pr = github.get_pull_request(token, owner, repo, pull_number)
    base_sha = pr['base.sha']

    diff_position = github_comments.lineNumberToDiffPosition(pr, path, commit_id, line_number, False)  # False = on_left (for now!)
    if not diff_position:
        return "Unable to get diff position for %s:%s @%s" % (path, line_number, commit_id)

    sys.stderr.write('diff_position=%s\n' % diff_position)

    response = github.post_comment(token, owner, repo, pull_number, commit_id, path, diff_position, body)

    # TODO(danvk): reply with the same filtered format as /comments
    return jsonify(response)



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

    return "Authenticated successfully!"


@app.route("/")
def hello():
    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True)
