"""
This module checks for open[/closed] ports on target host(s).  

**Features**:

- Check a port, a list of ports, range of ports or common ports
- Limit output to only show open ports
- Check multiple hosts via an input file of hostnames(and ports)
- Threaded to improve performance for large number of ports

**Usage**:

    port-check [-h] [-i filename] [-c] [-w secs] [-v] [-o] [connection]

    - -h: show help screen
    - -i: hosts list in filename provided
    - -c: list common port numbers and descriptions
    - -w: number of seconds to wait for connection
    - -v: verbose logging
    - -o: only show open connections
    - connenction: target in format hostname:port (see below)

    The port parameter can be one (or a combination) of below formats:

    - 80          check for single open port 80 on myHost
    - 80,443      check for open ports 80 and 443 on myHost
    - 20-40       check for open ports 20 thru 40 on myHost
    - 80,20-44    check for open ports 80 and 20 thru 44 on myHost
    - common      the string, check for all common ports
        
    Connection strings may also be loaded into a text file to be processed by
    using the -i command line parameter.

**Returns**:
    
    int: Return code
    
    - 0       if all connections are successful
    - 1-999   the number of un-successful connections
    - 1000+   parameter or data issue, see console message

"""
import argparse
import concurrent.futures
import pathlib
import sys
import textwrap
import threading
from typing import List

from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
import dt_tools.net.net_helper as net_helper
from dt_tools.os.os_helper import OSHelper
from dt_tools.os.project_helper import ProjectHelper
from dt_tools.console.console_helper import ConsoleHelper as console
from dt_tools.console.console_helper import ColorFG, TextStyle


stop_event = threading.Event()

