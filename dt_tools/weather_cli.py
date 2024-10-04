"""
Weather from the command-line!

Returns:
    _type_: _description_
"""
import argparse
import sys
import textwrap
from typing import Tuple

from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
from dt_tools.misc.geoloc import GeoLocation
from dt_tools.misc.weather.weather import CurrentConditions
from dt_tools.misc.weather.weather_forecast_alert import Forecast, ForecastType, LocationAlerts


def get_gps_coordinates(args: argparse.Namespace) -> Tuple[float, float]:
    lat: float = 0.0
    lon: float = 0.0
    
    geo = GeoLocation()
    if args.ip:
        if geo.get_location_via_ip():
            lat = geo.lat
            lon = geo.lon
    elif args.address:
        if geo.get_location_via_address_string(args.address):
            lat = geo.lat
            lon = geo.lon 
    elif args.gps:
        x, y = args.gps.split(',')
        try:
            lat = float(x)
            lon = float(y)
        except Exception:
            lat = 0.0
            lon = 0.0

    LOGGER.debug(f'Geo:\n{geo.to_string()}')
    return (lat, lon)

def valid_gps_coordinates(lat: float, lon: float) -> bool:
    return lat != 0.0 and lon != 0.0

def get_current_weather(args: argparse.Namespace) -> bool:
    lat, lon = get_gps_coordinates(args)
    if not valid_gps_coordinates(lat, lon):
        LOGGER.error('Unable to determine location.')
        return False
    
    weather = CurrentConditions()    
    weather.set_location_via_lat_lon(lat, lon)
    LOGGER.info(weather.to_string())
    return True

def get_weather_forecast(args: argparse.Namespace, forecast_code: str) -> bool:
    lat, lon = get_gps_coordinates(args)
    if not valid_gps_coordinates(lat, lon):
        LOGGER.error('Unable to determine location.')
        return False
    
    weather = Forecast(lat, lon)
    time_of_day = ForecastType.DAY if forecast_code[0] == 'd' else ForecastType.NIGHT
    day_offset = int(forecast_code[1])
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

    return True

def get_weather_alerts(args: argparse.Namespace) -> bool:
    lat, lon = get_gps_coordinates(args)
    if not valid_gps_coordinates(lat, lon):
        LOGGER.error('Unable to determine location.')
        return False
    
    LOGGER.info('')
    alerts = LocationAlerts(lat, lon)
    location = alerts.city_state if alerts.city_state is not None else f'{alerts.latitude:.4f}/{alerts.longitude:.4f}'
    if alerts.alert_count == 0:
        LOGGER.error(f'There are 0 alerts for {location}')
        return False
    
    LOGGER.success(f'Weather alerts for {location}')
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
        for line in alerts.description(idx).splitlines():
            LOGGER.info(f'     {line}')
        instructions = alerts.instruction(idx)
        if instructions != 'Unknown':
            LOGGER.info('')
            LOGGER.success('   Instructions:')
            for line in alerts.instruction(idx).splitlines():
                LOGGER.info(f'     {line}')

    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    loc_group = parser.add_argument_group(title='Location', description='Weather location identifier')
    ex_loc_group = loc_group.add_mutually_exclusive_group(required=True)
    ex_loc_group.add_argument('-ip', action='store_true', default=False, help='Location based on external (internet) IP.')
    ex_loc_group.add_argument('-address', type=str, metavar='house street,city,state,zip', help='Location or Address string.')
    ex_loc_group.add_argument('-gps', type=str, metavar='lat,lon', help='GPS coordinates.  Format: lat,lon (i.e. 123.0,-234.2)')
    cmd_group = parser.add_argument_group(title='Type', description='Weather/Forecast type')
    ex_cmd_group = cmd_group.add_mutually_exclusive_group(required=True)
    ex_cmd_group.add_argument('-current', action='store_true', default=False, help='Current weather conditions.')
    ex_cmd_group.add_argument('-today',    choices=['d','n'], help='Forecast for today (or tonight).')
    ex_cmd_group.add_argument('-tomorrow', choices=['d','n'], help='Forecast for tomorrow (day or tonight).')
    ex_cmd_group.add_argument('-day', choices=['d2','d3','d4','d5','n2','n3','n4','n5'], help='Forecast (day or night) for n days into future.')
    ex_cmd_group.add_argument('-alerts', action='store_true',default=False,  help='Weather alerts.')
    parser.add_argument('-summary', action='store_true', help='Just summarize weather results, else provide details')
    parser.add_argument('-speak', action='store_true', help='Speak the result')
    args = parser.parse_args()
    LOGGER.debug(args)
    
    if args.current:
        rc = get_current_weather(args)

    elif args.today or args.tomorrow or args.day:
        if args.today:
            code = f'{args.today}0'
        elif args.tomorrow:
            code = f'{args.tomorrow}1'
        else:
            code = args.day
        rc = get_weather_forecast(args, code)

    elif args.alerts:
        rc = get_weather_alerts(args)

    else:
        raise RuntimeError('Unknown cmd_group value. Logic error.')
    
    return rc

if __name__ == '__main__':
    lh.configure_logger(log_level='INFO', brightness=False)
    sys.exit(main())
