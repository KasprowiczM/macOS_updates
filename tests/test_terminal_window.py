"""Window sizing is optional and preserves the invoking user's dimensions."""
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
from terminal_app import TerminalWindow


class WindowTests(unittest.TestCase):
    class Terminal(io.StringIO):
        def isatty(self):
            return True
        def fileno(self):
            return 1

    def test_small_window_requested_and_prior_size_restored_even_on_error(self):
        output = self.Terminal()
        with patch.dict(os.environ, {'TERM': 'xterm-256color', 'TMUX': '', 'STY': ''}), patch('os.get_terminal_size', return_value=os.terminal_size((90, 26))):
            with self.assertRaises(RuntimeError):
                with TerminalWindow(output):
                    raise RuntimeError('fixture')
        self.assertEqual(output.getvalue(), '\x1b[8;38;140t\x1b[8;26;90t')

    def test_large_window_and_opt_out_do_not_resize(self):
        output = self.Terminal()
        with patch.dict(os.environ, {'TERM': 'xterm', 'TMUX': '', 'STY': ''}), patch('os.get_terminal_size', return_value=os.terminal_size((180, 50))):
            with TerminalWindow(output):
                pass
            with TerminalWindow(output, False):
                pass
        self.assertEqual(output.getvalue(), '')

    def test_pipe_and_multiplexer_never_receive_window_commands(self):
        for output, env in ((io.StringIO(), {}), (self.Terminal(), {'TMUX': '/fixture/session'})):
            with patch.dict(os.environ, env):
                with TerminalWindow(output):
                    pass
            self.assertEqual(output.getvalue(), '')

    def test_unavailable_terminal_size_is_nonfatal(self):
        output = self.Terminal()
        with patch.dict(os.environ, {'TERM': 'xterm', 'TMUX': '', 'STY': ''}), patch('os.get_terminal_size', side_effect=OSError('fixture')):
            with TerminalWindow(output):
                pass
        self.assertEqual(output.getvalue(), '')
