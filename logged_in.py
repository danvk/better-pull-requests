'''Wrapper to ensure that users are OAuthed into github.'''

from functools import wraps
from flask import session, url_for, redirect, request, current_app

def logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # for testing
        if current_app.config['FAKE_AUTH']:
            session.update(current_app.config['FAKE_AUTH'])

        if 'token' not in session:
            return redirect(url_for('login', next=request.url))
        else:
            return f(*args, **kwargs)
    return decorated_function
