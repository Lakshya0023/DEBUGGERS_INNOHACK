import sys
import os

# Add root directory to python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.server import app

class VercelPathFixMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        raw_uri = (
            environ.get('HTTP_X_MATCHED_PATH')
            or environ.get('HTTP_X_NOW_ROUTE_MATCHES')
            or environ.get('REQUEST_URI')
            or environ.get('RAW_URI')
            or ''
        )
        path_info = environ.get('PATH_INFO', '')

        # If Vercel set PATH_INFO directly to the function file name or /api, resolve it
        if path_info in ('/api/index.py', '/api/index', '/api', '/api/'):
            if raw_uri and not raw_uri.startswith('/api/index'):
                clean_path = raw_uri.split('?')[0]
                environ['PATH_INFO'] = clean_path if clean_path else '/'
            else:
                environ['PATH_INFO'] = '/'

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)

# Vercel entrypoint
handler = app
