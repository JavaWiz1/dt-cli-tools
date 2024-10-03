# dt-cli-tools

CLI tools using the dt suite of helpers (dt-misc, dt-console, dt-net)

For detailed usage information, supply -h or --help to command line.

    ex:  ip-helper -h

## ip-helper 

Retrieve IP information on Local and Internet IP addresses.

This utility interfaces with the free ipinfo.io site.  The ipinfo.io site
requires a user token which is free.

  - See 'setting up user token' (https://htmlpreview.github.io/?https://github.com/JavaWiz1/dt-net/blob/develop/docs/html/dt_tools.net.ip_info_helper.html) in docs for information on aquiring and setting up token.

Features:

    - IP Cache for to increase perfomance and and limit calls to ipinfo.io
    - Command line interface, or console prompt menu.
    - Commands to manage cache (list, clean, search,...)
    - Cached IP entry will auto-refresh if it is more than 48 hours old.


## lan-clients 

Create report of all identified clients on local network.

Entries are identified thru Address Resolution Protocal (ARP) cache or broadcast.
Default approach is ARP cache, however Broadcast (-b parameter) is more thorough, but takes more time.


Features:

  - Identifies LAN Clients and displays associated details:

    - IP Address
    - Hostname
    - MAC Address
    - MAC Vendor
  - Uses ARP Cache or ARP Broadcast to identify clients
  - Can output results into a pipe '|' delimited file


## port-check 

This module checks for open[/closed] ports on target host(s).

Features:

    - Check a port, a list of ports, range of ports or common ports
    - Limit output to only show open ports
    - Check multiple hosts via an input file of hostnames(and ports)
    - Threaded to improve performance for large number of ports


## set-iphelper-token  

This module creates the token file and stores the token used for interface with ipinfo.io.

To get your token, go to https:/ipinfo.io/missingauth


## speak

Speak text from command-line or text file.

Features:

    - Input from command line or file
    - Selectable accents (see --list option for values)
    - Control cadence/speed of voice


## wol-cli 

Send Wake-on-LAN (WOL) packet to device.

WOL is a standard for Ethernet and Token-Ring which allows a computer to be
turned on or awakened from sleep-mode via a network message.

A 'magic' packet is sent to the MAC address of the target device, which if
enabled, will signal the device to wake-up.

This module allows the user to send WOL to hostnames and IPs in addition to
the MAC address.  This is accomplished by leveraging a cache that this program
maintains which relates the MAC to IP and hostname.