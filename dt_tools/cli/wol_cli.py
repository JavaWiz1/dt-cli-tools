"""
Send **Wake-on-LAN (WOL)** packet to device.

WOL is a standard for Ethernet and Token-Ring which allows a computer to be 
turned on or awakened from sleep-mode via a network message.

A 'magic' packet is sent to the MAC address of the target device, which if
enabled, will signal the device to wake-up.

This module allows the user to send WOL to hostnames and IPs in addition to
the MAC address.  This is accomplished by leveraging a cache that this program
maintains which relates the MAC to IP and hostname (see option -s and -l).

**Usage**:
    
    wol-cli [-h] (-m MAC | -n NAME | -i IP | -l | -s | -c | -d) [-t TIMEOUT] [-v]

    Where parameters are:
  
    - -h show this help message and exit
    - -m MAC Wake via MAC Address
    - -n NAME Wake via Hostname
    - -i IP Wake via IP Address
    - -t TIMEOUTSeconds to wait for device to come online
    - -v Verbose logging    

    Cache control commands:

    - -s Scan for new devices to 'seed' or update the cache run.  
    - -l List the contents of the cache to the terminal.
    - -c Clean/purge cache of stale entries (devices that have not been online in 7 or more days).
    - -d Delete cache and re-create

Note::

    - The scan (-s) operation should be done on a regular basis when devices are online.  
    - This will keep the cache updated with the most recent online devices, their hostnames and IPs.
    - Not all devices support WOL, and in some cases device must be configured (see https://www.lifewire.com/wake-on-lan-4149800)

Returns:

    int: True if WOL packet sent succesfully else False

"""
import argparse
import datetime
import json
import pathlib
import sys
from dataclasses import dataclass
from typing import Dict, List

from dataclasses_json import dataclass_json
from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
import dt_tools.net.net_helper as net_helper
from dt_tools.console.console_helper import ColorFG, TextStyle
from dt_tools.console.console_helper import ConsoleHelper as console
from dt_tools.console.console_helper import ConsoleInputHelper as ih
from dt_tools.console.spinner import Spinner, SpinnerType
from dt_tools.net.net_helper import LAN_Client
from dt_tools.net.wol import WOL
from dt_tools.os.os_helper import OSHelper
from dt_tools.os.project_helper import ProjectHelper

MAC_INFO_LOCATION=pathlib.Path('~').expanduser().absolute() / ".IpHelper" / "WolMacDefinitions.json"

@dataclass_json
@dataclass
class _WOL_Device():
    name: str
    ip: str
    mac: str
    modified: datetime.date


def _lookup_mac_entry(device_id: str) -> _WOL_Device:
    LOGGER.trace(f'_lookup_mac_entry("{device_id}")')
    cached_mac_dict = _retrieve_device_dict()
    # found_entry = {'name': '', 'ip': '', 'mac': ''}
    found_entry = None

    for entry in cached_mac_dict.values():
        LOGGER.trace(f'- {entry}')
        if entry.ip == device_id or entry.name.lower().startswith(device_id.lower()):
            found_entry = entry
            LOGGER.trace('- FOUND')
            break
    return found_entry

def _print_device_dict(device_dict: Dict[str, _WOL_Device]):
    LOGGER.info("")
    LOGGER.info('Mac                IP               Name')
    LOGGER.info('-----------------  ---------------  -----------------------------------------')
    
    devices: Dict[str, _WOL_Device] = {}
    # Build dict with IP key in format 999.999.999.999 (for sorting)
    for device in device_dict.values():
        octet = device.ip.split('.')
        ip_key = f'{int(octet[0]):3d}.{int(octet[1]):3d}.{int(octet[2]):3c}.{int(octet[3]):3d}'
        devices[ip_key] = device
    # Build sorted dictionary
    sorted_ips = list(devices.keys())
    sorted_ips.sort()
    sorted_devices = {i: devices[i] for i in sorted_ips}
    # Display
    for entry in sorted_devices.values():
        lvl = "INFO" if net_helper.ping(entry.name) else "WARNING"
        LOGGER.log(lvl, f"{entry.mac}  {entry.ip:15}  {entry.name}")

    LOGGER.info('')
    LOGGER.success(f'{len(device_dict.keys())} device entries.')

