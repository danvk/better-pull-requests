'''Wrapper to ensure that users are OAuthed into github.

If they are not, it redirects them to the OAuth login flow.
'''

from functools import wraps
from flask import session, url_for, redirect, request, current_app

def logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # for testing
        if 'FAKE_AUTH' in current_app.config:
            session.update(current_app.config['FAKE_AUTH'])

        if 'token' not in session:
            return redirect(url_for('login', next=request.url))
        else:
            return f(*args, **kwargs)
    return decorated_function
