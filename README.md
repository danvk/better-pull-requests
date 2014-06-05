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
    python app.py
