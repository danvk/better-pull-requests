import github
from flask import Flask
app = Flask(__name__)

@app.route("/pulls/<user>/<repo>")
def pulls(user, repo):
    pull_requests = github.get_pull_requests(user, repo)
    def pr_fmt(pr):
        return "<a href='/pull/%s/%s/%s'>#%s</a> %s (%s)" % (user, repo, pr['number'], pr['number'], pr['title'], pr['user.login'])

    return "Pull requests:<br/>%s" % '<br/>'.join([pr_fmt(p) for p in pull_requests])


@app.route("/pull/<user>/<repo>/<number>")
def pull(user, repo, number):
    commits = github.get_pull_request_commits(user, repo, number)
    def commit_fmt(c):
        return "%s %s (%s)" % (c['sha'], c['commit.message'], c['author.login'])

    return "Pull request %s<br/><br/>%s" % (
            number, '<br/>'.join([commit_fmt(c) for c in commits]))


@app.route("/")
def hello():
    return "Hello World!"

if __name__ == "__main__":
    app.run(debug=True)
