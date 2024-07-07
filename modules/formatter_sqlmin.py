import sublime
from ..libs.sqlmin import sqlmin
from .. import log
from ..core import common

DOTFILES = []
MODULE_CONFIG = {
    'source': 'https://github.com/bitst0rm',
    'name': 'SQLMin',
    'uid': 'sqlmin',
    'type': 'minifier',
    'syntaxes': ['sql'],
    'exclude_syntaxes': None,
    'executable_path': None,
    'args': None,
    'config_path': {
        'default': 'sqlmin_rc.json'
    },
    'comment': 'build-in, no executable'
}


class SqlminFormatter(common.Module):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def format(self):
        path = self.get_config_path()
        json = {}
        if path:
            with open(path, 'r', encoding='utf-8') as file:
                data = file.read()
            json = sublime.decode_value(data)
            log.debug('Command: %s', json)

        try:
            text = self.get_text_from_region(self.region)
            output = sqlmin.minify(text, json)
            exitcode = output['code']
            result = output['result']

            if exitcode > 0:
                self.print_exiterr(exitcode, result)
            else:
                return result
        except OSError:
            self.print_oserr(json)

        return None
