from .. import log
from ..core import common

INTERPRETERS = ['ruby']
EXECUTABLES = ['rufo']
DOTFILES = ['.rufo']
MODULE_CONFIG = {
    'source': 'https://github.com/ruby-formatter/rufo',
    'name': 'Rufo',
    'uid': 'rufo',
    'type': 'beautifier',
    'syntaxes': ['ruby'],
    'exclude_syntaxes': None,
    'executable_path': '/path/to/bin/rufo',
    'args': None,
    'config_path': None,
    'comment': 'requires "environ": {"GEM_PATH": ["/path/to/dir/ruby"]}. opinionated, no config. requires ruby on PATH if omit interpreter_path'
}


class RufoFormatter(common.Module):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_cmd(self):
        cmd = self.get_combo_cmd(runtime_type='ruby')
        if not cmd:
            return None

        cmd.extend(['--simple-exit'])

        log.debug('Command: %s', cmd)
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
