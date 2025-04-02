'''
Test suite for the WeeWX Ecowitt gateway driver.

Copyright (C) 2020-24 Gary Roderick                gjroderick<at>gmail.com

A python3 unittest based test suite for aspects of the Ecowitt gateway driver.
The test suite tests correct operation of:

-

Version: 0.1.0a18                                 Date: ? August 2024

Revision History
    ?? August 2024      v0.1.0
        -   initial release

To run the test suite:

-   copy this file to the target machine, nominally to the USER_ROOT/tests
    directory

-   run the test suite using:

    PYTHONPATH=/home/weewx/weewx-data/bin:/home/weewx/weewx/src python3 -m user.tests.test_http
'''
# python imports
import socket
import struct
import unittest

from io import StringIO
from unittest.mock import patch

import configobj

# WeeWX imports
import weewx
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
TEST_SUITE_VERSION = '0.1.0a18'


class bcolors:
    '''Colors used for terminals'''
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
        self.debug_config = configobj.ConfigObj(StringIO(debug_string))

    def test_constants(self):
        '''Test constants used by DebugOptions.'''

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
        '''Test the setting of DebugOptions properties on initialisation.'''

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
            # create a string contsaining the debug groups to be set
            debug_string = 'debug = %s' % ', '.join(all_groups)
            # convert to a configobj
            _config = configobj.ConfigObj(StringIO(debug_string))
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


class DeviceCatchupTestCase(unittest.TestCase):
    """Test the EcowittDeviceCatchup class."""

    # config used for mocked EcowittDeviceCatchup object
    device_catchup_config = {
        'ip_address': '192.168.99.99'
    }
    # mocked EcowittDevice.get_sdmmc_info response
    fake_get_sdmmc_info_data = {}

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
        # obtain an EcowittDeviceCatchup object
        device_catchup = self.get_device_catchup(config=device_catchup_config_copy,
                                                 caller='test_device_catchup_init')
        # test the IP address was properly set
        self.assertSequenceEqual(device_catchup.ip_address,
                                 device_catchup_config_copy['ip_address'])

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

# class SensorsTestCase(unittest.TestCase):
#     '''Test the Sensors class.'''
# 
#     # test sensor ID data
#     sensor_id_data = 'FF FF 3C 01 54 00 FF FF FF FE FF 00 01 FF FF FF FE FF 00 '\
#                      '06 00 00 00 5B 00 04 07 00 00 00 BE 00 04 08 00 00 00 D0 00 04 '\
#                      '0F 00 00 CD 19 0D 04 10 00 00 CD 04 1F 00 11 FF FF FF FE 1F 00 '\
#                      '15 FF FF FF FE 1F 00 16 00 00 C4 97 06 04 17 FF FF FF FE 0F 00 '\
#                      '18 FF FF FF FE 0F 00 19 FF FF FF FE 0F 00 1A 00 00 D3 D3 05 03 '\
#                      '1E FF FF FF FE 0F 00 1F 00 00 2A E7 3F 04 34'
#     # processed sensor ID data
#     sensor_data = {b'\x00': {'id': 'fffffffe', 'battery': None, 'signal': 0},
#                    b'\x01': {'id': 'fffffffe', 'battery': None, 'signal': 0},
#                    b'\x06': {'id': '0000005b', 'battery': 0, 'signal': 4},
#                    b'\x07': {'id': '000000be', 'battery': 0, 'signal': 4},
#                    b'\x08': {'id': '000000d0', 'battery': 0, 'signal': 4},
#                    b'\x0f': {'id': '0000cd19', 'battery': 1.3, 'signal': 4},
#                    b'\x10': {'id': '0000cd04', 'battery': None, 'signal': 0},
#                    b'\x11': {'id': 'fffffffe', 'battery': None, 'signal': 0},
#                    b'\x15': {'id': 'fffffffe', 'battery': None, 'signal': 0},
#                    b'\x16': {'id': '0000c497', 'battery': 6, 'signal': 4},
#                    b'\x17': {'id': 'fffffffe', 'battery': None, 'signal': 0},
#                    b'\x18': {'id': 'fffffffe', 'battery': None, 'signal': 0},
#                    b'\x19': {'id': 'fffffffe', 'battery': None, 'signal': 0},
#                    b'\x1a': {'id': '0000d3d3', 'battery': 5, 'signal': 3},
#                    b'\x1e': {'id': 'fffffffe', 'battery': None, 'signal': 0},
#                    b'\x1f': {'id': '00002ae7', 'battery': 1.26, 'signal': 4}}
#     connected_addresses = [b'\x06', b'\x07', b'\x08', b'\x0f',
#                            b'\x10', b'\x16', b'\x1a', b'\x1f']
#     batt_sig_data = {'wn31_ch1_batt': 0, 'wn31_ch1_sig': 4,
#                      'wn31_ch2_batt': 0, 'wn31_ch2_sig': 4,
#                      'wn31_ch3_batt': 0, 'wn31_ch3_sig': 4,
#                      'wh41_ch1_batt': 6, 'wh41_ch1_sig': 4,
#                      'wh51_ch2_batt': 1.3, 'wh51_ch2_sig': 4,
#                      'wh51_ch3_batt': None, 'wh51_ch3_sig': 0,
#                      'wh57_batt': 5, 'wh57_sig': 3,
#                      'wn34_ch1_batt': 1.26, 'wn34_ch1_sig': 4}
# 
#     def setUp(self):
# 
#         # get a Sensors object
#         self.sensors = user.gw1000.Sensors()
# 
#     def test_set_sensor_id_data(self):
#         '''Test the set_sensor_id_data() method.'''
# 
#         # test when passed an empty dict
#         self.sensors.set_sensor_id_data(None)
#         self.assertDictEqual(self.sensors.sensor_data, {})
# 
#         # test when passed a zero length data bytestring
#         self.sensors.set_sensor_id_data(b'')
#         self.assertDictEqual(self.sensors.sensor_data, {})
# 
#         # test when passed a valid bytestring
#         self.sensors.set_sensor_id_data(hex_to_bytes(self.sensor_id_data))
#         self.assertDictEqual(self.sensors.sensor_data, self.sensor_data)
# 
#     def test_properties(self):
#         '''Test class Sensors.sensor_data related property methods.'''
# 
#         # test when passed an empty dict
#         self.sensors.set_sensor_id_data(None)
#         # addresses property
#         self.assertSequenceEqual(self.sensors.addresses, {}.keys())
#         # connected_addresses property
#         self.assertListEqual(list(self.sensors.connected_addresses), [])
#         # data property
#         self.assertDictEqual(self.sensors.data, {})
#         # battery_and_signal_data property
#         self.assertDictEqual(self.sensors.battery_and_signal_data, {})
# 
#         # test when passed a zero length data bytestring
#         self.sensors.set_sensor_id_data(b'')
#         # addresses property
#         self.assertSequenceEqual(self.sensors.addresses, {}.keys())
#         # connected_addresses property
#         self.assertListEqual(list(self.sensors.connected_addresses), [])
#         # data property
#         self.assertDictEqual(self.sensors.data, {})
#         # battery_and_signal_data property
#         self.assertDictEqual(self.sensors.battery_and_signal_data, {})
# 
#         # test when passed a valid bytestring
#         self.sensors.set_sensor_id_data(hex_to_bytes(self.sensor_id_data))
#         # addresses property
#         self.assertSequenceEqual(self.sensors.addresses,
#                                  self.sensor_data.keys())
#         # connected_addresses property
#         self.assertListEqual(list(self.sensors.connected_addresses),
#                              self.connected_addresses)
#         # data property
#         self.assertDictEqual(self.sensors.data, self.sensor_data)
#         # battery_and_signal_data property
#         self.assertDictEqual(self.sensors.battery_and_signal_data, self.batt_sig_data)
# 
#     def test_sensor_data_methods(self):
#         '''Test Sensors.sensor_data related methods.'''
# 
#         # test when passed an empty dict
#         self.sensors.set_sensor_id_data(None)
#         # id method
#         self.assertRaises(KeyError, self.sensors.id, b'\x00')
#         # battery_state method
#         self.assertRaises(KeyError, self.sensors.battery_state, b'\x00')
#         # signal_level method
#         self.assertRaises(KeyError, self.sensors.signal_level, b'\x00')
# 
#         # test when passed a zero length data bytestring
#         self.sensors.set_sensor_id_data(b'')
#         # id method
#         self.assertRaises(KeyError, self.sensors.id, b'\x00')
#         # battery_state method
#         self.assertRaises(KeyError, self.sensors.battery_state, b'\x00')
#         # signal_level method
#         self.assertRaises(KeyError, self.sensors.signal_level, b'\x00')
# 
#         # test when passed a valid bytestring
#         self.sensors.set_sensor_id_data(hex_to_bytes(self.sensor_id_data))
#         # id method
#         # for a non-existent sensor
#         self.assertRaises(KeyError, self.sensors.id, b'\x34')
#         # for an existing sensor
#         self.assertEqual(self.sensors.id(b'\x11'), 'fffffffe')
#         self.assertEqual(self.sensors.id(b'\x1a'), '0000d3d3')
#         # battery_state method
#         # for a non-existent sensor
#         self.assertRaises(KeyError, self.sensors.battery_state, b'\x34')
#         # for an existing sensor
#         self.assertIsNone(self.sensors.battery_state(b'\x11'))
#         self.assertEqual(self.sensors.battery_state(b'\x1a'), 5)
#         # signal_level method
#         # for a non-existent sensor
#         self.assertRaises(KeyError, self.sensors.signal_level, b'\x34')
#         # for an existing sensor
#         self.assertEqual(self.sensors.signal_level(b'\x11'), 0)
#         self.assertEqual(self.sensors.signal_level(b'\x1a'), 3)
# 
#     def test_battery_methods(self):
#         '''Test battery state methods'''
# 
#         # binary battery states (method batt_binary())
#         self.assertEqual(self.sensors.batt_binary(255), 1)
#         self.assertEqual(self.sensors.batt_binary(4), 0)
# 
#         # integer battery states (method batt_int())
#         for int_batt in range(7):
#             self.assertEqual(self.sensors.batt_int(int_batt), int_batt)
# 
#         # voltage battery states (method batt_volt())
#         self.assertEqual(self.sensors.batt_volt(0), 0.00)
#         self.assertEqual(self.sensors.batt_volt(100), 2.00)
#         self.assertEqual(self.sensors.batt_volt(101), 2.02)
#         self.assertEqual(self.sensors.batt_volt(255), 5.1)
# 
#         # voltage battery states (method wh40_batt_volt())
#         # first check operation if ignore_legacy_wh40_battery is True
#         self.sensors.ignore_wh40_batt = True
#         # legacy WH40
#         self.assertIsNone(self.sensors.wh40_batt_volt(0))
#         self.assertIsNone(self.sensors.wh40_batt_volt(15))
#         self.assertIsNone(self.sensors.wh40_batt_volt(19))
#         # contemporary WH40
#         self.assertEqual(self.sensors.wh40_batt_volt(20), 0.20)
#         self.assertEqual(self.sensors.wh40_batt_volt(150), 1.50)
#         self.assertEqual(self.sensors.wh40_batt_volt(255), 2.55)
#         # now check operation if ignore_legacy_wh40_battery is False
#         self.sensors.ignore_wh40_batt = False
#         # legacy WH40
#         self.assertEqual(self.sensors.wh40_batt_volt(0), 0.0)
#         self.assertEqual(self.sensors.wh40_batt_volt(15), 1.5)
#         self.assertEqual(self.sensors.wh40_batt_volt(19), 1.9)
#         # contemporary WH40
#         self.assertEqual(self.sensors.wh40_batt_volt(20), 0.20)
#         self.assertEqual(self.sensors.wh40_batt_volt(150), 1.50)
#         self.assertEqual(self.sensors.wh40_batt_volt(255), 2.55)
# 
#         # voltage battery states (method batt_volt_tenth())
#         self.assertEqual(self.sensors.batt_volt_tenth(0), 0.00)
#         self.assertEqual(self.sensors.batt_volt_tenth(15), 1.5)
#         self.assertEqual(self.sensors.batt_volt_tenth(17), 1.7)
#         self.assertEqual(self.sensors.batt_volt_tenth(255), 25.5)
# 
#         # binary description
#         self.assertEqual(self.sensors.batt_state_desc(b'\x00', 0), 'OK')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x00', 1), 'low')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x00', 2), 'Unknown')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x00', None), 'Unknown')
# 
#         # int description
#         self.assertEqual(self.sensors.batt_state_desc(b'\x16', 0), 'low')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x16', 1), 'low')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x16', 4), 'OK')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x16', 6), 'DC')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x16', 7), 'Unknown')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x16', None), 'Unknown')
# 
#         # voltage description
#         self.assertEqual(self.sensors.batt_state_desc(b'\x20', 0), 'low')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x20', 1.2), 'low')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x20', 1.5), 'OK')
#         self.assertEqual(self.sensors.batt_state_desc(b'\x20', None), 'Unknown')


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
        # test unknown device units unit string
        # get the test input
        json_object = json_object_test_data['temperature']
        # pop off the 'unit' key to force device units to be used
        _ = json_object.pop('unit', None)
        # make a copy of the device units to be used, we need to change them
        metric_device_units = dict(device_units['metric'])
        # pop off the 'group_temperature' key
        _ = metric_device_units.pop('group_temperature', None)
        # perform the test, we should see a ParseError exception
        self.assertRaises(user.ecowitt_http.ParseError,
                          self.parser.parse_obs_value,
                          key='val',
                          json_object=json_object,
                          unit_group='group_temperature',
                          device_units=metric_device_units)
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
        # now check where device units are used but a None device units
        # parameter was used
        # get the test input
        json_object = json_object_test_data['temperature']
        # pop off the 'unit' key to force device units to be used
        _ = json_object.pop('unit', None)
        # perform the test, we should see a ParseError exception
        self.assertRaises(user.ecowitt_http.ParseError,
                          self.parser.parse_obs_value,
                          key='val',
                          json_object=json_object,
                          unit_group='group_temperature',
                          device_units=None)

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


