import argparse
import pathlib
import sys
import textwrap

from loguru import logger as LOGGER

import dt_tools.console.console_helper as console_helper
import dt_tools.logger.logging_helper as lh
import dt_tools.net.net_helper as net_helper


def _process_host_file(input_filename: str, wait: float = 1.0) -> int:
    LOGGER.debug(f'_process_host_file() - {input_filename}')
    fn = pathlib.Path(input_filename)
    with open(fn, mode="r") as in_file:
        host_list = in_file.read().splitlines()
    
    ret_cd = 0
    for host_line in host_list:
        if host_line.startswith("##"):
            LOGGER.info(host_line.replace("##","").strip())
        elif not host_line.startswith("#") and host_line.strip():
            ret_cd += _process_host_connection(host_line, wait)

    return ret_cd

def _process_host_connection(host_connection: str, wait: float = 1.0) -> int:
    LOGGER.debug(f'_process_host_connection() - {host_connection}')    
    tokens = host_connection.split(':')
    if len(tokens) != 2:
        LOGGER.warning(f'Invalid host line - {host_connection}')
        return 1000

    ret_cd = 0        
    host = tokens[0]
    display_closed = True
    if tokens[1] == 'common':
        ports = net_helper.COMMON_PORTS.values()
        display_closed = False
    else:
        ports = tokens[1].split(',')

    if not net_helper.is_valid_host(host):
        LOGGER.error(f'{host:20} invalid, could not resolve - BYPASS')
        ret_cd = 1
    else:
        for port in ports:
            ret_cd += _check_host(host, port, wait, display_closed)
    
    return ret_cd

def _check_host(host: str, port: int, wait: float = 1.0, display_closed: bool = True) -> int:
    host_id = f'{host}:{port}'
    if net_helper.is_port_open(host, port, wait):
        ret_cd = 0
        port_name = net_helper.get_port_name(port)
        if port_name is None:
            port_name = ''            
        LOGGER.success(f'{host_id:20} open   {port_name}')
    else: 
        ret_cd = 1
        if display_closed:
            LOGGER.warning(f'{host_id:20} closed')

    return ret_cd

def _validate_commandline_args(args: argparse.Namespace):
    ret_cd = 0
    if not args.connection and not args.input:
        LOGGER.error('Must supply either connection or input\n')
        ret_cd = 3000
    elif args.connection and args.input:
        print('Must supply ONLY connection OR input, not both\n')
        ret_cd = 3100
    elif args.connection:
        if len(args.connection.split(':')) != 2:
            LOGGER.error('Invalid parameters, must include host:port\n')
            ret_cd = 3200
    else: # must be input file
        if not pathlib.Path(args.input).exists():
            LOGGER.error(f'File not found - {args.input}')
            ret_cd = 3300

    return ret_cd


def main():
    
    parser = argparse.ArgumentParser()
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.description = textwrap.dedent(f'''\
        Connection string is formatted as follows:
        ------------------------------------------
            {parser.prog} myHost:80          check for open port 80 on myHost
            {parser.prog} myHost:80,443      check for open ports 80 and 443 on myHost
        
        Connection strings may also be loaded into a text file to be processed by
        using the -i command line parameter:
        ------------------------------------------
            {parser.prog} -i my_hostlist.txt

         ''') 
    parser.epilog = textwrap.dedent('''\
            RetCd   Meaning
            -----   ----------------------------------------------
            0       if all connections are successful
            1-999   the number of un-successful connections
            1000+   parameter or data issue, see console message
    ''')
    parser.add_argument('-i', '--input', type=str, required=False, metavar="filename",
                            help='Input file containing connection definitions')
    parser.add_argument('-w', '--wait', type=float, required=False, default=1.0, metavar="secs",
                            help='Time to wait (default 1 second)')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                            help='Enable verbose console messages')
    parser.add_argument('connection', nargs='?',
                            help='Host/IP:port(s) to check, see above for examples')
    args = parser.parse_args()
    if args.verbose:
        lh.configure_logger(log_level="DEBUG")
        LOGGER.debug('DEBUG LOGGING ON')
    else:
        lh.configure_logger()

    ret_cd = _validate_commandline_args(args)
    if ret_cd > 0:
        parser.print_usage()
        return ret_cd

    if args.connection:
        ret_cd = _process_host_connection(args.connection, args.wait)
    else:
        ret_cd = _process_host_file(args.input, args.wait)

    return ret_cd

if __name__ == "__main__":
    console_helper.enable_ctrl_c_handler()
    sys.exit(main())
   
