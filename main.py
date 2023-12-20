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

import os
import sys
import time
import json
import logging
import zipfile
import tempfile
import traceback
import threading
from threading import Event
from datetime import datetime

import sublime
import sublime_plugin

from .core import common, configurator
from .core.wcounter import *
from .core.smanager import *
from .core.version import __version__
from .core.formatter import Formatter

log = logging.getLogger(__name__)

SYNC_SCROLL = {
    'view_pairs': [],
    'view_src': None,
    'view_dst': None,
    'view_active': None,
    'abort': False
}


def plugin_loaded():
    api = common.Base()

    api.remove_junk()
    ready = configurator.create_package_config_files()
    if ready:
        api.get_config()
        api.setup_shared_config_files()

        if api.is_quick_options_mode():
            is_enabled = api.query(common.config, False, 'quick_options', 'debug')
        else:
            is_enabled = common.config.get('debug')
        common.enable_logging() if is_enabled else common.disable_logging()
    log.info('%s version: %s (Python %s)', common.PACKAGE_NAME, __version__, '.'.join(map(str, sys.version_info[:3])))
    log.debug('Plugin initialization ' + ('succeeded.' if ready else 'failed.'))


class ShowVersionCommand(sublime_plugin.WindowCommand):
    def run(self):
        sublime.message_dialog(common.PACKAGE_NAME + '\nVersion: ' + __version__)


class OpenConfigFoldersCommand(sublime_plugin.WindowCommand, common.Base):
    def run(self):
        seen = set()

        config_dir = os.path.join(sublime.packages_path(), 'User', common.ASSETS_DIRECTORY, 'config')
        if os.path.isdir(config_dir):
            self.window.run_command('open_dir', {'dir': config_dir})
            seen.add(config_dir)

        for formatter in common.config.get('formatters', {}).values():
            for path in formatter.get('config_path', {}).values():
                if path and isinstance(path, str):
                    dir_path = self.get_pathinfo(path)['cwd']
                    if os.path.isdir(dir_path) and dir_path not in seen:
                        self.window.run_command('open_dir', {'dir': dir_path})
                        seen.add(dir_path)


class ConfigManagerCommand(sublime_plugin.WindowCommand, common.Base):
    backup_temp_dir = None

    def get_config_paths_to_zip(self):
        file_paths_to_zip = [
            self.quick_options_config_file(),
            os.path.join(sublime.packages_path(), 'User', 'Formatter.sublime-settings'),
            os.path.join(sublime.packages_path(), 'User', 'Default (' + sublime.platform().upper() + ').sublime-keymap'),
            SESSION_FILE
        ]

        config_paths = [
            path for formatter in common.config.get('formatters', {}).values()
            for path in formatter.get('config_path', {}).values()
            if path and isinstance(path, str)
        ]

        file_paths_to_zip.extend(config_paths)
        return [path for path in file_paths_to_zip if path and os.path.isfile(path)]

    def cleanup_temp_dir(self):
        if self.backup_temp_dir:
            self.backup_temp_dir.cleanup()
            self.backup_temp_dir = None

    def backup_config(self):
        self.cleanup_temp_dir()

        file_paths_to_zip = self.get_config_paths_to_zip()

        self.backup_temp_dir = tempfile.TemporaryDirectory()
        zip_file_name = 'Formatter_config_{}.zip'.format(datetime.now().strftime('%Y_%m_%d'))
        zip_file_path = os.path.join(self.backup_temp_dir.name, zip_file_name)

        try:
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in file_paths_to_zip:
                    zipf.write(file_path, file_path)
        except Exception as e:
            self.popup_message('Error during backup: %s' % e)
            self.cleanup_temp_dir()
            return

        self.window.run_command('open_dir', {'dir': self.backup_temp_dir.name})
        self.popup_message('Your backup file successfully created.', 'INFO', dialog=True)

    def restore_config(self):
        def on_done(file_path):
            file_path = file_path.strip()

            if file_path and file_path.lower().endswith('.zip') and os.path.isfile(file_path):
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall('/')
                except Exception as e:
                    self.popup_message('Error during restore: %s' % e)
                    return
                self.popup_message('Restore completed successfully.', 'INFO', dialog=True)
            else:
                self.popup_message('File not found: %s' % file_path, 'ERROR')

        self.window.show_input_panel('Enter the path to the backup zip file:', '', on_done, None, None)

    def run(self, **kwargs):
        task_type = kwargs.get('type', None)

        if task_type == 'backup':
            self.backup_config()
        elif task_type == 'restore':
            self.restore_config()