def _save_device_dict(device_dict: Dict[str, _WOL_Device]) -> bool:
    LOGGER.info('  - Save updated device list')
    MAC_INFO_LOCATION.with_suffix(".json.5").unlink(missing_ok = True)
    for i in range(4,0,-1):
        if MAC_INFO_LOCATION.with_suffix(f'.json.{i}').exists(): 
            MAC_INFO_LOCATION.with_suffix(f'.json.{i}').rename(MAC_INFO_LOCATION.with_suffix(f'.json.{i+1}'))
    if MAC_INFO_LOCATION.exists():
        MAC_INFO_LOCATION.rename(MAC_INFO_LOCATION.with_suffix('.json.1'))
    
    json_dict = {}
    for k,v in device_dict.items():
        # Convert WOL_Device to serializable object
        json_dict[k] = v.to_dict()

    MAC_INFO_LOCATION.write_text(json.dumps(json_dict, indent=2))
    LOGGER.info(f'    {len(device_dict.keys())} entries saved to {MAC_INFO_LOCATION}.')
    return True

def _retrieve_device_dict() -> Dict[str, _WOL_Device]:
    device_dict: Dict[str, _WOL_Device] = {}
    if MAC_INFO_LOCATION.exists():
        LOGGER.debug(f'loading device dict: {MAC_INFO_LOCATION}')
        try:
            json_dict = json.loads(MAC_INFO_LOCATION.read_text())
            for k,v in json_dict.items():
                # Reconstruct WOL_Device
                device = _WOL_Device(name=v['name'], ip=v['ip'], mac=v['mac'], modified=v['modified'])
                device_dict[k] = device
        except Exception as ex:
            LOGGER.error(f'Error loading {MAC_INFO_LOCATION}, {ex}')

    LOGGER.info(f'  - Retrieved cached device list. {len(device_dict.keys())} entries loaded.')
    return device_dict

def _merge_device_dicts(realtime_device_dict: Dict[str, _WOL_Device], 
                       cached_device_dict: Dict[str, _WOL_Device]) -> Dict[str, _WOL_Device]:
    
    LOGGER.info('  - Build cache')
    new_cnt = 0
    upd_cnt = 0
    exist_cnt = 0
    cached_cnt = 0
    merged_dict: Dict[str, _WOL_Device] = {}

    # Load all reporting devices
    for mac in realtime_device_dict.keys():
        if cached_device_dict.get(mac, None) is None:
            new_cnt += 1
            LOGGER.debug(f'new: {mac}')
        else:
            if realtime_device_dict[mac].ip != cached_device_dict[mac].ip or \
               realtime_device_dict[mac].name != cached_device_dict[mac].name:
                upd_cnt += 1
                LOGGER.debug(f'upd: {mac}')
                LOGGER.debug(f'  realtime: {realtime_device_dict[mac]}')
                LOGGER.debug(f'  cached  : {cached_device_dict[mac]}')
            else:
                LOGGER.debug(f'existing: {mac}')
                exist_cnt += 1
        merged_dict[mac] = realtime_device_dict[mac]

    # Load all offline (non reporting) cached devices    
    for mac in cached_device_dict.keys():
        if merged_dict.get(mac,None) is None:
            cached_cnt +=1
            merged_dict[mac] = cached_device_dict[mac]
            LOGGER.debug(f'not online: {mac}')

    tot_cnt = len(merged_dict)
    LOGGER.info(f'      {exist_cnt} existing, {new_cnt} added, {upd_cnt} updated, {cached_cnt} not online, {tot_cnt} total entries.')

    return merged_dict

def _clean_cache(current_cache: Dict[str, _WOL_Device]) -> Dict[str, _WOL_Device]:
    today = datetime.date.today()
    updated_cache: Dict[str, _WOL_Device] = {}
    for mac, entry in current_cache.items():
        modified = datetime.datetime.strptime(entry.modified, '%Y-%m-%d').date()
        if (today - modified).days > 7:
            # device hasn't been seen (via this pgm) in over a week
            continue
        updated_cache[mac] = entry
    
    entries_dropped = len(current_cache) - len(updated_cache)
    if entries_dropped > 0:
        LOGGER.info(f'    {entries_dropped} stale entries dropped, {len(updated_cache)} total entries remain in cache.')
    else:
        LOGGER.info(f'    No stale entries detected.  {len(updated_cache)} total entries remain in cache.')
        
    return updated_cache

