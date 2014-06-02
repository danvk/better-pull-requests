from collections import defaultdict
import json

from flask import Flask, url_for, render_template, request, jsonify
import github
import git

app = Flask(__name__)

@app.route("/repo/<user>/<repo>")
def repo(user, repo):
    pull_requests = github.get_pull_requests(user, repo)

    format_pull_requests = [{
        'url': url_for('pull', user=user, repo=repo, number=pr['number']),
        'number': pr['number'],
        'title': pr['title'],
        'user': pr['user.login']
        } for pr in pull_requests]

    return render_template('repo.html', pull_requests=format_pull_requests)


@app.route("/pull/<user>/<repo>/<number>")
def pull(user, repo, number):
    commits = github.get_pull_request_commits(user, repo, number)
    pr = github.get_pull_request(user, repo, number)
    comments = github.get_pull_request_comments(user, repo, number)

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



@app.route("/")
def hello():
    return "Hello World!"

if __name__ == "__main__":
    app.run(debug=True)
