import argparse
import datetime
import json
# import platform
# import socket
# import subprocess
import sys
from typing import List
from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
# from dt_tools.config.config_helper import Configuration
from dt_tools.console import console_helper as ch
from dt_tools.console.spinner import Spinner, SpinnerType
# from dt_tools.net.ip_info_helper import IpHelper
from dt_tools.net.wol import WOL
from dt_tools.os.project_helper import ProjectHelper
import dt_tools.net.net_helper as net_helper
from dt_tools.net.net_helper import LAN_Client
import pathlib 


MAC_INFO_LOCATION=pathlib.Path('~').expanduser().absolute() / ".IpHelper" / "WolMacDefinitions.json"


def lookup_mac_entry(device_id: str) -> dict:
    mac_dict = retrieve_device_dict()
    found_entry = {'name': '', 'ip': '', 'mac': ''}
    for entry in mac_dict.values():
        if entry['ip'] == device_id or entry['name'].startswith(device_id):
            found_entry = entry
            break
    return (found_entry['mac'], found_entry['name'], found_entry['ip'])

def print_device_dict(device_dict: dict):
    # print(json.dumps(device_dict, indent=2))
    LOGGER.info("")
    LOGGER.info('Mac                IP               Name')
    LOGGER.info('-----------------  ---------------  -----------------------------------------')
    sorted_devices = dict(sorted(device_dict.items(), key=lambda x:int(x[1]['ip'].split('.')[3])))
    for entry in sorted_devices.values():
        LOGGER.info(f"{entry['mac']}  {entry['ip']:15}  {entry['name']}")
    LOGGER.info(f'{len(device_dict.keys())} entries.')

def save_device_dict(device_dict: dict) -> bool:
    LOGGER.info('  - Save updated device list')
    MAC_INFO_LOCATION.with_suffix(".json.5").unlink(missing_ok = True)
    for i in range(4,0,-1):
        if MAC_INFO_LOCATION.with_suffix(f'.json.{i}').exists(): 
            MAC_INFO_LOCATION.with_suffix(f'.json.{i}').rename(MAC_INFO_LOCATION.with_suffix(f'.json.{i+1}'))
    if MAC_INFO_LOCATION.exists():
        MAC_INFO_LOCATION.rename(MAC_INFO_LOCATION.with_suffix('.json.1'))    
    MAC_INFO_LOCATION.write_text(json.dumps(device_dict, indent=2))
    LOGGER.info(f'    {len(device_dict.keys())} entries saved to {MAC_INFO_LOCATION}.')
    return True

def retrieve_device_dict() -> dict:
    device_dict = {}
    if MAC_INFO_LOCATION.exists():
        LOGGER.debug(f'loading device dict: {MAC_INFO_LOCATION}')
        device_dict = json.loads(MAC_INFO_LOCATION.read_text())

    LOGGER.info(f'  - Retrieve cached device list. {len(device_dict.keys())} entries loaded.')
    return device_dict

def merge_device_dicts(new_device_list: list, current_device_dict: dict, desc: str = "Merge new or update devices") -> dict:
    LOGGER.info(f'  - {desc}')
    new_cnt = 0
    for mac in current_device_dict.keys():
        if new_device_list.get(mac,None) is None:
            new_cnt +=1
        new_device_list[mac] = current_device_dict[mac]

    if new_cnt > 0:
        LOGGER.info(f'    {new_cnt} entries added, {len(new_device_list)} total entries.')
    
    return new_device_list

def retrieve_lan_devices() -> dict:
    LOGGER.info('  - Scan for devices')
    lan_list: List[LAN_Client] = []
    spinner = Spinner('    ARP Broadcast scan ', spinner=SpinnerType.BALL_BOUNCER, show_elapsed=True)
    spinner.start_spinner()
    lan_list = net_helper.get_lan_clients_ARP_broadcast(include_hostname=True)
    today = str(datetime.date.today())
    lan_dict = {}
    for entry in lan_list:
        if not entry.hostname.startswith('-> '):
            lan_dict[entry.mac] = {"name": entry.hostname, "ip": entry.ip, "mac": entry.mac, "modified": today}
    spinner.stop_spinner()
    LOGGER.info(f'    {len(lan_dict.keys())} entries detected.')
    return lan_dict

# def get_nmap_dict() -> dict:
#     scan_cmd = ['nmap', '-sn', '192.168.1.0/24']
#     if platform.system() == 'Linux':
#         scan_cmd.insert(0, 'sudo')
#     spinner = Spinner("    nmap scan ", spinner=SpinnerType.BALL_BOUNCER ,show_elapsed=True)
#     spinner.start_spinner()
#     scan_result = subprocess.run(scan_cmd, capture_output=True)
#     spinner.stop_spinner()

