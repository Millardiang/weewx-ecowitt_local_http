"""
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

                 Installer for Ecowitt Local HTTP API Driver

Version: 0.1.0a21                                       Date: xx April 2025

Revision History
    xx April 2025      v0.1.0
        -   initial implementation
"""

# python imports
import configobj
import io
from setup import ExtensionInstaller

# WeeWX imports
import weewx


REQUIRED_WEEWX_VERSION = "5.0.0"
DRIVER_VERSION = "0.1.0a21"
# define our config as a multiline string so we can preserve comments
ecowitt_config = """
[EcowittHttp]
    # This section is for the Ecowitt Local HTTP API driver.

    # How often to poll the API, default is every 20 seconds:
    poll_interval = 20

    # The driver to use:
    driver = user.ecowitt_http
    
[StdWXCalculate]

    [[Calculations]]
        t_rain = prefer_hardware
        p_rain = prefer_hardware
        
    [[Deltas]]
        [[[t_rain]]]
            input = t_rainyear
        [[[p_rain]]]
            input = p_rainyear
            
[Accumulator]

    # Start Ecowitt local HTTP API driver extractors
    [[daymaxwind]]
        extractor = last
    [[lightning_distance]]
        extractor = last
    [[lightning_strike_count]]
        extractor = sum
    [[lightning_last_det_time]]
        extractor = last
    [[t_rain]]
        extractor = sum
    [[t_rainevent]]
        extractor = last
    [[t_rainhour]]
        extractor = last
    [[t_stormRain]]
        extractor = last
    [[t_rainday]]
        extractor = last
    [[t_rainweek]]
        extractor = last
    [[t_rainmonth]]
        extractor = last
    [[t_rainyear]]
        extractor = last
    [[p_rain]]
        extractor = sum
    [[p_rainevent]]
        extractor = last
    [[p_rainhour]]
        extractor = last
    [[p_stormRain]]
        extractor = last
    [[p_rainday]]
        extractor = last
    [[p_rainweek]]
        extractor = last
    [[p_rainmonth]]
        extractor = last
    [[p_rainyear]]
        extractor = last
    [[is_raining]]
        extractor = last
    [[pm2_51_24h_avg]]
        extractor = last
    [[pm2_52_24h_avg]]
        extractor = last
    [[pm2_53_24h_avg]]
        extractor = last
    [[pm2_54_24h_avg]]
        extractor = last
    [[pm2_55_24h_avg]]
        extractor = last
    [[pm10_24h_avg]]
        extractor = last
    [[co2_24h_avg]]
        extractor = last
    [[heap_free]]
        extractor = last
    [[wh40_batt]]
        extractor = last
    [[wh26_batt]]
        extractor = last
    [[wh25_batt]]
        extractor = last
    [[wh65_batt]]
        extractor = last
    [[wn32_batt]]
        extractor = last
    [[wn31_ch1_batt]]
        extractor = last
    [[wn31_ch2_batt]]
        extractor = last
    [[wn31_ch3_batt]]
        extractor = last
    [[wn31_ch4_batt]]
        extractor = last
    [[wn31_ch5_batt]]
        extractor = last
    [[wn31_ch6_batt]]
        extractor = last
    [[wn31_ch7_batt]]
        extractor = last
    [[wn31_ch8_batt]]
        extractor = last
    [[wn34_ch1_batt]]
        extractor = last
    [[wn34_ch2_batt]]
        extractor = last
    [[wn34_ch3_batt]]
        extractor = last
    [[wn34_ch4_batt]]
        extractor = last
    [[wn34_ch5_batt]]
        extractor = last
    [[wn34_ch6_batt]]
        extractor = last
    [[wn34_ch7_batt]]
        extractor = last
    [[wn34_ch8_batt]]
        extractor = last
    [[wn35_ch1_batt]]
        extractor = last
    [[wn35_ch2_batt]]
        extractor = last
    [[wn35_ch3_batt]]
        extractor = last
    [[wn35_ch4_batt]]
        extractor = last
    [[wn35_ch5_batt]]
        extractor = last
    [[wn35_ch6_batt]]
        extractor = last
    [[wn35_ch7_batt]]
        extractor = last
    [[wn35_ch8_batt]]
        extractor = last
    [[wh41_ch1_batt]]
        extractor = last
    [[wh41_ch2_batt]]
        extractor = last
    [[wh41_ch3_batt]]
        extractor = last
    [[wh41_ch4_batt]]
        extractor = last
    [[wh45_batt]]
        extractor = last
    [[wh51_ch1_batt]]
        extractor = last
    [[wh51_ch2_batt]]
        extractor = last
    [[wh51_ch3_batt]]
        extractor = last
    [[wh51_ch4_batt]]
        extractor = last
    [[wh51_ch5_batt]]
        extractor = last
    [[wh51_ch6_batt]]
        extractor = last
    [[wh51_ch7_batt]]
        extractor = last
    [[wh51_ch8_batt]]
        extractor = last
    [[wh51_ch9_batt]]
        extractor = last
    [[wh51_ch10_batt]]
        extractor = last
    [[wh51_ch11_batt]]
        extractor = last
    [[wh51_ch12_batt]]
        extractor = last
    [[wh51_ch13_batt]]
        extractor = last
    [[wh51_ch14_batt]]
        extractor = last
    [[wh51_ch15_batt]]
        extractor = last
    [[wh51_ch16_batt]]
        extractor = last
    [[wh54_ch1_batt]]
        extractor = last
    [[wh54_ch2_batt]]
        extractor = last
    [[wh54_ch3_batt]]
        extractor = last
    [[wh54_ch4_batt]]
        extractor = last
    [[wh55_ch1_batt]]
        extractor = last
    [[wh55_ch2_batt]]
        extractor = last
    [[wh55_ch3_batt]]
        extractor = last
    [[wh55_ch4_batt]]
        extractor = last
    [[wh57_batt]]
        extractor = last
    [[wh68_batt]]
        extractor = last
    [[ws80_batt]]
        extractor = last
    [[ws90_batt]]
        extractor = last
    [[wh40_sig]]
        extractor = last
    [[wh26_sig]]
        extractor = last
    [[wh25_sig]]
        extractor = last
    [[wh65_sig]]
        extractor = last
    [[wn32_sig]]
        extractor = last
    [[wn31_ch1_sig]]
        extractor = last
    [[wn31_ch2_sig]]
        extractor = last
    [[wn31_ch3_sig]]
        extractor = last
    [[wn31_ch4_sig]]
        extractor = last
    [[wn31_ch5_sig]]
        extractor = last
    [[wn31_ch6_sig]]
        extractor = last
    [[wn31_ch7_sig]]
        extractor = last
    [[wn31_ch8_sig]]
        extractor = last
    [[wn34_ch1_sig]]
        extractor = last
    [[wn34_ch2_sig]]
        extractor = last
    [[wn34_ch3_sig]]
        extractor = last
    [[wn34_ch4_sig]]
        extractor = last
    [[wn34_ch5_sig]]
        extractor = last
    [[wn34_ch6_sig]]
        extractor = last
    [[wn34_ch7_sig]]
        extractor = last
    [[wn34_ch8_sig]]
        extractor = last
    [[wn35_ch1_sig]]
        extractor = last
    [[wn35_ch2_sig]]
        extractor = last
    [[wn35_ch3_sig]]
        extractor = last
    [[wn35_ch4_sig]]
        extractor = last
    [[wn35_ch5_sig]]
        extractor = last
    [[wn35_ch6_sig]]
        extractor = last
    [[wn35_ch7_sig]]
        extractor = last
    [[wn35_ch8_sig]]
        extractor = last
    [[wh41_ch1_sig]]
        extractor = last
    [[wh41_ch2_sig]]
        extractor = last
    [[wh41_ch3_sig]]
        extractor = last
    [[wh41_ch4_sig]]
        extractor = last
    [[wh45_sig]]
        extractor = last
    [[wh51_ch1_sig]]
        extractor = last
    [[wh51_ch2_sig]]
        extractor = last
    [[wh51_ch3_sig]]
        extractor = last
    [[wh51_ch4_sig]]
        extractor = last
    [[wh51_ch5_sig]]
        extractor = last
    [[wh51_ch6_sig]]
        extractor = last
    [[wh51_ch7_sig]]
        extractor = last
    [[wh51_ch8_sig]]
        extractor = last
    [[wh51_ch9_sig]]
        extractor = last
    [[wh51_ch10_sig]]
        extractor = last
    [[wh51_ch11_sig]]
        extractor = last
    [[wh51_ch12_sig]]
        extractor = last
    [[wh51_ch13_sig]]
        extractor = last
    [[wh51_ch14_sig]]
        extractor = last
    [[wh51_ch15_sig]]
        extractor = last
    [[wh51_ch16_sig]]
        extractor = last
    [[wh54_ch1_sig]]
        extractor = last
    [[wh54_ch2_sig]]
        extractor = last
    [[wh54_ch3_sig]]
        extractor = last
    [[wh54_ch4_sig]]
        extractor = last
    [[wh55_ch1_sig]]
        extractor = last
    [[wh55_ch2_sig]]
        extractor = last
    [[wh55_ch3_sig]]
        extractor = last
    [[wh55_ch4_sig]]
        extractor = last
    [[wh57_sig]]
        extractor = last
    [[wh68_sig]]
        extractor = last
    [[ws80_sig]]
        extractor = last
    # End Ecowitt local HTTP API driver extractors
"""