class QuickOptionsCommand(sublime_plugin.WindowCommand, common.Base):
    option_mapping = {
        'debug': 'Enable Debugging',
        'layout': 'Choose Layout',
        'enable_project_config': 'Enable Project Config',
        'format_on_unique': 'Enable Format on Unique',
        'format_on_paste': 'Enable Format on Paste',
        'format_on_save': 'Enable Format on Save',
        'new_file_on_format': 'Enable New File on Format',
        'recursive_folder_format': 'Enable Recursive Folder Format',
        'use_user_settings': 'Reset (persistent User Settings use)',
        'save_quick_options': 'Save (persistent Quick Options use)'
    }

    def run(self):
        self.options = []
        config_values = common.config.get('quick_options', {})

        for key, title in self.option_mapping.items():
            option_value = config_values.get(key, False)
            option_status = '[x]' if option_value else '[-]'
            if key == 'use_user_settings':
                option_status = '[-]' if config_values else '[x]'
            if key == 'save_quick_options':
                option_status = '[x]' if config_values and self.load_quick_options() else '[-]'
            if key in ['layout', 'format_on_paste', 'format_on_save', 'new_file_on_format'] and option_value:
                option_label = '{} {}: {}'.format(option_status, title, option_value if isinstance(option_value, str) else ', '.join(option_value))
            else:
                option_label = '{} {}'.format(option_status, title)
            self.options.append(option_label)

        self.show_main_menu()

    def show_main_menu(self):
        self.window.show_quick_panel(self.options, self.on_done)

    def show_layout_menu(self):
        layouts = ['single', '2cols', '2rows', '<< Back']
        self.window.show_quick_panel(layouts, lambda layout_index: self.on_layout_menu_done(layouts, layout_index))

    def on_layout_menu_done(self, layouts, layout_index):
        if layout_index != -1:
            layout_value = layouts[layout_index]
            if layout_value == '<< Back':
                self.show_main_menu()
            else:
                common.config.setdefault('quick_options', {})['layout'] = layout_value
                self.run()

    def show_format_on_paste_menu(self):
        uid_list = list(common.config.get('formatters', {}).keys())
        uid_list.append('<< Back')
        self.window.show_quick_panel(uid_list, lambda uid_index: self.on_format_on_paste_menu_done(uid_list, uid_index))

    def show_format_on_save_menu(self):
        uid_list = list(common.config.get('formatters', {}).keys())
        uid_list.append('<< Back')
        self.window.show_quick_panel(uid_list, lambda uid_index: self.on_format_on_save_menu_done(uid_list, uid_index))

    def on_format_on_paste_menu_done(self, uid_list, uid_index):
        if uid_index != -1:
            uid_value = uid_list[uid_index]
            if uid_value == '<< Back':
                self.show_main_menu()
            else:
                current_format_on_paste = common.config.setdefault('quick_options', {}).get('format_on_paste', [])
                if uid_value not in current_format_on_paste:
                    current_format_on_paste.append(uid_value)
                    common.config.setdefault('quick_options', {})['format_on_paste'] = current_format_on_paste
                self.run()

    def on_format_on_save_menu_done(self, uid_list, uid_index):
        if uid_index != -1:
            uid_value = uid_list[uid_index]
            if uid_value == '<< Back':
                self.show_main_menu()
            else:
                current_format_on_save = common.config.setdefault('quick_options', {}).get('format_on_save', [])
                if uid_value not in current_format_on_save:
                    current_format_on_save.append(uid_value)
                    common.config.setdefault('quick_options', {})['format_on_save'] = current_format_on_save
                self.run()

    def show_new_file_format_input(self):
        value = self.query(common.config, '', 'quick_options', 'new_file_on_format')
        self.window.show_input_panel(
            'Enter a suffix for "New File on Format" (to disable: false or spaces):',
            value if (value and isinstance(value, str)) else '',
            self.on_new_file_format_input_done, None, None
        )

    def on_new_file_format_input_done(self, user_input):
        if user_input:
            value = False if (user_input.isspace() or user_input.strip().lower() == 'false') else user_input.strip().strip('.').replace('[-]', '').replace('[x]', '')
            common.config.setdefault('quick_options', {})['new_file_on_format'] = value
        self.run()

    def save_quick_options_config(self):
        config_json = common.config.get('quick_options', {})
        self.save_qo_config_file(config_json)

    def on_done(self, index):
        if index != -1:
            selected_option = self.options[index]
            if 'Choose Layout' in selected_option:
                self.show_layout_menu()
            elif 'Enable Format on Paste' in selected_option:
                is_rff_on = self.query(common.config, False, 'quick_options', 'recursive_folder_format')
                if is_rff_on:
                    self.popup_message('Format on Paste is not compatible with an enabled Recursive Folder Format.', 'ERROR')
                    self.run()
                else:
                    self.show_format_on_paste_menu()
            elif 'Enable Format on Save' in selected_option:
                is_rff_on = self.query(common.config, False, 'quick_options', 'recursive_folder_format')
                if is_rff_on:
                    self.popup_message('Format on Save is not compatible with an enabled Recursive Folder Format.', 'ERROR')
                    self.run()
                else:
                    self.show_format_on_save_menu()
            elif 'Enable New File on Format' in selected_option:
                self.show_new_file_format_input()
            else:
                self.toggle_option_status(index)

    def toggle_option_status(self, index):
        selected_option = self.options[index]
        if '[-]' in selected_option:
            selected_option = selected_option.replace('[-]', '[x]')
            option_value = True
        else:
            selected_option = selected_option.replace('[x]', '[-]')
            option_value = False

        config_key = list(self.option_mapping.keys())[index]
        if config_key == 'use_user_settings':
            common.config['quick_options'] = {}
            self.save_qo_config_file({})
        elif config_key == 'save_quick_options':
            self.save_quick_options_config()
        else:
            if config_key == 'debug':
                if option_value:
                    common.enable_logging()
                else:
                    common.disable_logging()
            if config_key == 'format_on_unique':
                if option_value:
                    self.popup_message('Format on Unique requires at least an enabled Format on Save and/or Format on Paste in this Quick Options mode.\n\nDue to the limited UI design of Sublime Text panel, you must input your unique syntaxes through References > Package Settings > Formatter > Settings > "format_on_unique" if not already done before.', 'INFO', dialog=True)
            if config_key == 'recursive_folder_format':
                is_fos_on = self.query(common.config, [], 'quick_options', 'format_on_paste')
                if option_value and is_fos_on:
                    self.popup_message('Recursive Folder Format is not compatible with an enabled Format on Paste.', 'ERROR')
                    self.run()
                    return
            if config_key == 'recursive_folder_format':
                is_fos_on = self.query(common.config, [], 'quick_options', 'format_on_save')
                if option_value and is_fos_on:
                    self.popup_message('Recursive Folder Format is not compatible with an enabled Format on Save.', 'ERROR')
                    self.run()
                    return
            common.config.setdefault('quick_options', {})[config_key] = option_value
        self.run()

    def save_qo_config_file(self, json_data):
        file = self.quick_options_config_file()
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)


