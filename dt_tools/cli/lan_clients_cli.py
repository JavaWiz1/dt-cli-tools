"""
Create report of all identified clients on local network.

Entries are identified thru Address Resolution Protocal (ARP) cache or broadcast.
Default approach is ARP cache, however Broadcast (-b parameter) is more thorough, but takes more time.


**Features**:

  - Identifies LAN Clients and displays associated details:

    - IP Address
    - Hostname
    - MAC Address
    - MAC Vendor
  - Uses ARP Cache or ARP Broadcast to identify clients
  - Can output results into a pipe '|' delimited file 

**Usage**:

  lan-clients [-h] [-o filename] [-b] [-v]

  Parameters:

  - -h help
  - -o filename: output file for pipe '|' delimited output data.
  - -b Use Broadcast ARP ping (insteac of ARP cache) to identify clients.
  - -v Verbose logging

**Note**::

    For devices that are only identified by their IP and MAC address (ie. hostname not resolvable),
    you may manually identify by updating ~/.IpHelper/mac_info.json, 
    which is keyed by mac address.

    Example entry below identifies Ring Doorbell-

        {
            "XX:XX:XX:XX:XX:XX": {
                "vendor": "Amazon Technologies Inc.",  
                "hostname": "Kitchen.Echo"  
            },
        }

    and will be displayed as:

    192.168.21.99    -> Kitchen.Echo               XX:XX:XX:XX:XX:XX  Amazon Technologies Inc.

  
**Returns**:

    int: number of client devices identified on LAN.

"""
import argparse
import pathlib
import queue
import signal
import sys
import threading
import time
from enum import Enum

import dt_tools.logger.logging_helper as lh
import dt_tools.net.net_helper as net_helper
from dt_tools.console.console_helper import ColorFG
from dt_tools.console.console_helper import ConsoleHelper as console
from dt_tools.console.console_helper import TextStyle
from dt_tools.console.spinner import Spinner
from dt_tools.net.ip_info_helper import IpHelper as ih
import dt_tools.net.net_helper as nh
from dt_tools.net.ip_info_helper import MAC_INFO_LOCATION
from dt_tools.net.net_helper import LAN_Client
from dt_tools.os.os_helper import OSHelper
from dt_tools.os.project_helper import ProjectHelper
from loguru import logger as LOGGER

ip_queue = queue.Queue()
resolved_queue = queue.SimpleQueue()
stop_event = threading.Event()

class SORT_KEY(Enum):
    IP = 1
    HOSTNAME = 2
    MAC = 3
    VENDOR = 4

def sort_by_ip(entry: LAN_Client):
    ip_tokens = entry.ip.split('.')
    sort_ip=''
    for t in ip_tokens:
        sort_ip += f'{int(t):3d}.'
    return sort_ip

def sort_by_hostname(entry: LAN_Client):
    return entry.hostname

def sort_by_mac(entry: LAN_Client):
    return entry.mac

def sort_by_vendor(entry: LAN_Client):
    return entry.vendor

def _build_queue(load_via_broadcast: bool = False, sort_key: SORT_KEY = SORT_KEY.IP) -> int:
    # Retrieve clients based on ARP cache
    spinner = Spinner('Searching', show_elapsed=True)
    if load_via_broadcast:
        search_type = "ARP Broadcast"
        search_display = console.cwrap(search_type, fg=ColorFG.DEFAULT, style=TextStyle.ITALIC)
        spinner.start_spinner(f'searching for clients via {search_display}')
        client_list = net_helper.get_lan_clients_ARP_broadcast(include_hostname=True, include_mac_vendor=True)
    else:
        search_type = "ARP Cache"
        search_display = console.cwrap(search_type, fg=ColorFG.DEFAULT, style=TextStyle.ITALIC)
        spinner.start_spinner(f'searching for clients via {search_display}')
        client_list = net_helper.get_lan_clients_from_ARP_cache(include_hostname=True, include_mac_vendor=True)

    LOGGER.debug(f'{len(client_list)} clients retrieved.')
    if sort_key == SORT_KEY.IP:
        client_list.sort(key=sort_by_ip)
    elif sort_key == SORT_KEY.HOSTNAME:
        client_list.sort(key=sort_by_hostname)
    elif sort_key == SORT_KEY.MAC:
        client_list.sort(key=sort_by_mac)
    elif sort_key == SORT_KEY.VENDOR:
        client_list.sort(key=sort_by_vendor)
    else:
        LOGGER.warning(f'Unknown sortkey [{sort_key}], default to ip.')
        # UNknown
        client_list.sort(key=sort_by_ip)

    for client in client_list:
        spinner.caption_suffix('Loading queue.')
        ip_queue.put(client)
    
    spinner.stop_spinner()
    console.print(f'{console.cwrap(len(client_list),ColorFG.WHITE)} clients identified via ({console.cwrap(search_type, ColorFG.WHITE)}) in {spinner.elapsed_time}.')
    return len(client_list)