def _sub_list(in_list: list, cols: int) -> list:
    final = [in_list[i * cols:(i + 1) * cols] for i in range((len(in_list) + cols - 1) // cols )] 
    return final


def _list_common_ports():
    LOGGER.info('Common Ports')
    LOGGER.info('')
    LOGGER.info('  Port  Description           Port  Description           Port  Description')
    LOGGER.info('  ----- --------------------  ----- --------------------  ----- --------------------')
    chunks = _sub_list(list(net_helper.COMMON_PORTS.items()), 3)
    for item in chunks:
        p1_name = item[0][0]
        port1   = f'{item[0][1]:5d}'.lstrip('0') if len(item) > 0 else ''
        p2_name = item[1][0] if len(item) > 1 else ''
        port2   = f'{item[1][1]:5d}'.lstrip('0') if len(item) > 1 else ''
        p3_name = item[2][0] if len(item) > 2 else ''
        port3   = f'{item[2][1]:5d}'.lstrip('0') if len(item) > 2 else ''
        LOGGER.info(f'  {port1:5} {p1_name:20}  {port2:5} {p2_name:20}  {port3:5} {p3_name:20}')

def _process_host_file(input_filename: str, wait: float = 1.0, only_open: bool = False) -> int:
    LOGGER.debug(f'_process_host_file() - {input_filename}')
    fn = pathlib.Path(input_filename)
    with open(fn, mode="r") as in_file:
        host_list = in_file.read().splitlines()
    
    ret_cd = 0
    for host_line in host_list:
        if host_line.startswith("##"):
            LOGGER.info(host_line.replace("##","").strip())
        elif not host_line.startswith("#") and host_line.strip():
            ret_cd += _process_host_connection(host_line, wait, only_open)

    return ret_cd

def _extract_ports(ports_string: str) -> List[int]:
    if ports_string == 'common':
        ports_list = net_helper.COMMON_PORTS.values()
    else:
        ports_list = ports_string.split(',')
    
    ports = []
    for port in ports_list:
        # Expand ranges if there are any
        if isinstance(port, int):
            ports.append(port)
        else:
            token = port.split('-')
            if len(token) == 1:
                if token[0].isdigit():
                    ports.append(int(token[0]))
                else:
                    LOGGER.warning(f'{token[0]} Dropped.  Port must be numeric')
            elif len(token) == 2:
                try:
                    b_port = int(token[0])
                    e_port = int(token[1])
                except ValueError:
                    LOGGER.warning(f'{port} Dropped.  Non-numeric port parameter')
                else:
                    if b_port < e_port:
                        ports.extend(list(range(int(token[0]), int(token[1])+1)))
                    else:
                        LOGGER.warning(f'{port} Dropped. Invalid port range')

    return ports

def _process_host_connection(host_connection: str, wait: float = 1.0, only_open: bool = False) -> int:
    LOGGER.debug(f'_process_host_connection() - {host_connection}')    
    tokens = host_connection.split(':')
    if len(tokens) != 2:
        LOGGER.info('')
        LOGGER.warning(f'Invalid host line - {host_connection}')
        return 1000
    
    host = tokens[0]
    if not net_helper.is_valid_host(host):
        if not net_helper.ping(host):
            LOGGER.info('')
            LOGGER.warning(f'{host:20} invalid, could not resolve hostname - BYPASS')
            return 1001
    
    ports = _extract_ports(tokens[1])
    if len(ports) == 0:
        LOGGER.info('')
        LOGGER.warning(f'Invalid ports parameter: {tokens[1]}')
        return 1002
    
    ret_cd = 0        
    display_closed = not only_open
    num_ports = len(ports)
    futures = []
    thread_cnt = min(num_ports, 30) # Limit thread count to 30 max
    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_cnt) as executor:
        if num_ports > thread_cnt:
            LOGGER.info('')
            dsply_ports = console.cwrap(num_ports, fg=ColorFG.WHITE2, style=TextStyle.BOLD)
            dsply_host = console.cwrap(host, fg=ColorFG.WHITE2, style=TextStyle.BOLD)
            LOGGER.info(f'Checking {dsply_ports} ports on {dsply_host} with {executor._max_workers} threads.')
            LOGGER.info('')
        future:concurrent.futures.Future = None
        for port in ports:
            future = executor.submit(_check_host, host, port, wait, display_closed)
            futures.append(future)
        for future in futures:
            ret_cd += future.result()
        if ret_cd == num_ports:
            LOGGER.warning('  No open ports detected.')
    return ret_cd

def _check_host(host: str, port: int, wait: float = 1.5, display_closed: bool = True) -> int:
    host_id = f'{host}:{port}'
    port_name = net_helper.get_port_name(port)
    if port_name is None:
        port_name = ''
    if net_helper.is_port_open(host, port, wait):
        ret_cd = 0
        status = console.cwrap('open  ', fg=ColorFG.GREEN2, style=[TextStyle.BOLD])            
        LOGGER.info(f'{host_id:20} {status} {port_name}')
    else: 
        ret_cd = 1
        if display_closed:
            status = console.cwrap('closed', fg=ColorFG.YELLOW2, style=[TextStyle.BOLD])            
            LOGGER.info(f'{host_id:20} {status} {port_name}')

    return ret_cd

def _validate_commandline_args(args: argparse.Namespace):
    ret_cd = 0
    if not args.common:
        if not args.connection and not args.input:
            LOGGER.error('Must supply either connection or input\n')
            ret_cd = 3000
        elif args.connection and args.input:
            print('Must supply ONLY connection OR input, not both\n')
            ret_cd = 3100
        elif args.connection:
            if len(args.connection.split(':')) != 2:
                LOGGER.error('Invalid parameters, must include host:port or host:common\n')
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
        {parser.prog} myHost:ports

            where ports are combinations of formats:
            80          check for single open port 80 on myHost
            80,443      check for open ports 80 and 443 on myHost
            20-40       check for open ports 20 thru 40 on myHost
            80,20-44    check for open ports 80 and 20 thru 44 on myHost
            common      the string, check for all common ports
        
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
    parser.add_argument('-c', '--common', action='store_true', default=False,
                            help='List common ports and exit')
    parser.add_argument('-w', '--wait', type=float, required=False, default=1.0, metavar="secs",
                            help='Time to wait (default 1 second)')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                            help='-v:debug -vv:trace')
    parser.add_argument('-o', '--only_open', action='store_true', default=False,
                            help='Only display open ports')
    parser.add_argument('connection', nargs='?',
                            help='Host/IP:port(s) to check, see above for examples')
    args = parser.parse_args()
    if args.verbose == 0:
        log_level = "INFO"
        log_format = lh.DEFAULT_CONSOLE_LOGFMT
    elif args.verbose == 1:
        log_level = "DEBUG"
        LOGGER.enable('dt_tools.net.net_helper')
        log_format = lh.DEFAULT_DEBUG_LOGFMT
    else:
        log_level = "TRACE"
        LOGGER.enable('dt_tools.net.net_helper')
        log_format = lh.DEFAULT_DEBUG_LOGFMT

    lh.configure_logger(log_level=log_level, log_format=log_format, brightness=False)

    version = f"(v{console.cwrap(ProjectHelper.determine_version('dt-cli-tools'), style=[TextStyle.ITALIC, TextStyle.UNDERLINE])})"
    console.print_line_separator(' ', 80)
    console.print_line_separator(f'{parser.prog} {version}', 80)
    console.print('')

    ret_cd = _validate_commandline_args(args)
    if ret_cd > 0:
        console.print('')
        parser.print_usage()
        return ret_cd

    if args.common:
        console.print('')
        _list_common_ports()
        return ret_cd
    
    if args.connection:
        ret_cd = _process_host_connection(args.connection, args.wait, args.only_open)
    else:
        ret_cd = _process_host_file(args.input, args.wait, args.only_open)

    return ret_cd

if __name__ == "__main__":
    OSHelper.enable_ctrl_c_handler()
    sys.exit(main())
   
