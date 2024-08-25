"""
Retrieve IP Information and manage IP Helper data cache.
"""
import argparse
import json
import sys

from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
import dt_tools.net.net_helper as nh
from dt_tools.console.console_helper import ConsoleInputHelper as InputHelper
from dt_tools.net.ip_info_helper import IpHelper
from dt_tools.os.project_helper import ProjectHelper


def _display_loop_prelude():
    LOGGER.info('')
    LOGGER.info('This utility displays IP infomation.  It also manages an IP information cache')
    LOGGER.info('that is used in other dt- utilties.')
    LOGGER.info('')
    LOGGER.info('Input          Description')
    LOGGER.info('-------------  -----------------------------------------------------------------------')
    LOGGER.info('9.9.9.9 [b]    Enter IP address, b will bypass cache and do an internet lookup.')
    LOGGER.info('c [9.9.9.9]    Clear cache.  If IP address supplied, only that entry will be deleted.')
    LOGGER.info('f <str>        Search for str in cache and list entries.')
    LOGGER.info('h              This help screen.')
    LOGGER.info('l [9.9.9.9]    List cache.  If IP address supplied, only that entry will be listed.')
    LOGGER.info('q              Quit.')

def display_ip_info(ip_info: IpHelper, ip: str, show_all: bool = True, bypass_cache: bool = False):
    info_json = ip_info.get_ip_info(ip, bypass_cache=bypass_cache)
    if info_json.get('error'):
        display_error(info_json)
    else:
        ip_info.list_cache(ip) 

def display_error(error_dict: dict):
    print(f'- {json.dumps(error_dict, indent=2)}')

def command_loop(ip_info: IpHelper):
    _display_loop_prelude()
    prompt = "Enter IP [b]ypass cache, (c)lear cache [ip], (h)elp, (l)ist [ip], (f)ind str, (q)uit > "
    token = InputHelper().get_input_with_timeout(prompt).split()
    cmd = token[0]
    while cmd not in ['Q', 'q']:
        
        if cmd in ['C', 'c']:
            if len(token) > 1:
                cnt = ip_info.clear_cache(token[1])
            else:
                cnt = -1
                resp = InputHelper.get_input_with_timeout(' Are you sure? (y/n)? ', InputHelper.YES_NO_RESPONSE)
                if resp.lower() == 'y':
                    cnt = ip_info.clear_cache()
            if cnt >= 0:
                LOGGER.info(f'  {cnt} entries removed from cache.')
        
        elif cmd in ['F', 'f']:
            if len(token) == 1:
                LOGGER.warning('- Missing search criteria')
            else:
                ip_info.find_in_cache(token[1])
        
        elif cmd in ['H', 'h']:
            _display_loop_prelude()

        elif cmd in ['L', 'l']:
            if len(token) > 1:
                ip_info.list_cache(token[1])
            else:
                ip_info.list_cache()
        
        else:
            # Assume IP address lookup
            bypass_cache = False
            ip_addr = token[0]
            if not nh.is_valid_ipaddress(ip_addr):
                LOGGER.warning(f'  {ip_addr} does not appear to be valid.')
            else:
                if len(token) == 2 and token[1] in ['B', 'b']:
                    LOGGER.warning('  Bypass requested.')
                    bypass_cache = True
                display_ip_info(ip_info, token[0], show_all=True, bypass_cache=bypass_cache)
        
        token = ''
        token = InputHelper().get_input_with_timeout(f"\n{prompt}").split()
        cmd = token[0]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', default=False, help='Clear IP or IP cache.')
    parser.add_argument('-l', '--list',  action='store_true', default=False, help='List IP or all IPs in cache')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Verbose mode')
    parser.add_argument('ip', nargs='?')
    args = parser.parse_args()

    if args.verbose == 0:
        log_lvl = "INFO"
    elif args.verbose == 1:
        log_lvl = "DEBUG"
    else:
        log_lvl = "TRACE"
    lh.configure_logger(log_level=log_lvl, log_format=lh.DEFAULT_CONSOLE_LOGFMT)

    # LOGGER.info(f'{parser.prog}  (v{__version__})')
    version = ProjectHelper.determine_version('dt_cli_tools')
    LOGGER.info('='*80)
    LOGGER.info(f'{parser.prog} v{version}')
    LOGGER.info('='*80)
    LOGGER.info('')
    ip_helper = IpHelper()
    LOGGER.level(log_lvl)
    if args.clear or args.list:
        if args.clear:
            LOGGER.success(f'  {ip_helper.clear_cache(args.ip)} entries removed.')
        elif args.list:
            ip_helper.list_cache(args.ip)
        else:
            LOGGER.critcal('  Unknown command')
    else:
        LOGGER.info(f'Cache loaded with {len(ip_helper._cache)} entries.')
        LOGGER.debug('')
        if args.ip:
            display_ip_info(ip_helper, args.ip, show_all=True)
        else:
            command_loop(ip_helper)

if __name__ == "__main__":
    main()
    sys.exit()