def _queue_item_worker(name: str):
    lan_entry: LAN_Client
    while not ip_queue.empty():
        lan_entry = ip_queue.get()
        ip_address = lan_entry.ip # ip_queue.get()
        host_name = 'unknown' if lan_entry.hostname is None else lan_entry.hostname
        mac = 'unknown' if lan_entry.mac is None else lan_entry.mac
        if mac != 'unknown' and lan_entry.vendor is None:
            lan_entry.vendor = nh.get_vendor_from_mac(mac)
        vendor = 'unknown' if lan_entry.vendor is None else lan_entry.vendor
        item_line = f'{ip_address:15} {host_name:28} {mac:17}  {vendor}'
        if 'unknown' in host_name or 'unknown' in vendor:
            item_line = console.cwrap(item_line, ColorFG.YELLOW2)
        console.print(item_line)
        queue_entry = f'{ip_address}|{host_name}|{mac}|{vendor}'
        resolved_queue.put(queue_entry)
        ip_queue.task_done()
        if stop_event.is_set():
            break

def _process_queue():
    start = time.time()
    threads = []
    num_threads = min(ip_queue.qsize(), 30)
    console.print('')
    console.print_line_separator('IP Address      Hostname                     MAC                MAC Vendor', 100)
    for id in range(num_threads):
        worker = threading.Thread(target=_queue_item_worker,args=(id,), daemon=True)        # worker.setDaemon(True)
        worker.start()
        threads.append(worker)
        time.sleep(.1)

    while not ip_queue.empty() and not stop_event.is_set():
        time.sleep(2)
    
    for thread in threads:
        thread.join()

    elapsed = f'{time.time() - start:.2f}'
    summary_line = f'\n{console.cwrap(resolved_queue.qsize(), ColorFG.WHITE2)} entries resolved in {console.cwrap(elapsed, ColorFG.WHITE2)} seconds using {num_threads} threads.'
    console.print(summary_line, eol='\n\n')

def _dump_resolved_hosts_to_file(out_filename: str) -> bool:
    success = False
    out_buff = ''
    while not resolved_queue.empty():
        host_tuple = resolved_queue.get()
        out_buff += f'{host_tuple}\n'
    fh = pathlib.Path(out_filename)
    try:
        fh.write_text(out_buff, encoding='utf-8')
        console.print(f'Dump file: {fh.absolute()} created.')
        success = True
    except Exception as ex: 
        LOGGER.exception(f'Unable to create {fh.absolute()} {repr(ex)}')

    return success

def _edit_mac_cache():
    editor = 'notepad' if OSHelper.is_windows() else 'nano'
    editor_exe = OSHelper.is_executable_available(editor)
    if editor_exe is None:
        LOGGER.warning(f'Unable to edit cache.  {editor} not found.')
        return
    OSHelper.run_command(f'{editor_exe} {MAC_INFO_LOCATION}')
    
def _signal_handler(signum, frame):
    print('CTRL-C: Waiting for threads to stop...')
    stop_event.set()
    sys.exit(1)

signal.signal(signal.SIGINT, _signal_handler)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.description = "lan-clients - find clients on network."
    parser.add_argument('-o', '--output', type=str, required=False, metavar='filename',
                            help='Output file containing resolved hostnames')
    parser.add_argument('-b', '--broadcast', action='store_true', default=False, 
                            help='Use ARP Broadcast vs Cache to identify clients')
    parser.add_argument('-l', '--list', action='store_true', default=False,
                            help='List user maintained MAC cache')
    parser.add_argument('-e', '--edit', action ='store_true', 
                            help='Edit user maintained MAC cache')
    parser.add_argument('-s', '--sort', choices=['ip','hostname','mac','vendor'], default='ip', 
                            help='Sort key (default ip)')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                            help='Enable verbose console messages')
    args = parser.parse_args()
    if args.verbose == 0:
        log_lvl = "INFO"
    elif args.verbose == 1:
        log_lvl = "DEBUG"
    else:
        log_lvl = "TRACE"
    lh.configure_logger(log_level=log_lvl)

    version = f"(v{console.cwrap(ProjectHelper.determine_version('dt-cli-tools'), style=[TextStyle.ITALIC, TextStyle.UNDERLINE])})"
    console.print_line_separator(' ', 80)
    console.print_line_separator(f'{parser.prog} {version}', 80)
    console.print('')
    if args.list:
        LOGGER.enable('dt_tools.net.ip_info_helper')
        ih().list_mac_cache()
        return 0
    if args.edit:
        _edit_mac_cache()
        return 0
    start = time.time()
    sort_key = SORT_KEY[args.sort.upper()]
    num_clients = _build_queue(args.broadcast, sort_key=sort_key)
    _process_queue()
    if args.output:
        _dump_resolved_hosts_to_file(args.output)
    
    elapsed = f'{time.time() - start:.2f}'
    console.print(f'Total elapsed time {console.cwrap(elapsed, ColorFG.WHITE2, style=TextStyle.BOLD)} seconds.')
    return num_clients

if __name__ == "__main__":
    sys.exit(main())
