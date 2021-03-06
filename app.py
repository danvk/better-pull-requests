import json
import logging
import os
import re
import sys
import urllib

from flask import (url_for, render_template, flash, send_from_directory,
                   request, jsonify, session, redirect, Response)

import authentication
import config
import github
import github_comments
import gitcritic
import comment_db
from logged_in import logged_in

app = config.create_app()
db = comment_db.CommentDb()
authentication.install_github_oauth(app)


@app.route("/<owner>/<repo>")
@logged_in
def plain_repo(owner, repo):
    return redirect(url_for("repo", owner=owner, repo=repo))


@app.route("/<owner>/<repo>/pulls")
@logged_in
def repo(owner, repo):
    result = gitcritic.handle_get_pull_requests(owner, repo)
    if result:
        return render_template('repo.html', **result)
    else:
        return "Error"


@app.route("/<owner>/<repo>/pull/<number>")
@logged_in
def pull(owner, repo, number):
    sha1 = request.args.get('sha1', None)
    sha2 = request.args.get('sha2', None)
    token = session['token']
    login = session['login']

    pr = gitcritic.PullRequest.from_github(db, token, login, owner, repo, number)

    if not sha1: sha1 = pr.pull_request['base']['sha']
    if not sha2: sha2 = pr.pull_request['head']['sha']

    for commit in pr.commits:
        if commit['sha'] == sha1: commit['selected_left'] = True
        if commit['sha'] == sha2: commit['selected_right'] = True

    pr.add_file_diff_links(sha1, sha2)

    return render_template('pull_request.html',
                           logged_in_user=login,
                           owner=owner, repo=repo,
                           commits=pr.commits,
                           pull_request=pr.pull_request,
                           comments=pr.comments,
                           files=pr.files)


@app.route("/<owner>/<repo>/get_contents", methods=['POST'])
@logged_in
def get_contents(owner, repo):
    token = session['token']
    path = request.form.get('path', '')
    sha = request.form.get('sha', '')
    if not (path and sha):
        e = {"code": "incomplete",
             "message": "Incomplete request (need path, sha)"}
        response = jsonify(e)
        response.status_code = 400
        return response

    contents = github.get_file_at_ref(token, owner, repo, path, sha) or ''
    return Response(contents, mimetype='text/plain')


@app.route("/<owner>/<repo>/pull/<number>/diff")
@logged_in
def file_diff(owner, repo, number):
    token = session['token']
    login = session['login']
    path = request.args.get('path', '')
    sha1 = request.args.get('sha1', '')
    sha2 = request.args.get('sha2', '')
    if not (path and sha1 and sha2):
        return "Incomplete request (need path, sha1, sha2)"

    pr = gitcritic.PullRequest.from_github(db, token, login, owner, repo, number)

    unified_diff = github.get_file_diff(token, owner, repo, path, sha1, sha2)
    if not unified_diff:
        return "Unable to get diff for %s..%s" % (sha1, sha2)

    # github excludes the first four header lines of "git diff"
    github_diff = '\n'.join(unified_diff.split('\n')[4:])

    # before = github.get_file_at_ref(token, owner, repo, path, sha1) or ''
    # after = github.get_file_at_ref(token, owner, repo, path, sha2) or ''

    for commit in pr.commits:
        if commit['sha'] == sha1: commit['selected_left'] = True
        if commit['sha'] == sha2: commit['selected_right'] = True

    pr.add_file_diff_links(sha1, sha2)

    idxs = [i for (i, f) in enumerate(pr.files) if f['filename'] == path]

    if idxs:
        file_idx = idxs[0]
        prev_file = pr.files[file_idx - 1] if file_idx > 0 else None
        next_file = pr.files[file_idx + 1] if file_idx < len(pr.files) - 1 else None
        app.logger.info("next_file: %s", next_file)
    else:
        # The current file is not part of this diff.
        # Just do something sensible.
        prev_file = None
        next_file = pr.files[0] if len(pr.files) > 0 else None

    pull_request_url = url_for('pull', owner=owner, repo=repo, number=number) + '?sha1=%s&sha2=%s' % (sha1, sha2)

    github_file_urls = map(lambda sha: 'http://github.com/%s/%s/blob/%s/%s' % (owner, repo, sha, path), [sha1, sha2])

    return render_template('file_diff.html',
                           logged_in_user=login,
                           owner=owner, repo=repo,
                           pull_request=pr.pull_request,
                           commits=pr.commits,
                           comments=pr.comments,
                           files=pr.files,
                           path=path, sha1=sha1, sha2=sha2,
                           # before_contents=before, after_contents=after,
                           prev_file=prev_file, next_file=next_file,
                           github_diff=github_diff,
                           pull_request_url=pull_request_url,
                           github_file_urls=github_file_urls)


