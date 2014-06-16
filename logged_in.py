'''Wrapper to ensure that users are OAuthed into github.'''

from functools import wraps
from flask import session, url_for, redirect, request

def logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'token' not in session:
            return redirect(url_for('login', next=request.url))
        else:
            return f(*args, **kwargs)
    return decorated_function
