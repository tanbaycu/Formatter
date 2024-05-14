import logging
from ..core import common

log = logging.getLogger(__name__)
INTERPRETERS = ['node']
EXECUTABLES = ['ts-standard']
MODULE_CONFIG = {
    'source': 'https://github.com/standard/ts-standard',
    'name': 'TS Standard',
    'uid': 'tsstandard',
    'type': 'beautifier',
    'syntaxes': ['ts'],
    'exclude_syntaxes': None,
    'executable_path': '/path/to/node_modules/.bin/ts-standard',
    'args': None,
    'config_path': None,
    'comment': 'requires node on PATH if omit interpreter_path. opinionated, no config'
}


class TsstandardFormatter(common.Module):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_cmd(self):
        cmd = self.get_combo_cmd(runtime_type='node')
        if not cmd:
            return None

        cmd.extend(['--fix', '--stdin', '-'])

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
                self.print_exiterr(exitcode, stderr)
            else:
                return stdout
        except OSError:
            self.print_oserr(cmd)

        return None
