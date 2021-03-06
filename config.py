'''Flask app configuration.

Pass a config file via the BETTER_PR_CONFIG environment variable.
See config.template for an example.
'''

import sys
import logging

from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension

import jinja_filters

class BasicConfig:
    DEBUG_TB_INTERCEPT_REDIRECTS=False  # no interstitial on redirects

def create_app():
    app = Flask(__name__)
    app.config.from_object(BasicConfig)
    app.config.from_envvar('BETTER_PR_CONFIG')
    toolbar = DebugToolbarExtension(app)
    jinja_filters.install_handlers(app)

    if not (app.config['GITHUB_CLIENT_SECRET']
            and app.config['GITHUB_CLIENT_ID']
            and app.config['ROOT_URI']):
        sys.stderr.write(
        'You need to fill out a config file before running this server.\n' +
        'See README.md for details.\n\n')
        sys.exit(1)

    if app.config.get('LOG_FILE'):
        file_handler = logging.FileHandler(app.config['LOG_FILE'])
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.DEBUG)
        log.addHandler(file_handler)
    else:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        app.logger.addHandler(handler)
        for logname in ['github', '']:
            log = logging.getLogger(logname)
            log.setLevel(logging.DEBUG)
            log.addHandler(handler)

    return app
