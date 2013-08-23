from flask import render_template
from changeover.server import app
from changeover.common.settings import Settings

@app.route('/')
def index():
    return render_template("index.html",
                           detector_name = Settings()['server_name'])