class RunFormatCommand(sublime_plugin.TextCommand, common.Base):
    def run(self, edit, **kwargs):
        # Edit object is useless here since it gets automatically
        # destroyed before the code is reached in the new thread.

        enable_project_config = self.query(common.config, False, 'quick_options', 'enable_project_config')
        if enable_project_config:
            has_cfgignore = True
        else:
            has_cfgignore = self.check_cfgignore()

        is_recursive = self.is_recursive_formatting_enabled(kwargs.get('uid', None))
        if is_recursive:
            self.run_recursive_formatting(has_cfgignore=has_cfgignore, **kwargs)
        else:
            self.run_single_formatting(has_cfgignore=has_cfgignore, **kwargs)

    def is_enabled(self):
        return not bool(self.view.settings().get('is_widget', False))

    def is_visible(self, **kwargs):
        is_debug_enabled = self.is_debug_enabled()
        common.enable_logging() if is_debug_enabled else common.disable_logging()

        is_disabled = self.query(common.config, True, 'formatters', kwargs.get('uid', None), 'disable')
        return not is_disabled

    def is_recursive_formatting_enabled(self, uid):
        if self.is_quick_options_mode():
            return self.query(common.config, False, 'quick_options', 'recursive_folder_format')
        else:
            return self.query(common.config, False, 'formatters', uid, 'recursive_folder_format', 'enable')

    def run_recursive_formatting(self, **kwargs):
        if self.view.file_name():
            with threading.Lock():
                log.debug('Starting the main thread for recursive folder formatting ...')
                recursive_format = RecursiveFormat(self.view, **kwargs)
                recursive_format_thread = threading.Thread(target=recursive_format.run)
                recursive_format_thread.start()
        else:
            self.popup_message('Please save the file first. Recursive folder formatting requires an existing file on disk, which must be opened as the starting point.', 'ERROR')

    def run_single_formatting(self, **kwargs):
        with threading.Lock():
            log.debug('Starting the main thread for single file formatting ...')
            single_format = SingleFormat(self.view, **kwargs)
            single_format_thread = threading.Thread(target=single_format.run)
            single_format_thread.start()

    def is_debug_enabled(self):
        if self.is_quick_options_mode():
            return self.query(common.config, False, 'quick_options', 'debug')
        else:
            return common.config.get('debug')


