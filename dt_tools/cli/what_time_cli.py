"""
Command line time utility.

Displays current time.  Additional can display sunrise/sunset on any
specific date or location.

**Usage**:

    what-time [-h] [-sr] [-ss] [-d DATE] [-s] [-v] [where ...]

    positional arguments:
    where                 Location - address, zip code, landmark,...

    options:
    -h, --help            show this help message and exit
    -sr, --sunrise        Display sunrise time
    -ss, --sunset         Display sunset time
    -d DATE, --date DATE  Target date (implies -sr and -ss)
    -s, --speak           Vocalize the time.
    -v, --verbose         Verbose logging

Examples:

    # What time is it now
    > what-time
    The time is 06:42 PM EST.

    # What time is sunrise/sunset on a specific date
    > what-time -d 2/2/25
    on February 02 2025, sunrise is at 07:16 AM EST, sunset is at 06:05 PM EST.

    # What time is it in specific location
    > what-time Cairo
    Cairo in Egypt, the time is 01:39 AM EET.

    # When is sunrise/sunset in specific location on specific date   
    > what-time -d 2/2/25 London England
    London England in United Kingdom, on February 02 2025, sunrise is at 07:38 AM GMT, sunset is at 04:51 PM GMT.

Returns:
    str: Query results or error message on invalid/non-specific input.

"""

import argparse
import sys
from datetime import datetime
from typing import Union

from dateutil import parser as dt_parser
from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
from dt_tools.geoloc.geoloc import GeoLocation
from dt_tools.sound.helper import Sound
from dt_tools.geoloc.sun import Sun, SunTimeException


def get_gps_coordinates(location: str) -> Union[GeoLocation, None]:
    geo = GeoLocation()
    try:
        if location is None or len(location) == 0:
            found = geo.get_location_via_ip()

        elif location.isdecimal():
            found = geo.get_location_via_zip(location)

        else:
            found = geo.get_location_via_address_string(location)
    
    except Exception as ex:
        found = False
        LOGGER.debug(ex)    

    if found:
        LOGGER.debug(f'geo:\n{geo.to_string()}')
        if geo.city is not None:
            geo.display_location = f'{geo.city} {geo.state}'
        else:
            geo.display_location = f'{location}'
            if geo.country != 'United States':
                geo.display_location += f' in {geo.country}'
        return geo
    
    return None

def display_date_info(location: str, date_string: str, sunrise: bool, sunset: bool, speak: bool) -> int:
    LOGGER.debug(f'display_date_info({location}, {date_string}, {sunrise}, {sunset}, {speak})')
    geo = get_gps_coordinates(location)
    if geo is None:
        LOGGER.error(f'Unable to resolve location: {location}')
        return -1
    
    time_fmt = "%I:%M %p %Z"
    time_str: str = ''
    sun = Sun(geo.lat, geo.lon)
    if len(location) > 0:
        time_str += f'{geo.display_location}, '
            
    if date_string is None:
        date = datetime.now().date()
        local_time = sun.time_now_at()
        if len(time_str) == 0:
            time_str += f'The time is {datetime.strftime(local_time, time_fmt)}, '
        else:
            time_str += f'the time is {datetime.strftime(local_time, time_fmt)}, '
    else:
        date = dt_parser.parse(date_string)
        time_str += f'on {datetime.strftime(date,"%B %d %Y")}, '

    if sunrise:
        try:
            sr_time = sun.get_gps_sunrise(date)
            time_str += f'sunrise is at {datetime.strftime(sr_time, time_fmt)}, '
        except SunTimeException as ste:
            time_str += str(ste)
    
    if sunset:
        try:
            ss_time = sun.get_gps_sunset(date)
            time_str += f'sunset is at {datetime.strftime(ss_time, time_fmt)}'
        except SunTimeException as ste:
            time_str += str(ste)

    time_str = time_str.rstrip().rstrip(',') + '.'
    LOGGER.info(time_str)
    if speak:
        Sound().speak(time_str, speed=1.25, wait=False)

    return 0

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('-sr', '--sunrise', required=False, action='store_true', help='Display sunrise time')
    parser.add_argument('-ss', '--sunset',  required=False, action='store_true', help='Display sunset time')
    parser.add_argument('-d',  '--date',    required=False, type=str,  default=None ,help='Target date (implies -sr and -ss)')
    parser.add_argument('-s', '--speak',    required=False, action='store_true', help='Vocalize the time.')
    parser.add_argument('-v',  '--verbose', required=False, action='count', default=0, help='Verbose logging')
    parser.add_argument('where', nargs='*', type=str, default='', help='Location - address, zip code, landmark,...')

    args = parser.parse_args()
    if args.verbose == 0:
        log_level = 'INFO'
        log_format = lh.DEFAULT_CONSOLE_LOGFMT
    elif args.verbose == 1:
        log_level = 'DEBUG'
        log_format = lh.DEFAULT_DEBUG_LOGFMT
    else:
        log_level = 'TRACE'
        log_format = lh.DEFAULT_DEBUG_LOGFMT
    
    lh.configure_logger(log_level=log_level, log_format=log_format, brightness=False)

    LOGGER.debug(f'args: {args}')
    if args.date is not None:
        args.sunrise = True
        args.sunset = True

    where = None if args.where is None else ' '.join(args.where)

    rc = display_date_info(where, args.date, args.sunrise, args.sunset, args.speak)


    return rc

if __name__ == '__main__':
    sys.exit(main())


# what-time location|zip
# -sr --sunrise -ss --sunset
# --date  (implies -sr -ss)