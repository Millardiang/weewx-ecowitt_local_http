# Ecowitt Local HTTP API Driver

**Note:** General support issues for the Ecowitt Local HTTP API driver (aka the Ecowitt local HTTP driver) should be raised in the Google Groups [weewx-user forum](https://groups.google.com/g/weewx-user "Google Groups weewx-user forum"). The Ecowitt local HTTP driver [Issues Page](https://github.com/gjr80/weewx-ecowitt_local_http/issues "Ecowitt local HTTP driver Issues") should only be used for specific bugs in the Ecowitt local HTTP driver code. It is recommended that even if an Ecowitt local HTTP driver bug is suspected, users first post to the Google Groups [weewx-user forum](https://groups.google.com/g/weewx-user "Google Groups weewx-user forum").

## Description

The Ecowitt local HTTP driver is a WeeWX driver that supports devices compatible with the Ecowitt Local HTTP API.

The Ecowitt local HTTP driver utilises the Ecowitt Local HTTP API thus using a pull methodology for obtaining data from the device rather than the push methodology. This has the advantage of giving the user more control over when the data is obtained from the device.

The Ecowitt local HTTP driver can be operated as a traditional WeeWX driver where it is the source of loop data, or it can be operated as a WeeWX service where it is used to augment loop data produced by another driver.

## Pre-Requisites

The Ecowitt local HTTP driver requires:

- WeeWX v5.0.0 or greater
- Python v3.6 or later

**Note:** Whilst the Ecowitt local HTTP driver has been written to be compatible with Python v3.6 and later, the driver utilises a number of features introduced in WeeWX v5.0.0 and hence cannot be reliably run under WeeWX v4.x and Python v3. The driver extension installer will refuse to install the driver under WeeWX v4 or earlier. The driver may be installed manually under WeeWX v4.x and Python v3, and it may work; however, this configuration is not supported. The driver will not run under Python v2.

## Installation Instructions

### Installation as a WeeWX driver

1.  If the Ecowitt local HTTP driver is to be installed on a fresh WeeWX installation first [install WeeWX](http://weewx.com/docs/5.1/usersguide/installing/) and configure WeeWX to use the *simulator* driver.

2.  Install the latest version of the Ecowitt local HTTP driver using the [*weectl* utility](http://weewx.com/docs/5.1/utilities/weectl-extension/#install-an-extension).

    **Note:** The exact command syntax to invoke *weectl* on your system will depend on the installer used to install WeeWX. Refer to [Installation methods](http://weewx.com/docs/5.1/usersguide/installing/#installation-methods) in the WeeWX [User's Guide](http://weewx.com/docs/5.1/usersguide/introduction/).

    For WeeWX package installs:

        weectl extension install https://github.com/gjr80/weewx-ecowitt_local_http/releases/latest/download/ecowitt_http.zip

    For WeeWX *pip* installs the Python virtual environment must be activated before the extension is installed:

        source ~/weewx-venv/bin/activate
        weectl extension install https://github.com/gjr80/weewx-ecowitt_local_http/releases/latest/download/ecowitt_http.zip

    For WeeWX installs from *git* the Python virtual environment must be activated before the extension is installed:

        source ~/weewx-venv/bin/activate
        python3 ~/weewx/src/weectl.py extension install https://github.com/gjr80/weewx-ecowitt_local_http/releases/latest/download/ecowitt_http.zip

3.  Test the Ecowitt local HTTP driver by running the driver file directly using the *--test-driver* command line option.

    For WeeWX package installs use:

        PYTHONPATH=/usr/share/weewx python3 /etc/weewx/bin/user/ecowitt_http.py --test-driver --ip-address=device_ip_address

    where *device_ip_address* is the IP address of the gateway device being used.

    For WeeWX *pip* installs the Python virtual environment must be activated before the driver is invoked:

        source ~/weewx-venv/bin/activate
        python3 ~/weewx-data/bin/user/ecowitt_http.py --test-driver --ip-address=device_ip_address

    where *device_ip_address* is the IP address of the gateway device being used.

    For WeeWX installs from *git* the Python virtual environment must be activated before the driver is invoked using the path to the local WeeWX *git* clone:

        source ~/weewx-venv/bin/activate
        PYTHONPATH=~/weewx/src python3 ~/weewx-data/bin/user/ecowitt_http.py --test-driver --ip-address=device_ip_address

    where *device_ip_address* is the IP address of the gateway device being used.

    You should observe loop packets being emitted on a regular basis. Once finished press *ctrl-c* to exit.

    **Note:** You will only see loop packets and not archive records when running the driver directly. This is because you are seeing output not from WeeWX, but rather directly from the driver.

4.  Select and configure the driver.

    For WeeWX package installs use:

        weectl station reconfigure --driver=user.ecowitt_http

    For WeeWX *pip* installs the Python virtual environment must be activated before *weectl* is used to select and configure the driver:

        source ~/weewx-venv/bin/activate
        weectl station reconfigure --driver=user.ecowitt_http

    For WeeWX installs from *git* the Python virtual environment must be activated before *weectl.py* is used to select and configure the driver:

        source ~/weewx-venv/bin/activate
        python3 ~/weewx/src/weectl.py station reconfigure --driver=user.ecowitt_http

5.  You may choose to [run WeeWX directly](http://weewx.com/docs/5.1/usersguide/running/#running-directly) to observe the loop packets and archive records being generated by WeeWX. If WeeWX is already running stop WeeWX before running the driver directly.

6.  Once satisfied that the Ecowitt local HTTP driver is operating correctly you can restart the WeeWX daemon:

        sudo /etc/init.d/weewx restart

    or

        sudo service weewx restart

    or

        sudo systemctl restart weewx

7.  You may wish to refer to the [Ecowitt local HTTP driver wiki](https://github.com/gjr80/weewx-ecowitt_local_http/wiki) for further guidance on customising the operation of the Ecowitt local HTTP driver and integrating device data into WeeWX generated reports.

### Installation as a WeeWX service

1. [Install WeeWX](http://weewx.com/docs/5.1/usersguide/installing/) and configure it to use either the *simulator* driver or another driver of your choice.

2. Install the Ecowitt local HTTP driver extension using the *weectl* utility as per *Installation as a WeeWX driver* step&nbsp;2 above.

3. Edit *weewx.conf* and under the *[Engine] [[Services]]* stanza add an entry *user.ecowitt_http.EcowittHttpService* to the *data_services* option. It should look something like:

       [Engine]

           [[Services]]
               ....
               data_services = user.ecowitt_http.EcowittHttpService

4. Test the Ecowitt local HTTP service by running the driver file directly using the *--test-service* command line option.

   For WeeWX package installs use:

        PYTHONPATH=/usr/share/weewx:/etc/weewx/bin python3 /etc/weewx/bin/user/ecowitt_http.py --test-service --ip-address=device_ip_address

   where *device_ip_address* is the IP address of the device being used.

   For WeeWX *pip* installs the Python virtual environment must be activated before the driver is invoked:

        source ~/weewx-venv/bin/activate
        PYTHONPATH=~/weewx-data/bin python3 ~/weewx-data/bin/user/ecowitt_http.py --test-service --ip-address=device_ip_address

   where *device_ip_address* is the IP address of the device being used.

   For WeeWX installs from *git* the Python virtual environment must be activated before the driver is invoked using the path to the local WeeWX *git* clone:

        source ~/weewx-venv/bin/activate
        PYTHONPATH=~/weewx/src:~/weewx-data/bin python3 ~/weewx-data/bin/user/ecowitt_http.py --test-service --ip-address=device_ip_address

   where *device_ip_address* is the IP address of the gateway device being used.

   You should observe loop packets being emitted on a regular basis.

   **Note:** When the Ecowitt local HTTP driver is run directly with the *--test-service* command line option a series of simulated loop packets are emitted every 10 seconds to simulate a running WeeWX instance. The gateway device is polled and the gateway device data added to the loop packets when available. As the default gateway device poll interval is 20 seconds not all loop packets will be augmented with gateway device data.

   **Note:** You will only see loop packets and not archive records when running the service directly. This is because you are seeing the direct output of the simulated loop packets and the Ecowitt local HTTP service and not WeeWX.

   Once finished press *ctrl-c* to exit.

5.  You may choose to [run WeeWX directly](http://weewx.com/docs/5.1/usersguide/running/#running-directly) to observe the loop packets and archive records being generated by WeeWX. Note that depending on the frequency of the loop packets emitted by the in-use driver and the polling interval of the Ecowitt local HTTP service, not all loop packets may include device data; however, provided the device polling interval is less than the frequency of the loop packets emitted by the in-use driver each archive record should contain device data.

6.  Once satisfied that the Ecowitt local HTTP service is operating correctly you can restart the WeeWX daemon:

        sudo /etc/init.d/weewx restart

    or

        sudo service weewx restart

    or

        sudo systemctl restart weewx

7.  You may wish to refer to the [Ecowitt local HTTP driver wiki](https://github.com/gjr80/weewx-ecowitt_local_http/wiki) for further guidance on customising the operation of the Ecowitt local HTTP driver and integrating device data into WeeWX generated reports.


## Upgrade Instructions

**Note:** Before upgrading the Ecowitt local HTTP driver, check the [Instructions for specific versions](https://github.com/gjr80/weewx-ecowitt_local_http/wiki/Upgrade-Guide#instructions-for-specific-versions) section of the Ecowitt local HTTP driver [Upgrade Guide](https://github.com/gjr80/weewx-ecowitt_local_http/wiki/Upgrade-Guide) to see if any specific actions are required as part of the upgrade.

To upgrade from an earlier version of the Ecowitt local HTTP driver (installed as either a WeeWX driver or a WeeWX service) simply install the Ecowitt local HTTP driver version you wish to upgrade to as per the [Installation Instructions](#installation-instructions) above.


## Support

General support issues for the Ecowitt local HTTP driver should be raised in the Google Groups [weewx-user forum](https://groups.google.com/g/weewx-user "Google Groups weewx-user forum"). The Ecowitt local HTTP driver [Issues Page](https://github.com/gjr80/weewx-ecowitt_local_http/issues "Ecowitt local HTTP driver Issues") should only be used for specific bugs in the Ecowitt local HTTP driver code. It is recommended that even if an Ecowitt local HTTP driver bug is suspected users first post to the Google Groups [weewx-user forum](https://groups.google.com/g/weewx-user "Google Groups weewx-user forum").

## Licensing

The Ecowitt local HTTP driver/GW1000 driver is licensed under the [GNU Public License v3](https://github.com/gjr80/weewx-ecowitt_local_http/blob/master/LICENSE "Ecowitt Gateway Driver License").