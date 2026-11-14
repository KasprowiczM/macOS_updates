"""Progress is telemetry, never authority; fixtures contain no real app paths."""
import io
import json
import os
import unittest
from unittest.mock import patch
from tui_events import emit, emit_plan, emit_target
from user_policy import identity_fingerprint, source_fingerprint


class EventsTests(unittest.TestCase):
    def action(self):
        return dict(action_id='action', target={'kind': 'app', 'id': 'instance'},
                    expected_target={'instance_id': 'instance', 'name': 'Example', 'path': '/fixture/Example.app'},
                    expected_resolution={'source': 'vendor'}, target_path='/fixture/Example.app',
                    from_version='1.0', reason_codes=['consent_required'],kind='open_native_updater')

    def test_default_output_is_unchanged(self):
        stream=io.StringIO()
        with patch.dict(os.environ, {'MAC_UPDATE_TUI_CHILD':'0'}):
            emit_plan({'actions':[self.action()]},stream)
        self.assertEqual(stream.getvalue(),'')

    def test_candidate_stream_contains_complete_table_and_bound_identity(self):
        stream=io.StringIO();action=self.action()
        with patch.dict(os.environ, {'MAC_UPDATE_TUI_CHILD':'1'}):
            emit_plan({'actions':[action]},stream)
        lines=stream.getvalue().splitlines()
        self.assertEqual(lines[0],'@@MAC_UPDATE_CANDIDATES_BEGIN')
        self.assertEqual(lines[-1],'@@MAC_UPDATE_CANDIDATES_END')
        row=json.loads(lines[1].split(' ',1)[1])
        self.assertEqual(row['target'],action['target'])
        self.assertEqual(row['identity_fingerprint'],identity_fingerprint(action['expected_target']))
        self.assertEqual(row['source_fingerprint'],source_fingerprint(action['expected_target'],action['expected_resolution']))
        self.assertNotIn('approved',row)

    def test_target_result_never_infers_verified_from_exit_or_status(self):
        stream=io.StringIO()
        with patch.dict(os.environ, {'MAC_UPDATE_TUI_CHILD':'1'}),patch('sys.stdout',stream):
            emit_target(self.action())
            emit_target(self.action(),{'status':'updated','verified':False,'after':'2'})
        rows=[json.loads(line.split(' ',1)[1]) for line in stream.getvalue().splitlines()]
        self.assertEqual(rows[0]['status'],'running')
        self.assertFalse(rows[1]['verified'])

    def test_oversized_payload_and_closed_output_are_nonfatal(self):
        stream=io.StringIO()
        with patch.dict(os.environ, {'MAC_UPDATE_TUI_CHILD':'1'}):
            emit('TEST',{'value':'x'*9000},stream)
            class Closed:
                def write(self,*args):raise BrokenPipeError()
            emit('TEST',{},Closed())
        self.assertEqual(stream.getvalue(),'')

    def test_telemetry_never_breaks_execution_with_minimal_actions(self):
        for child in ('0', '1'):
            with patch.dict(os.environ, {'MAC_UPDATE_TUI_CHILD': child}), patch('sys.stdout', io.StringIO()):
                emit_target({'action_id': 'minimal'})
                emit_plan({'actions': [{'action_id': 'minimal'}]})

    def test_parallel_records_remain_complete_and_phase_names_are_closed(self):
        from concurrent.futures import ThreadPoolExecutor
        from tui_events import emit_phase
        stream = io.StringIO()
        with patch.dict(os.environ, {'MAC_UPDATE_TUI_CHILD': '1'}), patch('sys.stdout', stream):
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda n: emit('TEST', {'n': n}), range(100)))
            emit_phase('vendor', 'running')
            emit_phase('injected\nphase', 'ok')
        lines = stream.getvalue().splitlines()
        self.assertEqual(len(lines), 101)
        self.assertEqual({json.loads(line.split(' ', 1)[1])['n'] for line in lines[:-1]}, set(range(100)))
        self.assertEqual(lines[-1], '@@MAC_UPDATE_PHASE internet running')
