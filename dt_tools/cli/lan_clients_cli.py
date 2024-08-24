"""
lan_clients

Create report of all identified clients on local network.

Entries are identified thru Address Resolution Protocal (ARP) cache or broadcast.
Default approach is ARP cache, however Broadcast (-b parameter) is more thorough, but takes more time.

For devices that are only identified by their IP and MAC address (ie. hostname not resolvable),
you may manually identify by updating ~/.IpHelper/mac_info.json, 
which is keyed by mac address.

For example, entry below identifies Ring Doorbell:
    {
        "XX:XX:XX:XX:XX:XX": {
            "vendor": "Amazon Technologies Inc.",
            "hostname": "Kitchen.Echo"
        },
    }

and will be displayed as:

192.168.21.99    -> Kitchen.Echo               XX:XX:XX:XX:XX:XX  Amazon Technologies Inc.

"""
import argparse
import pathlib
import queue
import signal
import sys
import threading
import time

import dt_tools.logger.logging_helper as lh
import dt_tools.net.net_helper as net_helper
from dt_tools.console.spinner import Spinner
from dt_tools.net.net_helper import LAN_Client
from dt_tools.os.project_helper import ProjectHelper
from loguru import logger as LOGGER

ip_queue = queue.Queue()
resolved_queue = queue.SimpleQueue()
stop_event = threading.Event()


def _build_queue(load_via_broadcast: bool = False) -> int:
    # Retrieve clients based on ARP cache
    spinner = Spinner('LAN Clients', show_elapsed=True)
    if load_via_broadcast:
        search_type = "ARP Broadcast"
        spinner.start_spinner('searching via ARP Broadcast')
        client_list = net_helper.get_lan_clients_ARP_broadcast(include_hostname=True, include_mac_vendor=True)
    else:
        search_type = "ARP Cache"
        spinner.start_spinner('searching via ARP cache')
        client_list = net_helper.get_lan_clients_from_ARP_cache(include_hostname=True, include_mac_vendor=True)

    LOGGER.debug(f'{len(client_list)} clients retrieved.')
    for client in client_list:
        spinner.caption_suffix('Loading queue.')
        ip_queue.put(client)
    
    spinner.stop_spinner()
    LOGGER.info(f'{len(client_list)} clients identified via {search_type} in {spinner.elapsed_time}.')

def _queue_item_worker(name: str):
    lan_entry: LAN_Client
    while not ip_queue.empty():
        lan_entry = ip_queue.get()
        ip_address = lan_entry.ip # ip_queue.get()
        host_name = 'unknown' if lan_entry.hostname is None else lan_entry.hostname
        mac = 'unknown' if lan_entry.mac is None else lan_entry.mac
        vendor = 'unknown' if lan_entry.vendor is None else lan_entry.vendor
        if 'unknown' in host_name or 'unknown' in vendor:
            LOGGER.warning(f'{ip_address:15} {host_name:28} {mac:17}  {vendor}')
        else:
            LOGGER.info(f'{ip_address:15} {host_name:28} {mac:17}  {vendor}')
        queue_entry = f'{ip_address}|{host_name}|{mac}|{vendor}'
        resolved_queue.put(queue_entry)
        ip_queue.task_done()
        if stop_event.is_set():
            break

def _process_queue():
    threads = []
    num_threads = ip_queue.qsize()
    print()
    LOGGER.info('IP Address      Hostname                     MAC                MAC Vendor')
    LOGGER.info('--------------- ---------------------------- -----------------  --------------------------- ')
    start = time.time()
    for id in range(num_threads):
        worker = threading.Thread(target=_queue_item_worker,args=(id,), daemon=True)        # worker.setDaemon(True)
        worker.start()
        threads.append(worker)
        time.sleep(.1)

    while not ip_queue.empty() and not stop_event.is_set():
        time.sleep(2)
    
    for thread in threads:
        thread.join()

    elapsed = time.time() - start
    print()
    LOGGER.info(f'{resolved_queue.qsize()} resolved entries in {elapsed:.2f} seconds using {num_threads} threads.')

def _dump_resolved_hosts_to_file(out_filename: str):
    out_buff = ''
    while not resolved_queue.empty():
        host_tuple = resolved_queue.get()
        out_buff += f'{host_tuple}\n'
    fh = pathlib.Path(out_filename)
    try:
        fh.write_text(out_buff)
        print(f'Dump file: {fh.absolute()}')
    except:  # noqa: E722
        print(out_buff)
        
def _signal_handler(signum, frame):
    print('CTRL-C: Waiting for threads to stop...')
    stop_event.set()
    sys.exit(1)

signal.signal(signal.SIGINT, _signal_handler)

def main():
    parser = argparse.ArgumentParser()
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.description = "lan-clients - find clients on network."
    parser.add_argument('-o', '--output', type=str, required=False, metavar='filename',
                            help='Output file containing resolved hostnames')
    parser.add_argument('-b', '--broadcast', action='store_true', default=False, 
                            help='Use ARP Broadcast vs Cache to identify clients')
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

    version = ProjectHelper.determine_version('dt-cli-tools')
    LOGGER.info('='*80)
    LOGGER.info(f'{parser.description}  (v{version})')
    LOGGER.info('='*80)
    LOGGER.info('')
    _ = _build_queue(args.broadcast)
    _process_queue()
    if args.output:
        _dump_resolved_hosts_to_file(parser.output)

if __name__ == "__main__":
    main()
