import os
import logging
from string import Template
from subprocess import Popen, PIPE

logger = logging.getLogger(__name__)

def build_sync_paths(input_path_list, config):
    """
    Build the source and target paths for rsync by replacing the
    template parameters with the correct values
    input_path_list: the triggered directory split into a list of src_folder_list
    config: the configuration dictionary
    """
    # match the path elements between the input and the config source path
    # and extract the template values from the triggered path
    tmp_dict = {}
    for i in range(len(config['src_folder_list'])):
        input_element = input_path_list[i]
        path_element = config['src_folder_list'][i]
        if path_element.startswith('${') and path_element.endswith('}'):
            tmp_dict[path_element[2:len(path_element)-1]] = input_element
        else:
            if path_element != input_element:
                raise Exception("Non matching path element '%s' \
                                 found in input path!"%input_element)

    # substitute the template parameters in the source and target path
    source = Template(config['src_folder']).substitute(tmp_dict)
    target = Template(config['tar_folder']).substitute(tmp_dict)

    # make sure the paths end with a trailing slash
    if not source.endswith("/"):
        source += "/"

    if not target.endswith("/"):
        target += "/"

    return source, target


def mkdir_remote(remote_dir, client_ssh, config):
    """
    Make the remote directory by creating each subdirectory separately.
    Change the permission of each newly created sub-directory to the target
    owner/group permission. 
    remote_dir: the remote directory that should be created
    client_ssh: reference to the ssh client object
    config: reference to the config object
    """
    remote_list = remote_dir.split("/")
    cmd  = "[ -d ${dir} ] || (${sudo} mkdir ${dir}"
    cmd += " && ${sudo} chown -R ${user}:${group} ${dir}"
    cmd += " && ${sudo} chmod -R ${chmod} ${dir})"
    cmd_dict = {'sudo' : "sudo" if config['sudo'] else "",
                'dir'  : "",
                'user' : config['owner'],
                'group': config['group'],
                'chmod': config['chmod']
               }

    # loop over all subdirectories. If the subdirectory doesn't exist, create it
    total_dir = "/"
    for curr_dir in remote_list:
        if not curr_dir:
            continue

        # build the command line
        total_dir = os.path.join(total_dir, curr_dir)
        cmd_dict['dir'] = total_dir

        # execute the ssh command
        _, _, stderr = client_ssh.exec_command(Template(cmd).substitute(cmd_dict))
        client_error = stderr.read()
        if client_error:
            raise Exception("Couldn't create target directory: '%s'"\
                             %client_error.rstrip())


def run_rsync(source, target, client_ssh, config, options=""):
    """
    Run rsync in order to copy the files from the detector server to the
    archive server. The process is done in three steps:
    1) Change the owner of the target directory to the user rsync uses to
       login to the archive server
    2) Call rsync to copy the data from the detector server to the archive
    3) Change the owner of the target directory back to the owner and group
       specified in the configuration file
    source: the source path on the detector server
    target: the target path on the archive server
    client_ssh: reference to the ssh client object
    config: reference to the config object
    options: additional options that should be given to rsync
    Returns a dictionary with information collected from rsync
    """
    cmd =  "${sudo} chown -R ${user}:${group} ${dir}"
    cmd += " && ${sudo} chmod -R ${chmod} ${dir}"
    cmd_dict = {'sudo' : "sudo" if config['sudo'] else "",
                'dir'  : target,
                'user' : "",
                'group': "",
                'chmod': config['chmod']
               }

    # pre-chown: change the owner of the target dir + files to the login user
    cmd_dict['user'] = config['user']
    cmd_dict['group'] = config['user']
    _, _, stderr = client_ssh.exec_command(Template(cmd).substitute(cmd_dict))
    client_error = stderr.read()
    if client_error:
        raise Exception("Couldn't change the ownership of the target directory: '%s'"\
                        %client_error.rstrip())

    # rsync: call rsync and collect the stats information
    proc = Popen(["rsync", options, "--stats", "-e ssh",
                  source, "%s@%s:%s"%(config['user'], config['host'], target)],
                  stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    if stderr:
        raise Exception("Error while calling rsync: '%s'"%stderr)

    out_list = stdout.split("\n")
    try:
        result_dict = {'files_total': int((out_list[1].split(':'))[1].strip())-1,
                       'files_transfered': int((out_list[2].split(':'))[1].strip()),
                       'bytes_sent': int((out_list[10].split(':'))[1].strip()),
                       'bytes_received': int((out_list[11].split(':'))[1].strip())
                      }
    except:
        logger.error("Couldn't read the rsync stats: %s"%stdout)
        result_dict = {}

    # post-chown: change the owner of the target dir + files to the target user
    cmd_dict['user'] = config['owner']
    cmd_dict['group'] = config['group']
    _, _, stderr = client_ssh.exec_command(Template(cmd).substitute(cmd_dict))
    client_error = stderr.read()
    if client_error:
        raise Exception("Couldn't change the ownership of the target directory: '%s'"\
                        %client_error.rstrip())

    # return a dictionary with the result of rsync
    return result_dict
