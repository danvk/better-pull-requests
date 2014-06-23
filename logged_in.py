'''Wrapper to ensure that users are OAuthed into github.

If they are not, it redirects them to the OAuth login flow.
'''

import re

from functools import wraps
from flask import session, url_for, redirect, request, current_app

def logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        url = request.url

        # for testing
        if 'FAKE_AUTH' in current_app.config:
            session.update(current_app.config['FAKE_AUTH'])
        if request.args.get('force_login'):
            del session['token']
            url = re.sub(r'[?&]force_login=[^&]+', '', url)

        if 'token' not in session:
            return redirect(url_for('login', next=url))
        else:
            return f(*args, **kwargs)
    return decorated_function
