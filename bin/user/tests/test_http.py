"""
Test suite for the WeeWX Ecowitt gateway driver.

Copyright (C) 2020-25 Gary Roderick                gjroderick<at>gmail.com

A python3 unittest based test suite for aspects of the Ecowitt gateway driver.
The test suite tests correct operation of:

-

Version: 0.1.0a27                                 Date: ? May 2025

Revision History
    ?? May 2025       v0.1.0
        -   initial release

To run the test suite:

-   copy this file to the target machine, nominally to the USER_ROOT/tests
    directory

-   run the test suite using:

    PYTHONPATH=/home/weewx/weewx-data/bin:/home/weewx/weewx/src python3 -m user.tests.test_http
"""
# python imports
import io
import os
import socket
import struct
import sys
import unittest
import urllib.response

from unittest.mock import patch

import configobj

# WeeWX imports
import weecfg
import weewx
import schemas.wview_extended
import weewx.units
import user.ecowitt_http

# TODO. Check speed_data data and result are correct
# TODO. Check rain_data data and result are correct
# TODO. Check rainrate_data data and result are correct
# TODO. Check big_rain_data data and result are correct
# TODO. Check light_data data and result are correct
# TODO. Check uv_data data and result are correct
# TODO. Check uvi_data data and result are correct
# TODO. Check datetime_data data and result are correct
# TODO. Check leak_data data and result are correct
# TODO. Check batt_data data and result are correct
# TODO. Check distance_data data and result are correct
# TODO. Check utc_data data and result are correct
# TODO. Check count_data data and result are correct
# TODO. Add decode display_firmware check refer issue #31

TEST_SUITE_NAME = 'Ecowitt HTTP driver'
TEST_SUITE_VERSION = '0.1.0a27'


class bcolors:
    """Colors used for terminals"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class ValueTupleMatcher:

    def __init__(self, expected):
        self.expected = expected

    def __repr__(self):
        return repr(self.expected)

    def __eq__(self, other):
        return self.expected.value == other.value and \
            self.expected.unit == other.unit and \
            self.expected.group == other.group


class DebugOptionsTestCase(unittest.TestCase):
    """Test the DebugOptions class."""

    # the debug option groups we know about
    debug_groups = ('rain', 'wind', 'loop', 'sensors',
                    'parser', 'catchup', 'collector')

    def setUp(self):

        # construct a debug option config that sets all available debug options
        debug_string = 'debug = %s' % ', '.join(self.debug_groups)
        self.debug_config = configobj.ConfigObj(io.StringIO(debug_string))

    def test_constants(self):
        """Test constants used by DebugOptions."""

        print()

        # check the default
        print('    testing constants...')
        # test available debug groups
        debug_options = user.ecowitt_http.DebugOptions()
        for group in self.debug_groups:
            self.assertFalse(getattr(debug_options, group))
        # check 'any' property
        self.assertEqual(user.ecowitt_http.DebugOptions.debug_groups,
                         self.debug_groups)

    def test_properties(self):
        """Test the setting of DebugOptions properties on initialisation."""

        print()

        # check the default
        print('    testing default debug options...')
        # first test passing in no config at all
        debug_options = user.ecowitt_http.DebugOptions()
        for group in self.debug_groups:
            self.assertFalse(getattr(debug_options, group))
        # check 'any' property
        self.assertFalse(debug_options.any)

        # test when passing in an empty config dict
        debug_options = user.ecowitt_http.DebugOptions(**{})
        for group in self.debug_groups:
            self.assertFalse(getattr(debug_options, group))
        # check 'any' property
        self.assertFalse(debug_options.any)

        # test setting all debug option
        print('    testing all debug options...')
        debug_options = user.ecowitt_http.DebugOptions(**self.debug_config)
        for group in self.debug_groups:
            self.assertTrue(getattr(debug_options, group))
        # check 'any' property
        self.assertTrue(debug_options.any)

        # check when just one debug option is True
        print('    testing setting one debug option at a time...')
        # first make a copy of our 'all True' debug config
        _config =  configobj.ConfigObj(self.debug_config)
        # iterate over each of our debug groups, this is the group that will be
        # set True for the test
        for true_group in self.debug_groups:
            _config['debug'] = true_group
            # get a fresh DebugOptions object
            debug_options = user.ecowitt_http.DebugOptions(**_config)
            # now check the DebugOptions object properties are set as expected
            for group in self.debug_groups:
                # the property for the group under test should be set True, all
                # others should be False
                if group == true_group:
                    self.assertTrue(getattr(debug_options, group))
                else:
                    self.assertFalse(getattr(debug_options, group))
            # check 'any' property, it should be True
            self.assertTrue(debug_options.any)

        # check when all but one debug option is True
        print('    testing setting all but one debug option at a time...')
        # iterate over each of our debug groups, this is the group that will be
        # not set for the test
        for false_group in self.debug_groups:
            # make a list of all available debug groups
            all_groups = list(self.debug_groups)
            # find 'false_group' in our list a remove it
            for index in range(len(all_groups)):
                if all_groups[index] == false_group:
                    all_groups.pop(index)
                    break
            # create a string containing the debug groups to be set
            debug_string = 'debug = %s' % ', '.join(all_groups)
            # convert to a configobj
            _config = configobj.ConfigObj(io.StringIO(debug_string))
            # get a fresh DebugOptions object using the config
            debug_options = user.ecowitt_http.DebugOptions(**_config)
            # now check the DebugOptions object properties are set as expected
            for group in self.debug_groups:
                # the property for the group under test should be set False, all
                # others should be True
                if group == false_group:
                    self.assertFalse(getattr(debug_options, group))
                else:
                    self.assertTrue(getattr(debug_options, group))
            # check 'any' property, it should be True
            self.assertTrue(debug_options.any)


class ConfEditorTestCase(unittest.TestCase):
    """Test the EcowittHttpDriverConfEditor class."""

    # test prompt for settings inputs
    prompt_for_settings_input = [
        '192.168.99.99', '10',
        'www.xxx.yyy.zzz', '10',
        '192.168.99.99', '10',
        '192.168.99.99', '10',
        '192.168.99.99', '10',
        '192.168.99.99', '10',
    ]
    prompt_for_settings_responses = [
        {'ip_address': '192.168.99.99', 'poll_interval': 10},
        {'ip_address': 'www.xxx.yyy.zzz', 'poll_interval': 10},
    ]

    # minimal [EcowittHttp] config string for conf editor testing
    minimal_driver_config_str = f"""
    [EcowittHttp]
        driver = user.ecowitt_http
        ip_address = 192.168.99.99
    """
    # minimal [StdWXCalculate] string for conf editor testing
    minimal_stdwx_config_str = f"""
    [StdWXCalculate]
        [[Calculations]]
            rain = prefer_hardware
"""
    # additional [StdWXCalculate] [[Calculations]] and [[Deltas]] entries for
    # conf editor do_rain() testing
    add_stdwx_config_str = f"""
    [StdWXCalculate]
        [[Calculations]]
            dewpoint = prefer_hardware
            windchill = prefer_hardware
        [[Delta]]
            [[[hail]]]
                input = yearHail
            [[[water]]]
                input = cumulative_water
"""
    # additional [StdWXCalculate] config entries for conf editor do_lightning()
    # testing
    add_lightning_config_str = f"""
    [StdWXCalculate]
        [[Calculations]]
            dewpoint = prefer_hardware
            windchill = prefer_hardware
        [[Delta]]
            [[[hail]]]
                input = yearHail
            [[[water]]]
                input = cumulative_water
"""
    # additional [StdArchive] config entries for conf editor
    # do_archive_record_generation() testing
    add_archive_config_str = f"""
    [StdArchive]
        # If the station hardware supports data logging then the archive interval
        # will be downloaded from the station. Otherwise, specify it (in seconds).
        archive_interval = 300
        
        # If possible, new archive records are downloaded from the station
        # hardware. If the hardware does not support this, then new archive
        # records will be generated in software.
        # Set the following to "software" to force software record generation.
        record_generation = hardware
        
        # Whether to include LOOP data in hi/low statistics.
        loop_hilo = True
