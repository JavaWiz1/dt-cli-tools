"""
Retrieve IP Information and manage IP Helper data cache.
"""
import argparse
import sys

from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
from dt_tools.console.console_helper import ConsoleInputHelper as InputHelper
from dt_tools.net.ip_info_helper import IpHelper
import json

def display_ip_info(ip_info: IpHelper, ip: str, show_all: bool = True, bypass_cache: bool = False):
    info_json = ip_info.get_ip_info(ip, bypass_cache=bypass_cache)
    if info_json.get('error'):
        display_error(info_json)
    else:
        ip_info._print_entry(info_json, show_all=show_all)    

def display_error(error_dict: dict):
    print(f'- {json.dumps(error_dict, indent=2)}')

def command_loop(ip_info: IpHelper):
    prompt = "Enter IP [b]ypass cache, (l)ist, (c)lear cache, (f)ind, (q)uit > "
    token = InputHelper().get_input_with_timeout(prompt).split()
    cmd = token[0]
    while cmd not in ['Q', 'q']:
        if cmd in ['C', 'c']:
            if len(token) > 1:
                ip_info.clear_cache(token[1])
            else:
                ip_info.clear_cache()
        elif cmd in ['L', 'l']:
            if len(token) > 1:
                ip_info.list_cache(token[1])
            else:
                ip_info.list_cache()
        elif cmd in ['F', 'f']:
            if len(token) == 1:
                LOGGER.warning('- Missing search criteria')
            else:
                ip_info.find_in_cache(token[1])
        else:
            bypass_cache = False
            if len(token) == 2 and token[1] in ['B', 'B']:
                LOGGER.debug('Bypass cache lookup requested.')
                bypass_cache = True
            display_ip_info(ip_info, token[0], show_all=True, bypass_cache=bypass_cache)
        token = ''
        token = InputHelper().get_input_with_timeout(f"\n{prompt}").split()
        cmd = token[0]

def main():
    parser = argparse.ArgumentParser(prog='ip-helper-cli')
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
    LOGGER.info('='*80)
    LOGGER.info(f'{parser.prog}: Get IP Info and manage IPHelper cache')
    LOGGER.info('='*80)
    LOGGER.info('')
    ip_helper = IpHelper()
    LOGGER.level(log_lvl)
    if args.clear or args.list:
        if args.clear:
            ip_helper.clear_cache(args.ip)
        elif args.list:
            ip_helper.list_cache(args.ip)
        else:
            LOGGER.critcal('Unknown command')
    else:
        LOGGER.debug(f'Cache loaded with {len(ip_helper._cache)} entries.')
        LOGGER.debug('')
        if args.ip:
            display_ip_info(ip_helper, args.ip, show_all=False)
        else:
            command_loop(ip_helper)

if __name__ == "__main__":
    main()
    sys.exit()
