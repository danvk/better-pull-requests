better-pull-requests
====================
An improved UI for github pull requests

The key features this adds on top of github's standard Pull Request UI are:

1. Two-column diff with expandable context
2. Diffs between arbitrary commits in a pull request
3. Draft comments which can be reviewed and published in batches

It also includes nice to haves like syntax coloring and keyboard shortcuts.

Setting Up
==========

    virtualenv env                   # make a new virtualenv named 'env'.
    source env/bin/activate          # activate the env (local pip, python).
    pip install -r requirements.txt  # install the requirements in the env.
    $EDITOR secrets.json             # See below
    python app.py

Now visit http://localhost:5000/ and OAuth into your app.

Then visit ```http://localhost:5000/repo/:owner/:repo``` to view open pull
requests for any github repo. For example, you can visit
http://localhost:5000/repo/danvk/test-repo to see pull requests in my test repo.

Getting a github client secret
==============================

OAuthing into github is essential for this server, so it requires you to set up
an app on github before you run. This is easy to do! Just go
[here](https://github.com/settings/applications/new) and fill out the form on
github. Request the ```repo``` and ```user``` scopes and set the callback URL to 
```http://localhost:5000/oauth_callback```. The other fields can be anything you
like.

Once you've registered your app, you need to put its "Client Secret" in the
secrets.json file. It should look something like this:


    {
      "github_client_secret": "0123456789abcdef (40 digit hex client_secret)",
    }