class SingleFormat(common.Base):
    def __init__(self, view, **kwargs):
        self.view = view
        self.kwargs = kwargs
        self.kwargs.update(view=self.view)
        self.success, self.failure = 0, 0
        self.cycles = []

    def run(self):
        self.print_sysinfo()
        try:
            for region in (self.view.sel() if self.has_selection() else [sublime.Region(0, self.view.size())]):
                self.kwargs.update(region=region)
                super().__init__(**self.kwargs)
                is_success = Formatter(**self.kwargs).run()
                self.cycles.append(is_success)
                self.print_status(is_success)

            if any(self.cycles):
                self.handle_successful_formatting()
            else:
                self.open_console_on_failure()
        except Exception as e:
            log.error('Error occurred: %s\n%s', e, ''.join(traceback.format_tb(e.__traceback__)))

    def has_selection(self):
        return any(not sel.empty() for sel in self.view.sel())

    def print_status(self, is_success):
        if is_success:
            self.success += 1
            log.debug('Formatting successful. 🎉😃🍰\n')
        else:
            self.failure += 1
            log.debug('Formatting failed. 💔😢💔\n')

        if common.config.get('show_statusbar'):
            self.set_status_bar_text()

    def set_status_bar_text(self):
        status_text = '{}({}) [ok:{}|ko:{}]'.format(common.PACKAGE_NAME, self.get_mode_description(short=True), self.success, self.failure)
        self.view.set_status(common.STATUS_KEY, status_text)

    def open_console_on_failure(self):
        if common.config.get('open_console_on_failure'):
            self.view.window().run_command('show_panel', {'panel': 'console', 'toggle': True})

    def handle_successful_formatting(self):
        uid = self.kwargs.get('uid', None)
        mode = 'qo' if self.is_quick_options_mode() else 'user'
        layout, suffix = self.get_layout_and_suffix(uid, mode)

        if suffix and isinstance(suffix, str):
            window = self.view.window()
            if mode == 'qo':
                window.set_layout(self.assign_layout(layout))
                window.focus_group(0)
            elif self.want_layout():
                self.setup_layout(self.view)
                window.focus_group(0)

            file_path = self.view.file_name()
            new_path = '{0}.{2}{1}'.format(*os.path.splitext(file_path) + (suffix,)) if file_path and os.path.isfile(file_path) else None
            self.view.run_command('transfer_content_view', {'path': new_path})
            sublime.set_timeout(self.undo_history, 250)

    def get_layout_and_suffix(self, uid, mode):
        if mode == 'qo':
            return (
                self.query(common.config, False, 'quick_options', 'layout'),
                self.query(common.config, False, 'quick_options', 'new_file_on_format')
            )
        else:
            return (
                self.query(common.config, False, 'layout', 'enable'),
                self.query(common.config, False, 'formatters', uid, 'new_file_on_format')
            )

    def undo_history(self):
        for _ in range(min(500, self.cycles.count(True))):
            self.view.run_command('undo')


class ReplaceContentViewCommand(sublime_plugin.TextCommand):
    def run(self, edit, result, region):
        self.view.replace(edit, sublime.Region(region[0], region[1]), result)


