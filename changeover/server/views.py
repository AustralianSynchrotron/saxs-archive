import json
from flask import render_template, request, jsonify, redirect, url_for, flash
from changeover.server import app
from changeover.common.settings import Settings
from changeover.server import status, stats, files, changeoverthread


#---------------------------------
#          web interface
#---------------------------------
@app.route('/')
@app.route('/status')
def web_index():
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
def web_statistics():
    """
    Returns the statistics website
    """
    return render_template("statistics.html",
                           detector_name = Settings()['server']['name'])


@app.route('/files')
def web_files():
    """
    Returns the file summary website
    """
    return render_template("files.html",
                           detector_name = Settings()['server']['name'])


@app.route('/changeover')
def web_changeover():
    """
    Returns the changeover website. Depending whether the changeover process
    is in progress or not the user is redirected to the progress page or
    the changeover form is shown.
    """
    curr_thread = getattr(app, 'changeover_thread', None)
    if (curr_thread != None) and (curr_thread.is_alive()):
        flash("Changeover is in progress.")
        return redirect(url_for('changeover_progress'))
    else:
        conf = Settings()
        folders = []
        for folder in conf['source']['folder_list']:
            if folder.startswith('${') and folder.endswith('}'):
                folders.append(folder[2:len(folder)-1])

        exclude_str = ",".join(json.loads(conf['rsync']['exclude']))
        return render_template("changeover_form.html",
                               detector_name = conf['server']['name'],
                               source_folder = conf['source']['folder'],
                               exclude = exclude_str,
                               folders=folders)


@app.route('/changeover/progress')
def web_changeover_progress():
    """
    Returns the changeover progress website. Depending whether the changeover
    process is on-going the changeover_progress or changeover_result page is shown.
    """
    conf = Settings()
    curr_thread = getattr(app, 'changeover_thread', None)
    if (curr_thread != None) and (curr_thread.is_alive()):
        return render_template("changeover_progress.html",
                               detector_name = conf['server']['name'])
    else:
        if curr_thread != None:
            return render_template("changeover_result.html",
                                   detector_name = conf['server']['name'])
        else:
            flash("No previous changeover process was found.")
            return redirect(url_for('changeover'))


@app.route('/settings')
def web_settings():
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
    rf = request.form
    return jsonify(**stats.aggregate(rf.get('year', None),
                                     rf.get('month', None),
                                     rf.get('day', None)))


@app.route('/rest/changeover/start', methods=['POST'])
def rest_changeover_start():
    """
    Starts the changeover process thread
    """
    curr_thread = getattr(app, 'changeover_thread', None)
    if (curr_thread != None) and (curr_thread.is_alive()):
        return jsonify(success=False)
    else:
        rf = request.form
        co_params = {'folder_folders': {}}

        # read boolean values (checkboxes)
        for key in ['folder_create', 'rsync_enabled', 'rsync_checksum',
                    'rsync_compress', 'post_checksum', 'post_delete']:
                    co_params[key] = rf.get(key, False, type=bool)
        
        # read excludes
        co_params['rsync_exclude'] = rf.get('rsync_exclude', "").split(","),
                     
        # convert folders to dictionary
        for key in rf.keys():
            if (key.startswith("folder_")) and (key != "folder_create"):
                co_params['folder_folders'][key[7:]] = rf[key]

        app.changeover_thread = changeoverthread.ChangeoverThread(**co_params)
        app.changeover_thread.start()
        return jsonify(success=True)


@app.route('/rest/changeover/status', methods=['GET'])
def rest_changeover_status():
    """
    Returns the status of the changeover process
    """
    pass


@app.route('/rest/changeover/stop', methods=['POST'])
def rest_changeover_stop():
    """
    Stops the changeover process thread
    """
    pass


@app.route('/rest/settings', methods=['GET'])
def rest_settings():
    """
    Returns the dictionary of the settings
    """
    return jsonify(**Settings())


@app.route('/rest/files/folders', methods=['GET'])
def rest_files_folders():
    """
    Returns a list of the source and their associated target folders together
    with a flag that indicates if the target folder exists.
    """
    return jsonify(**files.folders())


@app.route('/rest/files/files', methods=['POST'])
def rest_files_files():
    """
    Returns a file list comparing the specified source and target folders.
    Assumes the target folder exists!
    """
    rf = request.form
    return jsonify(**files.files(rf.get('source', ""), rf.get('target', "")))
