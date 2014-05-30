import github
from flask import Flask
app = Flask(__name__)

@app.route("/pulls/<user>/<repo>")
def pulls(user, repo):
    pull_requests = github.get_pull_requests(user, repo)
    def pr_fmt(pr):
        return "#%s %s (%s)" % (pr['number'], pr['title'], pr['user.login'])

    return "Pull requests:<br/>%s" % '<br/>'.join([pr_fmt(p) for p in pull_requests])

@app.route("/")
def hello():
    return "Hello World!"

if __name__ == "__main__":
    app.run(debug=True)