class TransferContentViewCommand(sublime_plugin.TextCommand, common.Base):
    def run(self, edit, **kwargs):
        path = kwargs.get('path', None)
        src_view = self.view

        dst_view = self.create_or_reuse_view(path, src_view)
        self.copy_content_and_selections(edit, src_view, dst_view)
        self.sync_scroll_views(src_view, dst_view)

        if path:
            self.save_dst_content(dst_view, path)
        else:
            log.debug('The view is an unsaved buffer and must be manually saved as a file.')
        self.show_status_on_new_file(dst_view)

    def create_or_reuse_view(self, path, src_view):
        ref_name = 'untitled-%s' % src_view.id()
        window = src_view.window()

        if path:
            # Reuse the same file
            dst_view = window.find_open_file(path)
            if dst_view:
                dst_view.run_command('select_all')
                dst_view.run_command('right_delete')
            else:
                dst_view = self.create_new_file(window, src_view.settings().get('syntax', None))
                dst_view.retarget(path)
                dst_view.set_scratch(True)
        else:
            # Reuse the same view
            dst_view = next((v for v in window.views() if v.name() == ref_name), None)
            if dst_view:
                # Reuse the same view
                dst_view.run_command('select_all')
                dst_view.run_command('right_delete')
            else:
                dst_view = self.create_new_file(window, src_view.settings().get('syntax', None))
                dst_view.set_name(ref_name)
                dst_view.set_scratch(False)

        return dst_view

    def create_new_file(self, window, syntax=None):
        if self.want_layout():
            window.focus_group(1)
        dst_view = window.new_file(syntax=syntax)
        return dst_view

    def copy_content_and_selections(self, edit, src_view, dst_view):
        dst_view.insert(edit, 0, src_view.substr(sublime.Region(0, src_view.size())))

        selections = list(src_view.sel())
        dst_view.sel().clear()
        dst_view.sel().add_all(selections)

        dst_view.set_viewport_position(src_view.viewport_position(), False)
        src_view.window().focus_view(dst_view)

    def sync_scroll_views(self, src_view, dst_view):
        SYNC_SCROLL['view_pairs'].append([src_view, dst_view])
        SYNC_SCROLL['view_pairs'] = self.get_unique(SYNC_SCROLL['view_pairs'])

    def save_dst_content(self, view, path):
        allcontent = view.substr(sublime.Region(0, view.size()))
        try:
            with open(path, 'w', encoding='utf-8') as file:
                file.write(allcontent)
        except OSError as e:
            log.error('Could not save file: %s\n%s', path, e)
            self.popup_message('Could not save file:\n' + path + '\nError mainly appears due to a lack of necessary permissions.', 'ERROR')

    def show_status_on_new_file(self, view):
        if view.is_loading():
            sublime.set_timeout(lambda: self.show_status_on_new_file(view), 250)
        else:
            if common.config.get('show_statusbar'):
                view.window().set_status_bar_visible(True)
                view.set_status(common.STATUS_KEY, self.view.get_status(common.STATUS_KEY))


