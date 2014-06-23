better-pull-requests
====================
An improved UI for github pull requests

The key features this adds on top of github's standard Pull Request UI are:

1. Two-column diff with expandable context
2. Diffs between arbitrary commits in a pull request
3. Draft comments which can be reviewed and published in batches

It also includes nice to haves like syntax coloring and keyboard shortcuts.

This tool is implemented using the github API and is designed to interoperate
with the code review tools on github.com. It's possible to do a code review
where one of the parties uses github's tools and the other does not. This also
lets you continue to use other tools built around github's Pull Requests, e.g.
Jenkins.

Setting Up
==========

    virtualenv env                   # make a new virtualenv named 'env'.
    source env/bin/activate          # activate the env (local pip, python).
    pip install -r requirements.txt  # install the requirements in the env.
    cp config.template app.cfg
    $EDITOR app.cfg                  # See notes below
    export BETTER_PR_CONFIG=app.cfg
    python app.py

Now visit http://localhost:5000/ and OAuth into your app.

Then visit ```http://localhost:5000/:owner/:repo/pulls``` to view open pull
requests for any github repo. For example, you can visit
http://localhost:5000/danvk/test-repo/pulls to see pull requests in my test repo.

Getting a github client secret
==============================

OAuthing into github is essential for this server, so it requires you to set up
an app on github before you run. This is easy to do! Just go
[here](https://github.com/settings/applications/new) and fill out the form on
github. Request the ```repo``` and ```user``` scopes and set the callback URL to 
```http://localhost:5000/oauth_callback```. The other fields can be anything you
like.

Once you've registered your app, you need to put its ID and secret into a
configuration. The provided config.template file shows you what this should
look like.

Testing
=======

To check for silly errors and run the unit tests:

    pylint -E *.py
    python *_test.py

gitcritic also has a simple golden screenshot test. To use it, install casperjs
(e.g. "brew install casperjs" on Mac OS X) and run:

    export BETTER_PR_CONFIG=testing.config; python app.py
    casperjs test pdiff-tests/*.js
