"""
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

                 Installer for Ecowitt Local HTTP API Driver

Version: 0.1.0a1                                       Date: xx March 2025

Revision History
    xx March 2025      v0.1.0
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
    
[Accumulator]

    # Start Ecowitt local HTTP API driver extractors

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