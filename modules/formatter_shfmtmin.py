import logging
from ..core import common

log = logging.getLogger(__name__)
EXECUTABLES = ['shfmt']
MODULE_CONFIG = {
    'source': 'https://github.com/mvdan/sh',
    'name': 'Shfmt',
    'uid': 'shfmtmin',
    'type': 'minifier',
    'syntaxes': ['bash'],
    'exclude_syntaxes': None,
    'executable_path': '/path/to/bin/shfmt',
    'args': None,
    'config_path': None,
    'comment': 'opinionated, no config'
}


class ShfmtminFormatter(common.Module):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_cmd(self):
        executable = self.get_executable(runtime_type=None)
        if not executable:
            return None

        cmd = [executable]

        cmd.extend(self.get_args())

        cmd.extend(['--minify', '-'])

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