# class ListsAndDictsTestCase(unittest.TestCase):
#     '''Test case to test list and dict consistency.'''
#
#     def setUp(self):
#
#         # construct the default field map and save for later, note we construct
#         # the default field map by passing gw1000.Gateway.construct_field_map
#         # an empty config dict
#         self.default_field_map = user.gw1000.Gateway.construct_field_map({})
#
#     def test_dicts(self):
#         '''Test dicts for consistency'''
#
#         # test that each WeeWX field in the driver default field map is
#         # assigned a unit group, either in the gw1000.default_groups or
#         # weewx.units.obs_group_dict observation group dictionaries
#         for w_field in self.default_field_map.keys():
#             if w_field not in weewx.units.obs_group_dict.keys():
#                 self.assertIn(w_field,
#                               user.gw1000.DEFAULT_GROUPS.keys(),
#                               msg='A field from the driver default field map is '
#                                   'missing from the default_groups observation group dictionary')
#
#         # test that each gateway device field in the driver default field map
#         # appears in the DirectGateway observation group dictionary
#         for g_field in self.default_field_map.values():
#             self.assertIn(g_field,
#                           user.gw1000.DirectGateway.gw_direct_obs_group_dict.keys(),
#                           msg='A field from the driver default field map is '
#                               'missing from the observation group dictionary')
#
#         # test that each gateway device field entry in the observation group
#         # dictionary is included in the driver default field map
#         for g_field in user.gw1000.DirectGateway.gw_direct_obs_group_dict.keys():
#             self.assertIn(g_field,
#                           self.default_field_map.values(),
#                           msg='A key from the observation group dictionary is '
#                               'missing from the driver default field map')
#
#
# class StationTestCase(unittest.TestCase):
#
#     fake_ip = '192.168.99.99'
#     fake_port = 44444
#     mock_mac = 'A1:B2:C3:D4:E5:F6'  # b'A1:B2:C3:D4:E5:F6'
#     mock_firmware = ''.join([chr(x) for x in b'\xff\xffP\x11\rGW1000_V1.6.8}'])
#     mock_system_params = {
#         'frequency': 0,
#         'sensor_type': 1,
#         'utc': 1674801882,
#         'timezone_index': 94,
#         'dst_status': False
#     }
#     # test sensor ID data
#     fake_sensor_id_data = 'FF FF 3C 01 54 00 FF FF FF FE FF 00 01 FF FF FF FE FF 00 '\
#                           '06 00 00 00 5B 00 04 07 00 00 00 BE 00 04 08 00 00 00 D0 00 04 '\
#                           '0F 00 00 CD 19 0D 04 10 00 00 CD 04 1F 00 11 FF FF FF FE 1F 00 '\
#                           '15 FF FF FF FE 1F 00 16 00 00 C4 97 06 04 17 FF FF FF FE 0F 00 '\
#                           '18 FF FF FF FE 0F 00 19 FF FF FF FE 0F 00 1A 00 00 D3 D3 05 03 '\
#                           '1E FF FF FF FE 0F 00 1F 00 00 2A E7 3F 04 34'
#
#     cmd_read_fware_ver = b'\x50'
#     read_fware_cmd_bytes = b'\xff\xffP\x03S'
#     read_fware_resp_bytes = b'\xff\xffP\x11\rGW1000_V1.6.1v'
#     read_fware_resp_bad_checksum_bytes = b'\xff\xffP\x11\rGW1000_V1.6.1z'
#     read_fware_resp_unex_cmd_bytes = b'\xff\xffQ\x11\rGW1000_V1.6.1w'
#     broadcast_response_data = 'FF FF 12 00 26 50 02 91 E3 FD 32 C0 A8 02 20 AF ' \
#                               'C8 16 47 57 31 30 30 30 2D 57 49 46 49 46 44 33 ' \
#                               '32 20 56 31 2E 36 2E 38 5F'
#     decoded_broadcast_response = {'mac': '50:02:91:E3:FD:32',
#                                   'ip_address': '192.168.2.32',
#                                   'port': 45000,
#                                   'ssid': 'GW1000-WIFIFD32 V1.6.8'}
#     cmd = 'CMD_READ_FIRMWARE_VERSION'
#     cmd_payload = '01 02 FF'
#     cmd_packet = 'FF FF 50 06 01 02 FF 58'
#     commands = {
#         'CMD_WRITE_SSID': 'FF FF 11 03 14',
#         'CMD_BROADCAST': 'FF FF 12 03 15',
#         'CMD_READ_ECOWITT': 'FF FF 1E 03 21',
#         'CMD_WRITE_ECOWITT': 'FF FF 1F 03 22',
#         'CMD_READ_WUNDERGROUND': 'FF FF 20 03 23',
#         'CMD_WRITE_WUNDERGROUND': 'FF FF 21 03 24',
#         'CMD_READ_WOW': 'FF FF 22 03 25',
#         'CMD_WRITE_WOW': 'FF FF 23 03 26',
#         'CMD_READ_WEATHERCLOUD': 'FF FF 24 03 27',
#         'CMD_WRITE_WEATHERCLOUD': 'FF FF 25 03 28',
#         'CMD_READ_STATION_MAC': 'FF FF 26 03 29',
#         'CMD_GW1000_LIVEDATA': 'FF FF 27 03 2A',
#         'CMD_GET_SOILHUMIAD': 'FF FF 28 03 2B',
#         'CMD_SET_SOILHUMIAD': 'FF FF 29 03 2C',
#         'CMD_READ_CUSTOMIZED': 'FF FF 2A 03 2D',
#         'CMD_WRITE_CUSTOMIZED': 'FF FF 2B 03 2E',
#         'CMD_GET_MulCH_OFFSET': 'FF FF 2C 03 2F',
#         'CMD_SET_MulCH_OFFSET': 'FF FF 2D 03 30',
#         'CMD_GET_PM25_OFFSET': 'FF FF 2E 03 31',
#         'CMD_SET_PM25_OFFSET': 'FF FF 2F 03 32',
#         'CMD_READ_SSSS': 'FF FF 30 03 33',
#         'CMD_WRITE_SSSS': 'FF FF 31 03 34',
#         'CMD_READ_RAINDATA': 'FF FF 34 03 37',
#         'CMD_WRITE_RAINDATA': 'FF FF 35 03 38',
#         'CMD_READ_GAIN': 'FF FF 36 03 39',
#         'CMD_WRITE_GAIN': 'FF FF 37 03 3A',
#         'CMD_READ_CALIBRATION': 'FF FF 38 03 3B',
#         'CMD_WRITE_CALIBRATION': 'FF FF 39 03 3C',
#         'CMD_READ_SENSOR_ID': 'FF FF 3A 03 3D',
#         'CMD_WRITE_SENSOR_ID': 'FF FF 3B 03 3E',
#         'CMD_READ_SENSOR_ID_NEW': 'FF FF 3C 03 3F',
#         'CMD_WRITE_REBOOT': 'FF FF 40 03 43',
#         'CMD_WRITE_RESET': 'FF FF 41 03 44',
#         'CMD_WRITE_UPDATE': 'FF FF 43 03 46',
#         'CMD_READ_FIRMWARE_VERSION': 'FF FF 50 03 53',
#         'CMD_READ_USR_PATH': 'FF FF 51 03 54',
#         'CMD_WRITE_USR_PATH': 'FF FF 52 03 55',
#         'CMD_GET_CO2_OFFSET': 'FF FF 53 03 56',
#         'CMD_SET_CO2_OFFSET': 'FF FF 54 03 57',
#         'CMD_READ_RSTRAIN_TIME': 'FF FF 55 03 58',
#         'CMD_WRITE_RSTRAIN_TIME': 'FF FF 56 03 59',
#         'CMD_READ_RAIN': 'FF FF 57 03 5A',
#         'CMD_WRITE_RAIN': 'FF FF 58 03 5B',
#         'CMD_GET_MulCH_T_OFFSET': 'FF FF 59 03 5C'
#     }
#     # Station.discover() multiple device discovery response
#     discover_multi_resp = [{'mac': 'E8:68:E7:87:1A:4F',  # b'\xe8h\xe7\x87\x1aO'
#                             'ip_address': '192.168.50.3',
#                             'port': 45001,
#                             'ssid': 'GW1100C-WIFI1A4F V2.0.9',
#                             'model': 'GW1100'},
#                            {'mac': 'DC:4F:22:58:A2:45',  # b'\xdcO'X\xa2E'
#                             'ip_address': '192.168.50.6',
#                             'port': 45002,
#                             'ssid': 'GW1000-WIFIA245 V1.6.7',
#                             'model': 'GW1000'},
#                            {'mac': '50:02:91:E3:D3:68',  # b'P\x02\x91\xe3\xd3h'
#                             'ip_address': '192.168.50.7',
#                             'port': 45003,
#                             'ssid': 'GW1000-WIFID368 V1.6.8',
#                             'model': 'GW1000'}
#                            ]
#     # Station.discover() multiple device discovery response with different MAC
#     discover_multi_diff_resp = [{'mac': b'\xe8h\xe7\x87\x1bO',  # 'E8:68:E7:87:1B:4F',
#                                  'ip_address': '192.168.50.3',
#                                  'port': 45001,
#                                  'ssid': 'GW1100C-WIFI1A4F V2.0.9',
#                                  'model': 'GW1100'},
#                                 {'mac': b'\xdcO'X\xa3E',  # 'DC:4F:22:58:A3:45'
#                                  'ip_address': '192.168.50.6',
#                                  'port': 45002,
#                                  'ssid': 'GW1000-WIFIA245 V1.6.7',
#                                  'model': 'GW1000'},
#                                 {'mac': b'P\x02\x91\xe3\xd2h',  # '50:02:91:E3:D2:68',
#                                  'ip_address': '192.168.50.7',
#                                  'port': 45003,
#                                  'ssid': 'GW1000-WIFID368 V1.6.8',
#                                  'model': 'GW1000'}
#                                 ]
#
#     @classmethod
#     def setUpClass(cls):
#         '''Setup the StationTestCase to perform its tests.
#
#         Determines the IP address and port to use for the Station tests. A
#         GatewayCollector.Station object is required to perform some
#         StationTestCase tests. If either or both of IP address and port are not
#         specified when instantiating a Station object device discovery will be
#         initiated which may result in delays or failure of the test case if no
#         device is found. To avoid such situations an IP address and port number
#         is always used when instantiating a Station object as part of this test
#         case.
#
#         The IP address and port number are determined as follows:
#         - if --ip-address and --port were specified on the command line then
#           the specified parameters are used
#         - if --ip-address is specified on the command line but --port was not
#           then port 45000 is used
#         - if --port is specified on the command line but --ip-address was not
#           then a fake IP address is used
#         - if neither --ip-address or --port number is specified on the command
#           line then a fake IP address and port number are used
#         '''
#
#         # set the IP address we will use
#         cls.test_ip = cls.ip_address if cls.ip_address is not None else StationTestCase.fake_ip
#         # set the port number we will use
#         cls.test_port = cls.port if cls.port is not None else StationTestCase.fake_port
#
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_cmd_vocab(self, mock_get_mac, mock_get_firmware,
#                        mock_get_sys, mock_get_sensor_id):
#         '''Test command dictionaries for completeness.
#
#         Tests:
#         1. Station.api_commands contains all api_commands
#         2. the command code for each Station.api_commands agrees with the test suite
#         3. all Station.api_commands entries are in the test suite
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (string)
#         mock_get_mac.return_value = StationTestCase.mock_mac
#         # get_firmware_version - display_firmware version (string)
#         mock_get_firmware.return_value = StationTestCase.mock_firmware
#         # get_system_params - system parameters (dict)
#         mock_get_sys.return_value = StationTestCase.mock_system_params
#         # get_sensor_id - get sensor IDs (bytestring)
#         mock_get_sensor_id.return_value = None
#         # get our mocked gateway device API object
#         gw_device_api = user.gw1000.GatewayApi(ip_address=self.test_ip,
#                                                port=self.test_port)
#         # Check that the class Station command list is complete. This is a
#         # simple check for (1) inclusion of the command and (2) the command
#         # code (byte) is correct.
#         for cmd, response in self.commands.items():
#             # check for inclusion of the command
#             self.assertIn(cmd,
#                           gw_device_api.api_commands.keys(),
#                           msg='Command '%s' not found in Station.api_commands' % cmd)
#             # check the command code byte is correct
#             self.assertEqual(hex_to_bytes(response)[2:3],
#                              gw_device_api.api_commands[cmd],
#                              msg='Command code for command '%s' in '
#                                  'Station.api_commands(0x%s) disagrees with '
#                                  'command code in test suite (0x%s)' % (cmd,
#                                                                         bytes_to_hex(gw_device_api.api_commands[cmd]),
#                                                                         bytes_to_hex(hex_to_bytes(response)[2:3])))
#
#         # Check that we are testing everything in class Station command list.
#         # This is a simple check that only needs to check for inclusion of the
#         # command, the validity of the command code is checked in the earlier
#         # iteration.
#         for cmd, code in gw_device_api.api_commands.items():
#             # check for inclusion of the command
#             self.assertIn(cmd,
#                           self.commands.keys(),
#                           msg='Command '%s' is in Station.api_commands but it is not being tested' % cmd)
#
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_calc_checksum(self, mock_get_mac, mock_get_firmware,
#                            mock_get_system_params, mock_get_sensor_id):
#         '''Test checksum calculation.
#
#         Tests:
#         1. calculating the checksum of a bytestring
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (bytestring)
#         mock_get_mac.return_value = StationTestCase.mock_mac
#         # get_firmware_version - display_firmware version (bytestring)
#         mock_get_firmware.return_value = StationTestCase.mock_firmware
#         # get_system_params - system parameters (dict)
#         mock_get_system_params.return_value = StationTestCase.mock_system_params
#         # get_sensor_id - sensor ID data
#         mock_get_sensor_id.return_value = None
#         # get our mocked gateway device API object
#         gw_device_api = user.gw1000.GatewayApi(ip_address=self.test_ip,
#                                                port=self.test_port)
#         # test checksum calculation
#         self.assertEqual(gw_device_api.calc_checksum(b'00112233bbccddee'), 168)
#
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_build_cmd_packet(self, mock_get_mac, mock_get_firmware,
#                               mock_get_system_params, mock_get_sensor_id):
#         '''Test construction of an API command packet
#
#         Tests:
#         1. building a command packet for each command in Station.api_commands
#         2. building a command packet with a payload
#         3. building a command packet for an unknown command
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (string)
#         mock_get_mac.return_value = StationTestCase.mock_mac
#         # get_firmware_version - display_firmware version (string)
#         mock_get_firmware.return_value = StationTestCase.mock_firmware
#         # get_system_params - system parameters (dict)
#         mock_get_system_params.return_value = StationTestCase.mock_system_params
#         # get_sensor_id - sensor ID data
#         mock_get_sensor_id.return_value = None
#         # get our mocked gateway device API object
#         gw_device_api = user.gw1000.GatewayApi(ip_address=self.test_ip,
#                                                port=self.test_port)
#         # test the command packet built for each API command we know about
#         for cmd, packet in self.commands.items():
#             self.assertEqual(gw_device_api.build_cmd_packet(cmd), hex_to_bytes(packet))
#         # test a command packet that has a payload
#         self.assertEqual(gw_device_api.build_cmd_packet(self.cmd, hex_to_bytes(self.cmd_payload)),
#                          hex_to_bytes(self.cmd_packet))
#         # test building a command packet for an unknown command, should be an UnknownCommand exception
#         self.assertRaises(user.gw1000.UnknownApiCommand,
#                           gw_device_api.build_cmd_packet,
#                           cmd='UNKNOWN_COMMAND')
#
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_decode_broadcast_response(self, mock_get_mac, mock_get_firmware,
#                                        mock_get_system_params, mock_get_sensor_id):
#         '''Test decoding of a broadcast response
#
#         Tests:
#         1. decode a broadcast response
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (bytestring)
#         mock_get_mac.return_value = StationTestCase.mock_mac
#         # get_firmware_version - display_firmware version (bytestring)
#         mock_get_firmware.return_value = StationTestCase.mock_firmware
#         # get_system_params - system parameters (dict)
#         mock_get_system_params.return_value = StationTestCase.mock_system_params
#         # get_sensor_id - sensor ID data
#         mock_get_sensor_id.return_value = None
#
#         # get our mocked gateway device API object
#         gw_device_api = user.gw1000.GatewayApi(ip_address=self.test_ip,
#                                                port=self.test_port)
#         # get the broadcast response test data as a bytestring
#         data = hex_to_bytes(self.broadcast_response_data)
#         # test broadcast response decode
#         self.assertEqual(gw_device_api.decode_broadcast_response(data), self.decoded_broadcast_response)
#
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_api_response_validity_check(self, mock_get_mac, mock_get_firmware,
#                                          mock_get_sys, mock_get_sensor_id):
#         '''Test validity checking of an API response
#
#         Tests:
#         1. checks Station.check_response() with good data
#         2. checks that Station.check_response() raises an InvalidChecksum
#            exception for a response with an invalid checksum
#         3. checks that Station.check_response() raises an UnknownApiCommand
#            exception for a response with a valid check sum but an unexpected
#            command code
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (bytestring)
#         mock_get_mac.return_value = StationTestCase.mock_mac
#         # get_firmware_version - display_firmware version (bytestring)
#         mock_get_firmware.return_value = StationTestCase.mock_firmware
#         # get_system_params() - system parameters (bytestring)
#         mock_get_sys.return_value = StationTestCase.mock_system_params
#         # get_sensor_id - get sensor IDs (bytestring)
#         mock_get_sensor_id.return_value = None
#
#         # get our mocked gateway device API object
#         gw_device_api = user.gw1000.GatewayApi(ip_address=self.test_ip,
#                                                port=self.test_port)
#         # test check_response() with good data, should be no exception
#         try:
#             gw_device_api.check_response(self.read_fware_resp_bytes,
#                                          self.cmd_read_fware_ver)
#         except user.gw1000.InvalidChecksum:
#             self.fail('check_response() raised an InvalidChecksum exception')
#         except user.gw1000.UnknownApiCommand:
#             self.fail('check_response() raised an UnknownApiCommand exception')
#         # test check_response() with a bad checksum data, should be an InvalidChecksum exception
#         self.assertRaises(user.gw1000.InvalidChecksum,
#                           gw_device_api.check_response,
#                           response=self.read_fware_resp_bad_checksum_bytes,
#                           cmd_code=self.cmd_read_fware_ver)
#         # test check_response() with a valid checksum but unexpected command
#         # code, should be an UnknownApiCommand exception
#         self.assertRaises(user.gw1000.UnknownApiCommand,
#                           gw_device_api.check_response,
#                           response=self.read_fware_resp_unex_cmd_bytes,
#                           cmd_code=self.cmd_read_fware_ver)
#
#     @patch.object(user.gw1000.GatewayApi, 'discover')
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_discovery(self, mock_get_mac, mock_get_firmware,
#                        mock_get_sys, mock_get_sensor_id, mock_discover):
#         '''Test discovery related methods.
#
#         Tests:
#         1.
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (bytestring)
#         mock_get_mac.return_value = StationTestCase.discover_multi_resp[2]['mac']
#         # get_firmware_version - display_firmware version (bytestring)
#         mock_get_firmware.return_value = StationTestCase.mock_firmware
#         # get_system_params() - system parameters (bytestring)
#         mock_get_sys.return_value = StationTestCase.mock_system_params
#         # get_sensor_id - get sensor IDs (bytestring)
#         mock_get_sensor_id.return_value = None
#         # discover() - list of discovered devices (list of dicts)
#         mock_discover.return_value = StationTestCase.discover_multi_resp
#
#         # get our mocked gateway device API object
#         gw_device_api = user.gw1000.GatewayApi(ip_address=self.test_ip,
#                                                port=self.test_port)
#         # to use discovery we need to fool the Station object into thinking it
#         # used discovery to obtain the current devices IP address and port
#         gw_device_api.ip_discovered = True
#         # to speed up testing we can reduce some retries and wait times
#         gw_device_api.max_tries = 1
#         gw_device_api.retry_wait = 3
#
#         # test Station.rediscover() when the original device is found again
#         # force rediscovery
#         gw_device_api.rediscover()
#         # test that we retained the original MAC address after rediscovery
#         self.assertEqual(gw_device_api.mac, StationTestCase.discover_multi_resp[2]['mac'])
#         # test that the new IP address was detected
#         self.assertEqual(gw_device_api.ip_address.decode(),
#                          StationTestCase.discover_multi_resp[2]['ip_address'])
#         # test that the new port number was detected
#         self.assertEqual(gw_device_api.port,
#                          StationTestCase.discover_multi_resp[2]['port'])
#
#         # test Station.rediscover() when devices are found but not the original
#         # device
#         mock_discover.return_value = StationTestCase.discover_multi_diff_resp
#         # reset our Station object IP address and port
#         gw_device_api.ip_address = self.test_ip.encode()
#         gw_device_api.port = self.test_port
#         # force rediscovery
#         gw_device_api.rediscover()
#         # test that we retained the original MAC address after rediscovery
#         self.assertEqual(gw_device_api.mac, StationTestCase.discover_multi_resp[2]['mac'])
#         # test that the new IP address was detected
#         self.assertEqual(gw_device_api.ip_address.decode(), self.test_ip)
#         # test that the new port number was detected
#         self.assertEqual(gw_device_api.port, self.test_port)
#
#         # now test Station.rediscover() when no devices are found
#         mock_discover.return_value = []
#         # reset our Station object IP address and port
#         gw_device_api.ip_address = self.test_ip.encode()
#         gw_device_api.port = self.test_port
#         # force rediscovery
#         gw_device_api.rediscover()
#         # test that we retained the original MAC address after rediscovery
#         self.assertEqual(gw_device_api.mac, StationTestCase.discover_multi_resp[2]['mac'])
#         # test that the new IP address was detected
#         self.assertEqual(gw_device_api.ip_address.decode(), self.test_ip)
#         # test that the new port number was detected
#         self.assertEqual(gw_device_api.port, self.test_port)
#
#         # now test Station.rediscover() when Station.discover() raises an
#         # exception
#         mock_discover.side_effect = socket.error
#         # reset our Station object IP address and port
#         gw_device_api.ip_address = self.test_ip.encode()
#         gw_device_api.port = self.test_port
#         # force rediscovery
#         gw_device_api.rediscover()
#         # test that we retained the original MAC address after rediscovery
#         self.assertEqual(gw_device_api.mac, StationTestCase.discover_multi_resp[2]['mac'])
#         # test that the new IP address was detected
#         self.assertEqual(gw_device_api.ip_address.decode(), self.test_ip)
#         # test that the new port number was detected
#         self.assertEqual(gw_device_api.port, self.test_port)
#
# class GatewayDriverTestCase(unittest.TestCase):
#     '''Test the GatewayDriver.
#
#     Uses mock to simulate methods required to run a GatewayDriver without a
#     connected gateway device. If for some reason the GatewayDriver cannot be
#     run the test is skipped.
#     '''
#
#     fake_ip = '192.168.99.99'
#     fake_port = 44444
#     fake_mac = b'\xdcO'X\xa2E'
#     user_field_map = {
#         'dateTime': 'datetime',
#         'inTemp': 'intemp',
#         'outTemp': 'outtemp'
#     }
#     user_field_extensions = {
#         'insideTemp': 'intemp',
#         'aqi': 'pm10'
#     }
#     # Create a dummy config so we can stand up a dummy engine with a
#     # GatewayDriver.
#     dummy_config = '''
#     [Station]
#         station_type = GW1000
#         altitude = 0, meter
#         latitude = 0
#         longitude = 0
#     [GW1000]
#         driver = user.gw1000
#     [Engine]
#         [[Services]]'''
#     # dummy gateway device data used to exercise the device to WeeWX mapping
#     gw_data = {'absbarometer': 1009.3,
#                'datetime': 1632109437,
#                'inHumidity': 56,
#                'inTemp': 27.3,
#                'lightningcount': 32,
#                't_raintotals': 100.3,
#                'relbarometer': 1014.3,
#                'usUnits': 17
#                }
#     # mapped dummy GW1000 data
#     result_data = {'dateTime': 1632109437,
#                    'inHumidity': 56,
#                    'inTemp': 27.3,
#                    'lightningcount': 32,
#                    'pressure': 1009.3,
#                    'relbarometer': 1014.3,
#                    'totalRain': 100.3,
#                    'usUnits': 17
#                    }
#     # amount to increment delta measurements
#     increment = 5.6
#     # mocked read_system_parameters() output
#     # mock_sys_params_resp = b'\xff\xff0\x0b\x00\x01b7\rj^\x02\xac'
#     mock_sys_params_resp = {
#         'frequency': 0,
#         'sensor_type': 1,
#         'utc': 1647775082,
#         'timezone_index': 94,
#         'dst_status': True
#     }
#     # mocked get_firmware() response
#     # mock_get_firm_resp = b'\xff\xffP\x11\rGW1000_V1.6.8}'
#     mock_get_firm_resp = ''.join([chr(x) for x in b'\xff\xffP\x11\rGW1000_V1.6.8}'])
#     # mocked get_sensor_id() response
#     mock_sensor_id_resp = 'FF FF 3C 01 54 00 FF FF FF FE FF 00 01 FF FF FF ' \
#                           'FE FF 00 02 FF FF FF FE FF 00 03 FF FF FF FE 1F ' \
#                           '00 05 00 00 00 E4 00 04 06 00 00 00 5B 00 04 07 ' \
#                           '00 00 00 BE 00 04 08 00 00 00 D0 00 04 09 00 00 ' \
#                           '00 52 00 04 0A 00 00 00 6C 00 04 0B 00 00 00 C8 ' \
#                           '00 04 0C 00 00 00 EE 00 04 0D FF FF FF FE 00 00 ' \
#                           '0E 00 00 CD 19 0D 04 0F 00 00 CB D1 0D 04 10 FF ' \
#                           'FF FF FE 1F 00 11 00 00 CD 04 1F 00 12 FF FF FF ' \
#                           'FE 1F 00 13 FF FF FF FE 1F 00 14 FF FF FF FE 1F ' \
#                           '00 15 FF FF FF FE 1F 00 16 00 00 C4 97 06 04 17 ' \
#                           'FF FF FF FE 0F 00 18 FF FF FF FE 0F 00 19 FF FF ' \
#                           'FF FE 0F 00 1A 00 00 D3 D3 05 00 1B FF FF FF FE ' \
#                           '0F 00 1C FF FF FF FE 0F 00 1D FF FF FF FE 0F 00 ' \
#                           '1E FF FF FF FE 0F 00 1F 00 00 2A E7 40 04 20 FF ' \
#                           'FF FF FE FF 00 21 FF FF FF FE FF 00 22 FF FF FF ' \
#                           'FE FF 00 23 FF FF FF FE FF 00 24 FF FF FF FE FF ' \
#                           '00 25 FF FF FF FE FF 00 26 FF FF FF FE FF 00 27 ' \
#                           'FF FF FF FE 0F 00 28 FF FF FF FE FF 00 29 FF FF ' \
#                           'FF FE FF 00 2A FF FF FF FE FF 00 2B FF FF FF FE ' \
#                           'FF 00 2C FF FF FF FE FF 00 2D FF FF FF FE FF 00 ' \
#                           '2E FF FF FF FE FF 00 2F FF FF FF FE FF 00 30 FF ' \
#                           'FF FF FE FF 00 F4'
#
#     @classmethod
#     def setUpClass(cls):
#         '''Setup the GatewayDriverTestCase to perform its tests.'''
#
#         # construct our config dict
#         config = configobj.ConfigObj(StringIO(GatewayDriverTestCase.dummy_config))
#         # set the IP address we will use, if we received an IP address via the
#         # command line use it, otherwise use a fake address
#         config['GW1000']['ip_address'] = cls.ip_address if cls.ip_address is not None else GatewayDriverTestCase.fake_ip
#         # set the port number we will use, if we received a port number via the
#         # command line use it, otherwise use a fake port number
#         config['GW1000']['port'] = cls.port if cls.port is not None else GatewayDriverTestCase.fake_port
#         # save the config dict for use later
#         cls.gw1000_config = config
#         field_map = dict(user.gw1000.Gateway.default_field_map)
#         # now add in the rain field map
#         field_map.update(user.gw1000.Gateway.rain_field_map)
#         # now add in the wind field map
#         field_map.update(user.gw1000.Gateway.wind_field_map)
#         # now add in the battery state field map
#         field_map.update(user.gw1000.Gateway.battery_field_map)
#         # now add in the sensor signal field map
#         field_map.update(user.gw1000.Gateway.sensor_signal_field_map)
#         cls.default_field_map = field_map
#
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_map_construction(self, mock_get_mac, mock_get_firmware, mock_get_sys, mock_get_sensor_id):
#         '''Test GatewayDriver mapping construction
#
#         Tests:
#         1.  the default field map is used when no user specified field map or
#             field map extensions are provided
#         2.  a user specified field map overrides the default field map
#         3.  a user specified field map and field map extensions override the
#             default field map
#         4.  a user specified field extension without a user specified field map
#             correctly modifies the default field map
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (bytestring)
#         mock_get_mac.return_value = GatewayDriverTestCase.fake_mac
#         # get_firmware_version - display_firmware version (bytestring)
#         mock_get_firmware.return_value = GatewayDriverTestCase.mock_get_firm_resp
#         # get_system_params() - system parameters (bytestring)
#         mock_get_sys.return_value = GatewayDriverTestCase.mock_sys_params_resp
#         # get_sensor_id - get sensor IDs (bytestring)
#         mock_get_sensor_id.return_value = hex_to_bytes(GatewayDriverTestCase.mock_sensor_id_resp)
#
#         # we will be manipulating the gateway config so make a copy
#         # that we can alter without affecting other test methods
#         gw1000_config_copy = configobj.ConfigObj(self.gw1000_config)
#         # obtain a GatewayDriver object
#         gw_driver = self.get_gateway_driver(config=gw1000_config_copy,
#                                              caller='test_map_construction')
#
#         # test the default field map
#         # check the GatewayDriver field map consists of the default field map
#         self.assertDictEqual(gw_driver.field_map, self.default_field_map)
#
#         # test a user specified field map
#         # add a user defined field map to our config
#         gw1000_config_copy['GW1000']['field_map'] = GatewayDriverTestCase.user_field_map
#         # obtain a new GatewayDriver object using the modified config
#         gw_driver = self.get_gateway_driver(config=gw1000_config_copy,
#                                              caller='test_map_construction')
#         # check the GatewayDriver field map consists of the user specified
#         # field map
#         self.assertDictEqual(gw_driver.field_map, GatewayDriverTestCase.user_field_map)
#
#         # test a user specified field map with user specified field map extensions
#         # add user defined field map extensions to our config
#         gw1000_config_copy['GW1000']['field_map_extensions'] = GatewayDriverTestCase.user_field_extensions
#         # obtain a new GatewayDriver object using the modified config
#         gw_driver = self.get_gateway_driver(config=gw1000_config_copy,
#                                              caller='test_map_construction')
#         # construct the expected result, it will consist of the user specified
#         # field map modified by the user specified field map extensions
#         _result = dict(GatewayDriverTestCase.user_field_map)
#         # the gateway field 'intemp' is being re-mapped so pop its entry from
#         # the user specified field map
#         _dummy = _result.pop('inTemp')
#         # update the field map with the field map extensions
#         _result.update(GatewayDriverTestCase.user_field_extensions)
#         # check the GatewayDriver field map consists of the user specified
#         # field map modified by the user specified field map extensions
#         self.assertDictEqual(gw_driver.field_map, _result)
#
#         # test the default field map with user specified field map extensions
#         # remove the user defined field map from our config
#         _dummy = gw1000_config_copy['GW1000'].pop('field_map')
#         # obtain a new GatewayDriver object using the modified config
#         gw_driver = self.get_gateway_driver(config=gw1000_config_copy,
#                                              caller='test_map_construction')
#         # construct the expected result
#         _result = dict(self.default_field_map)
#         # the gateway fields 'intemp' and 'pm10' are being re-mapped so pop
#         # each fields entry from the result field map
#         _dummy = _result.pop('inTemp')
#         _dummy = _result.pop('pm10')
#         # update the field map with the field map extensions
#         _result.update(GatewayDriverTestCase.user_field_extensions)
#         # check the GatewayDriver field map consists of the default field map
#         # modified by the user specified field map extensions
#         self.assertDictEqual(gw_driver.field_map, _result)
#
#     @staticmethod
#     def get_gateway_driver(config, caller):
#         '''Get a GatewayDriver object.
#
#         Start a dummy engine with the Ecowitt gateway driver.
#
#         Return a GatewayDriver object or raise a unittest.SkipTest exception.
#         '''
#
#         # create a dummy engine, wrap in a try..except in case there is an
#         # error
#         try:
#             engine = weewx.engine.StdEngine(config)
#         except user.gw1000.GWIOError as e:
#             # could not communicate with the mocked or real gateway device for
#             # some reason, skip the test if we have an engine try to shut it
#             # down
#             if engine:
#                 print('\nShutting down engine ... ', end='')
#                 engine.shutDown()
#             # now raise unittest.SkipTest to skip this test class
#             raise unittest.SkipTest('%s: Unable to connect to GW1000' % caller)
#         return engine.console
#
# class GatewayServiceTestCase(unittest.TestCase):
#     '''Test the GatewayService.
#
#     Uses mock to simulate methods required to run a GatewayService without a
#     connected gateway device. If for some reason the GatewayService cannot be
#     run the test is skipped.
#     '''
#
#     fake_ip = '192.168.99.99'
#     fake_port = 44444
#     fake_mac = b'\xdcO'X\xa2E'
#     user_field_map = {
#         'dateTime': 'datetime',
#         'inTemp': 'intemp',
#         'outTemp': 'outtemp'
#     }
#     user_field_extensions = {
#         'insideTemp': 'intemp',
#         'aqi': 'pm10'
#     }
#     # Create a dummy config so we can stand up a dummy engine with a dummy
#     # simulator emitting arbitrary loop packets. Only include the
#     # GatewayService service, we don't need the others. This will be a
#     # 'loop packets only' setup, no archive records; but that doesn't
#     # matter, we just need to be able to exercise the GatewayService.
#     dummy_config = '''
#     [Station]
#         station_type = Simulator
#         altitude = 0, meter
#         latitude = 0
#         longitude = 0
#     [Simulator]
#         driver = weewx.drivers.simulator
#         mode = simulator
#     [GW1000]
#     [Engine]
#         [[Services]]
#             data_services = user.gw1000.GatewayService'''
#     # dummy gateway device data used to exercise the device to WeeWX mapping
#     gw_data = {'absbarometer': 1009.3,
#                'datetime': 1632109437,
#                'inHumidity': 56,
#                'inTemp': 27.3,
#                'lightningcount': 32,
#                't_raintotals': 100.3,
#                'relbarometer': 1014.3,
#                'usUnits': 17
#                }
#     # mapped dummy GW1000 data
#     result_data = {'dateTime': 1632109437,
#                    'inHumidity': 56,
#                    'inTemp': 27.3,
#                    'lightningcount': 32,
#                    'pressure': 1009.3,
#                    'relbarometer': 1014.3,
#                    'totalRain': 100.3,
#                    'usUnits': 17
#                    }
#     # amount to increment delta measurements
#     increment = 5.6
#     # mocked read_system_parameters() output
#     # mock_sys_params_resp = b'\xff\xff0\x0b\x00\x01b7\rj^\x02\xac'
#     mock_sys_params_resp = {
#         'frequency': 0,
#         'sensor_type': 1,
#         'utc': 1647775082,
#         'timezone_index': 94,
#         'dst_status': True
#     }
#     # mocked get_firmware() response
#     # mock_get_firm_resp = b'\xff\xffP\x11\rGW1000_V1.6.8}'
#     mock_get_firm_resp = ''.join([chr(x) for x in b'\xff\xffP\x11\rGW1000_V1.6.8}'])
#     # mocked get_sensor_id() response
#     mock_sensor_id_resp = 'FF FF 3C 01 54 00 FF FF FF FE FF 00 01 FF FF FF ' \
#                           'FE FF 00 02 FF FF FF FE FF 00 03 FF FF FF FE 1F ' \
#                           '00 05 00 00 00 E4 00 04 06 00 00 00 5B 00 04 07 ' \
#                           '00 00 00 BE 00 04 08 00 00 00 D0 00 04 09 00 00 ' \
#                           '00 52 00 04 0A 00 00 00 6C 00 04 0B 00 00 00 C8 ' \
#                           '00 04 0C 00 00 00 EE 00 04 0D FF FF FF FE 00 00 ' \
#                           '0E 00 00 CD 19 0D 04 0F 00 00 CB D1 0D 04 10 FF ' \
#                           'FF FF FE 1F 00 11 00 00 CD 04 1F 00 12 FF FF FF ' \
#                           'FE 1F 00 13 FF FF FF FE 1F 00 14 FF FF FF FE 1F ' \
#                           '00 15 FF FF FF FE 1F 00 16 00 00 C4 97 06 04 17 ' \
#                           'FF FF FF FE 0F 00 18 FF FF FF FE 0F 00 19 FF FF ' \
#                           'FF FE 0F 00 1A 00 00 D3 D3 05 00 1B FF FF FF FE ' \
#                           '0F 00 1C FF FF FF FE 0F 00 1D FF FF FF FE 0F 00 ' \
#                           '1E FF FF FF FE 0F 00 1F 00 00 2A E7 40 04 20 FF ' \
#                           'FF FF FE FF 00 21 FF FF FF FE FF 00 22 FF FF FF ' \
#                           'FE FF 00 23 FF FF FF FE FF 00 24 FF FF FF FE FF ' \
#                           '00 25 FF FF FF FE FF 00 26 FF FF FF FE FF 00 27 ' \
#                           'FF FF FF FE 0F 00 28 FF FF FF FE FF 00 29 FF FF ' \
#                           'FF FE FF 00 2A FF FF FF FE FF 00 2B FF FF FF FE ' \
#                           'FF 00 2C FF FF FF FE FF 00 2D FF FF FF FE FF 00 ' \
#                           '2E FF FF FF FE FF 00 2F FF FF FF FE FF 00 30 FF ' \
#                           'FF FF FE FF 00 F4'
#
#     @classmethod
#     def setUpClass(cls):
#         '''Setup the GatewayServiceTestCase to perform its tests.'''
#
#         # construct our config dict
#         config = configobj.ConfigObj(StringIO(GatewayServiceTestCase.dummy_config))
#         # set the IP address we will use, if we received an IP address via the
#         # command line use it, otherwise use a fake address
#         config['GW1000']['ip_address'] = cls.ip_address if cls.ip_address is not None else GatewayServiceTestCase.fake_ip
#         # set the port number we will use, if we received a port number via the
#         # command line use it, otherwise use a fake port number
#         config['GW1000']['port'] = cls.port if cls.port is not None else GatewayServiceTestCase.fake_port
#         # save the service config dict for use later
#         cls.gw1000_svc_config = config
#         field_map = dict(user.gw1000.Gateway.default_field_map)
#         # now add in the rain field map
#         field_map.update(user.gw1000.Gateway.rain_field_map)
#         # now add in the wind field map
#         field_map.update(user.gw1000.Gateway.wind_field_map)
#         # now add in the battery state field map
#         field_map.update(user.gw1000.Gateway.battery_field_map)
#         # now add in the sensor signal field map
#         field_map.update(user.gw1000.Gateway.sensor_signal_field_map)
#         cls.default_field_map = field_map
#
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_map_construction(self, mock_get_mac, mock_get_firmware, mock_get_sys, mock_get_sensor_id):
#         '''Test GatewayService mapping construction
#
#         Tests:
#         1.  the default field map is used when no user specified field map or
#             field map extensions are provided
#         2.  a user specified field map overrides the default field map
#         3.  a user specified field map and field map extensions override the
#             default field map
#         4.  a user specified field extension without a user specified field map
#             correctly modifies the default field map
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (bytestring)
#         mock_get_mac.return_value = GatewayServiceTestCase.fake_mac
#         # get_firmware_version - display_firmware version (bytestring)
#         mock_get_firmware.return_value = GatewayServiceTestCase.mock_get_firm_resp
#         # get_system_params() - system parameters (bytestring)
#         mock_get_sys.return_value = GatewayServiceTestCase.mock_sys_params_resp
#         # get_sensor_id - get sensor IDs (bytestring)
#         mock_get_sensor_id.return_value = hex_to_bytes(GatewayServiceTestCase.mock_sensor_id_resp)
#
#         # we will be manipulating the gateway service config so make a copy
#         # that we can alter without affecting other test methods
#         gw1000_svc_config_copy = configobj.ConfigObj(self.gw1000_svc_config)
#         # obtain a GatewayService object
#         gw_service = self.get_gateway_service(config=gw1000_svc_config_copy,
#                                               caller='test_map_construction')
#
#         # test the default field map
#         # check the GatewayService field map consists of the default field map
#         self.assertDictEqual(gw_service.field_map, self.default_field_map)
#
#         # test a user specified field map
#         # add a user defined field map to our config
#         gw1000_svc_config_copy['GW1000']['field_map'] = GatewayServiceTestCase.user_field_map
#         # obtain a new GatewayService object using the modified config
#         gw_service = self.get_gateway_service(config=gw1000_svc_config_copy,
#                                               caller='test_map_construction')
#         # check the GatewayService field map consists of the user specified
#         # field map
#         self.assertDictEqual(gw_service.field_map, GatewayServiceTestCase.user_field_map)
#
#         # test a user specified field map with user specified field map extensions
#         # add user defined field map extensions to our config
#         gw1000_svc_config_copy['GW1000']['field_map_extensions'] = GatewayServiceTestCase.user_field_extensions
#         # obtain a new GatewayService object using the modified config
#         gw_service = self.get_gateway_service(config=gw1000_svc_config_copy,
#                                               caller='test_map_construction')
#         # construct the expected result, it will consist of the user specified
#         # field map modified by the user specified field map extensions
#         _result = dict(GatewayServiceTestCase.user_field_map)
#         # the gateway field 'intemp' is being re-mapped so pop its entry from
#         # the user specified field map
#         _dummy = _result.pop('inTemp')
#         # update the field map with the field map extensions
#         _result.update(GatewayServiceTestCase.user_field_extensions)
#         # check the GatewayService field map consists of the user specified
#         # field map modified by the user specified field map extensions
#         self.assertDictEqual(gw_service.field_map, _result)
#
#         # test the default field map with user specified field map extensions
#         # remove the user defined field map from our config
#         _dummy = gw1000_svc_config_copy['GW1000'].pop('field_map')
#         # obtain a new GatewayService object using the modified config
#         gw_service = self.get_gateway_service(config=gw1000_svc_config_copy,
#                                               caller='test_map_construction')
#         # construct the expected result
#         _result = dict(self.default_field_map)
#         # the gateway fields 'intemp' and 'pm10' are being re-mapped so pop
#         # each fields entry from the result field map
#         _dummy = _result.pop('inTemp')
#         _dummy = _result.pop('pm10')
#         # update the field map with the field map extensions
#         _result.update(GatewayServiceTestCase.user_field_extensions)
#         # check the GatewayService field map consists of the default field map
#         # modified by the user specified field map extensions
#         self.assertDictEqual(gw_service.field_map, _result)
#
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_map_operation(self, mock_get_mac, mock_get_firmware, mock_get_sys, mock_get_sensor_id):
#         '''Test GatewayService mapping operation
#
#         Tests:
#         1. field dateTime is included in the mapped data
#         2. field usUnits is included in the mapped data
#         3. gateway device obs data is correctly mapped to WeeWX fields
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (bytestring)
#         mock_get_mac.return_value = GatewayServiceTestCase.fake_mac
#         # get_firmware_version - display_firmware version (bytestring)
#         mock_get_firmware.return_value = GatewayServiceTestCase.mock_get_firm_resp
#         # get_system_params() - system parameters (bytestring)
#         mock_get_sys.return_value = GatewayServiceTestCase.mock_sys_params_resp
#         # get_sensor_id - get sensor IDs (bytestring)
#         mock_get_sensor_id.return_value = hex_to_bytes(GatewayServiceTestCase.mock_sensor_id_resp)
#         # obtain a GatewayService object
#         gw_service = self.get_gateway_service(config=self.gw1000_svc_config,
#                                               caller='test_map')
#         # get a mapped  version of our GW1000 test data
#         mapped_gw_data = gw_service.map_data(self.gw_data)
#         # check that our mapped data has a field 'dateTime'
#         self.assertIn('dateTime', mapped_gw_data)
#         # check that our mapped data has a field 'usUnits'
#         self.assertIn('usUnits', mapped_gw_data)
#         # check that the usUnits field is set to weewx.METRICWX
#         self.assertEqual(weewx.METRICWX, mapped_gw_data.get('usUnits'))
#
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_rain(self, mock_get_mac, mock_get_firmware, mock_get_sys, mock_get_sensor_id):
#         '''Test GW1000Service correctly calculates WeeWX field rain
#
#         Tests:
#         1. field rain is included in the GW1000 data
#         2. field rain is set to None if this is the first packet
#         2. field rain is correctly calculated for a subsequent packet
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (bytestring)
#         mock_get_mac.return_value = GatewayServiceTestCase.fake_mac
#         # get_firmware_version - display_firmware version (bytestring)
#         mock_get_firmware.return_value = GatewayServiceTestCase.mock_get_firm_resp
#         # get_system_params - system parameters (bytestring)
#         mock_get_sys.return_value = GatewayServiceTestCase.mock_sys_params_resp
#         # get_sensor_id - get sensor IDs (bytestring)
#         mock_get_sensor_id.return_value = hex_to_bytes(GatewayServiceTestCase.mock_sensor_id_resp)
#         # obtain a GW1000 service
#         gw1000_svc = self.get_gateway_service(config=self.gw1000_svc_config,
#                                               caller='test_map')
#         # set some GW1000 service parameters to enable rain related tests
#         gw1000_svc.rain_total_field = 't_raintotals'
#         gw1000_svc.rain_mapping_confirmed = True
#         # take a copy of our test data as we will be changing it
#         _gw1000_data = dict(self.gw_data)
#         # perform the rain calculation
#         gw1000_svc.calculate_rain(_gw1000_data)
#         # check that our data now has field 'rain'
#         self.assertIn('t_rain', _gw1000_data)
#         # check that the field rain is None as this is the first packet
#         self.assertIsNone(_gw1000_data['t_rain'])
#         # increment increase the rainfall in our GW1000 data
#         _gw1000_data['t_raintotals'] += self.increment
#         # perform the rain calculation
#         gw1000_svc.calculate_rain(_gw1000_data)
#         # Check that the field rain is now the increment we used. Use
#         # AlmostEqual as unit conversion could cause assertEqual to fail.
#         self.assertAlmostEqual(_gw1000_data.get('t_rain'), self.increment, places=3)
#         # check delta_rain calculation
#         # last_rain is None
#         self.assertIsNone(gw1000_svc.delta_rain(rain=10.2, last_rain=None))
#         # rain is None
#         self.assertIsNone(gw1000_svc.delta_rain(rain=None, last_rain=5.2))
#         # rain < last_rain
#         self.assertEqual(gw1000_svc.delta_rain(rain=4.2, last_rain=5.8), 4.2)
#         # rain and last_rain are not None
#         self.assertAlmostEqual(gw1000_svc.delta_rain(rain=12.2, last_rain=5.8),
#                                6.4,
#                                places=3)
#
#     @patch.object(user.gw1000.GatewayApi, 'get_sensor_id')
#     @patch.object(user.gw1000.GatewayApi, 'get_system_params')
#     @patch.object(user.gw1000.GatewayApi, 'get_firmware_version')
#     @patch.object(user.gw1000.GatewayApi, 'get_mac_address')
#     def test_lightning(self, mock_get_mac, mock_get_firmware, mock_get_sys, mock_get_sensor_id):
#         '''Test GW1000Service correctly calculates WeeWX field lightning_strike_count
#
#         Tests:
#         1. field lightning_strike_count is included in the GW1000 data
#         2. field lightning_strike_count is set to None if this is the first
#            packet
#         2. field lightning_strike_count is correctly calculated for a
#            subsequent packet
#         '''
#
#         # set return values for mocked methods
#         # get_mac_address - MAC address (bytestring)
#         mock_get_mac.return_value = GatewayServiceTestCase.fake_mac
#         # get_firmware_version - display_firmware version (bytestring)
#         mock_get_firmware.return_value = GatewayServiceTestCase.mock_get_firm_resp
#         # get_system_params - system parameters (bytestring)
#         mock_get_sys.return_value = GatewayServiceTestCase.mock_sys_params_resp
#         # get_sensor_id - get sensor IDs (bytestring)
#         mock_get_sensor_id.return_value = hex_to_bytes(GatewayServiceTestCase.mock_sensor_id_resp)
#         # obtain a GW1000 service
#         gw1000_svc = self.get_gateway_service(config=self.gw1000_svc_config,
#                                               caller='test_map')
#         # take a copy of our test data as we will be changing it
#         _gw1000_data = dict(self.gw_data)
#         # perform the lightning calculation
#         gw1000_svc.calculate_lightning_count(_gw1000_data)
#         # check that our data now has field 'lightning_strike_count'
#         self.assertIn('lightning_strike_count', _gw1000_data)
#         # check that the field lightning_strike_count is None as this is the
#         # first packet
#         self.assertIsNone(_gw1000_data.get('lightning_strike_count', 1))
#         # increment increase the lightning count in our GW1000 data
#         _gw1000_data['lightningcount'] += self.increment
#         # perform the lightning calculation
#         gw1000_svc.calculate_lightning_count(_gw1000_data)
#         # check that the field lightning_strike_count is now the increment we
#         # used
#         self.assertAlmostEqual(_gw1000_data.get('lightning_strike_count'),
#                                self.increment,
#                                places=1)
#         # check delta_lightning calculation
#         # last_count is None
#         self.assertIsNone(gw1000_svc.delta_lightning(count=10, last_count=None))
#         # count is None
#         self.assertIsNone(gw1000_svc.delta_lightning(count=None, last_count=5))
#         # count < last_count
#         self.assertEqual(gw1000_svc.delta_lightning(count=42, last_count=58), 42)
#         # count and last_count are not None
#         self.assertEqual(gw1000_svc.delta_lightning(count=122, last_count=58), 64)
#
#     @staticmethod
#     def get_gateway_service(config, caller):
#         '''Get a GatewayService object.
#
#         Start a dummy engine with the Ecowitt gateway driver running as a
#         service.
#
#         Return a GatewayService object or raise a unittest.SkipTest exception.
#         '''
#
#         # create a dummy engine, wrap in a try..except in case there is an
#         # error
#         try:
#             engine = weewx.engine.StdEngine(config)
#         except user.gw1000.GWIOError as e:
#             # could not communicate with the mocked or real gateway device for
#             # some reason, skip the test if we have an engine try to shut it
#             # down
#             if engine:
#                 print('\nShutting down engine ... ', end='')
#                 engine.shutDown()
#             # now raise unittest.SkipTest to skip this test class
#             raise unittest.SkipTest('%s: Unable to connect to GW1000' % caller)
#         else:
#             # Our GatewayService will have been instantiated by the engine
#             # during its startup. Whilst access to the service is not normally
#             # required we require access here so we can obtain info about the
#             # station we are using for this test. The engine does not provide a
#             # ready means to access that GatewayService so we can do a bit of
#             # guessing and iterate over the engine's services and select the
#             # one that has a 'collector' property. Unlikely to cause a problem
#             # since there are only two services in the dummy engine.
#             gateway_service = None
#             for service in engine.service_obj:
#                 if hasattr(service, 'collector'):
#                     gateway_service = service
#             if gateway_service:
#                 # tell the user what device we are using
#                 if gateway_service.collector.device.ip_address.decode() == GatewayServiceTestCase.fake_ip:
#                     _stem = '\nUsing mocked GW1x00 at %s:%d ... '
#                 else:
#                     _stem = '\nUsing real GW1x00 at %s:%d ... '
#                 print(_stem % (gateway_service.collector.device.ip_address.decode(),
#                                gateway_service.collector.device.port),
#                       end='')
#             else:
#                 # we could not get the GatewayService for some reason, shutdown
#                 # the engine and skip this test
#                 if engine:
#                     print('\nShutting down engine ... ', end='')
#                     engine.shutDown()
#                 # now skip this test class
#                 raise unittest.SkipTest('%s: Could not obtain GatewayService object' % caller)
#             return gateway_service


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
    '''Create a TestSuite object containing the tests we are to perform.'''

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
    # finally return the populated test suite
    return suite


def main():
    import argparse

    # test cases that are production ready
    # test_cases = (DebugOptionsTestCase, SensorsTestCase, HttpParserTestCase,
    #               UtilitiesTestCase, ListsAndDictsTestCase, StationTestCase,
    #               GatewayServiceTestCase, GatewayDriverTestCase)
    test_cases = (DebugOptionsTestCase, HttpParserTestCase,
                  EcowittSensorsTestCase, UtilitiesTestCase,
                  DeviceCatchupTestCase) #SensorsTestCase, HttpParserTestCase,
#                  ListsAndDictsTestCase, StationTestCase,
#                  GatewayServiceTestCase, GatewayDriverTestCase)

    usage = f'''{bcolors.BOLD}%(prog)s --help
                    --version
                    --test [--ip-address=IP_ADDRESS]
                           [-v|--verbose VERBOSITY]{bcolors.ENDC}
    '''
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
        # run the tests
        # first set the IP address and port to use in StationTestCase and
        # GatewayServiceTestCase
    #     StationTestCase.ip_address = args.ip_address
    #     StationTestCase.port = args.port
    # #    StationTestCase.no_device = args.no_device
    #     GatewayDriverTestCase.ip_address = args.ip_address
    #     GatewayDriverTestCase.port = args.port
    #     GatewayServiceTestCase.ip_address = args.ip_address
    #     GatewayServiceTestCase.port = args.port
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