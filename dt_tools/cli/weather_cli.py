"""
Weather from the command-line!

This utility will provide weather information (current, forecast or alerts) for a 
on provided location.  It can also vocalize the information by adding the -speak option.

Simply provide:
  
    - **Location** : address (or landmark), ip or gps coordinates.
                     (ip is your internet address, mostly likely your ISP endpoint).
    - **Type**     : current (now), today/tomorrow/day (forecast) or alerts.
    - **options**  : any additional options.

**Features**:

    - Specify target locations by IP, address/landmark or GPS coordinates (latitude, longitude).
    - Specify what type of information to be returned (current conditions, weather forecast or current alerts).
    - Speak the results thru your devices speakers.


**Usage**::

    weather_cli LOCATION TYPE [-h] [-summary] [-speak] 

    Where LOCATION and TYPE are required and defined below.

    **Location**:
        Weather location identifier:
        -ip                   Location based on external (internet) IP.
        -address <house street,city,state,zip> 
                              Location or Address string.
        -gps lat,lon          GPS coordinates. Format: lat,lon (i.e. 40.6892,-74.0445)

    **Type**:
        Weather/Forecast type:
        -current              Current weather conditions.
        -today {d,n}          Forecast for today (or tonight).
        -tomorrow {d,n}       Forecast for tomorrow (day or tonight).
        -day {d2,d3,d4,d5,n2,n3,n4,n5} 
                              Forecast (day or night) for n days into future.
        -alerts               Weather alerts.

    **Options**:
        -h, --help            show this help message and exit
        -summary              Just summarize weather results, else provide details
        -speak                Speak the result

**Returns**:
    
    bool: result - True if successful, False if unable to identify location

    
**Examples**::

    # Current weather at your location
    > weather-cli -ip -current
    
    # Current weather at Statue of Liberty
    > weather-cli -address "Statue of Liberty" -current
    > weather-cli -gps 40.6892,-74.0445 -current

    # Current location tonights Forecast
    > weather-cli -ip -today n

    # Speak current location tomorrows daytime forecast
    > weather-cli -ip -tommorrow d -speak

    # Speak current location 3 days from now night time forecast
    > weather-cli -ip -day 3n -speak

    # Weather alerts for current location
    > weather-cli -ip -alerts
"""
import argparse
import sys
import textwrap
from dataclasses import asdict
from datetime import datetime as dt
from typing import Tuple

from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
from dt_tools.console.console_helper import ConsoleHelper, TextStyle
from dt_tools.geoloc.geoloc import GeoLocation
from dt_tools.os.project_helper import ProjectHelper
from dt_tools.sound.helper import Accent, Sound
from dt_tools.weather.common import ForecastType
from dt_tools.weather.common import WeatherSymbols as ws
from dt_tools.weather.weather import CurrentConditions
from dt_tools.weather.weather_forecast_alert import (
    Forecast,
    ForecastDay,
    LocationAlerts,
)


