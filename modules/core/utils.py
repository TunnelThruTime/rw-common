import os

def assure_config_files(dir_path, pkg_name, config_contents=None):
    """ Builds a user config ini file with the dir_path (if NoneType set to $HOME/.config),
        and the pkg_name for making a dir to put the file inside.

    :dir_path: 
        a string of the absolute path to mkdir for config file 
            if None function uses: `os.environ['HOME'] + '.config/'`
    :pkg_name:
        a string of the name of the dir in your dir_path that will house
        your config file, which is always 'config.ini'
    :config_contents:
        a string that is inserted as the contents of the new config file
    :returns:
        returns absolute path to the config file as a string

    """
    if isinstance(dir_path, type(None)):
        dir_path = os.environ['HOME'] + '/.config/'
    dir_conf = dir_path + pkg_name
    file_conf = dir_conf + '/config.ini'
    if not os.path.exists(dir_conf):
        os.mkdir(dir_conf)
    if not os.path.isfile(file_conf):
        if config_contents:
            with open(file_conf, 'w') as f:
                f.write(config_contents)
        else:
            with open(file_conf, 'w') as f:
                pass
    return file_conf
