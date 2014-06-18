'''Views and logic for github OAuth.'''

from flask_oauthlib.client import OAuth

def install_github_oauth(app):
    oauth = OAuth(app)
    github_auth = oauth.remote_app(
        'github',
        consumer_key=app.config['GITHUB_CLIENT_ID'],
        consumer_secret=app.config['GITHUB_CLIENT_SECRET'],
        request_token_params={'scope': 'repo,user'},
        base_url='https://api.github.com/',
        request_token_url=None,
        access_token_method='POST',
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize'
    )

    @app.route('/login')
    def login():
        return github_auth.authorize(callback=url_for('authorized', _external=True, next=request.args.get('next') or request.referrer or None))


    @app.route('/logout')
    def logout():
        session.pop('token', None)
        return redirect(url_for('index'))


    @app.route('/oauth_callback')
    @github_auth.authorized_handler
    def authorized(resp):
        next_url = request.args.get('next') or url_for('index')
        if resp is None:
            return 'Access denied: reason=%s error=%s' % (
                request.args['error_reason'],
                request.args['error_description']
            )
        session['token'] = resp['access_token']
        user_info = github.get_current_user_info(session['token'])
        if not user_info:
            return "Unable to get user info."
        session['login'] = user_info['login']
        return redirect(next_url)


    @github_auth.tokengetter
    def get_github_oauth_token():
        token = session.get('token')
        if token:
            return (token, '')
        else:
            return token