# ==  Helper Routines  ===================================================================================
def _build_command_line_parser() -> argparse.ArgumentParser:
    epilog = "Weather CLI Utility\n"
    epilog += "----------------------------------------------------------------------------------------\n"
    epilog += "This utility will provide weather information (current, forecast or alerts) based\n"
    epilog += "on provided location.  It can also vocalize the information by adding the -speak option.\n\n"
    epilog += "Simply provide-\n"
    epilog += "  Location : address (or landmark), ip or gps coordinates\n"
    epilog += "             (ip is your internet address, mostly likely your ISP endpoint)\n"
    epilog += "  Type     : current (now), today/tomorrow/day (forecast) or alerts\n\n"
    epilog += "Examples-\n"
    epilog += "  > weather_cli -ip -current\n"
    epilog += "  > weather_cli -address 'Statue of Liberty' -tomorrow d\n"
    epilog += "----------------------------------------------------------------------------------------\n"
    # description = textwrap.dedent(description)
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog)
    loc_group = parser.add_argument_group(title='Location', description='Weather location identifier')
    ex_loc_group = loc_group.add_mutually_exclusive_group(required=True)
    ex_loc_group.add_argument('-ip', action='store_true', default=False, 
                              help='Location based on external (internet) IP.')
    ex_loc_group.add_argument('-address', type=str, metavar='house street,city,state,zip', 
                              help='Location or Address string.')
    ex_loc_group.add_argument('-gps', type=str, metavar='lat,lon', 
                              help='GPS coordinates.  Format: lat,lon (i.e. 40.6892,-74.0445)')
    
    cmd_group = parser.add_argument_group(title='Type', description='Weather/Forecast type')
    ex_cmd_group = cmd_group.add_mutually_exclusive_group(required=True)
    ex_cmd_group.add_argument('-current', action='store_true', default=False, 
                              help='Current weather conditions.')
    ex_cmd_group.add_argument('-today',    choices=['d','n'], 
                              help='Forecast for today (or tonight).')
    ex_cmd_group.add_argument('-tomorrow', choices=['d','n'], 
                              help='Forecast for tomorrow (day or tonight).')
    ex_cmd_group.add_argument('-day', choices=['d2','d3','d4','d5','n2','n3','n4','n5'], 
                              help='Forecast (day or night) for n days into future.')
    ex_cmd_group.add_argument('-alerts', action='store_true',default=False,  
                              help='Weather alerts.')
    
    parser.add_argument('-summary', action='store_true', 
                        help='Just summarize weather results, else provide details')
    parser.add_argument('-speak', action='store_true', 
                        help='Speak the result')
    parser.add_argument('-a', '--accent', type=str, default='us',
                        help='Speak accent (speak -l to list all accent codes)')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Verbose logging')
    return parser
    

def _speak(text: str, speed: float = 1.25, accent_cd: str = 'us', wait: bool = True) -> bool:
    text = text.replace('\n', ' ').replace('. ', '.\n')
    accent = Accent(accent_cd)
    LOGGER.debug(f'Speak Weather ({accent}):')
    for line in text.splitlines():
        LOGGER.debug(f'  {line.strip()}')

    return Sound().speak(text, speed=speed, accent=accent, wait=wait)

def _get_gps_coordinates(args: argparse.Namespace) -> Tuple[float, float, str]:
    lat: float = 0.0
    lon: float = 0.0
    place: str = ''

    geo = GeoLocation()
    if args.ip:
        LOGGER.debug('- get geoloc based on ip.')
        if geo.get_location_via_ip():
            lat = geo.lat
            lon = geo.lon
            place = geo.display_name
    elif args.address:
        LOGGER.debug('- get geoloc based on address.')
        if geo.get_location_via_address_string(args.address):
            lat = geo.lat
            lon = geo.lon
            place = args.address
    elif args.gps:
        LOGGER.debug('- get geoloc based on gps coordinates')
        x, y = args.gps.split(',')
        try:
            lat = float(x)
            lon = float(y)
        except Exception:
            lat = 0.0
            lon = 0.0

    LOGGER.debug(f'GeoLoc:\n{geo.to_string()}')
    return (lat, lon, place)

def _valid_gps_coordinates(lat: float, lon: float) -> bool:
    return lat != 0.0 and lon != 0.0

# ==  Weather Current Conditions  ========================================================================
def _get_current_weather(args: argparse.Namespace) -> bool:
    LOGGER.debug('_get_current_weather(): retrieve gps coordinates')
    lat, lon, place = _get_gps_coordinates(args)
    if not _valid_gps_coordinates(lat, lon):
        LOGGER.error('Unable to determine location.')
        return False
    
    weather = CurrentConditions()    
    weather.set_location_via_lat_lon(lat, lon)
    LOGGER.success(f'Current weather conditions for {dt.strftime(dt.now(),"%A - %H:%M %p")}')
    LOGGER.trace(f'weather:\n{asdict(weather)}')
    location = f"{weather.loc_name} {weather.loc_region}" if place is None else place
    LOGGER.info(f'  {location}. [{weather.lat_long}]')
    LOGGER.info('')
    for line in weather.to_string().splitlines():
        LOGGER.info(f'  {line}')

    if args.speak:
        return _speak_current_conditions(weather, args)
    
    return True

