import os
import re
import logging
from string import Template
from subprocess import Popen, PIPE
from changeover.common.settings import Settings

logger = logging.getLogger(__name__)


def get_source_folders():
    """
    Returns a list of the source folders matching the template given in the
    configuration file.
    """
    conf = Settings()
    n_folders = len(conf['source']['folder_list'])
    temp = Template(conf['source']['folder'])
    regex = re.sub(temp.pattern, "(.*)", temp.template)
    return [d[0] for d in os.walk(conf['source']['watch']) \
            if (re.match(regex,d[0]) != None) and \
               (len(d[0].split("/")) >= n_folders)]


def build_sync_paths(input_path):
    """
    Build the source and target paths for rsync by replacing the
    template parameters with the correct values
    input_path: the triggered directory
    """
    conf = Settings()

    # check the length of the triggered path
    input_path_list = input_path.split('/')
    src_path_list = conf['source']['folder_list']
    if len(input_path_list) < len(src_path_list):
        raise Exception(("The triggered path (%s) is shorter than the "%input_path)+
                        ("source path (%s)!"%conf['source']['folder']))

    # match the path elements between the input and the config source path
    # and extract the template values from the triggered path
    tmp_dict = {}
    for i in range(len(src_path_list)):
        input_element = input_path_list[i]
        path_element = src_path_list[i]
        if path_element.startswith('${') and path_element.endswith('}'):
            tmp_dict[path_element[2:len(path_element)-1]] = input_element
        else:
            if path_element != input_element:
                raise Exception(("Non matching path element '%s' "%input_element)+
                                 "found in input path!")

    # substitute the template parameters in the source and target path
    source = Template(conf['source']['folder']).substitute(tmp_dict)
    target = Template(conf['target']['folder']).substitute(tmp_dict)

    # make sure the triggered path starts with the substituted config source path
    if not input_path.startswith(source):
        raise Exception("There is a mismatch between the substituted config source "+
                        "path (%s) and the triggered path (%s)!"%(input_path, source))

    # append subdirectories
    if len(input_path_list) > len(src_path_list):
        post = input_path_list[len(src_path_list):]
        source = os.path.join(source, *post)
        target = os.path.join(target, *post)

    # make sure the paths end with a trailing slash
    if not source.endswith("/"):
        source += "/"

    if not target.endswith("/"):
        target += "/"

    return source, target


def mkdir_remote(remote_dir, client_ssh):
    """
    Make the remote directory by creating each subdirectory separately.
    Change the permission of each newly created sub-directory to the target
    owner/group permission. 
    remote_dir: the remote directory that should be created
    client_ssh: reference to the ssh client object
    """
    remote_list = remote_dir.split("/")
    cmd  = "[ -d ${dir} ] || (${sudo} mkdir ${dir}"
    cmd += " && ${sudo} chown -R ${user}:${group} ${dir}"
    cmd += " && ${sudo} chmod -R ${chmod} ${dir})"
    cmd_dict = {'sudo' : "sudo" if Settings()['target']['sudo'] else "",
                'dir'  : "",
                'user' : Settings()['target']['owner'],
                'group': Settings()['target']['group'],
                'chmod': Settings()['target']['permission']
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


def run_rsync(source, target, file_list, client_ssh, options="", exclude_list=[]):
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
    file_list: the list of files that should be rsynced
    client_ssh: reference to the ssh client object
    options: additional options that should be given to rsync
    Returns a dictionary with information collected from rsync
    """
    conf = Settings()['target']
    cmd =  "${sudo} chown ${options} ${user}:${group} ${target}"
    cmd += " && ${sudo} chmod ${options} ${chmod} ${target}"
    cmd_dict = {'sudo'   : "sudo" if conf['sudo']==True else "",
                'options': "",
                'target' : "",
                'user'   : "",
                'group'  : "",
                'chmod'  : ""
               }

    # pre-chown: change the owner of the target dir to the login user
    cmd_dict['user']   = conf['user']
    cmd_dict['group']  = conf['user']
    cmd_dict['target'] = target
    cmd_dict['chmod']  = "755"
    _, _, stderr = client_ssh.exec_command(Template(cmd).substitute(cmd_dict))
    client_error = stderr.read()
    if client_error:
        raise Exception("Couldn't change the ownership of the target directory: '%s'"\
                        %client_error.rstrip())

    # rsync: call rsync
    cmd_rsync = ["rsync", options]
    cmd_rsync.append("--files-from=-")
    for exclude in exclude_list:
        cmd_rsync.append("--exclude=%s"%exclude)
    cmd_rsync.extend(["--stats", "-e", "ssh",
                      source, "%s@%s:%s"%(conf['user'], conf['host'], target)])
    proc = Popen(cmd_rsync, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate(input='\n'.join(file_list))
    if stderr:
        raise Exception("Error while calling rsync: '%s'"%stderr)

    # parse output and collect the stats information
    out_list = stdout.split("\n")
    result_dict = {'source': source,
                   'target': target}
    try:
        for line in out_list:
            if not line:
                continue
            tokens = line.split()
            if line.startswith("Number of files:"):
                result_dict['files_total'] = int(tokens[3].strip())-1
            elif line.startswith("Number of files transferred:"):
                result_dict['files_transferred'] = int(tokens[4].strip())
            elif line.startswith("Total file size:"):
                result_dict['size_total'] = int(tokens[3].strip())
            elif line.startswith("Total transferred file size:"):
                result_dict['size_transferred'] = int(tokens[4].strip())
    except:
        logger.error("Couldn't read the rsync stats: %s"%stdout)

    # post-chown: change the owner of the target dir + files to the target user
    cmd_dict['user']   = conf['owner']
    cmd_dict['group']  = conf['group']
    cmd_dict['options'] = "-R"
    #cmd_dict['target'] = " ".join(os.path.join(target,f) for f in file_list)
    cmd_dict['chmod']  = conf['permission']

    #for f in file_list:
    #    cmd_dict['target'] = os.path.join(target,f)
    #    _, _, stderr = client_ssh.exec_command(Template(cmd).substitute(cmd_dict))
    #    client_error = stderr.read()
    #    if client_error:
    #        raise Exception("Couldn't change the ownership of the target file: '%s'"\
    #                        %client_error.rstrip())

    cmd_dict['target'] = target
    _, _, stderr = client_ssh.exec_command(Template(cmd).substitute(cmd_dict))
    client_error = stderr.read()
    if client_error:
        raise Exception("Couldn't change the ownership of the target directory: '%s'"\
                        %client_error.rstrip())

    # return a dictionary with the result of rsync
    return result_dict
