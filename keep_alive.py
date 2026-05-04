from flask import Flask
from threading import Thread
import os
import logging
import secrets

# Disable Flask default logging to keep terminal clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('', static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET', secrets.token_hex(24))

# Register Dashboard Blueprint
from dashboard import dashboard_bp
app.register_blueprint(dashboard_bp)


@app.route('/health')
def health():
    return "I'm alive"


def run():
    # Render provides the PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True  # Ensure thread dies when main process exits
    t.start()
    print(f"Dashboard & keep-alive server started on port {os.environ.get('PORT', 8080)}")
