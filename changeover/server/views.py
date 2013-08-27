from flask import render_template, jsonify
from changeover.server import app
from changeover.common.settings import Settings
from changeover.server import status
import json
import random

@app.route('/')
@app.route('/status')
def index():
    conf = Settings()
    rsync_status = status.rsync_running()
    ssh_status = status.ssh_connected()

    return render_template("status.html",
                            detector_name = conf['server']['name'],
                            rsync_running = rsync_status['runs'],
                            rsync_pid = rsync_status['pid'],
                            rsync_uptime = rsync_status['uptime'],
                            ssh_connected = ssh_status['connected'],
                            ssh_target = conf['target']['host'],
                            ssh_error_msg = ssh_status['error_msg']
                           )


@app.route('/statistics')
def statistics():
    return render_template("statistics.html",
                           detector_name = Settings()['server']['name'])


@app.route('/files')
def files():
    return render_template("files.html",
                           detector_name = Settings()['server']['name'])


@app.route('/changeover')
def changeover():
    return render_template("changeover.html",
                           detector_name = Settings()['server']['name'])


@app.route('/rest/statistics/data_per_day', methods=['POST'])
def rest_stats_data_per_day():
    result = []
    for i in range(48):
        result.append({'bin': i, 'value': random.random()})
    return json.dumps(result)

@app.route('/rest/statistics/number_files_per_day', methods=['POST'])
def rest_stats_number_files_per_day():
    result = []
    for i in range(48):
        result.append({'bin': i, 'value': int(random.random()*40)})
    return json.dumps(result)
