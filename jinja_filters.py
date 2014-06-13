import dateutil.parser
from datetime import datetime, timedelta
import time
import calendar
import babel.dates

def format_elapsed_time(timestamp):
    d = dateutil.parser.parse(timestamp)
    time_t = calendar.timegm(d.utctimetuple())
    now_time_t = time.time()
    elapsed_secs = now_time_t - time_t
    delta = timedelta(seconds=elapsed_secs)

    return babel.dates.format_timedelta(delta, threshold=1.2, locale='en_US') + ' ago'


def format_datetime(value, format='medium'):
    d = dateutil.parser.parse(value)
    return babel.dates.format_datetime(d, format=format, locale='en_US')


def install_handlers(app):
    app.jinja_env.filters['elapsed_time'] = format_elapsed_time
    app.jinja_env.filters['datetime'] = format_datetime
