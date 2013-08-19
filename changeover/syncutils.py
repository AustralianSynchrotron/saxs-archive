import os
import logging
from string import Template
from subprocess import Popen, PIPE

logger = logging.getLogger("settings")


def build_sync_paths(input_path_list, config):
    """
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
        target += "/."

    return source, target


def mkdir_remote(client_ssh, remote_dir, config):
    """
    """
    sudo_str = "sudo" if config['sudo'] else ""
    # check whether the remote directory already exists. If not, create it.
    remote_list = remote_dir.split("/")
    curr_dir = "/"
    for dir in remote_list:
        if dir and dir != ".":
    	    curr_dir = os.path.join(curr_dir, dir)
	    _, stdout, stderr = \
        	client_ssh.exec_command("[ -d %s ] || (%s mkdir %s \
                         && %s chown -R %s:%s %s)"%(curr_dir, sudo_str, curr_dir, sudo_str, config['user'], config['user'], curr_dir))
    #client_ssh.exec_command("%s chown -R %s:%s %s"%(sudo_str, config['user'], config['user'], remote_dir))
    return stderr.read() == ""


def run_rsync(source, target, options, config):
    """
    """
    proc = Popen(["rsync", options, "--stats", "-e ssh",
                  source, "%s@%s:%s"%(config['user'], config['host'], target)],
                  stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    if stderr != "":
        raise Exception("rsync error: %s"%stderr)
    #TODO: parse the stdout output into a dictionary
    #print stdout


def change_permissions(client_ssh, target, config):
    """
    """
    sudo_str = "sudo " if config['sudo'] else ""

    _, stdout, stderr = \
        client_ssh.exec_command("%schmod -R %s %s"%(sudo_str,
                                                    config['chmod'],
                                                    target))
    if stderr.read() != "":
        raise Exception("Couldn't change the permission: %s"%stderr.read())

    # change the ownership of the files
    _, stdout, stderr = \
        client_ssh.exec_command("%schown -R %s:%s %s"%(sudo_str,
                                                       config['owner'],
                                                       config['group'],
                                                       target))
    if stderr.read() != "":
        raise Exception("Couldn't change the ownership: %s"%stderr.read())

