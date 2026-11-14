"""Toolkit apply is handed to a separate, unapproved terminal confirmation."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tui_toolkit import finish_update


class ToolkitHandoffTests(unittest.TestCase):
    def test_receipt_is_private_temporary_and_confirmation_is_not_injected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();script=root/'scripts/update_toolkit.sh'
            script.parent.mkdir();script.write_text('# fixture')
            seen=[]
            def run(argv,env):
                self.assertEqual(argv[:3],['/bin/bash',str(script),'--apply'])
                path=Path(argv[3]);seen.append(path)
                self.assertEqual(path.stat().st_mode&0o777,0o600)
                self.assertEqual(json.loads(path.read_text()),{'target_sha':'a'*40})
                self.assertNotIn('MAC_UPDATE_TUI_CHILD',env)
                self.assertEqual(env['MAC_UPDATE_LANG'],'pl')
                return 2
            with patch.dict(os.environ,{'MAC_UPDATE_STATE_DIR':str(root/'state'),'MAC_UPDATE_TUI_CHILD':'1'}),patch('subprocess.call',run):
                self.assertEqual(finish_update(root,{'target_sha':'a'*40},'pl'),2)
            self.assertFalse(seen[0].exists())

    def test_symlinked_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();(root/'scripts').mkdir();(root/'other').write_text('# fixture')
            (root/'scripts/update_toolkit.sh').symlink_to(root/'other')
            with patch.dict(os.environ,{'MAC_UPDATE_STATE_DIR':str(root/'state')}),patch('subprocess.call',side_effect=AssertionError('no command')):
                with self.assertRaises(ValueError):finish_update(root,{},'en')