"""
    # responses for the mocked weecfg.prompt_with_options() side_effect for do_rain() testing
    prompt_responses = [
        'both', 'tipping', 't_yearrain',
        'both', 'piezo', 'p_yearrain',
        'tipping', 'tipping', 't_yearrain',
        'piezo', 'piezo', 'p_yearrain',
        'none',
        'both', 'tipping', 't_yearrain',
        'both', 'piezo', 'p_yearrain',
        'tipping', 'tipping', 't_yearrain',
        'piezo', 'piezo', 'p_yearrain',
        'none',
    ]
    # lookup table of expected do_rain() test responses, in each case the
    # expected response is a ConfigObj object; however, for the purposes of the
    # test method (assertDictEqual()) a dict is adequate
    test_responses = {
        'both_tipping': {'EcowittHttp':
                             {'driver': 'user.ecowitt_http',
                              'ip_address': '192.168.99.99',
                              'field_map_extensions':
                                  {'rainRate': 'rain.0x0E.val'}},
                         'StdWXCalculate':
                             {'Calculations':
                                  {'rain': 'prefer_hardware',
                                   'p_rain': 'prefer_hardware'},
                              'Delta':
                                  {'rain':
                                       {'input': 't_yearrain'},
                                   'p_rain':
                                       {'input': 'p_rainyear'}}}},
        'both_piezo': {'EcowittHttp':
                           {'driver': 'user.ecowitt_http',
                            'ip_address': '192.168.99.99',
                            'field_map_extensions':
                                {'rainRate': 'piezoRain.0x0E.val'}},
                       'StdWXCalculate':
                           {'Calculations':
                                {'rain': 'prefer_hardware',
                                 't_rain': 'prefer_hardware'},
                            'Delta':
                                {'rain':
                                    {'input': 'p_yearrain'},
                                 't_rain':
                                    {'input': 't_rainyear'}}}},
        'tipping_tipping': {'EcowittHttp':
                                {'driver': 'user.ecowitt_http',
                                 'ip_address': '192.168.99.99',
                                 'field_map_extensions':
                                     {'rainRate': 'rain.0x0E.val'}},
                            'StdWXCalculate':
                                {'Calculations':
                                     {'rain': 'prefer_hardware'},
                                 'Delta':
                                     {'rain':
                                          {'input': 't_yearrain'}}}},
        'piezo_piezo': {'EcowittHttp':
                            {'driver': 'user.ecowitt_http',
                             'ip_address': '192.168.99.99',
                             'field_map_extensions':
                                 {'rainRate': 'piezoRain.0x0E.val'}},
                        'StdWXCalculate':
                            {'Calculations':
                                 {'rain': 'prefer_hardware'},
                             'Delta':
                                 {'rain':
                                      {'input': 'p_yearrain'}}}},
        'none_none': {'EcowittHttp':
                          {'driver': 'user.ecowitt_http',
                           'ip_address': '192.168.99.99'},
                      'StdWXCalculate':
                          {'Calculations':
                               {'rain': 'prefer_hardware'}}},
        'both_tipping_add': {'EcowittHttp':
                                 {'driver': 'user.ecowitt_http',
                                  'ip_address': '192.168.99.99',
                                  'field_map_extensions':
                                       {'rainRate': 'rain.0x0E.val'}},
                             'StdWXCalculate':
                                 {'Calculations':
                                      {'rain': 'prefer_hardware',
                                       'p_rain': 'prefer_hardware',
                                       'dewpoint': 'prefer_hardware',
                                       'windchill': 'prefer_hardware'},
                                  'Delta':
                                      {'rain':
                                           {'input': 't_yearrain'},
                                      'p_rain':
                                           {'input': 'p_rainyear'},
                                      'hail':
                                           {'input': 'yearHail'},
                                      'water':
                                           {'input': 'cumulative_water'}}}},
        'both_piezo_add': {'EcowittHttp':
                               {'driver': 'user.ecowitt_http',
                                'ip_address': '192.168.99.99',
                                'field_map_extensions':
                                    {'rainRate': 'piezoRain.0x0E.val'}},
                           'StdWXCalculate':
                               {'Calculations':
                                    {'rain': 'prefer_hardware',
                                     't_rain': 'prefer_hardware',
                                     'dewpoint': 'prefer_hardware',
                                     'windchill': 'prefer_hardware'},
                                'Delta':
                                    {'rain':
                                         {'input': 'p_yearrain'},
                                     't_rain':
                                         {'input': 't_rainyear'},
                                     'hail':
                                         {'input': 'yearHail'},
                                     'water':
                                         {'input': 'cumulative_water'}}}},
        'tipping_tipping_add': {'EcowittHttp':
                                    {'driver': 'user.ecowitt_http',
                                     'ip_address': '192.168.99.99',
                                     'field_map_extensions':
                                         {'rainRate': 'rain.0x0E.val'}},
                                'StdWXCalculate':
                                    {'Calculations':
                                         {'rain': 'prefer_hardware',
                                          'dewpoint': 'prefer_hardware',
                                          'windchill': 'prefer_hardware'},
                                     'Delta':
                                         {'rain':
                                              {'input': 't_yearrain'},
                                          'hail':
                                              {'input': 'yearHail'},
                                          'water':
                                              {'input': 'cumulative_water'}}}},
        'piezo_piezo_add': {'EcowittHttp':
                                {'driver': 'user.ecowitt_http',
                                 'ip_address': '192.168.99.99',
                                 'field_map_extensions':
                                     {'rainRate': 'piezoRain.0x0E.val'}},
                            'StdWXCalculate':
                                {'Calculations':
                                     {'rain': 'prefer_hardware',
                                      'dewpoint': 'prefer_hardware',
                                      'windchill': 'prefer_hardware'},
                                 'Delta':
                                     {'rain':
                                          {'input': 'p_yearrain'},
                                      'hail':
                                          {'input': 'yearHail'},
                                      'water':
                                          {'input': 'cumulative_water'}}}},
        'none_none_add': {'EcowittHttp':
                              {'driver': 'user.ecowitt_http',
                               'ip_address': '192.168.99.99'},
                          'StdWXCalculate':
                              {'Calculations':
                                   {'rain': 'prefer_hardware',
                                    'dewpoint': 'prefer_hardware',
                                    'windchill': 'prefer_hardware'},
                               'Delta':
                                   {'hail':
                                        {'input': 'yearHail'},
                                    'water':
                                        {'input': 'cumulative_water'}}}},
    }
    # lightning test expected response
    lightning_responses = {
        'clean': {'EcowittHttp':
                      {'driver': 'user.ecowitt_http',
                      'ip_address': '192.168.99.99'},
                  'StdWXCalculate':
                      {'Calculations':
                           {'lightning_strike_count': 'prefer_hardware'},
                       'Delta':
                           {'lightning_strike_count':
                                {'input': 'lightningcount'}}}},
        'additional_config': {'EcowittHttp':
                                  {'driver': 'user.ecowitt_http',
                                   'ip_address': '192.168.99.99'},
                              'StdWXCalculate':
                                  {'Calculations':
                                       {'lightning_strike_count': 'prefer_hardware',
                                        'dewpoint': 'prefer_hardware',
                                        'windchill': 'prefer_hardware'},
                                   'Delta':
                                       {'lightning_strike_count':
                                            {'input': 'lightningcount'},
                                        'hail':
                                            {'input': 'yearHail'},
                                        'water':
                                            {'input': 'cumulative_water'}}}}
    }
    # archive record generation test expected response
    archive_response = {'EcowittHttp':
                             {'driver': 'user.ecowitt_http',
                              'ip_address': '192.168.99.99'},
                         'StdArchive':
                             {'archive_interval': '300',
                              'record_generation': 'software',
                              'loop_hilo': 'True'}}

    # patch.object to allow mocking of weecfg.prompt_with_options() function
    @patch.object(weecfg, 'prompt_with_options')
    def test_prompt_for_settings(self, mock_prompt_with_options):
        """Test conf editor prompt for settings."""
        return
        print()
        print('    testing driver configuration editor prompt for settings...')

        # set mocked items
        mock_prompt_with_options.side_effect = ConfEditorTestCase.prompt_for_settings_input

    def test_do_lightning(self):
        """Test conf editor lightning config."""

        print()
        print('    testing driver configuration editor lightning settings...')

        # store original stdout
        original_stdout = sys.stdout

        # test with no pre-existing [StdWXCalculate] [[Deltas]]
        print("        testing clean installation with minimal config...")
        # obtain the minimal test config, it is built from the minimal driver
        test_config = configobj.ConfigObj(io.StringIO(ConfEditorTestCase.minimal_driver_config_str))
        test_input = configobj.ConfigObj(test_config)
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_lightning(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.lightning_responses['clean'])

        # test with pre-existing [StdWXCalculate] [[Deltas]]
        print("        testing with pre-existsing [StdWXCalculate] [[Deltas]] config...")
        # obtain the minimal test config, it is built from the minimal driver
        test_config = configobj.ConfigObj(io.StringIO(ConfEditorTestCase.minimal_driver_config_str))
        test_input = configobj.ConfigObj(test_config)
        test_input.merge(configobj.ConfigObj(io.StringIO(ConfEditorTestCase.add_lightning_config_str)))
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_lightning(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.lightning_responses['additional_config'])

        print('    driver configuration editor lightning settings testing complete...')

    def test_do_archive_record_generation(self):
        """Test conf editor archive record generation config."""

        print()
        print('    testing driver configuration editor archive record generation settings...')

        # store original stdout
        original_stdout = sys.stdout

        # test against a hardware record generation config
        print("        testing a hardware record generation config...")
        # obtain the minimal test config, it is built from the minimal driver
        test_config = configobj.ConfigObj(io.StringIO(ConfEditorTestCase.minimal_driver_config_str))
        test_input = configobj.ConfigObj(test_config)
        # add in the [StdArchive] config
        test_input.merge(configobj.ConfigObj(io.StringIO(ConfEditorTestCase.add_archive_config_str)))
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_archive_record_generation(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.archive_response)

        # test against a software record generation config
        print("        testing a software record generation config...")
        # obtain the minimal test config, it is built from the minimal driver
        test_config = configobj.ConfigObj(io.StringIO(ConfEditorTestCase.minimal_driver_config_str))
        test_input = configobj.ConfigObj(test_config)
        # add in the [StdArchive] config
        test_input.merge(configobj.ConfigObj(io.StringIO(ConfEditorTestCase.add_archive_config_str)))
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_archive_record_generation(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.archive_response)

        print('    driver configuration editor archive record generation settings testing complete...')

    # patch.object to allow mocking of weecfg.prompt_with_options() function
    @patch.object(weecfg, 'prompt_with_options')
    def test_prompt_for_settings(self, mock_prompt_with_options):
        """Test conf editor prompt for settings."""

        print()
        print('    testing driver configuration editor prompt for settings...')

        # set mocked items
        mock_prompt_with_options.side_effect = ConfEditorTestCase.prompt_for_settings_input


    # patch.object to allow mocking of EcowittDevice.paired_rain_gauges property
    @patch.object(user.ecowitt_http.EcowittDevice,
                  'paired_rain_gauges',
                  new_callable=unittest.mock.PropertyMock)
    # patch.object to allow mocking of weecfg.prompt_with_options() function
    @patch.object(weecfg, 'prompt_with_options')
    def test_do_rain(self, mock_prompt_with_options, mock_paired_rain_gauges_property):
        """Test conf editor rain config.

        Tests the EcowittHttpDriverConfEditor.do_rain() methods which processes
        rain gauge and per-period rain config during device configuration.

        The method under test generates console output, use sys.stdout
        redirection to suppress this output.
        """

        print()
        print('    testing driver configuration editor rain settings...')
        # store original stdout
        original_stdout = sys.stdout

        # set mocked items
        mock_prompt_with_options.side_effect = ConfEditorTestCase.prompt_responses
        mock_paired_rain_gauges_property.return_value = ('tipping', 'piezo')
        # obtain the minimal test config, it is built from the minimal driver
        # config and minimal StdWXCalculate config
        test_config = configobj.ConfigObj(io.StringIO(ConfEditorTestCase.minimal_driver_config_str))
        test_config.merge(configobj.ConfigObj(io.StringIO(ConfEditorTestCase.minimal_stdwx_config_str)))

        # test both gauges, assigning tipping to WeeWX rain/rainRate
        # first make a copy of our minimal test config, no need for changes
        print("        testing both gauges, 'tipping' assigned to 'rain'/'rainRate'...")
        test_input = configobj.ConfigObj(test_config)
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_rain(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.test_responses['both_tipping'])

        # test both gauges, assigning piezo to WeeWX rain/rainRate
        # first make a copy of our minimal test config, no need for changes
        print("        testing both gauges, 'piezo' assigned to 'rain'/'rainRate'...")
        test_input = configobj.ConfigObj(test_config)
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_rain(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.test_responses['both_piezo'])

        # test tipping gauge, assigning tipping to WeeWX rain/rainRate
        # first make a copy of our minimal test config, no need for changes
        print("        testing tipping gauge, 'tipping' assigned to 'rain'/'rainRate'...")
        test_input = configobj.ConfigObj(test_config)
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_rain(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.test_responses['tipping_tipping'])

        # test piezo gauge, assigning piezo to WeeWX rain/rainRate
        # first make a copy of our minimal test config, no need for changes
        print("        testing piezo gauge, 'piezo' assigned to 'rain'/'rainRate'...")
        test_input = configobj.ConfigObj(test_config)
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_rain(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.test_responses['piezo_piezo'])

        # test no gauges
        # first make a copy of our minimal test config, no need for changes
        print("        testing no gauge...")
        test_input = configobj.ConfigObj(test_config)
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_rain(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.test_responses['none_none'])

        # test both gauges, assigning tipping to WeeWX rain/rainRate with
        # additional [StdWXCalculate] entries
        # first make a copy of our minimal test config, no need for changes
        print("        testing both gauges, 'tipping' assigned to 'rain'/'rainRate' "
              "with additional [StdWXCalculate] entries...")
        test_input = configobj.ConfigObj(test_config)
        test_input.merge(configobj.ConfigObj(io.StringIO(ConfEditorTestCase.add_stdwx_config_str)))
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_rain(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.test_responses['both_tipping_add'])

        # test both gauges, assigning piezo to WeeWX rain/rainRate with
        # additional [StdWXCalculate] entries
        # first make a copy of our minimal test config, no need for changes
        print("        testing both gauges, 'piezo' assigned to 'rain'/'rainRate' "
              "with additional [StdWXCalculate] entries...")
        test_input = configobj.ConfigObj(test_config)
        test_input.merge(configobj.ConfigObj(io.StringIO(ConfEditorTestCase.add_stdwx_config_str)))
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_rain(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.test_responses['both_piezo_add'])

        # test tipping gauge, assigning tipping to WeeWX rain/rainRate with
        # additional [StdWXCalculate] entries
        # first make a copy of our minimal test config, no need for changes
        print("        testing tipping gauge, 'tipping' assigned to 'rain'/'rainRate' "
              "with additional [StdWXCalculate] entries...")
        test_input = configobj.ConfigObj(test_config)
        test_input.merge(configobj.ConfigObj(io.StringIO(ConfEditorTestCase.add_stdwx_config_str)))
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_rain(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.test_responses['tipping_tipping_add'])

        # test piezo gauge, assigning piezo to WeeWX rain/rainRate with
        # additional [StdWXCalculate] entries
        # first make a copy of our minimal test config, no need for changes
        print("        testing piezo gauge, 'piezo' assigned to 'rain'/'rainRate' "
              "with additional [StdWXCalculate] entries...")
        test_input = configobj.ConfigObj(test_config)
        test_input.merge(configobj.ConfigObj(io.StringIO(ConfEditorTestCase.add_stdwx_config_str)))
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_rain(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.test_responses['piezo_piezo_add'])

        # test no gauges with additional [StdWXCalculate] entries
        # first make a copy of our minimal test config, no need for changes
        print("        testing no gauge with additional [StdWXCalculate] entries...")
        test_input = configobj.ConfigObj(test_config)
        test_input.merge(configobj.ConfigObj(io.StringIO(ConfEditorTestCase.add_stdwx_config_str)))
        # redirect stdout to a StringIO object
        sys.stdout = io.StringIO()
        user.ecowitt_http.EcowittHttpDriverConfEditor.do_rain(test_input)
        # restore stdout
        sys.stdout = original_stdout
        self.assertDictEqual(test_input, ConfEditorTestCase.test_responses['none_none_add'])

        print('    driver configuration editor rain settings testing complete...')

    def test_accumulator_config(self):
        """Test conf editor accumulator config.

        Some fields require Accumulator extractor settings other than the
        default (average), eg: sensor battery and signal state fields. Check
        these fields have been included the relevant accumulator config
        strings/dicts.
        """

        print()
        print('    testing accumulator extractor config...')

#        # schema_fields = [f[0] for f in schemas.wview_extended.table]
        mapper = user.ecowitt_http.HttpMapper()
        test_fields = list(mapper.default_sensor_state_map.keys())
        test_fields += list(mapper.default_rain_map.keys())
#        default_accum_fields = set(schema_fields) | set(driver_fields)
        accum_config_dict = configobj.ConfigObj(io.StringIO(user.ecowitt_http.EcowittHttpDriverConfEditor.accum_config_str))
        accum_config_dict_fields = accum_config_dict['Accumulator'].sections
        exclusions = ('wn34_ch1_volt', 'wn34_ch2_volt', 'wn34_ch3_volt', 'wn34_ch4_volt',
                      'wn34_ch5_volt', 'wn34_ch6_volt', 'wn34_ch7_volt', 'wn34_ch8_volt',
                      'wh51_ch1_volt', 'wh51_ch2_volt', 'wh51_ch3_volt', 'wh51_ch4_volt',
                      'wh51_ch5_volt', 'wh51_ch6_volt', 'wh51_ch7_volt', 'wh51_ch8_volt',
                      'wh51_ch9_volt', 'wh51_ch10_volt', 'wh51_ch11_volt', 'wh51_ch12_volt',
                      'wh51_ch13_volt', 'wh51_ch14_volt', 'wh51_ch15_volt', 'wh51_ch16_volt',
                      'wh54_ch1_volt', 'wh54_ch2_volt', 'wh54_ch3_volt', 'wh54_ch4_volt',
                      'ws90_volt', 'ws90_sig', 'rainRate', 'p_rainrate')
        # now get the field map from the mapper
        for weewx_field in test_fields:
            if weewx_field not in exclusions:
                self.assertIn(weewx_field, accum_config_dict_fields)


class DeviceCatchupTestCase(unittest.TestCase):
    """Test the EcowittDeviceCatchup class."""

    # config used for mocked EcowittDeviceCatchup object
    device_catchup_config = {
        'ip_address': '192.168.99.99'
    }
    # mocked EcowittDevice.get_sdmmc_info response
    fake_get_sdmmc_info_data = {}
    gen_get_sdmmc_info_data = {
        'info': {
            'Name':'SC16G',
            'Type':'SDHC/SDXC',
            'Speed':'20 MHz',
            'Size':'15193 MB',
            'Interval':'5'
        },
        'file_list': [
            {
                "name": "202503G.csv",
                "type": "file",
                "size": "1MB"
            },
            {
                "name": "202503Allsensors_G.csv",
                "type": "file",
                "size": "171KB"
            },
            {
                "name": "202504A.csv",
                "type": "file",
                "size": "1MB"
            },
            {
                "name": "202504Allsensors_A.csv",
                "type": "file",
                "size": "2MB"
            }
        ]
    }

    gen_history_first_six_results = {
        weewx.US: [
            {'wh25.inhumi': 73.0, 'common_list.0x02.val': 71.06, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 66.74, 'feelslike': 71.06, 'common_list.5.val': 0.1063079,
             'common_list.0x0B.val': 0.0, 'common_list.0x0C.val': 0.0, 'common_list.0x0A.val': 306.0,
             'wh25.abs': 29.8784, 'wh25.rel': 30.0674, 'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0,
             'rain.0x0E.val': 0.0, 't_rainhour': 0.0, 'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0,
             'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0, 'rain.0x13.val': 0.0079, 'piezoRain.0x0E.val': 0.0,
             'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0, 'piezoRain.0x10.val': 0.362205, 'piezoRain.0x11.val': 1.2953,
             'piezoRain.0x12.val': 10.6142, 'piezoRain.0x13.val': 23.7992,
             'ch_aisle.1.temp': 85.28, 'dewpoint1': 73.58, 'heatindex1': 92.48, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 81.32, 'dewpoint3': 73.04, 'heatindex3': 86.18, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 80.78, 'dewpoint4': 72.14, 'heatindex4': 85.1, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 82.22, 'dewpoint5': 73.58, 'heatindex5': 87.98, 'ch_aisle.5.humidity': 75.0,
             'ch_aisle.6.temp': 81.32, 'dewpoint6': 71.96, 'heatindex6': 85.64, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 82.4, 'dewpoint7': 72.86, 'heatindex7': 87.8, 'ch_aisle.7.humidity': 73.0,
             'lightning.count': 0.0, 'lightning.distance': 21.13, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 13.0,
             'ch_temp.1.temp': 79.16, 'ch_lds.1.air': 1.61, 'ch_lds.1.depth': 5.05, 'ch_lds.1.heat': 2044.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742522100.0, 'interval': 5},
            {'wh25.inhumi': 73.0, 'common_list.0x02.val': 71.06, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 66.74, 'feelslike': 71.06, 'common_list.5.val': 0.1063,
             'common_list.0x0B.val': 1.7896, 'common_list.0x0C.val': 3.1317, 'common_list.0x0A.val': 236.0,
             'wh25.abs': 29.8784, 'wh25.rel': 30.0379, 'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0,
             'rain.0x0E.val': 0.0, 't_rainhour': 0.0, 'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0,
             'rain.0x12.val': 0.0, 'rain.0x13.val': 0.0079, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0,
             'piezoRain.0x0D.val': 0.0, 'piezoRain.0x10.val': 0.3623, 'piezoRain.0x11.val': 1.2953,
             'piezoRain.0x12.val': 10.6142, 'piezoRain.0x13.val': 23.7992,
             'ch_aisle.1.temp': 85.64, 'dewpoint1': 73.94, 'heatindex1': 93.2, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 81.5, 'dewpoint3': 73.22, 'heatindex3': 86.72, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 80.78, 'dewpoint4': 72.14, 'heatindex4': 85.1, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 82.4, 'dewpoint5': 73.4, 'heatindex5': 88.16, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 81.5, 'dewpoint6': 72.14, 'heatindex6': 86, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 82.58, 'dewpoint7': 73.04, 'heatindex7': 88.34, 'ch_aisle.7.humidity': 73.0,
             'lightning.count': 0.0, 'lightning.distance': 21.13, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 13.0,
             'ch_temp.1.temp': 79.52, 'ch_lds.1.air': 1.64, 'ch_lds.1.depth': 5.02, 'ch_lds.1.heat': 2044.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742522400.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 71.06, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 66.74, 'feelslike': 71.06, 'common_list.5.val': 0.1063,
             'common_list.0x0B.val': 0.0, 'common_list.0x0C.val': 2.0132, 'common_list.0x0A.val': 288.0,
             'wh25.abs': 29.8755, 'wh25.rel': 30.0350, 'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0,
             'rain.0x0E.val': 0.0, 't_rainhour': 0.0, 'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0,
             'rain.0x12.val': 0.0, 'rain.0x13.val': 0.0079, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0,
             'piezoRain.0x0D.val': 0.0, 'piezoRain.0x10.val': 0.3622, 'piezoRain.0x11.val': 1.2953,
             'piezoRain.0x12.val': 10.6143, 'piezoRain.0x13.val': 23.7992,
             'ch_aisle.1.temp': 85.82, 'dewpoint1': 74.12, 'heatindex1': 93.74, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 81.68, 'dewpoint3': 73.4, 'heatindex3': 87.08, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 80.96, 'dewpoint4': 72.32, 'heatindex4': 85.46, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 82.58, 'dewpoint5': 73.58, 'heatindex5': 88.52, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 81.68, 'dewpoint6': 72.32, 'heatindex6': 86.36, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 82.76, 'dewpoint7': 73.22, 'heatindex7': 88.7, 'ch_aisle.7.humidity': 73.0,
             'lightning.count': 0.0, 'lightning.distance': 21.13, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 13.0,
             'ch_temp.1.temp': 79.7, 'ch_lds.1.air': 1.62, 'ch_lds.1.depth': 5.04, 'ch_lds.1.heat': 2044.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742522700.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 70.88, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 66.56, 'feelslike': 70.88, 'common_list.5.val': 0.1063,
             'common_list.0x0B.val': 3.3554, 'common_list.0x0C.val': 3.5791, 'common_list.0x0A.val': 226.0,
             'wh25.abs': 29.8814, 'wh25.rel': 30.0409, 'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0,
             'rain.0x0E.val': 0.0, 't_rainhour': 0.0, 'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0,
             'rain.0x12.val': 0.0, 'rain.0x13.val': 0.0079, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0,
             'piezoRain.0x0D.val': 0.0, 'piezoRain.0x10.val': 0.3622, 'piezoRain.0x11.val': 1.2953,
             'piezoRain.0x12.val': 10.6142, 'piezoRain.0x13.val': 23.7992,
             'ch_aisle.1.temp': 86.18, 'dewpoint1': 74.48, 'heatindex1': 94.64, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 81.86, 'dewpoint3': 73.58, 'heatindex3': 87.44, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 81.14, 'dewpoint4': 72.5, 'heatindex4': 85.64, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 82.94, 'dewpoint5': 73.94, 'heatindex5': 89.24, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 81.86, 'dewpoint6': 72.32, 'heatindex6': 86.9, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 82.94, 'dewpoint7': 73.04, 'heatindex7': 88.7, 'ch_aisle.7.humidity': 72.0,
             'lightning.count': 0.0, 'lightning.distance': 21.13, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 11.0,
             'ch_temp.1.temp': 79.7, 'ch_lds.1.air': 1.60, 'ch_lds.1.depth': 5.06, 'ch_lds.1.heat': 2046.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742523000.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 70.88, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 66.56, 'feelslike': 70.88, 'common_list.5.val': 0.1063,
             'common_list.0x0B.val': 1.5659, 'common_list.0x0C.val': 4.0265, 'common_list.0x0A.val': 228.0,
             'wh25.abs': 29.8814, 'wh25.rel': 30.0409, 'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0,
             'rain.0x0E.val': 0.0, 't_rainhour': 0.0, 'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0,
             'rain.0x12.val': 0.0, 'rain.0x13.val': 0.0079, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0,
             'piezoRain.0x0D.val': 0.0, 'piezoRain.0x10.val': 0.3622, 'piezoRain.0x11.val': 1.2953,
             'piezoRain.0x12.val': 10.6142, 'piezoRain.0x13.val': 23.7992,
             'ch_aisle.1.temp': 86.36, 'dewpoint1': 74.66, 'heatindex1': 95.0, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 81.86, 'dewpoint3': 73.58, 'heatindex3': 87.44, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 81.32, 'dewpoint4': 72.68, 'heatindex4': 86, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 83.12, 'dewpoint5': 73.94, 'heatindex5': 89.6, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 82.04, 'dewpoint6': 72.5, 'heatindex6': 87.08, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 83.12, 'dewpoint7': 73.22, 'heatindex7': 89.06, 'ch_aisle.7.humidity': 72.0,
             'lightning.count': 0.0, 'lightning.distance': 21.13, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 11.0,
             'ch_temp.1.temp': 79.88, 'ch_lds.1.air': 1.67, 'ch_lds.1.depth': 4.99, 'ch_lds.1.heat': 2048.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742523300.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 70.7, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 66.38, 'feelslike': 70.7, 'common_list.5.val': 0.1064,
             'common_list.0x0B.val': 2.0132, 'common_list.0x0C.val': 4.0265, 'common_list.0x0A.val': 234.0,
             'wh25.abs': 29.8784, 'wh25.rel': 30.0379, 'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0,
             'rain.0x0E.val': 0.0, 't_rainhour': 0.0, 'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0,
             'rain.0x12.val': 0.0, 'rain.0x13.val': 0.0079, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0,
             'piezoRain.0x0D.val': 0.0, 'piezoRain.0x10.val': 0.3622, 'piezoRain.0x11.val': 1.2953,
             'piezoRain.0x12.val': 10.6142, 'piezoRain.0x13.val': 23.7992,
             'ch_aisle.1.temp': 86.72, 'dewpoint1': 74.48, 'heatindex1': 95.36, 'ch_aisle.1.humidity': 67.0,
             'ch_aisle.3.temp': 82.04, 'dewpoint3': 73.4, 'heatindex3': 87.44, 'ch_aisle.3.humidity': 75.0,
             'ch_aisle.4.temp': 81.5, 'dewpoint4': 72.86, 'heatindex4': 86.36, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 83.3, 'dewpoint5': 74.12, 'heatindex5': 90.14, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 82.04, 'dewpoint6': 72.5, 'heatindex6': 87.08, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 83.48, 'dewpoint7': 73.58, 'heatindex7': 89.96, 'ch_aisle.7.humidity': 72.0,
             'lightning.count': 0.0, 'lightning.distance': 21.13, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 10.0,
             'ch_temp.1.temp': 80.24, 'ch_lds.1.air': 1.65, 'ch_lds.1.depth': 5.01, 'ch_lds.1.heat': 2048.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742523600.0, 'interval': 5}
        ],
        weewx.METRIC : [
            {'wh25.inhumi': 73.0, 'common_list.0x02.val': 21.7, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.3, 'feelslike': 21.7, 'common_list.5.val': 3.6,
             'common_list.0x0B.val': 0.0, 'common_list.0x0C.val': 0.0, 'common_list.0x0A.val': 306.0,
             'wh25.abs': 1011.8, 'wh25.rel': 1018.2, 'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0,
             'rain.0x0E.val': 0.0, 't_rainhour': 0.0, 'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0,
             'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0, 'rain.0x13.val': 0.02, 'piezoRain.0x0E.val': 0.0,
             'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0, 'piezoRain.0x10.val': 0.92, 'piezoRain.0x11.val': 3.29,
             'piezoRain.0x12.val': 26.96, 'piezoRain.0x13.val': 60.45,
             'ch_aisle.1.temp': 29.6, 'dewpoint1': 23.1, 'heatindex1': 33.6, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 27.4, 'dewpoint3': 22.8, 'heatindex3': 30.1, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 27.1, 'dewpoint4': 22.3, 'heatindex4': 29.5, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 27.9, 'dewpoint5': 23.1, 'heatindex5': 31.1, 'ch_aisle.5.humidity': 75.0,
             'ch_aisle.6.temp': 27.4, 'dewpoint6': 22.2, 'heatindex6': 29.8, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.0, 'dewpoint7': 22.7, 'heatindex7': 31.0, 'ch_aisle.7.humidity': 73.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 13.0,
             'ch_temp.1.temp': 26.2, 'ch_lds.1.air': 492.0, 'ch_lds.1.depth': 1538.0, 'ch_lds.1.heat': 2044.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742522100.0, 'interval': 5},
            {'wh25.inhumi': 73.0, 'common_list.0x02.val': 21.7, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.3, 'feelslike': 21.7, 'common_list.5.val': 3.6, 'common_list.0x0B.val': 2.88,
             'common_list.0x0C.val': 5.04, 'common_list.0x0A.val': 236.0, 'wh25.abs': 1011.8, 'wh25.rel': 1017.2,
             'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0, 'rain.0x0E.val': 0.0, 't_rainhour': 0.0,
             'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0,
             'rain.0x13.val': 0.02, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0,
             'piezoRain.0x10.val': 0.92, 'piezoRain.0x11.val': 3.29, 'piezoRain.0x12.val': 26.96,
             'piezoRain.0x13.val': 60.45,
             'ch_aisle.1.temp': 29.8, 'dewpoint1': 23.3, 'heatindex1': 34.0, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 27.5, 'dewpoint3': 22.9, 'heatindex3': 30.4, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 27.1, 'dewpoint4': 22.3, 'heatindex4': 29.5, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 28.0, 'dewpoint5': 23.0, 'heatindex5': 31.2, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 27.5, 'dewpoint6': 22.3, 'heatindex6': 30.0, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.1, 'dewpoint7': 22.8, 'heatindex7': 31.3, 'ch_aisle.7.humidity': 73.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 13.0,
             'ch_temp.1.temp': 26.4, 'ch_lds.1.air': 500.0, 'ch_lds.1.depth': 1530.0, 'ch_lds.1.heat': 2044.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742522400.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 21.7, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.3, 'feelslike': 21.7, 'common_list.5.val': 3.6, 'common_list.0x0B.val': 0.0,
             'common_list.0x0C.val': 3.24, 'common_list.0x0A.val': 288.0, 'wh25.abs': 1011.7, 'wh25.rel': 1017.1,
             'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0, 'rain.0x0E.val': 0.0, 't_rainhour': 0.0,
             'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0,
             'rain.0x13.val': 0.02, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0,
             'piezoRain.0x10.val': 0.92, 'piezoRain.0x11.val': 3.29, 'piezoRain.0x12.val': 26.96,
             'piezoRain.0x13.val': 60.45,
             'ch_aisle.1.temp': 29.9, 'dewpoint1': 23.4, 'heatindex1': 34.3, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 27.6, 'dewpoint3': 23.0, 'heatindex3': 30.6, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 27.2, 'dewpoint4': 22.4, 'heatindex4': 29.7, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 28.1, 'dewpoint5': 23.1, 'heatindex5': 31.4, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 27.6, 'dewpoint6': 22.4, 'heatindex6': 30.2, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.2, 'dewpoint7': 22.9, 'heatindex7': 31.5, 'ch_aisle.7.humidity': 73.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 13.0,
             'ch_temp.1.temp': 26.5, 'ch_lds.1.air': 494.0, 'ch_lds.1.depth': 1536.0, 'ch_lds.1.heat': 2044.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742522700.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 21.6, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.2, 'feelslike': 21.6, 'common_list.5.val': 3.6, 'common_list.0x0B.val': 5.4,
             'common_list.0x0C.val': 5.76, 'common_list.0x0A.val': 226.0, 'wh25.abs': 1011.9, 'wh25.rel': 1017.3,
             'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0, 'rain.0x0E.val': 0.0, 't_rainhour': 0.0,
             'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0,
             'rain.0x13.val': 0.02, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0,
             'piezoRain.0x10.val': 0.92, 'piezoRain.0x11.val': 3.29, 'piezoRain.0x12.val': 26.96,
             'piezoRain.0x13.val': 60.45,
             'ch_aisle.1.temp': 30.1, 'dewpoint1': 23.6, 'heatindex1': 34.8, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 27.7, 'dewpoint3': 23.1, 'heatindex3': 30.8, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 27.3, 'dewpoint4': 22.5, 'heatindex4': 29.8, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 28.3, 'dewpoint5': 23.3, 'heatindex5': 31.8, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 27.7, 'dewpoint6': 22.4, 'heatindex6': 30.5, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.3, 'dewpoint7': 22.8, 'heatindex7': 31.5, 'ch_aisle.7.humidity': 72.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 11.0,
             'ch_temp.1.temp': 26.5, 'ch_lds.1.air': 487.0, 'ch_lds.1.depth': 1543.0, 'ch_lds.1.heat': 2046.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742523000.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 21.6, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.2, 'feelslike': 21.6, 'common_list.5.val': 3.6, 'common_list.0x0B.val': 2.52,
             'common_list.0x0C.val': 6.48, 'common_list.0x0A.val': 228.0, 'wh25.abs': 1011.9, 'wh25.rel': 1017.3,
             'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0, 'rain.0x0E.val': 0.0, 't_rainhour': 0.0,
             'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0,
             'rain.0x13.val': 0.02, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0,
             'piezoRain.0x10.val': 0.92, 'piezoRain.0x11.val': 3.29, 'piezoRain.0x12.val': 26.96,
             'piezoRain.0x13.val': 60.45,
             'ch_aisle.1.temp': 30.2, 'dewpoint1': 23.7, 'heatindex1': 35.0, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 27.7, 'dewpoint3': 23.1, 'heatindex3': 30.8, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 27.4, 'dewpoint4': 22.6, 'heatindex4': 30.0, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 28.4, 'dewpoint5': 23.3, 'heatindex5': 32.0, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 27.8, 'dewpoint6': 22.5, 'heatindex6': 30.6, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.4, 'dewpoint7': 22.9, 'heatindex7': 31.7, 'ch_aisle.7.humidity': 72.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 11.0,
             'ch_temp.1.temp': 26.6, 'ch_lds.1.air': 510.0, 'ch_lds.1.depth': 1520.0, 'ch_lds.1.heat': 2048.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742523300.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 21.5, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.1, 'feelslike': 21.5, 'common_list.5.val': 3.6, 'common_list.0x0B.val': 3.24,
             'common_list.0x0C.val': 6.48, 'common_list.0x0A.val': 234.0, 'wh25.abs': 1011.8, 'wh25.rel': 1017.2,
             'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0, 'rain.0x0E.val': 0.0, 't_rainhour': 0.0,
             'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0,
             'rain.0x13.val': 0.02, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0,
             'piezoRain.0x10.val': 0.92, 'piezoRain.0x11.val': 3.29, 'piezoRain.0x12.val': 26.96,
             'piezoRain.0x13.val': 60.45,
             'ch_aisle.1.temp': 30.4, 'dewpoint1': 23.6, 'heatindex1': 35.2, 'ch_aisle.1.humidity': 67.0,
             'ch_aisle.3.temp': 27.8, 'dewpoint3': 23.0, 'heatindex3': 30.8, 'ch_aisle.3.humidity': 75.0,
             'ch_aisle.4.temp': 27.5, 'dewpoint4': 22.7, 'heatindex4': 30.2, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 28.5, 'dewpoint5': 23.4, 'heatindex5': 32.3, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 27.8, 'dewpoint6': 22.5, 'heatindex6': 30.6, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.6, 'dewpoint7': 23.1, 'heatindex7': 32.2, 'ch_aisle.7.humidity': 72.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 10.0,
             'ch_temp.1.temp': 26.8, 'ch_lds.1.air': 502.0, 'ch_lds.1.depth': 1528.0, 'ch_lds.1.heat': 2048.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742523600.0, 'interval': 5}
        ],
        weewx.METRICWX: [
            {'wh25.inhumi': 73.0, 'common_list.0x02.val': 21.7, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.3, 'feelslike': 21.7, 'common_list.5.val': 3.6,
             'common_list.0x0B.val': 0.0, 'common_list.0x0C.val': 0.0, 'common_list.0x0A.val': 306.0,
             'wh25.abs': 1011.8, 'wh25.rel': 1018.2, 'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0,
             'rain.0x0E.val': 0.0, 't_rainhour': 0.0, 'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0,
             'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0, 'rain.0x13.val': 0.2, 'piezoRain.0x0E.val': 0.0,
             'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0, 'piezoRain.0x10.val': 9.2, 'piezoRain.0x11.val': 32.9,
             'piezoRain.0x12.val': 269.6, 'piezoRain.0x13.val': 604.5,
             'ch_aisle.1.temp': 29.6, 'dewpoint1': 23.1, 'heatindex1': 33.6, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 27.4, 'dewpoint3': 22.8, 'heatindex3': 30.1, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 27.1, 'dewpoint4': 22.3, 'heatindex4': 29.5, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 27.9, 'dewpoint5': 23.1, 'heatindex5': 31.1, 'ch_aisle.5.humidity': 75.0,
             'ch_aisle.6.temp': 27.4, 'dewpoint6': 22.2, 'heatindex6': 29.8, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.0, 'dewpoint7': 22.7, 'heatindex7': 31.0, 'ch_aisle.7.humidity': 73.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 13.0,
             'ch_temp.1.temp': 26.2, 'ch_lds.1.air': 492.0, 'ch_lds.1.depth': 1538.0, 'ch_lds.1.heat': 2044.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742522100.0, 'interval': 5},
            {'wh25.inhumi': 73.0, 'common_list.0x02.val': 21.7, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.3, 'feelslike': 21.7, 'common_list.5.val': 3.6, 'common_list.0x0B.val': 0.8,
             'common_list.0x0C.val': 1.4, 'common_list.0x0A.val': 236.0, 'wh25.abs': 1011.8, 'wh25.rel': 1017.2,
             'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0, 'rain.0x0E.val': 0.0, 't_rainhour': 0.0,
             'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0,
             'rain.0x13.val': 0.2, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0,
             'piezoRain.0x10.val': 9.2, 'piezoRain.0x11.val': 32.9, 'piezoRain.0x12.val': 269.6,
             'piezoRain.0x13.val': 604.5,
             'ch_aisle.1.temp': 29.8, 'dewpoint1': 23.3, 'heatindex1': 34.0, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 27.5, 'dewpoint3': 22.9, 'heatindex3': 30.4, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 27.1, 'dewpoint4': 22.3, 'heatindex4': 29.5, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 28.0, 'dewpoint5': 23.0, 'heatindex5': 31.2, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 27.5, 'dewpoint6': 22.3, 'heatindex6': 30.0, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.1, 'dewpoint7': 22.8, 'heatindex7': 31.3, 'ch_aisle.7.humidity': 73.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 13.0,
             'ch_temp.1.temp': 26.4, 'ch_lds.1.air': 500.0, 'ch_lds.1.depth': 1530.0, 'ch_lds.1.heat': 2044.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742522400.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 21.7, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.3, 'feelslike': 21.7, 'common_list.5.val': 3.6, 'common_list.0x0B.val': 0.0,
             'common_list.0x0C.val': 0.9, 'common_list.0x0A.val': 288.0, 'wh25.abs': 1011.7, 'wh25.rel': 1017.1,
             'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0, 'rain.0x0E.val': 0.0, 't_rainhour': 0.0,
             'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0,
             'rain.0x13.val': 0.2, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0,
             'piezoRain.0x10.val': 9.2, 'piezoRain.0x11.val': 32.9, 'piezoRain.0x12.val': 269.6,
             'piezoRain.0x13.val': 604.5,
             'ch_aisle.1.temp': 29.9, 'dewpoint1': 23.4, 'heatindex1': 34.3, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 27.6, 'dewpoint3': 23.0, 'heatindex3': 30.6, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 27.2, 'dewpoint4': 22.4, 'heatindex4': 29.7, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 28.1, 'dewpoint5': 23.1, 'heatindex5': 31.4, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 27.6, 'dewpoint6': 22.4, 'heatindex6': 30.2, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.2, 'dewpoint7': 22.9, 'heatindex7': 31.5, 'ch_aisle.7.humidity': 73.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 13.0,
             'ch_temp.1.temp': 26.5, 'ch_lds.1.air': 494.0, 'ch_lds.1.depth': 1536.0, 'ch_lds.1.heat': 2044.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742522700.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 21.6, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.2, 'feelslike': 21.6, 'common_list.5.val': 3.6, 'common_list.0x0B.val': 1.5,
             'common_list.0x0C.val': 1.6, 'common_list.0x0A.val': 226.0, 'wh25.abs': 1011.9, 'wh25.rel': 1017.3,
             'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0, 'rain.0x0E.val': 0.0, 't_rainhour': 0.0,
             'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0,
             'rain.0x13.val': 0.2, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0,
             'piezoRain.0x10.val': 9.2, 'piezoRain.0x11.val': 32.9, 'piezoRain.0x12.val': 269.6,
             'piezoRain.0x13.val': 604.5,
             'ch_aisle.1.temp': 30.1, 'dewpoint1': 23.6, 'heatindex1': 34.8, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 27.7, 'dewpoint3': 23.1, 'heatindex3': 30.8, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 27.3, 'dewpoint4': 22.5, 'heatindex4': 29.8, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 28.3, 'dewpoint5': 23.3, 'heatindex5': 31.8, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 27.7, 'dewpoint6': 22.4, 'heatindex6': 30.5, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.3, 'dewpoint7': 22.8, 'heatindex7': 31.5, 'ch_aisle.7.humidity': 72.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 11.0,
             'ch_temp.1.temp': 26.5, 'ch_lds.1.air': 487.0, 'ch_lds.1.depth': 1543.0, 'ch_lds.1.heat': 2046.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742523000.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 21.6, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.2, 'feelslike': 21.6, 'common_list.5.val': 3.6, 'common_list.0x0B.val': 0.7,
             'common_list.0x0C.val': 1.8, 'common_list.0x0A.val': 228.0, 'wh25.abs': 1011.9, 'wh25.rel': 1017.3,
             'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0, 'rain.0x0E.val': 0.0, 't_rainhour': 0.0,
             'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0,
             'rain.0x13.val': 0.2, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0,
             'piezoRain.0x10.val': 9.2, 'piezoRain.0x11.val': 32.9, 'piezoRain.0x12.val': 269.6,
             'piezoRain.0x13.val': 604.5,
             'ch_aisle.1.temp': 30.2, 'dewpoint1': 23.7, 'heatindex1': 35.0, 'ch_aisle.1.humidity': 68.0,
             'ch_aisle.3.temp': 27.7, 'dewpoint3': 23.1, 'heatindex3': 30.8, 'ch_aisle.3.humidity': 76.0,
             'ch_aisle.4.temp': 27.4, 'dewpoint4': 22.6, 'heatindex4': 30.0, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 28.4, 'dewpoint5': 23.3, 'heatindex5': 32.0, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 27.8, 'dewpoint6': 22.5, 'heatindex6': 30.6, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.4, 'dewpoint7': 22.9, 'heatindex7': 31.7, 'ch_aisle.7.humidity': 72.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 11.0,
             'ch_temp.1.temp': 26.6, 'ch_lds.1.air': 510.0, 'ch_lds.1.depth': 1520.0, 'ch_lds.1.heat': 2048.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742523300.0, 'interval': 5},
            {'wh25.inhumi': 72.0, 'common_list.0x02.val': 21.5, 'common_list.0x07.val': 86.0,
             'common_list.0x03.val': 19.1, 'feelslike': 21.5, 'common_list.5.val': 3.6, 'common_list.0x0B.val': 0.9,
             'common_list.0x0C.val': 1.8, 'common_list.0x0A.val': 234.0, 'wh25.abs': 1011.8, 'wh25.rel': 1017.2,
             'common_list.0x15.val': 0.0, 'common_list.0x17.val': 0.0, 'rain.0x0E.val': 0.0, 't_rainhour': 0.0,
             'rain.0x0D.val': 0.0, 'rain.0x10.val': 0.0, 'rain.0x11.val': 0.0, 'rain.0x12.val': 0.0,
             'rain.0x13.val': 0.2, 'piezoRain.0x0E.val': 0.0, 'p_rainhour': 0.0, 'piezoRain.0x0D.val': 0.0,
             'piezoRain.0x10.val': 9.2, 'piezoRain.0x11.val': 32.9, 'piezoRain.0x12.val': 269.6,
             'piezoRain.0x13.val': 604.5,
             'ch_aisle.1.temp': 30.4, 'dewpoint1': 23.6, 'heatindex1': 35.2, 'ch_aisle.1.humidity': 67.0,
             'ch_aisle.3.temp': 27.8, 'dewpoint3': 23.0, 'heatindex3': 30.8, 'ch_aisle.3.humidity': 75.0,
             'ch_aisle.4.temp': 27.5, 'dewpoint4': 22.7, 'heatindex4': 30.2, 'ch_aisle.4.humidity': 75.0,
             'ch_aisle.5.temp': 28.5, 'dewpoint5': 23.4, 'heatindex5': 32.3, 'ch_aisle.5.humidity': 74.0,
             'ch_aisle.6.temp': 27.8, 'dewpoint6': 22.5, 'heatindex6': 30.6, 'ch_aisle.6.humidity': 73.0,
             'ch_aisle.7.temp': 28.6, 'dewpoint7': 23.1, 'heatindex7': 32.2, 'ch_aisle.7.humidity': 72.0,
             'lightning.count': 0.0, 'lightning.distance': 34.0, 'ch_soil.1.humidity': 32.0, 'ch_pm25.1.PM25': 10.0,
             'ch_temp.1.temp': 26.8, 'ch_lds.1.air': 502.0, 'ch_lds.1.depth': 1528.0, 'ch_lds.1.heat': 2048.0,
             'ch_lds.2.heat': 0.0, 'ch_lds.3.heat': 0.0, 'ch_lds.4.heat': 0.0, 'datetime': 1742523600.0, 'interval': 5}
        ]
    }
    gen_history_results_count = 8255
    clean_data = {
        'clean': {
            'test_data': ['12345ABCDE', '67890FGHIJ'],
            'response': ['12345ABCDE', '67890FGHIJ']
        },
        'null': {
            'test_data': ['1234\x005ABCDE', '678\x0090FGHI\x00J'],
            'response': ['12345ABCDE', '67890FGHIJ']
        },
        'blank': {
            'test_data': ['12345ABCDE', '\n', '\n', '67890FGHIJ'],
            'response': ['12345ABCDE', '67890FGHIJ']
        },
        'blanknull': {
            'test_data': ['\n', '1234\x005ABCDE', '\n', '678\x0090FGHI\x00J'],
            'response': ['12345ABCDE', '67890FGHIJ']
        }

    }

    @patch.object(user.ecowitt_http.EcowittDevice, 'get_sdmmc_info_data')
    def test_device_catchup_init(self, mock_get_sdmmc_info_data):
        """Test EcowittCatchupDevice initialisation."""

        print()
        print('   testing EcowittCatchupDevice initialisation ...')
        # set return values for mocked methods
        # get_sdmmc_info_data
        mock_get_sdmmc_info_data.return_value = DeviceCatchupTestCase.fake_get_sdmmc_info_data

        # we will be manipulating the catchup device config so make a copy that
        # we can alter without affecting other test methods
        device_catchup_config_copy = configobj.ConfigObj(self.device_catchup_config)

        # first test a minimal config, pretty much just IP address and the rest
        # are defaults
        # obtain an EcowittDeviceCatchup object
        device_catchup = self.get_device_catchup(config=device_catchup_config_copy,
                                                 caller='test_device_catchup_init')
        # test the IP address was properly set
        self.assertSequenceEqual(device_catchup.ip_address,
                                 device_catchup_config_copy['ip_address'])
        # test url_timeout was properly set
        self.assertEqual(device_catchup.url_timeout,
                         user.ecowitt_http.DEFAULT_URL_TIMEOUT)
        # test unit_system was properly set
        self.assertEqual(device_catchup.unit_system,
                         user.ecowitt_http.UNIT_SYSTEM)
        # test catchup_grace was properly set
        self.assertEqual(device_catchup.catchup_grace,
                         user.ecowitt_http.DEFAULT_CATCHUP_GRACE)
        # test max_catchup_retries was properly set
        self.assertEqual(device_catchup.max_catchup_retries,
                         user.ecowitt_http.DEFAULT_CATCHUP_RETRIES)

        # explicit values for non-IP address config items
        device_catchup_config_copy['url_timeout'] = 5
        device_catchup_config_copy['unit_system'] = weewx.US
        device_catchup_config_copy['catchup_grace'] = 2
        device_catchup_config_copy['max_retries'] = 4
        # obtain an EcowittDeviceCatchup object
        device_catchup = self.get_device_catchup(config=device_catchup_config_copy,
                                                 caller='test_device_catchup_init')
        # test the IP address was properly set
        self.assertSequenceEqual(device_catchup.ip_address,
                                 device_catchup_config_copy['ip_address'])
        # test url_timeout was properly set
        self.assertEqual(device_catchup.url_timeout, 5)
        # test unit_system was properly set
        self.assertEqual(device_catchup.unit_system, weewx.US)
        # test catchup_grace was properly set
        self.assertEqual(device_catchup.catchup_grace, 2)
        # test max_catchup_retries was properly set
        self.assertEqual(device_catchup.max_catchup_retries, 4)

        # nonsense values for non-IP address config items
        # first construct key word args for get_device_catchup() call
        kw_args = {'config': device_catchup_config_copy,
                   'caller': 'test_device_catchup_init'}
        # set nonsense url_timeout value
        device_catchup_config_copy['url_timeout'] = 'five'
        # test nonsense url_timeout raises a ValueError
        self.assertRaises(ValueError, self.get_device_catchup, **kw_args)
        # pop off url_timeout from key word args
        _ = device_catchup_config_copy.pop('url_timeout')
        # set nonsense unit_system value
        device_catchup_config_copy['unit_system'] = 'unit'
        # test nonsense unit_system raises a ValueError
        self.assertRaises(ValueError, self.get_device_catchup, **kw_args)
        # pop off unit_system from key word args
        _ = device_catchup_config_copy.pop('unit_system')
        # set nonsense catchup_grace value
        device_catchup_config_copy['catchup_grace'] = 'two'
        # test nonsense catchup_grace raises a ValueError
        self.assertRaises(ValueError, self.get_device_catchup, **kw_args)
        # pop off catchup_grace from key word args
        _ = device_catchup_config_copy.pop('catchup_grace')
        # set nonsense max_retries value
        device_catchup_config_copy['max_retries'] = 'four'
        # test nonsense max_retries raises a ValueError
        self.assertRaises(ValueError, self.get_device_catchup, **kw_args)

    @patch.object(user.ecowitt_http.EcowittDevice, 'get_sdmmc_info_data')
    def test_clean_data(self, mock_get_sdmmc_info_data):
        """Test EcowittCatchupDevice clean_data method."""

        print()
        print('   testing EcowittCatchupDevice.clean_data() ...')
        # set return values for mocked methods
        # get_sdmmc_info_data
        mock_get_sdmmc_info_data.return_value = DeviceCatchupTestCase.fake_get_sdmmc_info_data
        # obtain an EcowittDeviceCatchup object
        device_catchup = self.get_device_catchup(config=configobj.ConfigObj(self.device_catchup_config),
                                                 caller='test_clean_data')
        # test data that is already 'clean'
        self.assertSequenceEqual(device_catchup.clean_data(self.clean_data['clean']['test_data']),
                                 self.clean_data['clean']['response'])
        # test data that includes null bytes
        self.assertSequenceEqual(device_catchup.clean_data(self.clean_data['null']['test_data']),
                                 self.clean_data['null']['response'])
        # test data that includes blank lines
        self.assertSequenceEqual(device_catchup.clean_data(self.clean_data['blank']['test_data']),
                                 self.clean_data['blank']['response'])

    def fake_get_file(self, filename):
        """Creates a urllib.response.addinfourl object from a file.

        Args:
            filename: The file name.

        Returns:
            A urllib.response.addinfourl object.
        """

        # create the full path and file name
        filename_path = '/'.join(['/var/tmp', filename])
        # obtain the file contents
        with open(filename_path, 'rb') as f:
            file_content = f.read()
        # obtain the file contents as a binary stream
        file_obj = io.BytesIO(file_content)
        # set some headers
        headers = {
            'Content-Length': str(len(file_content)),
            'Content-Type': 'application/octet-stream',
            'Last-Modified': str(os.path.getmtime(filename_path))
        }
        # create the url
        url = 'file://' + os.path.abspath(filename_path)
        # create an addinfourl object
        response = urllib.response.addinfourl(file_obj, headers, url)
        # add the code and msg properties
        response.code = 200
        response.msg = 'OK'
        # return the addinfourl object
        return response

    @patch.object(user.ecowitt_http.EcowittDeviceCatchup, 'get_file', fake_get_file)
    @patch.object(user.ecowitt_http.EcowittDevice, 'get_sdmmc_info_data')
    def test_gen_history_records(self, mock_get_sdmmc_info_data):
        """Test EcowittCatchupDevice.gen_history_records method."""

        print()
        print('   testing EcowittCatchupDevice.gen_history_records() ...')
        # set return values for mocked methods
        # get_sdmmc_info_data
        mock_get_sdmmc_info_data.return_value = DeviceCatchupTestCase.gen_get_sdmmc_info_data

        for unit_system in (weewx.US, weewx.METRIC, weewx.METRICWX):
            # obtain an EcowittDeviceCatchup object that emits records using
            # the unit system being tested
            catchup_config = configobj.ConfigObj(self.device_catchup_config)
            catchup_config['unit_system'] = unit_system
            device_catchup = self.get_device_catchup(config=catchup_config,
                                                     caller='test_gen_history_records')
            rec_no = 0
            for rec in device_catchup.gen_history_records():
                if rec_no < len(self.gen_history_first_six_results[unit_system]):
                    for field in rec.keys():
                        self.assertAlmostEqual(rec[field],
                                               self.gen_history_first_six_results[unit_system][rec_no][field],
                                               2)
                rec_no += 1
            self.assertEqual(rec_no, self.gen_history_results_count)

    @staticmethod
    def get_device_catchup(config, caller):
        """Get an EcowittDeviceCatchup object.

        Return an EcowittDeviceCatchup object or raise a unittest.SkipTest
        exception.
        """

        # create a dummy engine, wrap in a try..except in case there is an
        # error
        try:
            catchup_obj = user.ecowitt_http.EcowittDeviceCatchup(**config)
        except user.ecowitt_http.CatchupObjectError as e:
            # could not communicate with the mocked or real gateway device for
            # some reason, skip the test if we have an engine try to shut it
            # down
            print("\nShutting down get_device_catchup... ")
            # now raise unittest.SkipTest to skip this test class
            raise unittest.SkipTest("%s: Unable to connect to obtain EcowittDeviceCatchup object" % caller)
        else:
            return catchup_obj


class HttpParserTestCase(unittest.TestCase):
    """Test the EcowittHttpParser class."""

    # supported devices
    supported_devices = ('GW1100', 'GW1200', 'GW2000',
                         'GW3000', 'WH2650', 'WH2680',
                         'WN1900', 'WS3900', 'WS3910')
    # unsupported devices
    unsupported_devices = ('GW1000',)
    # known device devices
    known_devices = supported_devices + unsupported_devices
    # lookup for Ecowitt units to WeeWX units
    unit_lookup = {
        'c': 'degree_C',
        'f': 'degree_F',
        'km': 'km',
        'mi': 'mile',
        'nmi': 'nautical_mile',
        'hpa': 'hPa',
        'kfc': 'kfc',
        'klux': 'klux',
        'kpa': 'kPa',
        'inhg': 'inHg',
        'mmhg': 'mmHg',
        'mm': 'mm',
        'in': 'inch',
        'ft': 'foot',
        'mm/hr': 'mm_per_hour',
        'in/hr': 'inch_per_hour',
        'km/h': 'km_per_hour',
        'm/s': 'meter_per_second',
        'mph': 'mile_per_hour',
        'knots': 'knot',
        '%': 'percent',
        'w/m2': 'watt_per_meter_squared'
    }
    # processor function lookup for common_list observations
    c_list_fns = {
        '0x01': 'process_temperature_object',
        '0x02': 'process_temperature_object',
        '0x03': 'process_temperature_object',
        '3': 'process_temperature_object',
        '0x04': 'process_temperature_object',
        '4': 'process_temperature_object',
        '0x05': 'process_temperature_object',
        '5': 'process_pressure_object', # VPD (suspected)
        '0x07': 'process_humidity_object',
        '0x08': 'process_noop_object',
        '0x09': 'process_noop_object',
        '0x0A': 'process_direction_object',
        '0x0B': 'process_speed_object',
        '0x0C': 'process_speed_object',
        '0x0D': 'process_rainfall_object',
        '0x0E': 'process_rainrate_object',
        '0x0F': 'process_rainfall_object',
        '0x10': 'process_rainfall_object',
        '0x11': 'process_rainfall_object',
        '0x12': 'process_rainfall_object',
        '0x13': 'process_rainfall_object',
        '0x14': 'process_rainfall_object',
        '0x15': 'process_light_object',
        '0x16': 'process_uv_radiation_object',
        '0x17': 'process_index_object',
        '0x18': 'process_noop_object',
        '0x19': 'process_speed_object',
        'srain_piezo': 'process_boolean_object'
    }
    # sensor IDs for sensors that are not registered (ie learning/registering
    # and disabled)
    not_registered = ('fffffffe', 'ffffffff')

    get_version_test_data = {
        'input': {
            'version': 'Version: GW2000C_V3.1.2',
            'newVersion': '1',
            'platform': 'ecowitt'
        },
        'result': {
            'version': 'Version: GW2000C_V3.1.2',
            'firmware_version': 'V3.1.2',
            'newVersion': 1,
            'platform': 'ecowitt'
        }
    }

    get_ws_settings_test_data = {
        'input': {
            'platform': 'ecowitt',
            'ost_interval': '1',
            'sta_mac': 'E8:68:E7:12:9D:D7',
            'wu_id': '',
            'wu_key': '',
            'wcl_id': '',
            'wcl_key': '',
            'wow_id': '',
            'wow_key': '',
            'Customized': 'disable',
            'Protocol': 'ecowitt',
            'ecowitt_ip': 'http://some.url.com',
            'ecowitt_path': '/ecowitt.php',
            'ecowitt_port': '80',
            'ecowitt_upload': '30',
            'usr_wu_ip': 'http://another.url.com',
            'usr_wu_path': '',
            'usr_wu_id': '',
            'usr_wu_key': '',
            'usr_wu_port': '80',
            'usr_wu_upload': '300'
        },
        'result': {
            'platform': 'ecowitt',
            'ost_interval': 1,
            'sta_mac': 'E8:68:E7:12:9D:D7',
            'wu_id': '',
            'wu_key': '',
            'wcl_id': '',
            'wcl_key': '',
            'wow_id': '',
            'wow_key': '',
            'Customized': False,
            'Protocol': 'ecowitt',
            'ecowitt_ip': 'http://some.url.com',
            'ecowitt_path': '/ecowitt.php',
            'ecowitt_port': 80,
            'ecowitt_upload': 30,
            'usr_wu_ip': 'http://another.url.com',
            'usr_wu_path': '',
            'usr_wu_id': '',
            'usr_wu_key': '',
            'usr_wu_port': 80,
            'usr_wu_upload': 300
        }
    }
    
    def setUp(self):

        # setup additional unit conversions etc
        user.ecowitt_http.define_units(dict())
        # get a Parser object
        self.parser = user.ecowitt_http.EcowittHttpParser()
        self.maxDiff = None

    def tearDown(self):

        pass

    def test_constants(self):
        """Test constants used by class EcowittHttpParser"""

        # test supported models
        print()
        print('    testing supported models...')
        self.assertEqual(user.ecowitt_http.SUPPORTED_DEVICES,
                        self.supported_devices)

        # test unsupported models
        print('    testing unsupported models...')
        self.assertEqual(user.ecowitt_http.UNSUPPORTED_DEVICES,
                         self.unsupported_devices)

        # test known models
        print('    testing known models...')
        self.assertEqual(user.ecowitt_http.KNOWN_DEVICES,
                         self.known_devices)

        # test unit lookup
        print('    testing unit lookup...')
        self.assertEqual(self.parser.unit_lookup, self.unit_lookup)

        # test common list processor function lookup
        print('    testing common list processor function lookup...')
        self.assertEqual(self.parser.processor_fns, self.c_list_fns)

        # test not_registered
        print('    testing not registered lookup...')
        self.assertEqual(self.parser.not_registered, self.not_registered)

        # TODO. Test light conversion functions ?

    def test_parse_obs_value(self):
        """Test the EcowittHttpParser.parse_obs_value() function."""

        key = 'temp'
        json_object_test_data = {'temperature': {'id': '0x03',
                                                 'val': '26.5',
                                                 'unit': 'C',
                                                 'battery': '0'},
                                 'humidity': {'id': '0x07',
                                              'val': '56%'},
                                 'direction': {'id': '0x0A',
                                               'val': '272'},
                                 'wind_speed': {'id': '0x0B',
                                                'val': '4.20 km/h'},
                                 'rain': {'id': '0x11',
                                          'val': '4.6 mm',
                                          'battery': '5',
                                          'voltage': '3.28'},
                                 'rain_rate': {'id': '0x0E',
                                               'val': '2.2 mm/Hr'},
                                 'light': {'id': '0x15',
                                           'val': '157.38 W/m2'},
#                                 'uv': {'id': '0x16',
#                                        'val': '0.0C'},
                                 'uvi': {'id': '0x17',
                                         'val': '1'}
                                 }
        unit_group = 'group_temperature'
        device_units = {'metric': {'group_temperature': 'degree_C',
                                   'group_pressure': 'hPa',
                                   'group_speed': 'km_per_hour',
                                   'group_rain': 'cm',
                                   'group_illuminance': 'lux',
                                   'group_direction': 'degree_compass'},
                        'metric_wx': {'group_temperature': 'degree_C',
                                      'group_pressure': 'hPa',
                                      'group_speed': 'meter_per_second',
                                      'group_rain': 'mm',
                                      'group_illuminance': 'lux',
                                      'group_direction': 'degree_compass'},
                        'us': {'group_temperature': 'degree_F',
                               'group_pressure': 'inHg',
                               'group_speed': 'mile_per_hour',
                               'group_rain': 'inch',
                               'group_illuminance': 'lux',
                               'group_direction': 'degree_compass'}
                        }
        print()
        print('    testing EcowittHttpParser.parse_obs_value()...')

        print()
        print('        testing processing of metric data responses...')
        # test normal responses for each obs type using metric data
        # temperature
        result = self.parser.parse_obs_value(key='val',
                                             json_object=json_object_test_data['temperature'],
                                             unit_group='group_temperature',
                                             device_units=device_units['metric'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(26.5, 'degree_C', 'group_temperature'))
        self.assertEqual(result, expected)
        # humidity
        result = self.parser.parse_obs_value(key='val',
                                             json_object=json_object_test_data['humidity'],
                                             unit_group='group_humidity',
                                             device_units=device_units['metric'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(56, 'percent', 'group_humidity'))
        self.assertEqual(result, expected)
        # direction
        result = self.parser.parse_obs_value(key='val',
                                             json_object=json_object_test_data['direction'],
                                             unit_group='group_direction',
                                             device_units=device_units['metric'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(272, 'degree_compass', 'group_direction'))
        self.assertEqual(result, expected)
        # wind speed
        result = self.parser.parse_obs_value(key='val',
                                             json_object=json_object_test_data['wind_speed'],
                                             unit_group='group_speed',
                                             device_units=device_units['metric'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(4.20, 'km_per_hour', 'group_speed'))
        self.assertEqual(result, expected)
        # rain
        result = self.parser.parse_obs_value(key='val',
                                             json_object=json_object_test_data['rain'],
                                             unit_group='group_rain',
                                             device_units=device_units['metric'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(4.6, 'mm', 'group_rain'))
        self.assertEqual(result, expected)
        # rain rate
        result = self.parser.parse_obs_value(key='val',
                                             json_object=json_object_test_data['rain_rate'],
                                             unit_group='group_rainrate',
                                             device_units=device_units['metric'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(2.2, 'mm_per_hour', 'group_rainrate'))
        self.assertEqual(result, expected)
        # light
        result = self.parser.parse_obs_value(key='val',
                                             json_object=json_object_test_data['light'],
                                             unit_group='group_illuminance',
                                             device_units=device_units['metric'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(157.38, 'watt_per_meter_squared', 'group_illuminance'))
        self.assertEqual(result, expected)

        # now test using imperial data
        print('        testing processing of US customary data responses...')
        # temperature
        _json_object = dict(json_object_test_data['temperature'])
        _json_object['unit'] = 'F'
        result = self.parser.parse_obs_value(key='val',
                                             json_object=_json_object,
                                             unit_group='group_temperature',
                                             device_units=device_units['us'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(26.5, 'degree_F', 'group_temperature'))
        self.assertEqual(result, expected)
        # wind speed
        _json_object = dict(json_object_test_data['wind_speed'])
        _json_object['val'] = '4.20 mph'
        result = self.parser.parse_obs_value(key='val',
                                             json_object=_json_object,
                                             unit_group='group_speed',
                                             device_units=device_units['us'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(4.20, 'mile_per_hour', 'group_speed'))
        self.assertEqual(result, expected)
        # rain
        _json_object = dict(json_object_test_data['rain'])
        _json_object['val'] = '4.6 in'
        result = self.parser.parse_obs_value(key='val',
                                             json_object=_json_object,
                                             unit_group='group_rain',
                                             device_units=device_units['us'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(4.6, 'inch', 'group_rain'))
        self.assertEqual(result, expected)
        # rain rate
        _json_object = dict(json_object_test_data['rain_rate'])
        _json_object['val'] = '2.2 in/Hr'
        result = self.parser.parse_obs_value(key='val',
                                             json_object=_json_object,
                                             unit_group='group_rainrate',
                                             device_units=device_units['us'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(2.2, 'inch_per_hour', 'group_rainrate'))
        self.assertEqual(result, expected)

        # now test using remaining untested units (eg m/s, knot)
        print('        testing processing of remaining unit data responses...')
        # wind speed - m/s
        _json_object = dict(json_object_test_data['wind_speed'])
        _json_object['val'] = '4.20 m/s'
        result = self.parser.parse_obs_value(key='val',
                                             json_object=_json_object,
                                             unit_group='group_speed',
                                             device_units=device_units['metric_wx'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(4.20, 'meter_per_second', 'group_speed'))
        self.assertEqual(result, expected)
        # wind speed - knots
        _json_object = dict(json_object_test_data['wind_speed'])
        _json_object['val'] = '4.20 knots'
        _device_units = dict(device_units['metric'])
        _device_units['group_speed'] = 'knot'
        result = self.parser.parse_obs_value(key='val',
                                             json_object=_json_object,
                                             unit_group='group_speed',
                                             device_units=_device_units)
        expected = ValueTupleMatcher(weewx.units.ValueTuple(4.20, 'knot', 'group_speed'))
        self.assertEqual(result, expected)

        # now test exceptions/error states brought on by bad inputs
        print('        testing processing of malformed data...')
        # test obs field is missing from input,units included in obs value
        # get the test input
        json_object = json_object_test_data['wind_speed']
        # pop off the 'val' field
        _ = json_object.pop('val', None)
        # perform the test, we should see a KeyError exception
        self.assertRaises(KeyError,
                          self.parser.parse_obs_value,
                          key='val',
                          json_object=json_object,
                          unit_group='group_speed',
                          device_units=device_units['metric'])
        # test no matches obtained from obs field regex
        # get the test input
        json_object = json_object_test_data['wind_speed']
        # set the 'val' key value to a string
        json_object['val'] = 'test'
        # perform the test, we should see a ParseError exception
        self.assertRaises(user.ecowitt_http.ParseError,
                          self.parser.parse_obs_value,
                          key='val',
                          json_object=json_object,
                          unit_group='group_speed',
                          device_units=device_units['metric'])
        # test where regex match cannot be converted to float
        # get the test input
        json_object = json_object_test_data['wind_speed']
        # set the 'val' key value to a string that will match with no numerics
        json_object['val'] = ',.,'
        # perform the test, we should see a ParseError exception
        self.assertRaises(user.ecowitt_http.ParseError,
                          self.parser.parse_obs_value,
                          key='val',
                          json_object=json_object,
                          unit_group='group_speed',
                          device_units=device_units['metric'])
        # test an included units with an unknown unit string
        # get the test input
        json_object = json_object_test_data['wind_speed']
        # set the 'val' key value to a numeric with an unknown unit string
        json_object['val'] = '4.2 dogs'
        # perform the test, we should see a ParseError exception
        self.assertRaises(user.ecowitt_http.ParseError,
                          self.parser.parse_obs_value,
                          key='val',
                          json_object=json_object,
                          unit_group='group_speed',
                          device_units=device_units['metric'])
        # test separate 'unit' key with unknown unit
        # get the test input
        json_object = json_object_test_data['temperature']
        # set the 'unit' key value to an unknown unit string
        json_object['unit'] = 'test'
        # perform the test, we should see a ParseError exception
        self.assertRaises(user.ecowitt_http.ParseError,
                          self.parser.parse_obs_value,
                          key='val',
                          json_object=json_object,
                          unit_group='group_temperature',
                          device_units=device_units['metric'])
        # # test unknown device units unit string
        # # get the test input
        # json_object = json_object_test_data['temperature']
        # # pop off the 'unit' key to force device units to be used
        # _ = json_object.pop('unit', None)
        # # make a copy of the device units to be used, we need to change them
        # metric_device_units = dict(device_units['metric'])
        # # pop off the 'group_temperature' key
        # _ = metric_device_units.pop('group_temperature', None)
        # # perform the test, we should see a ParseError exception
        # self.assertRaises(user.ecowitt_http.ParseError,
        #                   self.parser.parse_obs_value,
        #                   key='val',
        #                   json_object=json_object,
        #                   unit_group='group_temperature',
        #                   device_units=metric_device_units)
        # test that when device_units parameter is set to None the defaults
        # are used
        # first check where device units are used and a non-None device units
        # parameter was used
        # get the test input
        json_object = json_object_test_data['temperature']
        # pop off the 'unit' key to force device units to be used
        _ = json_object.pop('unit', None)
        result = self.parser.parse_obs_value(key='val',
                                             json_object=json_object,
                                             unit_group='group_temperature',
                                             device_units=device_units['metric'])
        expected = ValueTupleMatcher(weewx.units.ValueTuple(26.5, 'degree_C', 'group_temperature'))
        self.assertEqual(result, expected)
        # # now check where device units are used but a None device units
        # # parameter was used
        # # get the test input
        # json_object = json_object_test_data['temperature']
        # # pop off the 'unit' key to force device units to be used
        # _ = json_object.pop('unit', None)
        # # perform the test, we should see a ParseError exception
        # self.assertRaises(user.ecowitt_http.ParseError,
        #                   self.parser.parse_obs_value,
        #                   key='val',
        #                   json_object=json_object,
        #                   unit_group='group_temperature',
        #                   device_units=None)

    def test_parse_get_version(self):
        """Test the EcowittHttpParser.parse_get_version() method."""

        print()
        print('    testing EcowittHttpParser.parse_get_version()...')

        # test a normal response
        self.assertDictEqual(self.parser.parse_get_version(response=self.get_version_test_data['input']),
                             self.get_version_test_data['result'])

        # test a response that has no 'version' key
        # get the get_version test data and remove the 'version' field
        modified_input = dict(self.get_version_test_data['input'])
        _ = modified_input.pop('version')
        # get the expected result, it will have no 'version' and no
        # 'firmware_version' keys
        modified_result = dict(self.get_version_test_data['result'])
        _ = modified_result.pop('version')
        _ = modified_result.pop('firmware_version')
        # do the test
        self.assertDictEqual(self.parser.parse_get_version(response=modified_input),
                             modified_result)

        # test a response where the 'version' value is not a string
        # get the get_version test data and set the 'version' field to an integer
        modified_input = dict(self.get_version_test_data['input'])
        modified_input['version'] = 5
        # get the expected result, it will have 'version' key value set to '5'
        # and the 'firmware_version' key value set to None
        modified_result = dict(self.get_version_test_data['result'])
        modified_result['version'] = '5'
        modified_result['firmware_version'] = None
        self.assertDictEqual(self.parser.parse_get_version(response=modified_input),
                             modified_result)

        # test a response where the 'version' value contains no '_'
        # get the get_version test data and set the 'version' field to a string
        # without a '_'
        modified_input = dict(self.get_version_test_data['input'])
        modified_input['version'] = 'GW2000CV3.1.2'
        # get the expected result, it will have 'version' key value set to the
        # input 'version' key value and the 'firmware_version' key value set to
        # None
        modified_result = dict(self.get_version_test_data['result'])
        modified_result['version'] = 'GW2000CV3.1.2'
        modified_result['firmware_version'] = None
        self.assertDictEqual(self.parser.parse_get_version(response=modified_input),
                             modified_result)

        # test a response where the 'newVersion' cannot be converted to an int
        # get the get_version test data and set the 'newVersion' field to a
        # non-numeric parseable value
        modified_input = dict(self.get_version_test_data['input'])
        modified_input['newVersion'] = '2.3a'
        # get the expected result, it will have the 'newVersion' key value set
        # to None
        modified_result = dict(self.get_version_test_data['result'])
        modified_result['newVersion'] = None
        self.assertDictEqual(self.parser.parse_get_version(response=modified_input),
                             modified_result)

        # test the case where response is not a dict
        # perform the test, we should see a ParseError exception
        self.assertRaises(user.ecowitt_http.ParseError,
                          self.parser.parse_get_version,
                          response="test string")

    def test_parse_get_ws_settings(self):
        """Test the EcowittHttpParser.parse_get_ws_settings() method."""

        print()
        print('    testing EcowittHttpParser.parse_get_ws_settings()...')

        # test a normal response
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=self.get_ws_settings_test_data['input']),
                             self.get_ws_settings_test_data['result'])

        # test a response that has no 'platform' key
        # get the get_ws_settings test data and remove the 'platform' key
        modified_input = dict(self.get_ws_settings_test_data['input'])
        _ = modified_input.pop('platform', None)
        # get the expected result, it will have no 'platform' key
        modified_result = dict(self.get_ws_settings_test_data['result'])
        _ = modified_result.pop('platform', None)
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has no 'ost_interval' key
        # get the get_ws_settings test data and remove the 'ost_interval' key
        modified_input = dict(self.get_ws_settings_test_data['input'])
        _ = modified_input.pop('ost_interval', None)
        # get the expected result, it will have the 'interval' key value set to
        # None
        modified_result = dict(self.get_ws_settings_test_data['result'])
        _ = modified_result.pop('ost_interval', None)
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response where the 'ost_interval' key value is a numeric int
        # get the get_ws_settings test data and remove the 'ost_interval' key
        modified_input = dict(self.get_ws_settings_test_data['input'])
        modified_input['ost_interval'] = 10
        # get the expected result, it will have the 'interval' key value set
        # to 10
        modified_result = dict(self.get_ws_settings_test_data['result'])
        modified_result['ost_interval'] = 10
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response where the 'ost_interval' key value is a numeric float
        # get the get_ws_settings test data and remove the 'ost_interval' key
        modified_input = dict(self.get_ws_settings_test_data['input'])
        modified_input['ost_interval'] = 15.2
        # get the expected result, it will have the 'interval' key value set
        # to 15
        modified_result = dict(self.get_ws_settings_test_data['result'])
        modified_result['ost_interval'] = 15
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has no 'Customized' key
        # get the get_ws_settings test data and remove the 'Customized' key
        modified_input = dict(self.get_ws_settings_test_data['input'])
        _ = modified_input.pop('Customized', None)
        # get the expected result, it will have no 'cus_state' key
        modified_result = dict(self.get_ws_settings_test_data['result'])
        _ = modified_result.pop('Customized', None)
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has the 'Customized' key value set to a number
        # get the get_ws_settings test data and set the 'Customized' key to 5
        modified_input = dict(self.get_ws_settings_test_data['input'])
        modified_input['Customized'] = 5
        # get the expected result, it will have the 'cus_state' key value set to None
        modified_result = dict(self.get_ws_settings_test_data['result'])
        modified_result['Customized'] = None
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has no 'Protocol' key
        # get the get_ws_settings test data and remove the 'Protocol' key
        modified_input = dict(self.get_ws_settings_test_data['input'])
        _ = modified_input.pop('Protocol', None)
        # get the expected result, it will have no 'cus_protocol' key
        modified_result = dict(self.get_ws_settings_test_data['result'])
        _ = modified_result.pop('Protocol', None)
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has the 'Protocol' key value set to a number
        # get the get_ws_settings test data and set the 'Protocol' key to 5
        modified_input = dict(self.get_ws_settings_test_data['input'])
        modified_input['Protocol'] = 5
        # get the expected result, it will have the 'cus_protocol' key value
        # set to None
        modified_result = dict(self.get_ws_settings_test_data['result'])
        modified_result['Protocol'] = None
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test the case where source key value pairs for renamed (only) keys do
        # not exist
        # get the get_ws_settings test data and remove the keys concerned
        modified_input = dict(self.get_ws_settings_test_data['input'])
        _ = modified_input.pop('sta_mac', None)
        _ = modified_input.pop('ecowitt_ip', None)
        _ = modified_input.pop('ecowitt_path', None)
        _ = modified_input.pop('usr_wu_ip', None)
        _ = modified_input.pop('usr_wu_path', None)
        _ = modified_input.pop('usr_wu_id', None)
        _ = modified_input.pop('usr_wu_key', None)
        # get the expected result, it will have none of the keys concerned
        modified_result = dict(self.get_ws_settings_test_data['result'])
        _ = modified_result.pop('sta_mac', None)
        _ = modified_result.pop('ecowitt_ip', None)
        _ = modified_result.pop('ecowitt_path', None)
        _ = modified_result.pop('usr_wu_ip', None)
        _ = modified_result.pop('usr_wu_path', None)
        _ = modified_result.pop('usr_wu_id', None)
        _ = modified_result.pop('usr_wu_key', None)
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test the case where key value pairs that are passed through unchanged
        # do not exist
        # get the get_ws_settings test data and remove the keys concerned
        modified_input = dict(self.get_ws_settings_test_data['input'])
        _ = modified_input.pop('wu_id', None)
        _ = modified_input.pop('wu_key', None)
        _ = modified_input.pop('wcl_id', None)
        _ = modified_input.pop('wcl_key', None)
        _ = modified_input.pop('wow_id', None)
        _ = modified_input.pop('wow_key', None)
        # get the expected result, it will have none of the keys concerned
        modified_result = dict(self.get_ws_settings_test_data['result'])
        _ = modified_result.pop('wu_id', None)
        _ = modified_result.pop('wu_key', None)
        _ = modified_result.pop('wcl_id', None)
        _ = modified_result.pop('wcl_key', None)
        _ = modified_result.pop('wow_id', None)
        _ = modified_result.pop('wow_key', None)
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has no 'ecowitt_port' key
        # get the get_ws_settings test data and remove the 'ecowitt_port' key
        modified_input = dict(self.get_ws_settings_test_data['input'])
        _ = modified_input.pop('ecowitt_port', None)
        # get the expected result, it will have no 'cus_ecowitt_port' key
        modified_result = dict(self.get_ws_settings_test_data['result'])
        _ = modified_result.pop('ecowitt_port', None)
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has the 'ecowitt_port' key value cannot be
        # coalesced to an integer
        # get the get_ws_settings test data and set the 'ecowitt_port' key to 'abc'
        modified_input = dict(self.get_ws_settings_test_data['input'])
        modified_input['ecowitt_port'] = 'abc'
        # get the expected result, it will have the 'cus_ecowitt_port' key
        # value set to None
        modified_result = dict(self.get_ws_settings_test_data['result'])
        modified_result['ecowitt_port'] = None
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has no 'ecowitt_upload' key
        # get the get_ws_settings test data and remove the 'ecowitt_upload' key
        modified_input = dict(self.get_ws_settings_test_data['input'])
        _ = modified_input.pop('ecowitt_upload', None)
        # get the expected result, it will have no 'cus_ecowitt_interval' key
        modified_result = dict(self.get_ws_settings_test_data['result'])
        _ = modified_result.pop('ecowitt_upload', None)
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has the 'ecowitt_upload' key value cannot be
        # coalesced to an integer
        # get the get_ws_settings test data and set the 'ecowitt_upload' key to 'abc'
        modified_input = dict(self.get_ws_settings_test_data['input'])
        modified_input['ecowitt_upload'] = 'abc'
        # get the expected result, it will have the 'cus_ecowitt_interval' key
        # value set to None
        modified_result = dict(self.get_ws_settings_test_data['result'])
        modified_result['ecowitt_upload'] = None
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has no 'usr_wu_port' key
        # get the get_ws_settings test data and remove the 'usr_wu_port' key
        modified_input = dict(self.get_ws_settings_test_data['input'])
        _ = modified_input.pop('usr_wu_port', None)
        # get the expected result, it will have no 'cus_wu_port' key
        modified_result = dict(self.get_ws_settings_test_data['result'])
        _ = modified_result.pop('usr_wu_port', None)
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has the 'usr_wu_port' key value cannot be
        # coalesced to an integer
        # get the get_ws_settings test data and set the 'usr_wu_port' key to 'abc'
        modified_input = dict(self.get_ws_settings_test_data['input'])
        modified_input['usr_wu_port'] = 'abc'
        # get the expected result, it will have the 'cus_wu_port' key
        # value set to None
        modified_result = dict(self.get_ws_settings_test_data['result'])
        modified_result['usr_wu_port'] = None
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has no 'usr_wu_upload' key
        # get the get_ws_settings test data and remove the 'usr_wu_upload' key
        modified_input = dict(self.get_ws_settings_test_data['input'])
        _ = modified_input.pop('usr_wu_upload', None)
        # get the expected result, it will have no 'cus_wu_interval' key
        modified_result = dict(self.get_ws_settings_test_data['result'])
        _ = modified_result.pop('usr_wu_upload', None)
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test a response that has the 'usr_wu_upload' key value cannot be
        # coalesced to an integer
        # get the get_ws_settings test data and set the 'usr_wu_upload' key to 'abc'
        modified_input = dict(self.get_ws_settings_test_data['input'])
        modified_input['usr_wu_upload'] = 'abc'
        # get the expected result, it will have the 'cus_wu_interval' key
        # value set to None
        modified_result = dict(self.get_ws_settings_test_data['result'])
        modified_result['usr_wu_upload'] = None
        # do the test
        self.assertDictEqual(self.parser.parse_get_ws_settings(response=modified_input),
                             modified_result)

        # test the case where response is not a dict
        # perform the test, we should see a ParseError exception
        self.assertRaises(user.ecowitt_http.ParseError,
                          self.parser.parse_get_ws_settings,
                          response="test string")


class EcowittSensorsTestCase(unittest.TestCase):
    """Test the EcowittSensors class."""

    no_low = ('ws80', 'ws85', 'ws90')
    # sensors whose battery state is determined from a binary value (0|1)
    batt_binary = ('wh65', 'wh25', 'wh26', 'wn31', 'wn32')
    # sensors whose battery state is determined from an integer value
    batt_int = ('wh40', 'wh41', 'wh43', 'wh45', 'wh55', 'wh57')
    # sensors whose battery state is determined from a battery voltage value
    batt_volt = ('wh68', 'wh51', 'wh54', 'wn34', 'wn35', 'ws80', 'ws85', 'ws90')
    sensor_with_voltage = {
        'piezoRain.0x13.voltage': 48,
        'ch_soil.1.voltage': 14,
        'ch_soil.2.voltage': 15,
        'ch_soil.3.voltage': 16,
        'ch_soil.4.voltage': 17,
        'ch_soil.5.voltage': 18,
        'ch_soil.6.voltage': 19,
        'ch_soil.7.voltage': 20,
        'ch_soil.8.voltage': 21,
        'ch_soil.9.voltage': 58,
        'ch_soil.10.voltage': 59,
        'ch_soil.11.voltage': 60,
        'ch_soil.12.voltage': 61,
        'ch_soil.13.voltage': 62,
        'ch_soil.14.voltage': 63,
        'ch_soil.15.voltage': 64,
        'ch_soil.16.voltage': 65,
        'ch_temp.1.voltage': 31,
        'ch_temp.2.voltage': 32,
        'ch_temp.3.voltage': 33,
        'ch_temp.4.voltage': 34,
        'ch_temp.5.voltage': 35,
        'ch_temp.6.voltage': 36,
        'ch_temp.7.voltage': 37,
        'ch_temp.8.voltage': 38,
        'ch_lds.1.voltage': 66,
        'ch_lds.2.voltage': 67,
        'ch_lds.3.voltage': 68,
        'ch_lds.4.voltage': 69
    }
    # map of sensor address to composite sensor name (ie sensor model and
    # channel (as applicable))
    sensor_address = {
        0: 'ws69',
        1: 'wh68',
        2: 'ws80',
        3: 'wh40',
        4: 'wh25',
        5: 'wh26',
        6: 'wn31_ch1',
        7: 'wn31_ch2',
        8: 'wn31_ch3',
        9: 'wn31_ch4',
        10: 'wn31_ch5',
        11: 'wn31_ch6',
        12: 'wn31_ch7',
        13: 'wn31_ch8',
        14: 'wh51_ch1',
        15: 'wh51_ch2',
        16: 'wh51_ch3',
        17: 'wh51_ch4',
        18: 'wh51_ch5',
        19: 'wh51_ch6',
        20: 'wh51_ch7',
        21: 'wh51_ch8',
        22: 'wh41_ch1',
        23: 'wh41_ch2',
        24: 'wh41_ch3',
        25: 'wh41_ch4',
        26: 'wh57',
        27: 'wh55_ch1',
        28: 'wh55_ch2',
        29: 'wh55_ch3',
        30: 'wh55_ch4',
        31: 'wn34_ch1',
        32: 'wn34_ch2',
        33: 'wn34_ch3',
        34: 'wn34_ch4',
        35: 'wn34_ch5',
        36: 'wn34_ch6',
        37: 'wn34_ch7',
        38: 'wn34_ch8',
        39: 'wh45',
        40: 'wn35_ch1',
        41: 'wn35_ch2',
        42: 'wn35_ch3',
        43: 'wn35_ch4',
        44: 'wn35_ch5',
        45: 'wn35_ch6',
        46: 'wn35_ch7',
        47: 'wn35_ch8',
        48: 'ws90',
        49: 'ws85',
        58: 'wh51_ch9',
        59: 'wh51_ch10',
        60: 'wh51_ch11',
        61: 'wh51_ch12',
        62: 'wh51_ch13',
        63: 'wh51_ch14',
        64: 'wh51_ch15',
        65: 'wh51_ch16',
        66: 'wh54_ch1',
        67: 'wh54_ch2',
        68: 'wh54_ch3',
        69: 'wh54_ch4',
    }
    sensor_address_range = (0, 69)
    all_sensor_test_data = {
        'all_sensor_data': {
            'wh45': {
                'address': 39,
                'id': 'FFFFFFFF',
                'battery': None,
                'signal': 0,
                'enabled': False,
                'version': None
            },
            'wh41': {
                'ch1': {
                    'address': 22,
                    'id': 'C497',
                    'battery': 2,
                    'signal': 4,
                    'enabled': True,
                    'version': None
                },
                'ch2': {
                    'address': 23,
                    'id': 'FFFFFFFE',
                    'battery': None,
                    'signal': 0,
                    'enabled': False,
                    'version': None
                }
            }
        },
        'all_models_response' : ('wh41', 'wh45'),
        'all_response': ('wh41_ch1', 'wh41_ch2', 'wh45'),
        'enabled_response': ('wh41_ch1',),
        'disabled_response': ('wh41_ch2', 'wh45'),
        'learning_response': ('wh45',),
        'connected_response': ('wh41_ch1',)
    }


    def setUp(self):

        # # get an EcowittSensors object
        # self.parser = user.ecowitt_http.EcowittSensors()
        pass

    def tearDown(self):

        pass

    def test_constants(self):
        """Test constants used by class EcowittSensors"""

        # test sensor models with no low battery definition
        print()
        print("    testing 'no low battery' models...")
        self.assertEqual(user.ecowitt_http.EcowittSensors.no_low,
                         self.no_low)

        # test sensor battery state determination groups
        print("    testing battery state determination groups...")
        self.assertEqual(user.ecowitt_http.EcowittSensors.batt_binary,
                         self.batt_binary)
        self.assertEqual(user.ecowitt_http.EcowittSensors.batt_int,
                         self.batt_int)
        self.assertEqual(user.ecowitt_http.EcowittSensors.batt_volt,
                         self.batt_volt)

        # test livedata sensors that supply voltage data
        print("    testing sensors that provide voltage data...")
        self.assertEqual(user.ecowitt_http.EcowittSensors.sensor_with_voltage,
                         self.sensor_with_voltage)

        # test sensor address to model/channel map
        print("    testing sensors address to model/channel map...")
        self.assertEqual(user.ecowitt_http.EcowittSensors.sensor_address,
                         self.sensor_address)
        for address in user.ecowitt_http.EcowittSensors.sensor_with_voltage.values():
            self.assertGreaterEqual(address,
                                    self.sensor_address_range[0])
            self.assertLessEqual(address,
                                 self.sensor_address_range[1])
        for address in user.ecowitt_http.EcowittSensors.sensor_address.keys():
            self.assertGreaterEqual(address,
                                    self.sensor_address_range[0])
            self.assertLessEqual(address,
                                 self.sensor_address_range[1])

    def test_init(self):
        """Test the initialisation of an Ecowitt Sensors object."""

        # test initialisation with no parameters
        sensors = user.ecowitt_http.EcowittSensors()
        self.assertDictEqual(sensors.all_sensor_data, dict())

        # test initialisation with live data only
        sensors = user.ecowitt_http.EcowittSensors()
        self.assertDictEqual(sensors.all_sensor_data, dict())

        # test initialisation with sensor data only
        sensors = user.ecowitt_http.EcowittSensors()
        self.assertDictEqual(sensors.all_sensor_data, dict())

        # test initialisation with both sensor data and live data
        sensors = user.ecowitt_http.EcowittSensors()
        self.assertDictEqual(sensors.all_sensor_data, dict())

        # test initialisation with sensor data and invalid live data
        sensors = user.ecowitt_http.EcowittSensors()
        self.assertDictEqual(sensors.all_sensor_data, dict())

        # test initialisation with live data and invalid sensor data
        sensors = user.ecowitt_http.EcowittSensors()
        self.assertDictEqual(sensors.all_sensor_data, dict())

    def test_basic_properties(self):
        """Test basic EcowittSensors properties."""

        sensors = user.ecowitt_http.EcowittSensors()
        sensors.all_sensor_data = self.all_sensor_test_data['all_sensor_data']
        self.assertTupleEqual(sensors.all_models, self.all_sensor_test_data['all_models_response'])
        self.assertTupleEqual(sensors.all, self.all_sensor_test_data['all_response'])
        self.assertTupleEqual(sensors.enabled, self.all_sensor_test_data['enabled_response'])
        self.assertTupleEqual(sensors.disabled, self.all_sensor_test_data['disabled_response'])
        self.assertTupleEqual(sensors.learning, self.all_sensor_test_data['learning_response'])
        self.assertTupleEqual(sensors.connected, self.all_sensor_test_data['connected_response'])


class UtilitiesTestCase(unittest.TestCase):
    """Unit tests for utility functions."""

    unsorted_dict = {'leak2': 'leak2',
                     'inHumidity': 'inhumid',
                     'wn31_ch3_batt': 'wn31_ch3_batt',
                     'leak1': 'leak1',
                     'wn31_ch2_batt': 'wn31_ch2_batt',
                     'windDir': 'winddir',
                     'inTemp': 'intemp'}
    sorted_dict_str = "{'inHumidity': 'inhumid', 'inTemp': 'intemp', " \
                      "'leak1': 'leak1', 'leak2': 'leak2', " \
                      "'windDir': 'winddir', " \
                      "'wn31_ch2_batt': 'wn31_ch2_batt', " \
                      "'wn31_ch3_batt': 'wn31_ch3_batt'}"
    sorted_keys = ['inHumidity', 'inTemp', 'leak1', 'leak2',
                   'windDir', 'wn31_ch2_batt', 'wn31_ch3_batt']
    bytes_to_hex_fail_str = "cannot represent '%s' as hexadecimal bytes"
    flatten_test_data = {
        'source': {
            'temp': {
                'ch1': {
                    'val': 13,
                    'id': 'abcd'
                },
                'ch2': {
                    'val': 23,
                    'id': 'efgh'
                },
                'ch3': {
                    'val': 33,
                    'id': 'ijkl'
                },
            },
            'humid': {
                'ch1': {
                    'val': 81,
                    'id': '1234'
                },
                'ch2': {
                    'val': 82,
                    'id': '5678'
                }
            }
        },
        'result': {
            'temp.ch1.val': 13,
            'temp.ch1.id': 'abcd',
            'temp.ch2.val': 23,
            'temp.ch2.id': 'efgh',
            'temp.ch3.val': 33,
            'temp.ch3.id': 'ijkl',
            'humid.ch1.val': 81,
            'humid.ch1.id': '1234',
            'humid.ch2.val': 82,
            'humid.ch2.id': '5678',
        }
    }
    ch_enum_test_data = {
        'source': {
            'channel': [{'val': 13, 'channel': 0},
                        {'val': 23, 'channel': 1},
                        {'val': 33, 'channel': 2},
                        {'val': 53, 'channel': 4}],
            'id': [{'val': 14, 'id': 0},
                   {'val': 24, 'id': 1},
                   {'val': 34, 'id': 2},
                   {'val': 54, 'id': 4}]
        },
        'result': {
            'channel': [(0, {'val': 13, 'channel': 0}),
                        (1, {'val': 23, 'channel': 1}),
                        (2, {'val': 33, 'channel': 2}),
                        (4, {'val': 53, 'channel': 4})],
            'id': [(0, {'val': 14, 'id': 0}),
                   (1, {'val': 24, 'id': 1}),
                   (2, {'val': 34, 'id': 2}),
                   (4, {'val': 54, 'id': 4})]
        }
    }

    def test_utilities(self):
        """Test utility functions

        Tests:
        1. natural_sort_keys()
        2. natural_sort_dict()
        3. bytes_to_hex()
        """

        print()
        print('    testing natural_sort_keys()...')
        # test natural_sort_keys()
        self.assertEqual(user.ecowitt_http.natural_sort_keys(self.unsorted_dict),
                         self.sorted_keys)

        print('    testing natural_sort_dict()...')
        # test natural_sort_dict()
        self.assertEqual(user.ecowitt_http.natural_sort_dict(self.unsorted_dict),
                         self.sorted_dict_str)

        print('    testing bytes_to_hex()...')
        # test bytes_to_hex()
        # with defaults
        self.assertEqual(user.ecowitt_http.bytes_to_hex(hex_to_bytes('ff 00 66 b2')),
                         'FF 00 66 B2')
        # with defaults and a separator
        self.assertEqual(user.ecowitt_http.bytes_to_hex(hex_to_bytes('ff 00 66 b2'), separator=':'),
                         'FF:00:66:B2')
        # with defaults using lower case
        self.assertEqual(user.ecowitt_http.bytes_to_hex(hex_to_bytes('ff 00 66 b2'), caps=False),
                         'ff 00 66 b2')
        # with a separator and lower case
        self.assertEqual(user.ecowitt_http.bytes_to_hex(hex_to_bytes('ff 00 66 b2'), separator=':', caps=False),
                         'ff:00:66:b2')
        # and check exceptions raised
        # TypeError
        self.assertEqual(user.ecowitt_http.bytes_to_hex(22), self.bytes_to_hex_fail_str % 22)
        # AttributeError
        self.assertEqual(user.ecowitt_http.bytes_to_hex(hex_to_bytes('ff 00 66 b2'), separator=None),
                         self.bytes_to_hex_fail_str % hex_to_bytes('ff 00 66 b2'))

        print('    testing obfuscate()...')
        # test obfuscate()
        # > 8 character string, should see trailing 4 characters
        self.assertEqual(user.ecowitt_http.obfuscate('1234567890'), '******7890')
        # 7 character string, should see trailing 3 characters
        self.assertEqual(user.ecowitt_http.obfuscate('1234567'), '****567')
        # 5 character string, should see trailing 2 characters
        self.assertEqual(user.ecowitt_http.obfuscate('12345'), '***45')
        # 3 character string, should see last character
        self.assertEqual(user.ecowitt_http.obfuscate('123'), '**3')
        # 2 character string, should see no characters
        self.assertEqual(user.ecowitt_http.obfuscate('12'), '**')
        # check obfuscation character
        self.assertEqual(user.ecowitt_http.obfuscate('1234567890', obf_char='#'),
                         '######7890')

    def test_flatten(self):
        """Test flatten() utility function"""

        print()
        print('    testing flatten()...')
        # test flatten()
        # normal data and defaults
        self.assertEqual(user.ecowitt_http.flatten(self.flatten_test_data['source']),
                         self.flatten_test_data['result'])

        # normal data with ':' separator
        _result = dict()
        for k, v in self.flatten_test_data['result'].items():
            new_key = k.replace('.', ':')
            _result[new_key] = v
        self.assertEqual(user.ecowitt_http.flatten(self.flatten_test_data['source'], separator=':'),
                         _result)

        # normal data with a parent_key string
        _result = dict()
        for k, v in self.flatten_test_data['result'].items():
            new_key = '.'.join(['data', k])
            _result[new_key] = v
        self.assertEqual(user.ecowitt_http.flatten(self.flatten_test_data['source'], parent_key='data'),
                         _result)

        # passing something that is not a dict
        # we should get None in return
        self.assertIsNone(user.ecowitt_http.flatten('test data'))

        # passing None
        # we should get None in return
        self.assertIsNone(user.ecowitt_http.flatten(None))

    def test_channelise_enumerate(self):
        """Test channelise_enumerate() utility function"""

        print()
        print('    testing channelise_enumerate()...')
        # test channelise_enumerate()
        # normal data and defaults using key 'channel'
        self.assertEqual(list(user.ecowitt_http.channelise_enumerate(self.ch_enum_test_data['source']['channel'], channelise=True)),
                         self.ch_enum_test_data['result']['channel'])
        # normal data and defaults using key 'id'
        self.assertEqual(list(user.ecowitt_http.channelise_enumerate(self.ch_enum_test_data['source']['id'], channelise=True)),
                         self.ch_enum_test_data['result']['id'])

    def test_calc_checksum(self):
        """Test calc_checksum() utility function"""

        print()
        print('    testing calc_checksum()...')
        self.assertEqual(user.ecowitt_http.calc_checksum(b'00112233bbccddee'), 168)


def hex_to_bytes(hex_string):
    """Takes a string of hex character pairs and returns a string of bytes.

    Allows us to specify a byte string in a little more human-readable format.
    Takes a space delimited string of hex pairs and converts to a string of
    bytes. hex_string pairs must be spaced delimited, eg 'AB 2E 3B'.

    If we only ran under python3 we could use bytes.fromhex(), but we need to
    cater for python2 as well so use struct.pack.
    """

    # first get our hex string as a list of integers
    dec_list = [int(a, 16) for a in hex_string.split()]
    # now pack them in a sequence of bytes
    return struct.pack('B' * len(dec_list), *dec_list)


def suite(test_cases):
    """Create a TestSuite object containing the tests we are to perform."""

    # get a test loader
    loader = unittest.TestLoader()
    # create an empty test suite
    suite = unittest.TestSuite()
    # iterate over the test cases we are to add
    for test_class in test_cases:
        # get the tests from the test case
        tests = loader.loadTestsFromTestCase(test_class)
        # add the tests to the test suite
        suite.addTests(tests)
    # finally, return the populated test suite
    return suite


def main():
    import argparse

    # test cases that are production ready
    # test_cases = (DebugOptionsTestCase, SensorsTestCase, HttpParserTestCase,
    #               UtilitiesTestCase, ListsAndDictsTestCase, StationTestCase,
    #               GatewayServiceTestCase, GatewayDriverTestCase)
    test_cases = (DebugOptionsTestCase, HttpParserTestCase,
                  EcowittSensorsTestCase, UtilitiesTestCase,
                  ConfEditorTestCase) #SensorsTestCase, HttpParserTestCase,
#                  DeviceCatchupTestCase, ConfEditorTestCase) #SensorsTestCase, HttpParserTestCase,
#                  ListsAndDictsTestCase, StationTestCase,
#                  GatewayServiceTestCase, GatewayDriverTestCase)

    usage = f"""{bcolors.BOLD}%(prog)s --help
                    --version
                    --test [--ip-address=IP_ADDRESS]
                           [-v|--verbose VERBOSITY]{bcolors.ENDC}
    """
    description = 'Test the Ecowitt HTTP driver code.'
    epilog = """You must ensure the WeeWX user modules are in your PYTHONPATH. For example:

    PYTHONPATH=~/weewx-data/bin:/home/weewx/weewx/src python3 -m user.tests.test_http
    """

    parser = argparse.ArgumentParser(usage=usage,
                                     description=description,
                                     epilog=epilog,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--version', dest='version', action='store_true',
                        help='display Ecowitt HTTP driver test suite version number')
    parser.add_argument('--test', dest='test', action='store_true',
                        help='run the test suite')
    parser.add_argument('--ip-address', dest='ip_address', metavar='IP_ADDRESS',
                        help='device IP address to use')
#    parser.add_argument('--no-device', dest='no_device', action='store_true',
#                        help='skip tests that require a physical gateway device')
    parser.add_argument('--verbose', dest='verbosity', type=int, metavar='VERBOSITY',
                        default=2,
                        help='how much status to display, 0-2')
    # parse the arguments
    namespace = parser.parse_args()

    # process the args
    if namespace.version:
        # display version number
        print('%s test suite version: %s' % (TEST_SUITE_NAME, TEST_SUITE_VERSION))
        exit(0)
    elif namespace.test:
        # get a test runner with appropriate verbosity
        runner = unittest.TextTestRunner(verbosity=namespace.verbosity)
        # create a test suite and run the included tests
        runner.run(suite(test_cases))
        exit(0)
    else:
        # display our help
        parser.print_help()


if __name__ == '__main__':
    main()