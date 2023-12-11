#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# @rev          $Format:%H$ ($Format:%h$)
# @tree         $Format:%T$ ($Format:%t$)
# @date         $Format:%ci$
# @author       $Format:%an$ <$Format:%ae$>
# @copyright    Copyright (c) 2019-present, Duc Ng. (bitst0rm)
# @link         https://github.com/bitst0rm
# @license      The MIT License (MIT)

import logging
from ..core import common
from ..libs import yaml

log = logging.getLogger(__name__)
EXECUTABLES = ['hindent']
MODULE_CONFIG = {
    'source': 'https://github.com/mihaimaruseac/hindent',
    'name': 'Hindent',
    'uid': 'hindent',
    'type': 'beautifier',
    'syntaxes': ['haskell'],
    'exclude_syntaxes': None,
    "executable_path": "",
    'args': None,
    'config_path': {
        'default': 'hindent_rc.yaml'
    }
}


class HindentFormatter(common.Module):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_cmd(self):
        executable = self.get_executable(runtime_type='haskell')
        if not executable:
            return None

        cmd = [executable]

        cmd.extend(self.get_args())

        path = self.get_config_path()
        if path:
            with open(path, 'r', encoding='utf-8') as file:
                cfg_dict = yaml.safe_load(file)

                # Hindent does not have an option to
                # read external config file. We build one.
                flattened_list = []

                for key, value in cfg_dict.items():
                    if key.isupper() and isinstance(value, list):
                        for item in value:
                            flattened_list.extend(['-' + key, item])
                    elif value is None:
                        flattened_list.extend(['--' + key, 'null'])
                    elif isinstance(value, bool):
                        if value:
                            flattened_list.append('--' + key)
                    else:
                        flattened_list.extend(['--' + key, str(value)])

                cmd.extend(flattened_list)

        cmd.extend(['--'])

        log.debug('Current arguments: %s', cmd)
        cmd = self.fix_cmd(cmd)

        return cmd

    def format(self):
        cmd = self.get_cmd()
        if not self.is_valid_cmd(cmd):
            return None

        try:
            exitcode, stdout, stderr = self.exec_cmd(cmd)

            if exitcode > 0:
                log.error('File not formatted due to an error (exitcode=%d): "%s"', exitcode, stderr)
            else:
                return stdout
        except OSError:
            log.error('An error occurred while executing the command: %s', ' '.join(cmd))

        return None