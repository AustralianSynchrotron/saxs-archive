import json
from flask import render_template, request, jsonify
from changeover.server import app
from changeover.common.settings import Settings
from changeover.server import status, stats


#---------------------------------
#          web interface
#---------------------------------
@app.route('/')
@app.route('/status')
def index():
    """
    Returns the status website
    """
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
    """
    Returns the statistics website
    """
    return render_template("statistics.html",
                           detector_name = Settings()['server']['name'])

@app.route('/files')
def files():
    """
    Returns the file summary website
    """
    return render_template("files.html",
                           detector_name = Settings()['server']['name'])

@app.route('/changeover')
def changeover():
    """
    Returns the changeover website
    """
    conf = Settings()
    folders = []
    for folder in conf['source']['folder_list']:
        if folder.startswith('${') and folder.endswith('}'):
            folders.append(folder[2:len(folder)-1])

    exclude_str = ",".join(json.loads(conf['rsync']['exclude']))

    return render_template("changeover.html",
                           detector_name = conf['server']['name'],
                           source_folder = conf['source']['folder'],
                           exclude = exclude_str,
                           folders=folders)

@app.route('/settings')
def settings():
    """
    Returns the settings summary website
    """
    return render_template("settings.html",
                           detector_name = Settings()['server']['name'],
                           settings = Settings())


#---------------------------------
#         REST interface
#---------------------------------
@app.route('/rest/statistics', methods=['POST'])
def rest_stats():
    """
    Returns the aggregated statistics for the specified year, month and day
    """
    year = request.form['year'] if 'year' in request.form else None
    month = request.form['month'] if 'month' in request.form else None
    day = request.form['day'] if 'day' in request.form else None
    return jsonify(**stats.aggregate(year, month, day))

@app.route('/rest/changeover/start', methods=['POST'])
def rest_changeover_start():
    """
    Starts the changeover process thread
    """
    print request.form
    return jsonify(success=True)

@app.route('/rest/settings', methods=['GET'])
def rest_settings():
    """
    Returns the dictionary of the settings
    """
    return jsonify(**Settings())