def _retrieve_lan_devices() -> Dict[str, _WOL_Device]:
    LOGGER.info('  - Scan for current online devices')
    spinner = Spinner('    ARP Broadcast scan ', spinner=SpinnerType.BALL_BOUNCER, show_elapsed=True)

    spinner.start_spinner()
    lan_list: List[LAN_Client] = []
    lan_list = net_helper.get_lan_clients_ARP_broadcast(include_hostname=True)
    today = str(datetime.date.today())
    wol_lan_dict: Dict[str, _WOL_Device] = {}
    for entry in lan_list:
        if entry.hostname is not None and not entry.hostname.startswith('-> '):
            device = _WOL_Device(name=entry.hostname, ip=entry.ip, mac=entry.mac, modified=today)
            wol_lan_dict[entry.mac] = device
    spinner.stop_spinner()

    LOGGER.info(f'      {len(wol_lan_dict.keys())} devices detected.')
    return wol_lan_dict


def _device_scan() -> bool:
    realtime_device_dict = _retrieve_lan_devices()
    cached_device_dict = _retrieve_device_dict()
    merged_device_dict = _merge_device_dicts(realtime_device_dict, cached_device_dict)
    if not _dicts_equal(cached_device_dict, merged_device_dict):
        _save_device_dict(merged_device_dict)
    return True

def _clean_device_cache() -> bool:
    realtime_device_dict = _retrieve_lan_devices()
    cached_device_dict = _retrieve_device_dict()
    merged_device_dict = _merge_device_dicts(realtime_device_dict, cached_device_dict)
    updated_cache = _clean_cache(merged_device_dict)
    if not _dicts_equal(updated_cache, cached_device_dict):
        _save_device_dict(updated_cache)
    return True

def _edit_device_cache() -> bool:
    if OSHelper.is_windows():
        notepad = OSHelper.is_executable_available('notepad')
        if notepad is None:
            rc = -1
            output = ['Notepad executable not found in path.']
        else:
            rc, output = OSHelper.run_command(f'{notepad} {MAC_INFO_LOCATION}')
    else:
        nano = OSHelper.is_executable_available('nano')
        if nano is None:
            rc = -1
            output = ['Notepad executable not found in path.']
        else:
            rc, output = OSHelper.run_command(f'{nano} {MAC_INFO_LOCATION}')

    if rc != 0:
        LOGGER.error(f'Unable to edit {MAC_INFO_LOCATION}')
        for line in output:
            LOGGER.warning(f'  {line}')
    return rc == 0

def _dicts_equal(d1: dict, d2: dict) -> bool:
    are_equal = False
    if len(d1.keys()) == len(d2.keys()):
        shared_items = {k: d1[k] for k in d1 if k in d2 and d1[k] == d2[k]}
        if len(d1.keys()) == len(shared_items.keys()):
            are_equal = True
    return are_equal

def _resolve_target(args: argparse.Namespace) -> str:    
    ip = None
    if args.mac:
        mac = net_helper.format_mac(args.mac)
        ip = net_helper.get_ip_from_mac(args.mac)
        hostname = net_helper.get_hostname_from_ip(ip)
    elif args.name:
        hostname = args.name
        ip = net_helper.get_ip_from_hostname(args.name)
        mac = net_helper.get_mac_address(ip)
    elif args.ip:
        ip = args.ip
        mac = net_helper.get_mac_address(ip)
        hostname = net_helper.get_hostname_from_ip(ip)
    
    if ip is not None:
        return f'[Host: {hostname}  ip: {ip}  mac: {mac}]'
    
    return ''