# construct our config dict
ecowitt_dict = configobj.ConfigObj(io.StringIO(ecowitt_config))


def version_compare(v1, v2):
    """Basic 'distutils' and 'packaging' free version comparison.

    v1 and v2 are WeeWX version numbers in string format.

    Returns:
        0 if v1 and v2 are the same
        -1 if v1 is less than v2
        +1 if v1 is greater than v2
    """

    import itertools
    mash = itertools.zip_longest(v1.split('.'), v2.split('.'), fillvalue='0')
    for x1, x2 in mash:
        if x1 > x2:
            return 1
        if x1 < x2:
            return -1
    return 0


def loader():
    return EcowittHttpInstaller()


class EcowittHttpInstaller(ExtensionInstaller):
    def __init__(self):
        if version_compare(weewx.__version__, REQUIRED_WEEWX_VERSION) < 0:
            msg = "%s requires WeeWX %s or greater, found %s" % (''.join(('Ecowitt local HTTP API driver ', DRIVER_VERSION)),
                                                                 REQUIRED_WEEWX_VERSION,
                                                                 weewx.__version__)
            raise weewx.UnsupportedFeature(msg)
        super().__init__(
            version=DRIVER_VERSION,
            name='Ecowitt local HTTP API driver',
            description='WeeWX driver for devices supporting the Ecowitt local HTTP API.',
            author="Gary Roderick",
            author_email="gjroderick<@>gmail.com",
            files=[('bin/user', ['bin/user/ecowitt_http.py'])],
            config=ecowitt_dict
        )