def _speak_current_conditions(weather: CurrentConditions, args: argparse.Namespace) -> bool:
    from datetime import datetime as dt
    time_now = dt.now().strftime("%I:%M%p")

    content = f"Current conditions in {weather.loc_name} at {time_now}.\n"
    if int(weather.temp) == int(weather.feels_like):
        content += f"  {weather.condition}.  Temperature {weather.temp:.0f}{ws.degree.value}.\n"
    else:
        content += f"  {weather.condition}.  Temperature {weather.temp:.0f}{ws.degree.value}, feels like {weather.feels_like:.0f}{ws.degree.value}.\n"
    if not args.summary:
        content += f'  {weather.humidity_pct:.0f}% humidity, air quality is {weather.aqi_text}.\n'
        if weather.precipitation > 0.0:
            content += f'{weather.precipitation} inches of precipitation.\n'
        content += f'  Visibility {weather.visibility_mi} miles.\n'
        content += f'  Wind {ws.translate_compass_point(weather.wind_direction)} {weather.wind_speed_mph:.0f} mph, gusts up to {weather.wind_gust_mph:.0f} mph.\n'
        content += f'  Sunrise at {weather.sunrise.strftime("%I:%M%p")}, Sunset at {weather.sunset.strftime("%I:%M%p")}'
    return _speak(content, accent_cd=args.accent, wait=False)


# ==  Weather Forecast  ===================================================================================
def _get_weather_forecast(args: argparse.Namespace, forecast_code: str) -> bool:
    lat, lon, place = _get_gps_coordinates(args)
    if not _valid_gps_coordinates(lat, lon):
        LOGGER.error('Unable to determine location.')
        return False
    
    weather = Forecast(lat, lon)
    time_of_day = ForecastType.DAY if forecast_code[0] == 'd' else ForecastType.NIGHT
    day_offset = int(forecast_code[1])
    LOGGER.debug(f'Day offset: {day_offset} time of day: {time_of_day}')
    forecast = weather.forecast_for_future_day(days_in_future=day_offset, time_of_day=time_of_day)
    LOGGER.debug(forecast.to_string())
    if args.summary:
        LOGGER.success(f'Forecast summary for {forecast.name}')
        LOGGER.info(f'  {forecast.city}, {forecast.state_full} - {forecast.timeframe}')
        LOGGER.info('')
        LOGGER.info(f'  {forecast.short_forecast}')
    else:
        LOGGER.success(f'Detailed summary for {forecast.name}')
        LOGGER.info(f'  {forecast.city}, {forecast.state_full} - {forecast.timeframe}')
        LOGGER.info('')
        lines = textwrap.wrap(forecast.detailed_forecast, width=90, 
                            initial_indent='  ',
                            subsequent_indent=' '*2)
        text = '\n'.join(lines) + '\n'           
        LOGGER.info(f'{text}')
        if args.speak:
            return _speak_forecast(forecast=forecast, args=args)

    return True

def _speak_forecast(forecast: ForecastDay, args: argparse.Namespace) -> bool:
    content = f"Forecast for {forecast.city} {forecast.state_full} {forecast.timeframe}.\n"
    if args.summary:
        content += forecast.short_forecast
    else:
        content += forecast.detailed_forecast
    return _speak(content, accent_cd=args.accent)