class RecursiveFormat(common.Base):
    CONTEXT = {
        'entry_view': None,
        'new_view': None,
        'kwargs': None,
        'cwd': None,
        'filelist': [],
        'filelist_length': 0,
        'current_index': 0,
        'success_count': 0,
        'failure_count': 0,
        'mode_description': None
    }

    def __init__(self, view, **kwargs):
        self.view = view
        self.kwargs = kwargs

    def run(self):
        self.print_sysinfo()
        try:
            cwd = self.get_current_working_directory()
            filelist = self.get_recursive_files(cwd)

            self.prepare_context(cwd, filelist)
            self.process_files()

        except Exception as e:
            self.handle_error(e)

    def get_current_working_directory(self):
        return self.get_pathinfo(self.view.file_name())['cwd']

    def get_recursive_files(self, cwd):
        items = self.get_recursive_format_items()
        return self.get_recursive_filelist(
            cwd,
            items.get('exclude_folders_regex', []),
            items.get('exclude_files_regex', []),
            items.get('exclude_extensions', [])
        )

    def get_recursive_format_items(self):
        uid = self.kwargs.get('uid', None)
        return self.query(common.config, {}, 'formatters', uid, 'recursive_folder_format')

    def prepare_context(self, cwd, filelist):
        self.CONTEXT.update({
            'entry_view': self.view,
            'new_view': None,
            'kwargs': self.kwargs,
            'cwd': cwd,
            'filelist': filelist,
            'filelist_length': len(filelist),
            'current_index': 0,
            'success_count': 0,
            'failure_count': 0,
            'mode_description': self.get_mode_description(short=True)
        })

    def process_files(self):
        self.open_next_file()

    def open_next_file(self):
        # Loop files sequentially
        if self.CONTEXT['current_index'] < self.CONTEXT['filelist_length']:
            file_path = self.CONTEXT['filelist'][self.CONTEXT['current_index']]
            new_view = self.CONTEXT['entry_view'].window().open_file(file_path)
            self.CONTEXT['current_index'] += 1

            # open_file() is asynchronous. Use EventListener on_load() to catch
            # the returned view when the file is finished loading.
            if new_view.is_loading():
                self.CONTEXT['new_view'] = new_view
            else:
                self.next_thread(new_view, is_ready=True)

    def next_thread(self, new_view, is_ready=False):
        def format_completed(is_success):
            self.post_recursive_format(new_view, is_success)
            if is_ready and is_success:
                new_view.run_command('undo')
            elif self.CONTEXT['entry_view'] != new_view:
                new_view.set_scratch(True)
                new_view.close()

            if self.CONTEXT['current_index'] == self.CONTEXT['filelist_length']:
                # Handle the last file
                self.handle_formatting_completion()

            self.open_next_file()

        thread = SequenceFormatThread(new_view, callback=format_completed, **self.CONTEXT['kwargs'])
        thread.start()

    def post_recursive_format(self, new_view, is_success):
        new_cwd = self.get_post_format_cwd(is_success)
        self.show_result(is_success)
        self.save_formatted_file(new_view, new_cwd, is_success)

    def get_post_format_cwd(self, is_success):
        base_directory = self.CONTEXT['cwd']
        sub_directory = common.RECURSIVE_SUCCESS_DIRECTORY if is_success else common.RECURSIVE_FAILURE_DIRECTORY
        return os.path.join(base_directory, sub_directory)

    def show_result(self, is_success):
        if is_success:
            self.CONTEXT['success_count'] += 1
            log.debug('Formatting successful. 🎉😃🍰\n')
        else:
            self.CONTEXT['failure_count'] += 1
            log.debug('Formatting failed. 💔😢💔\n')

    def save_formatted_file(self, new_view, new_cwd, is_success):
        file_path = new_view.file_name()
        new_file_path = self.generate_new_file_path(file_path, new_cwd, is_success)
        cwd = self.get_pathinfo(new_file_path)['cwd']

        try:
            os.makedirs(cwd, exist_ok=True)
            text = new_view.substr(sublime.Region(0, new_view.size()))
            with open(new_file_path, 'w', encoding='utf-8') as f:
                f.write(text)
        except OSError as e:
            self.handle_error(e, cwd, new_file_path)

    def generate_new_file_path(self, file_path, new_cwd, is_success):
        new_file_path = file_path.replace(self.CONTEXT['cwd'], new_cwd, 1)
        if is_success:
            suffix = self.get_new_file_suffix()
            if suffix and isinstance(suffix, str):
                new_file_path = '{0}.{2}{1}'.format(*os.path.splitext(new_file_path) + (suffix,))
        return new_file_path

    def get_new_file_suffix(self):
        if self.is_quick_options_mode():
            return self.query(common.config, False, 'quick_options', 'new_file_on_format')
        else:
            uid = self.CONTEXT['kwargs'].get('uid', None)
            return self.query(common.config, False, 'formatters', uid, 'new_file_on_format')

    def handle_formatting_completion(self):
        self.update_status_bar()
        self.open_console_on_failure()
        self.show_completion_message()
        self.reset_context()

    def update_status_bar(self):
        if common.config.get('show_statusbar'):
            current_view = self.get_current_view()
            current_view.window().set_status_bar_visible(True)
            status_text = self.generate_status_text()
            current_view.set_status(common.STATUS_KEY, status_text)

    def get_current_view(self):
        return sublime.active_window().active_view()

    def generate_status_text(self):
        return '{}({}) [total:{}|ok:{}|ko:{}]'.format(
            common.PACKAGE_NAME, self.CONTEXT['mode_description'],
            self.CONTEXT['filelist_length'],
            self.CONTEXT['success_count'],
            self.CONTEXT['failure_count']
        )

    def open_console_on_failure(self):
        if common.config.get('open_console_on_failure') and self.CONTEXT['failure_count'] > 0:
            current_view = self.get_current_view()
            current_view.window().run_command('show_panel', {'panel': 'console', 'toggle': True})

    def show_completion_message(self):
        ok = self.CONTEXT['success_count']
        ko = self.CONTEXT['failure_count']
        total = self.CONTEXT['filelist_length']
        success_rate = '{:.2f}'.format((ok / total) * 100)
        self.popup_message('Formatting COMPLETED!\n\nOK: %s\nKO: %s\nTotal: %s\nSuccess Rate: %s%%\n\nPlease check the results in:\n%s' % (ok, ko, total, success_rate, self.CONTEXT['cwd']), 'INFO', dialog=True)

    def reset_context(self):
        for key, value in self.CONTEXT.items():
            if isinstance(value, list):
                self.CONTEXT[key] = []
            elif isinstance(value, int):
                self.CONTEXT[key] = 0
            else:
                self.CONTEXT[key] = None
        # Reset and end

    def handle_error(self, error, cwd=None, file_path=None):
        log.error('Error occurred: %s\n%s', error, ''.join(traceback.format_tb(error.__traceback__)))
        if cwd and (error.errno != os.errno.EEXIST):
            log.error('Could not create directory: %s', cwd)
            self.popup_message('Could not create directory: %s\nError mainly appears due to a lack of necessary permissions.' % cwd, 'ERROR')
        if file_path:
            log.error('Could not save file: %s', file_path)
            self.popup_message('Could not save file: %s\nError mainly appears due to a lack of necessary permissions.' % file_path, 'ERROR')


