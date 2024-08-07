from ..core.common import Module

INTERPRETERS = ['node']
EXECUTABLES = ['sql-formatter']
DOTFILES = []
MODULE_CONFIG = {
    'source': 'https://github.com/sql-formatter-org/sql-formatter',
    'name': 'SQL Formatter',
    'uid': 'sqlformatter',
    'type': 'beautifier',
    'syntaxes': ['sql'],
    'exclude_syntaxes': None,
    'executable_path': '/path/to/node_modules/.bin/sql-formatter',
    'args': None,
    'config_path': {
        'default': 'sql_formatter_rc.json'
    },
    'comment': 'requires node on PATH if omit interpreter_path'
}


class SqlformatterFormatter(Module):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_cmd(self):
        cmd = self.get_combo_cmd(runtime_type='node')
        if not cmd:
            return None

        path = self.get_config_path()
        if path:
            cmd.extend(['--config', path])

        return cmd

    def format(self):
        cmd = self.get_cmd()

        try:
            exitcode, stdout, stderr = self.exec_cmd(cmd)

            if exitcode > 0:
                self.print_exiterr(exitcode, stderr)
            else:
                return stdout
        except Exception as e:
            self.print_oserr(cmd, e)

        return None