# ==  Weather Alerts  =====================================================================================
def _get_weather_alerts(args: argparse.Namespace) -> bool:
    lat, lon, place = _get_gps_coordinates(args)
    if not _valid_gps_coordinates(lat, lon):
        LOGGER.error('Unable to determine location.')
        return False
    
    LOGGER.info('')
    alerts = LocationAlerts(lat, lon)
    # location = alerts.city_state if alerts.city_state is not None else f'{alerts.latitude:.4f}/{alerts.longitude:.4f}'
    location = alerts.city_state if alerts.city_state is not None else f'{place}'
    if alerts.alert_count == 0:
        LOGGER.error(f'There are 0 alerts for {location} [{alerts.latitude:.4f}/{alerts.longitude:.4f}]')
        if args.speak:
            _speak(f'There are 0 alerts for {location}', accent_cd=args.accent)
        return False
    
    LOGGER.success(f'Weather alerts for {location} [{alerts.latitude:.4f}/{alerts.longitude:.4f}]')
    if args.speak:
        _speak(f'{alerts.alert_count} weather alerts for {alerts.city} {alerts.state_full}.',
               accent_cd=args.accent, wait=False)

    for idx in range(alerts.alert_count):
        LOGGER.warning(f'{idx+1:2d} {alerts.headline(idx)}')
        LOGGER.info(f'   Type      : {alerts.message_type(idx)}')
        LOGGER.info(f'   Effective : {alerts.effective(idx)}')
        LOGGER.info(f'   Expires   : {alerts.expires(idx)}')
        LOGGER.info(f'   Certainty : {alerts.certainty(idx)}')
        # LOGGER.info(f'  Event     : {alerts.event(idx)}')
        LOGGER.info(f'   Status    : {alerts.status(idx)}')
        LOGGER.info('')
        LOGGER.success( '   Description:')
        content = ''
        for line in alerts.description(idx).splitlines():
            LOGGER.info(f'     {line}')
            content += f"{line}\n"
        if args.speak and not args.summary:
            content = content.replace('* ', '')
            text = f'Alert {idx+1}.  {alerts.headline(idx)}. {content}'
            _speak(text, accent_cd=args.accent)

        instructions = alerts.instruction(idx)
        if instructions != 'Unknown':
            LOGGER.info('')
            LOGGER.success('   Instructions:')
            for line in instructions.splitlines():
                LOGGER.info(f'     {line}')
            if args.speak and not args.summary:
                _speak(instructions, accent_cd=args.accent)

    return True


# ==================================================================================================================
def main() -> bool:
    parser = _build_command_line_parser()    
    args = parser.parse_args()
    if args.verbose == 0:
        l_level = "INFO"    
        l_format = lh.DEFAULT_CONSOLE_LOGFMT
        enable_loggers = None
    elif args.verbose == 1:
        l_level = "DEBUG"
        l_format = lh.DEFAULT_DEBUG_LOGFMT2
        enable_loggers = ['dt_tools']
    else:
        l_level = "TRACE"
        l_format = lh.DEFAULT_DEBUG_LOGFMT
        enable_loggers = ['dt_tools']

    lh.configure_logger(log_level=l_level, log_format=l_format, brightness=False, 
                        enable_loggers=enable_loggers, disable_loggers=['logging'])

    version = f'{ConsoleHelper.cwrap(ProjectHelper.determine_version("dt-cli-tools"), style=TextStyle.ITALIC)}'
    ConsoleHelper.print_line_separator(length=80)
    ConsoleHelper.print_line_separator(f'{parser.prog}  (v{version})', 80)
    success = False
    LOGGER.debug(f'args: {args}')    
    try:
        Accent(args.accent)
    except ValueError as ve:
        LOGGER.error(f'{repr(ve)}, defaulting to "us".')
        args.accent = 'us'
    if args.current:
        # Current Forecast
        success = _get_current_weather(args)

    elif args.today or args.tomorrow or args.day:
        # Forecast weather
        if args.today:
            code = f'{args.today}0'
        elif args.tomorrow:
            code = f'{args.tomorrow}1'
        else:
            code = args.day
        success = _get_weather_forecast(args, code)

    elif args.alerts:
        # Weather Alerts
        success = _get_weather_alerts(args)

    else:
        raise RuntimeError('Unknown cmd_group value. Logic error.')
    
    return success

if __name__ == '__main__':
    sys.exit(main())
