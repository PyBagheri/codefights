import unittest

from simulator.tests.base import (
    # Will be used by Python's unittest.
    setUpModule,
    tearDownModule,
    
    SimulatorTests,
    
    rm_left_spaces,
)


class ResultTest(SimulatorTests, unittest.TestCase):         
    def test_different_types_can_be_sent(self):
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
            'game_settings': {'test_args': test_args},
            'codes_filenames': ['fights/testcode1.py'],
        }

        res = self.request_simulation_and_result(data)
        
        self.assertEqual(res, {
            'fight_id': 1234,
            'report': [expected_return_value],
            'final_states': [0]
        })


    # More tests to be added ...