@app.route("/count_open_pull_requests", methods=['POST'])
@logged_in
def count_open_pull_requests():
    owner = request.form['owner']
    repo = request.form['repo']
    return jsonify(gitcritic.count_open_pull_requests(owner, repo))


@app.route("/check_for_updates", methods=['POST'])
def check_for_updates():
    owner = request.form['owner']
    repo = request.form['repo']
    pull_number = request.form['pull_number']
    updated_at = request.form['updated_at']
    token = session['token']

    pr = github.get_pull_request(token, owner, repo, pull_number,
                                 bust_cache=True)

    if not pr:
        return "Error"

    if pr['updated_at'] <= updated_at:
        return "OK"

    # Invalidate associated RPCs: commit list, comments
    github.expire_cache_for_pull_request_children(owner, repo, pull_number)
    return "Update"


@app.route("/save_draft", methods=['POST'])
@logged_in
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
    github_comments.add_line_number_to_comment(token, owner, repo, base_sha,
                                               result)
    return jsonify(result)


@app.route("/publish_draft_comments", methods=['POST'])
@logged_in
def publish_draft_comments():
    owner = request.form['owner']
    repo = request.form['repo']
    pull_number = request.form['pull_number']
    token = session['token']
    login = session['login']

    new_top_level = request.form['top_level_comment']

    if not owner:
        return "Incomplete post_comment request, missing owner"
    if not repo:
        return "Incomplete post_comment request, missing repo"
    if not pull_number:
        return "Incomplete post_comment request, missing pull_number"

    draft_comments = db.get_draft_comments(login, owner, repo, pull_number)
    if not draft_comments and not new_top_level:
        return "No comments to publish!"

    # TODO(danvk): publish comments in parallel
    errors = []
    for comment in draft_comments:
        result = github.post_comment(token, owner, repo, pull_number, comment)
        if not result:
            errors.append(comment)
            sys.stderr.write("Unable to publish comment: %s" % json.dumps(comment))
        else:
            db.delete_draft_comments([comment['id']])

    logging.info('Successfully published %d comments', len(draft_comments))

    if new_top_level:
        result = github.post_issue_comment(token, owner, repo, pull_number,
                                           new_top_level)
        if not result:
            return "Unable to publish comment: %s" % new_top_level

    github.expire_cache_for_pull_request(owner, repo, pull_number)
    github.expire_cache_for_pull_request_children(owner, repo, pull_number)
    if errors:
        flash("Some comments could not be published. They've been left as drafts.")
    return redirect(url_for('pull', owner=owner, repo=repo, number=pull_number))


@app.route("/discard_draft_comment", methods=['POST'])
@logged_in
def discard_draft_comment():
    comment_id = int(request.form['id'])
    if not comment_id:
        return "Missing 'id' parameter"

    if db.delete_draft_comments([comment_id]):
        return "OK"
    else:
        return "Error"


@app.route('/')
@logged_in
def index():
    return user(session['login'])


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/img'),
                               'favicon.ico',
                               mimetype='image/vnd.microsoft.icon')


@app.route('/<user>')
@logged_in
def user(user):
    token = session['token']
    subscriptions = github.get_user_subscriptions(token, user)

    if not subscriptions:
        subscriptions = []

    # Filter out repos without open issues. Since PRs are issues, these can't
    # have any open pull requests.
    subscriptions = filter(lambda s: s['open_issues_count'] > 0, subscriptions)

    return render_template('subscriptions.html',
                           logged_in_user=session['login'],
                           subscriptions=subscriptions)


if __name__ == "__main__":
    app.run(host='0.0.0.0')
