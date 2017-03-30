# -*- coding: utf-8 -*-

# Copyright 2015 Donne Martin. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

from __future__ import print_function

import os
import platform
import subprocess
import sys

import click
from prompt_toolkit import AbortAction, Application, CommandLineInterface
from prompt_toolkit.filters import Always
from prompt_toolkit.interface import AcceptAction
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.shortcuts import create_default_layout, create_eventloop
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from .__init__ import __version__
from .completer import Completer
from .hacker_news_cli import HackerNewsCli
from .keys import KeyManager
from .style import StyleFactory
from .toolbar import Toolbar
from .utils import TextUtils


class Haxor(object):
    """Encapsulate the Hacker News CLI.

    :type cli: :class:`prompt_toolkit.CommandLineInterface`
    :param cli: An instance of `prompt_toolkit.CommandLineInterface`.

    :type CMDS_ENABLE_PAGINATE: list (const)
    :param CMDS_ENABLE_PAGINATE: A list of commands that kick off pagination.

    :type CMDS_NO_PAGINATE: list (const)
    :param CMDS_NO_PAGINATE: A list of commands that disable pagination.

    :type completer: :class:`prompt_toolkit.completer`
    :param completer: An instance of `prompt_toolkit.completer`.

    :type hacker_news_cli: :class:`hacker_news_cli.HackerNewsCli`
    :param hacker_news_cli: An instance of `hacker_news_cli.HackerNewsCli`.

    :type key_manager: :class:`prompt_toolkit.key_binding.manager.
        KeyBindingManager`
    :param key_manager: An instance of `prompt_toolkit.key_binding.manager.
        KeyBindingManager`.

    :type PAGINATE_CMD: str (const)
    :param PAGINATE_CMD: The command to enable pagination.

    :type paginate_comments: bool
    :param paginate_comments: Determines whether to paginate
            comments.

    :type text_utils: :class:`util.TextUtils`
    :param text_utils: An instance of `util.TextUtils`.

    :type theme: str
    :param theme: The prompt_toolkit lexer theme.
    """

    CMDS_NO_PAGINATE = [
        '-b',
        '--browser',
        '>',
        '<',
    ]
    CMDS_ENABLE_PAGINATE = [
        '-cq',
        '--comments_regex_query',
        '-c',
        '--comments',
        '-cr',
        '--comments_recent',
        '-cu',
        '--comments_unseen',
        '-ch',
        '--comments_hide_non_matching',
        'hiring',
        'freelance',
    ]
    PAGINATE_CMD = ' | less -r'
    PAGINATE_CMD_WIN = ' | more'

    def __init__(self):
        self.cli = None
        self.key_manager = None
        self.theme = 'vim'
        self.paginate_comments = True
        self.hacker_news_cli = HackerNewsCli()
        self.text_utils = TextUtils()
        self.completer = Completer(fuzzy_match=False,
                                   text_utils=self.text_utils)
        self._create_cli()
        if platform.system() == 'Windows':
            self.CMDS_ENABLE_PAGINATE.append('view')

    def _create_key_manager(self):
        """Create the :class:`KeyManager`.

        The inputs to KeyManager are expected to be callable, so we can't
        use the standard @property and @attrib.setter for these attributes.
        Lambdas cannot contain assignments so we're forced to define setters.

        :rtype: :class:`prompt_toolkit.key_binding.manager
        :return: KeyBindingManager with callables to set the toolbar options.
        """

        def set_paginate_comments(paginate_comments):
            """Setter for paginating comments mode.

            :type paginate: bool
            :param paginate: The paginate comments mode.
            """
            self.paginate_comments = paginate_comments

        return KeyManager(
            set_paginate_comments, lambda: self.paginate_comments)

    def _create_cli(self):
        """Create the prompt_toolkit's CommandLineInterface."""
        history = FileHistory(os.path.expanduser('~/.haxornewshistory'))
        toolbar = Toolbar(lambda: self.paginate_comments)
        layout = create_default_layout(
            message=u'haxor> ',
            reserve_space_for_menu=True,
            get_bottom_toolbar_tokens=toolbar.handler,
        )
        cli_buffer = Buffer(
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            completer=self.completer,
            complete_while_typing=Always(),
            accept_action=AcceptAction.RETURN_DOCUMENT)
        self.key_manager = self._create_key_manager()
        style_factory = StyleFactory(self.theme)
        application = Application(
            mouse_support=False,
            style=style_factory.style,
            layout=layout,
            buffer=cli_buffer,
            key_bindings_registry=self.key_manager.manager.registry,
            on_exit=AbortAction.RAISE_EXCEPTION,
            on_abort=AbortAction.RETRY,
            ignore_case=True)
        eventloop = create_eventloop()
        self.cli = CommandLineInterface(
            application=application,
            eventloop=eventloop)

    def _add_comment_pagination(self, document_text):
        """Add the command to enable comment pagination where applicable.

        Pagination is enabled if the command views comments and the
        browser flag is not enabled.

        :type document_text: str
        :param document_text: The input command.

        :rtype: str
        :return: the input command with pagination enabled.
        """
        if not any(sub in document_text for sub in self.CMDS_NO_PAGINATE):
            if any(sub in document_text for sub in self.CMDS_ENABLE_PAGINATE):
                if platform.system() == 'Windows':
                    document_text += self.PAGINATE_CMD_WIN
                else:
                    document_text += self.PAGINATE_CMD
        return document_text

    def handle_exit(self, document):
        """Exits if the user typed exit or quit

        :type document: :class:`prompt_toolkit.document.Document`
        :param document: An instance of `prompt_toolkit.document.Document`.
        """
        if document.text in ('exit', 'quit'):
            sys.exit()

    def run_command(self, document):
        """Run the given command.

        :type document: :class:`prompt_toolkit.document.Document`
        :param document: An instance of `prompt_toolkit.document.Document`.
        """
        try:
            if self.paginate_comments:
                text = document.text
                text = self._add_comment_pagination(text)
            subprocess.call(text, shell=True)
        except Exception as e:
            click.secho(e, fg='red')

    def run_cli(self):
        """Run the main loop."""
        click.echo('Version: ' + __version__)
        click.echo('Syntax: hn <command> [params] [options]')
        while True:
            document = self.cli.run()
            self.handle_exit(document)
            self.run_command(document)
