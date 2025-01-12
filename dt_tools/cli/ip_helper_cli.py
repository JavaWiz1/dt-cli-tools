"""
Retrieve IP information on Local and Internet IP addresses.  

This utility interfaces with the free **ipinfo.io** site.  The ipinfo.io site
requires a user token which is free.

  - See 'setting up user token' (https://htmlpreview.github.io/?https://github.com/JavaWiz1/dt-net/blob/develop/docs/html/dt_tools.net.ip_info_helper.html) in docs for information on aquiring and setting up token.

**Features**:

    - IP Cache for to increase perfomance and and limit calls to ipinfo.io
    - Command line interface, or console prompt menu.
    - Commands to manage cache (list, clean, search,...)
    - Cached IP entry will auto-refresh if it is more than 48 hours old.

**Usage**:

    ip-helper [-h] [-c] [-l] [-v] [ip [b]]

    Parameters:

      - -h Help
      - -c [ip]: Clear ip from cache, or clear whole cache if IP not specified.
      - -l [ip]: List IP info from cache, or all cache entries
      - -v Verbose output
      - optional ip address to lookup (optional 'b' parm will bypass cache and re-lookup at ipinfo.io)
      
        - If ip is supplied, it will be looked up and info will be displayed.
        - If ip is NOT supplied, a prompt menu will be displayed for user input. 

"""
import argparse
import json
import sys

from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
import dt_tools.net.net_helper as nh
from dt_tools.console.console_helper import ConsoleHelper as console
from dt_tools.console.console_helper import ColorFG, TextStyle
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
    LOGGER.info('l [9.9.9.9]    List IP cache.  If IP address supplied, only that entry will be listed.')
    LOGGER.info('lm             List MAC cache (manually maintained)')
    LOGGER.info('q              Quit.')
    LOGGER.info('')

def _display_ip_info(ip_info: IpHelper, ip: str, show_all: bool = True, bypass_cache: bool = False):
    if nh.ping(ip):
        info_json = ip_info.get_ip_info(ip, bypass_cache=bypass_cache)
        if info_json.get('error'):
            _display_error(info_json)
        else:
            ip_info.list_cache(ip) 
    else:
        print(f'- {console.cwrap(ip, fg=ColorFG.RED,style=[TextStyle.BOLD, TextStyle.ITALIC])} is not pingable.  Valid host?')

def _display_error(error_dict: dict):
    print(f'- {json.dumps(error_dict, indent=2)}')

def _command_loop(ip_info: IpHelper):
    _display_loop_prelude()
    c_IP = f"Enter {console.cwrap('IP', ColorFG.WHITE2, style=TextStyle.BOLD)} [b]ypass cache" 
    c_CLEAR = f"{console.cwrap('(c)', ColorFG.WHITE2, style=TextStyle.BOLD)}lear cache [ip]" 
    c_HELP = f"{console.cwrap('(h)', ColorFG.WHITE2, style=TextStyle.BOLD)}elp"
    c_LIST = f"{console.cwrap('(l)', ColorFG.WHITE2, style=TextStyle.BOLD)}ist [ip]"
    c_LIST_MAC = f"{console.cwrap('(lm)', ColorFG.WHITE2, style=TextStyle.BOLD)}ist mac"
    c_FIND = f"{console.cwrap('(f)', ColorFG.WHITE2, style=TextStyle.BOLD)}ind <str>"
    c_QUIT = f"{console.cwrap('(q)', ColorFG.WHITE2, style=TextStyle.BOLD)}uit"
    prompt = f"{c_IP}, {c_CLEAR}, {c_HELP}, {c_LIST}, {c_LIST_MAC}, {c_FIND}, {c_QUIT} > "
    token = ''
    while len(token) == 0:
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
        
        elif cmd in ['LM', 'lm']:
                ip_info.list_mac_cache()
                
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
                _display_ip_info(ip_info, token[0], show_all=True, bypass_cache=bypass_cache)
        
        token = ''
        while len(token) == 0:
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
    lh.configure_logger(log_level=log_lvl, log_format=lh.DEFAULT_CONSOLE_LOGFMT, brightness=False)

    version = f'v{console.cwrap(ProjectHelper.determine_version("dt-cli-tools"), style=TextStyle.ITALIC)}'
    console.print_line_separator(length=80)
    console.print_line_separator(f'{parser.prog}  {version}', 80)
    console.print('')

    ip_helper = IpHelper()
    LOGGER.enable('dt_tools.net.ip_info_helper')
    if args.clear or args.list:
        if args.clear:
            LOGGER.success(f'  {ip_helper.clear_cache(args.ip)} entries removed.')
        elif args.list:
            ip_helper.list_cache(args.ip)
        else:
            LOGGER.critcal('  Unknown command')
    else:
        if args.ip:
            LOGGER.debug(f'Cache loaded with {len(ip_helper._cache)} entries.')
            LOGGER.debug('')
            _display_ip_info(ip_helper, args.ip, show_all=True)
        else:
            LOGGER.info(f'Cache loaded with {len(ip_helper._cache)} entries.')
            LOGGER.info('')
            _command_loop(ip_helper)

if __name__ == "__main__":
    main()
    sys.exit(0)