#     stdoutput = scan_result.stdout.decode('utf-8')
#     mac_dict = {}
#     host_name = ''
#     ip = ''
#     mac = ''
#     today = str(datetime.date.today())
#     for line in stdoutput.split('\n'):
#         LOGGER.debug(f'    {line}')
#         if line.startswith('Nmap scan report'):
#             tokens = line.split('for')
#             token = tokens[1].strip().replace('\r','`')
#             if token.count('(') > 0:
#                 host_name = token.split(' ')[0]
#                 ip = token.split('(')[1].replace(')', '')
#         elif line.startswith('MAC'):
#             if host_name:
#                 tokens = line.split('Address: ')
#                 token = tokens[1].strip().replace('\r','')
#                 mac = token.split()[0].lower()
#                 dict_entry = {'name': host_name.lower(), 'ip': ip, 'mac': mac, 'modified': today }
#                 LOGGER.debug(f'      {dict_entry}')
#                 mac_dict[mac_key(mac)] = dict_entry
#                 host_name = ''
#                 ip = ''
#                 mac = ''
#     LOGGER.info(f'    {len(mac_dict.keys())} nmap entries detected.')
#     return mac_dict

# def get_arp_dict() -> dict:
#     if platform.system() == 'Linux':
#         arp_cmd = ['arp', '-n']
#     else:
#         arp_cmd = ['arp', '-a']

#     today = str(datetime.date.today())
#     spinner = Spinner("    arp scan ", spinner=SpinnerType.BALL_BOUNCER ,show_elapsed=True)
#     spinner.start_spinner()
#     scan_result = subprocess.run(arp_cmd, capture_output=True)

#     stdoutput = scan_result.stdout.decode('utf-8')
#     device_list = []
#     for line in stdoutput.splitlines(keepends=False):
#         token = line.split()
#         name = None
#         if platform.system() == "Linux":
#             name = "?"
#             ip = token[0]
#             mac = token[2]
#         else:
#             if len(token) == 3:
#                 name = '?'
#                 ip = token[0]
#                 mac = token[1]

#         if name and ip.startswith('192'):
#             if name == "?":
#                 spinner.caption_suffix(f'attempt to resolve {ip}')
#                 try:
#                     name = socket.gethostbyaddr(ip)[0]
#                     LOGGER.debug(f'ip: {ip} Resolves to {name}')
#                 except Exception as ex:
#                     LOGGER.debug(f'unable to resolve {ip} - {repr(ex)}')
#             if name != '?':
#                 mac = mac.lower()
#                 device_entry = {'name': name.lower(), 'ip': ip, 'mac': mac, 'modified': today}
#                 device_list.append(device_entry)

#     spinner.stop_spinner()        
#     device_dict = {}
#     for de in device_list:
#         mac = de['mac']
#         device_dict[mac_key(mac)] = de
    
#     LOGGER.info(f'    {len(device_dict.keys())} arp entries detected.')
#     return device_dict


# def mac_key(mac: str) -> str:
#     if len(mac) == 17:
#         mac = mac.replace(mac[2],'')
#     return mac


# ================================================================================================    
def main() -> int:
    ch.enable_ctrl_c_handler()
    parser = argparse.ArgumentParser(prog='wol-cli', description='Wake-on Lan CLI')
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('-m', '--mac')
    input_group.add_argument('-n', '--name')
    input_group.add_argument('-i', '--ip')
    input_group.add_argument('-l', '--list', action='store_true')
    input_group.add_argument('-s', '--scan', action='store_true')
    parser.add_argument('-t','--timeout', type=int, default=45)
    parser.add_argument('-v','--verbose', action='store_true')
    
    try:
        args = parser.parse_args()
    except (argparse.ArgumentError, IndexError) as ae:
        LOGGER.critical(repr(ae))
        return 1

    LG_LEVEL = "INFO"
    end_tag = '\n'

    if args.verbose:
        LG_LEVEL = "DEBUG"
        end_tag = ''
    lh.configure_logger(log_level=LG_LEVEL, log_format=lh.DEFAULT_CONSOLE_LOGFMT)
    version = ProjectHelper.determine_version('dt_tools_cli')
    LOGGER.info(f'{parser.prog}: {parser.description} (v{version})')
    LOGGER.info()
    success = False
    if args.mac:
        wol = WOL()
        LOGGER.info(f'Sending WOL to {args.mac} ', end=end_tag, flush=True)
        success = wol.send_wol_via_mac(args.mac, args.timeout)
    elif args.ip or args.name:
        wol = WOL()
        if args.ip:
            host = args.ip
        else:
            host = args.name.lower()
        LOGGER.info(f'Sending WOL to {host} ',end=end_tag,flush=True)
        success = wol.send_wol_to_host(host, wait_secs=args.timeout)
        if not success:
            mac, name, ip = lookup_mac_entry(host)
            if mac:
                LOGGER.info(f'  - {host} resolves to {mac}/{ip}')
                LOGGER.info(f'Sending WOL to {mac} ', end=end_tag, flush=True)
                success = wol.send_wol_via_mac(mac, wait_secs=args.timeout, ip=ip)

    elif args.list:
        device_dict = retrieve_device_dict()
        print_device_dict(device_dict)
        success = True
    else: # args.scan -s
        LOGGER.info('MAC Scan requested')
        new_device_dict = retrieve_lan_devices()
        cur_device_dict = retrieve_device_dict()
        merged_device_dict = merge_device_dicts(new_device_dict, cur_device_dict, "Merge nmap/arp with current devices")
        # new_entries = len(merged_device_dict) - len(cur_device_dict)
        save_device_dict(merged_device_dict)
        success = True
    if success:
        LOGGER.success('Successful.')
    else:
        LOGGER.error('Unsuccessful.')

    return success

if __name__ == "__main__":
    sys.exit(main())