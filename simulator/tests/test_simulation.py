import unittest

from simulator.tests import test_base

from simulator.tests.test_base import (
    setUpModule,
    tearDownModule,
    
    rm_left_spaces,
)

import json


class ResultTest(unittest.TestCase):  
    # We include the cleanup on setup too, just
    # to be sure. It doesn't hurt :/
    def setUp(self):
        self.cleanup_redis_streams()
    
    
    def tearDown(self):
        self.cleanup_redis_streams()
    
    
    def cleanup_redis_streams(self):
        test_base.redis_client.xtrim(
            test_base.project_settings.REDIS_SIMULATOR_STREAM,
            maxlen='0',
        )
        
        test_base.redis_client.xtrim(
            test_base.project_settings.REDIS_SIMULATION_RESULTS_STREAM,
            maxlen='0',
        )
    
    
    def request_simulation_and_result(self, data):
        test_base.redis_client.xadd(test_base.project_settings.REDIS_SIMULATOR_STREAM,
            {'data': json.dumps(data)}
        )
        
        # The indices: 1st (and only) stream; 2nd item (messages);
        # 1st (and only) message; 2nd item (message data); the json raw.
        return json.loads(test_base.redis_client.xread(
            {test_base.project_settings.REDIS_SIMULATION_RESULTS_STREAM: '0'},
            count=1,
            block=0  # block until message arrives
        )[0][1][0][1]['data'])
        
    
    def test_different_types_can_be_sent(self):
        code = rm_left_spaces(
        """
        class Main:
            def testfunc1(self, *args):
                arg_list = {}
                for i in range(len(args)):
                    arg_list[i] = args[i]
                return arg_list
        """, 8)
        
        # JSON-serializable types. Note:
        # - tuples will be converted to list.
        # - dict keys cannot be integers. They will
        #   be converted to string.
        test_args = (
            'string',
            123,
            ['list', 321, {'nested': True}, ['yes']],
            {'key': 'value'},
            True,
            False,
            None
        )
        
        expected_return_value = {str(i):test_args[i] for i in range(len(test_args))}
        
        data = {
            'fight_id': 1234,
            'game': 'testgame1',
            'game_settings': {'player_count': 1, 'test_args': test_args},
            'player_codes': [code],
        }

        res = self.request_simulation_and_result(data)
        
        self.assertEqual(res, {
            'fight_id': 1234,
            'report': [expected_return_value],
            'final_states': [0]
        })


    # More tests to be added ...