class SequenceFormatThread(threading.Thread, common.Base):
    def __init__(self, view, callback, **kwargs):
        self.view = view
        self.kwargs = kwargs
        self.callback = callback
        self.is_success = False
        threading.Thread.__init__(self)
        self.lock = threading.Lock()

    def run(self):
        try:
            with self.lock:
                region = sublime.Region(0, self.view.size())
                uid = self.kwargs.get('uid', None)
                syntax = self.get_assigned_syntax(self.view, uid, region)
                exclude_syntaxes = self.query(common.config, [], 'formatters', uid, 'recursive_folder_format', 'exclude_syntaxes')
                if not syntax or syntax in exclude_syntaxes:
                    if not syntax:
                        scope = self.query(common.config, [], 'formatters', uid, 'syntaxes')
                        log.warning('Syntax out of the scope. Plugin scope: %s, ID: %s, File syntax: %s, File: %s', scope, uid, syntax, self.view.file_name())
                    self.callback(False)
                else:
                    self.kwargs.update({
                        'view': self.view,
                        'region': region
                    })
                    self.is_success = Formatter(**self.kwargs).run()
                    self.callback(self.is_success)
        except Exception as e:
            log.error('Error occurred: %s\n%s', e, ''.join(traceback.format_tb(e.__traceback__)))