# ================================================================================================    
def main() -> int:
    c_handle = lh.configure_logger(log_level="INFO", log_format=lh.DEFAULT_CONSOLE_LOGFMT, brightness=False)
    OSHelper.enable_ctrl_c_handler()
    version = ProjectHelper.determine_version('dt-cli-tools')
    parser = argparse.ArgumentParser(prog='wol-cli', description=f'Wake-on-Lan CLI  v{version}')
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('-m', '--mac',  type=str, help='Wake via MAC Address')
    input_group.add_argument('-n', '--name', type=str, help='Wake via Hostname')
    input_group.add_argument('-i', '--ip',   type=str, help='Wake via IP Address')
    input_group.add_argument('-l', '--list',   action='store_true', help='List WOL cache')
    input_group.add_argument('-s', '--scan',   action='store_true', help='Scan and create/update WOL cache')
    input_group.add_argument('-c', '--clean',  action='store_true', help='Clean cache of old entries')
    input_group.add_argument('-e', '--edit',   action='store_true', help='Edit the cache')
    input_group.add_argument('-d', '--delete', action='store_true', help='Delete cache and re-create')
    parser.add_argument('-t','--timeout', type=int, default=45, help='Seconds to wait for device to come online')
    parser.add_argument('-v','--verbose', action='count', default=0, help="Verbose logging, more v's, more verbose")
    
    try:
        # sys.argv.append('-e')
        args = parser.parse_args()
    except (argparse.ArgumentError, IndexError) as ae:
        LOGGER.critical(repr(ae))
        return 1

    LG_LEVEL = "INFO"
    end_tag = '\n'


    if args.verbose > 0:
        if args.verbose > 1:
            if args.verbose == 2:
                LG_LEVEL = "DEBUG"
                LG_FORMAT = lh.DEFAULT_DEBUG_LOGFMT
            else:
                LG_LEVEL = "TRACE"
                LG_FORMAT = lh.DEFAULT_DEBUG_LOGFMT2
            end_tag = ''

        lh.configure_logger(log_level=LG_LEVEL, 
                            log_format=LG_FORMAT,
                            enable_loggers=['dt_tools'],
                            brightness=False)
    
    LOGGER.debug('')
    LOGGER.debug(f'{console.cwrap(parser.description, fg=ColorFG.WHITE2, style=TextStyle.BOLD)}')

    success = False
    wol = WOL()
    if args.mac:
        LOGGER.info(f'Sending WOL to {console.cwrap(args.mac, fg=ColorFG.WHITE2, style=[TextStyle.BOLD,TextStyle.ITALIC])}', end=end_tag, flush=True)
        success = wol.send_wol_via_mac(args.mac, args.timeout)
        if not success:
            LOGGER.error(f'- {wol.status_message}')

    elif args.ip or args.name:
        if args.ip:
            host = args.ip
        else:
            host = args.name.lower()
        if net_helper.ping(host):
            LOGGER.info(f'{host} is already online.')
            success = True
        else:
            LOGGER.info(f'Sending WOL to {console.cwrap(host, fg=ColorFG.WHITE2, style=[TextStyle.BOLD,TextStyle.ITALIC])} ',end=end_tag,flush=True)
            success = wol.send_wol_to_host(host, wait_secs=args.timeout)
            if not success:
                LOGGER.error(f'- Unable to send to host: {wol.status_message}')
                LOGGER.info('- Attempt to lookup host in cache...')
                mac_entry = _lookup_mac_entry(host)
                if mac_entry is not None:
                    LOGGER.info(f'  - {host} resolves to {mac_entry.mac}/{mac_entry.ip}')
                    LOGGER.info(f'Sending WOL to {console.cwrap(mac_entry.mac, fg=ColorFG.WHITE2, style=[TextStyle.BOLD,TextStyle.ITALIC])} ', end=end_tag, flush=True)
                    success = wol.send_wol_via_mac(mac_entry.mac, wait_secs=args.timeout, ip=mac_entry.ip)
                    if not success:
                        LOGGER.error(f'- {wol.status_message}')

    elif args.list:
        LOGGER.warning('Display device list')
        device_dict = _retrieve_device_dict()
        _print_device_dict(device_dict)
        success = True

    elif args.scan:
        LOGGER.warning('Device Scan requested')
        success = _device_scan()

    elif args.clean:
        LOGGER.warning('Cache clean requested')
        success = _clean_device_cache()

    elif args.edit:
        LOGGER.warning('Edit cache requested')
        success = _edit_device_cache()

    elif args.delete:
        LOGGER.error('Cache delete requested')
        if ih.get_input_with_timeout('Are you sure? ', ih.YES_NO_RESPONSE).lower() == 'y':
            LOGGER.warning('- Removing existing cache')
            MAC_INFO_LOCATION.unlink(missing_ok=True)
            LOGGER.warning('Rebuild cache')
            success = _device_scan()

    LOGGER.info('')
    if success:
        msg = 'Online.'
        if args.mac or args.ip or args.name:
            msg += f'  {_resolve_target(args)}'
        LOGGER.success(msg)
    else:
        LOGGER.error('Offline.')

    return success

if __name__ == "__main__":
    sys.exit(main())