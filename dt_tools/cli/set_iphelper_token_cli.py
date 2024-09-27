"""
This module creates the token file and stores the token used for interface with ipinfo.io.

To get your token, go to https:/ipinfo.io/missingauth

"""
import json

import dt_tools.logger.logging_helper as lh
from dt_tools.console.console_helper import (ColorFG, TextStyle,
                                             ConsoleHelper, ConsoleInputHelper)
from loguru import logger as LOGGER 

import dt_tools.net.ip_info_helper as ih


def manage_token():
    console = ConsoleHelper()
    console_input = ConsoleInputHelper()

    ip_helper = console.cwrap("IpHelper", fg=ColorFG.WHITE2, style=TextStyle.BOLD)
    note = console.cwrap('NOTE:', fg=ColorFG.YELLOW2, style=[TextStyle.BOLD, TextStyle.ITALIC])
    token_file = console.cwrap(ih.IP_INFO_TOKEN_LOCATION, fg=ColorFG.WHITE2, style=TextStyle.BOLD)

    console.print('')
    console.print_line_separator('', 90)
    console.print_line_separator(f' {ip_helper} Token Manager', 90)
    console.print('')
    console.print('The dt-cli-tools utilities and the dt-net python package leverage ipinfo.io for ip')
    console.print('address geo-location information.\n')
    console.print('To leverage the ipinfo.io API, a (free) valid token from ipinfo.io is required.')
    console.print('- (see https://ipinfo.io/missingauth)\n')
    console.print('This is a one-time process to acquire the API token and save it locally')
    console.print('for future use.\n')
    console.print('Once a valid token has been aquired, it can be entered via this script and will')
    console.print('be made available to the IpHelper routines.\n')
    console.print('If you already have a token, but forget what it is, you may log back into ipinfo.io')
    console.print('to retrieve your token.')
    console.print('')
    console.print('Process:')
    console.print(' 1. Go to https://ipinfo.io')
    console.print(' 2. Click on "Sign Up".')
    console.print(' 3. Create your free account by filling out the form.')
    console.print(' 4. You will be assigned a token, copy it to your clipboard.')
    console.print(' 5. When prompted, enter it into this script.\n')
    console.print(f'{note}  The token is stored locally in {token_file}.')
    console.print('       format: {"token": "xxxxxxxxxxxxxx"}')
    console.print('')
    if console_input.get_input_with_timeout('Continue (y/n) > ', ['y', 'n']) == 'y':
        token = console_input.get_input_with_timeout('Token > ')
        if len(token.strip()) == 0:
            LOGGER.warning('Empty token, did not save.')
        else:
            token_dict = json.dumps({"token": token})
            ih.IP_INFO_TOKEN_LOCATION.parent.mkdir(parents=True, exist_ok=True)
            ih.IP_INFO_TOKEN_LOCATION.write_text(token_dict)
            LOGGER.success('Token saved.')
        LOGGER.info('')
    
    print('Process complete.')

if __name__ == "__main__":
    lh.configure_logger()
    manage_token()