class FormatterListener(sublime_plugin.EventListener, common.Base):
    def __init__(self, *args, **kwargs):
        self.running = threading.Event()
        self.scroll_lock = threading.Lock()
        self.scroll_thread = None

    def on_load(self, view):
        if view == RecursiveFormat.CONTEXT['new_view']:
            RecursiveFormat(view).next_thread(view, is_ready=False)

    def on_activated(self, view):
        window = view.window()
        if self.query(common.config, False, 'layout', 'sync_scroll'):
            do_run = any(view in view_pair for view_pair in SYNC_SCROLL['view_pairs'])
            self.running.set() if do_run else self.running.clear()  # control pause/resume scrolling

            if window and self.want_layout() and window.num_groups() == 2 and len(SYNC_SCROLL['view_pairs']) > 0:
                for view_pair in SYNC_SCROLL['view_pairs']:
                    if view in view_pair:
                        SYNC_SCROLL['view_src'], SYNC_SCROLL['view_dst'] = view_pair
                        SYNC_SCROLL['view_active'] = 'src' if view == SYNC_SCROLL['view_src'] else 'dst'
                        break
                self.start_scroll_thread()

    def start_scroll_thread(self):
        if not self.scroll_thread or not self.scroll_thread.is_alive():
            self.scroll_thread = threading.Thread(target=self.sync_scroll)
            self.scroll_thread.start()
            log.debug('Starting a thread for scroll synchronization.')

    @common.run_once
    def sync_scroll(self, *args, **kwargs):
        with self.scroll_lock:
            self.running.set()  # start running
            while not SYNC_SCROLL['abort']:
                if not self.running.is_set():
                    log.debug('Scroll synchronization paused.')
                    self.running.wait()  # pause/resume
                if SYNC_SCROLL['view_active'] and SYNC_SCROLL['view_dst'] and SYNC_SCROLL['view_src']:
                    if SYNC_SCROLL['view_active'] == 'src':
                        SYNC_SCROLL['view_dst'].set_viewport_position(SYNC_SCROLL['view_src'].viewport_position(), False)
                    else:
                        SYNC_SCROLL['view_src'].set_viewport_position(SYNC_SCROLL['view_dst'].viewport_position(), False)
                time.sleep(0.25)

    def set_abort_sync_scroll(self):
        SYNC_SCROLL['abort'] = True
        if self.scroll_thread and self.scroll_thread.is_alive():
            self.running.clear()
            self.scroll_thread = None

    def on_pre_close(self, view):
        window = view.window()
        if window and self.want_layout() and window.num_groups() == 2 and len(SYNC_SCROLL['view_pairs']) > 0:
            if self.query(common.config, False, 'layout', 'sync_scroll'):
                for view_pair in SYNC_SCROLL['view_pairs']:
                    if view in view_pair:
                        # Remove pair for sync scroll
                        SYNC_SCROLL['view_pairs'].remove(view_pair)
                        break

            # Auto switching to single layout upon closing the latest view
            group, _ = window.get_view_index(view)
            if len(window.views_in_group(group)) == 1:
                sublime.set_timeout(lambda: window.set_layout(self.assign_layout('single')), 0)

    def on_post_text_command(self, view, command_name, args):
        if command_name in ['paste', 'paste_and_indent']:
            self._on_paste_or_save(view, opkey='format_on_paste')
            return None

    def on_pre_save(self, view):
        self._on_paste_or_save(view, opkey='format_on_save')

    def _on_paste_or_save(self, view, opkey=None):
        if not opkey:
            return None

        unique = common.config.get('format_on_unique', None)
        is_qo_mode = self.is_quick_options_mode()
        is_fou_on = self.query(common.config, False, 'quick_options', 'format_on_unique')

        if unique and isinstance(unique, dict) and ((is_qo_mode and is_fou_on) or unique.get('enable', False)):
            self._on_paste_or_save__unique(view, unique, opkey)
        else:
            self._on_paste_or_save__regular(view, opkey)

    def _on_paste_or_save__unique(self, view, unique, opkey):
        def are_unique_values(unique):
            flat_values = [value for key, values_list in unique.items() if key != 'enable' for value in values_list]
            return (len(flat_values) == len(set(flat_values)))

        formatters = common.config.get('formatters')

        if are_unique_values(unique):
            for uid, value in unique.items():
                if uid == 'enable':
                    continue

                v = self.query(formatters, None, uid)
                if self._on_paste_or_save__should_skip_formatter(uid, v, opkey):
                    continue

                syntax = self._on_paste_or_save__get_syntax(view, uid)
                if syntax in value:
                    SingleFormat(view, uid=uid).run()
                    break
        else:
            self.popup_message('There are duplicate syntaxes in your "format_on_unique" option setting. Please sort them out.', 'ERROR')

    def _on_paste_or_save__regular(self, view, opkey):
        seen = set()
        formatters = common.config.get('formatters')

        for uid, value in formatters.items():
            if self._on_paste_or_save__should_skip_formatter(uid, value, opkey):
                continue

            syntax = self._on_paste_or_save__get_syntax(view, uid)
            if syntax in value.get('syntaxes', []) and syntax not in seen:
                log.debug('"%s" enabled for ID: %s, using syntax: %s', opkey, uid, syntax)
                SingleFormat(view, uid=uid).run()
                seen.add(syntax)

    def _on_paste_or_save__should_skip_formatter(self, uid, value, opkey):
        is_qo_mode = self.is_quick_options_mode()
        is_rff_on = self.query(common.config, False, 'quick_options', 'recursive_folder_format')

        if not isinstance(value, dict) or value.get('disable', True):
            return True

        if (is_qo_mode and uid not in self.query(common.config, [], 'quick_options', opkey)) or (not is_qo_mode and not value.get(opkey, False)):
            return True

        if (is_qo_mode and is_rff_on) or (not is_qo_mode and self.query(value, False, 'recursive_folder_format', 'enable')):
            mode = 'Quick Options' if is_qo_mode else 'User Settings'
            log.info('%s mode: %s has the "%s" option enabled, which is incompatible with "recursive_folder_format" mode.', mode, uid, opkey)
            return True

        return False

    def _on_paste_or_save__get_syntax(self, view, uid):
        is_selected = any(not sel.empty() for sel in view.sel())

        if is_selected:
            # Selections: find the first non-empty region or use the first region if all are empty
            region = next((region for region in view.sel() if not region.empty()), view.sel()[0])
        else:
            # Entire file
            region = sublime.Region(0, view.size())

        syntax = self.get_assigned_syntax(view=view, uid=uid, region=region)
        return syntax

    def on_post_save(self, view):
        if common.config.get('debug') and common.config.get('dev'):
            # For development only
            self.set_abort_sync_scroll()
            self.reload_modules()  # might need hit save twice for python < 3.4 (imp.reload upstream bug)
            self.sync_scroll.reset_run()
