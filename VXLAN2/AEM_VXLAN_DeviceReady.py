import os
import subprocess
from collections import Counter
import time


def get_hostname():

    with open('/mnt/flash/startup-config') as f:
    # with open('startup-config') as f:
        startup = f.readlines()

    # Get Hostname
    for line in startup:
        if "hostname" in line:
            hostname = line.split("\n")[0][9:]
    return hostname


def get_lldp_interfaces():
    # run lldp bash command from python
    output = subprocess.Popen(["/usr/bin/FastCli", "-c", "show lldp neigh | i Ethernet"], stdout=subprocess.PIPE).communicate()[0]    
    out2 = list(iter(output.split()))

    leaf_count = 0
    spine_count = 0
    switch_list = []
    for switch in out2:
        # print(switch.decode())
        if "leaf" in switch.decode():
            leaf_count + 1
            switch_list.append(switch.decode())
        elif "spine" in switch.decode():
            spine_count + 1
            switch_list.append(switch.decode())
    
    return switch_list


# Configure IP Addresses
def interface_config(hostname, switch_list):
    interface = []

    if "spine" in hostname:
        for switch in switch_list:
            eth = f"\
interface ethernet{switch[-1]}\n\
description LINK to {switch.upper()}.LAB\n\
mtu 9200\n\
logging event link-status\n\
no switchport\n\
ip address 10.{hostname[-1]}.1{switch[-1]}.0/31\n\
arp aging timeout 1200\n\
"       
            interface.append(eth)

        lo0 = f"\
interface loopback 0\n\
description MANAGEMENT\n\
ip address 10.10.10.{hostname[-1]}/32\n\
"
        interface.extend([lo0])

    elif "leaf" in hostname:
        print(f"{hostname} Interface IP Addresses will be...")
        eth1 = f"10.{hostname[-1]}.1{hostname[-1]}.1/31"
        eth2 = f"10.{hostname[-1]}.1{hostname[-1]}.1/31"

        for switch in switch_list:
            eth = f"\
interface ethernet{switch[-1]}\n\
description LINK to {switch.upper()}.LAB\n\
mtu 9200\n\
logging event link-status\n\
no switchport\n\
ip address 10.{switch[-1]}.1{hostname[-1]}.1/31\n\
arp aging timeout 1200\n\
"                 
            interface.append(eth)

        lo0 = f"\
interface loopback 0\n\
description MANAGEMENT\n\
ip address 10.10.10.1{hostname[-1]}/32\n\
"

        lo1 = f"\
interface loopback 1\n\
description LOGICAL VTEP\n\
ip address 172.20.{hostname[-1]}.{hostname[-1]}/32\n\
"
        interface.extend([eth1, eth2, lo0, lo1])

    interface_text = "\n".join(interface)
    print(interface_text)

    return interface


# BGP Underlay Config
def underlay_config(hostname, switch_list):

# ['leaf1', 'leaf2', 'leaf3', 'leaf4']

    if "spine" in hostname:
        # Create BGP Config
        bgp_config = []
        asn = 'router bgp 65000'
        router_id = f" router-id 10.10.10.{hostname[-1]}"
        distance = ' distance bgp 20 200 200'
        
        bgp_config.insert(0,asn)
        bgp_config.insert(1,router_id)
        bgp_config.insert(2,distance)

        for switch in switch_list:
            neighbour = f"\
 neighbor LEAFS6511{switch[-1]} peer group\n\
 neighbor LEAFS6511{switch[-1]} remote-as 6511{switch[-1]}\n\
 neighbor 10.{hostname[-1]}.1{switch[-1]}.1 peer group LEAFS6511{switch[-1]}\n\
 neighbor 10.{hostname[-1]}.1{switch[-1]}.1 description LEAF{switch[-1]}.LAB\n\
"
            bgp_config.append(neighbour)

    elif "leaf" in hostname:
        # Create BGP Config
        bgp_config = []
        asn = f'router bgp 6511{hostname[-1]}'
        router_id = f" router-id 10.10.10.1{hostname[-1]}"
        distance = ' distance bgp 20 200 200'
        bgp_group = ' neighbor SPINE peer group'
        bgp_group_asn = ' neighbor SPINE remote-as 65000'
        redistribute = ' redistribute connected\n'

        bgp_config.insert(0,asn)
        bgp_config.insert(1,router_id)
        bgp_config.insert(2,distance)
        bgp_config.insert(3,bgp_group)
        bgp_config.insert(4,bgp_group_asn)

        # ['spine1', 'spine2', 'spine3', 'spine4']
        for switch in switch_list:
            neighbour = f"\
 neighbor 10.{switch[-1]}.1{hostname[-1]}.0 peer group SPINE\n\
 neighbor 10.{switch[-1]}.1{hostname[-1]}.0 description SPINE{switch[-1]}.LAB\n\
"
            bgp_config.append(neighbour)
        bgp_config.append(redistribute)

    return bgp_config


# VTEP Config
def vtep_config(hostname):
    vtep_config = []
    asn = f'router bgp 6511{hostname[-1]}'
    router_id = f" router-id 10.10.10.1{hostname[-1]}"
    vtep_net = f" network 172.20.{hostname[-1]}.{hostname[-1]}/32\n"

    vtep_config.insert(0,asn)
    vtep_config.insert(1,router_id)
    vtep_config.insert(2,vtep_net)

    return vtep_config


# VXLAN EVPN
def vxlan_config(hostname, switch_list):
    
    if "spine" in hostname:
        vtep_bgp = [
                    "router bgp 65000",
                    " neighbor EVPN peer group",
                    " neighbor EVPN next-hop-unchanged",
                    " neighbor EVPN update-source Loopback0",
                    " neighbor EVPN ebgp-multihop 3",
                    " neighbor EVPN send-community extended",
                    " !"
                    ]

        for switch in switch_list:
            neighbour1 = f" neighbor 10.10.10.1{switch[-1]} peer group EVPN"
            neighbour2 = f" neighbor 10.10.10.1{switch[-1]} remote-as 6511{switch[-1]}"
            neighbour3 = f" neighbor 10.10.10.1{switch[-1]} description LEAF{switch[-1]}"

            vtep_bgp.extend([neighbour1, neighbour2, neighbour3])

    elif "leaf" in hostname:
        vtep_bgp = [
                    "interface Vxlan1",
                    " vxlan source-interface Loopback1",
                    " vxlan udp-port 4789\n!",
                    f"router bgp 6511{hostname[-1]}",
                    " neighbor EVPN peer group",
                    " neighbor EVPN remote-as 65000",
                    " neighbor EVPN update-source Loopback0",
                    " neighbor EVPN ebgp-multihop 3",
                    " neighbor EVPN send-community extended",
                    "!"
                    ]

        for switch in switch_list:
            neighbour1 = f" neighbor 10.10.10.{switch[-1]} peer group EVPN"
            neighbour2 = f" neighbor 10.10.10.{switch[-1]} description SPINE{switch[-1]}.LAB"

            vtep_bgp.extend([neighbour1, neighbour2])

    redistribute = ' redistribute connected'
    evpn_family = '!\n address-family evpn'
    evpn_active = '  neighbor EVPN activate\n'
    service = f'service routing protocols model multi-agent'

    vtep_bgp.extend([redistribute, evpn_family, evpn_active]) 
    vtep_bgp.insert(0,service)

    return vtep_bgp


# VXLAN EVPN VRF
def vxlan_vrf_config(hostname):
    
    vrf_config = [
                "vrf instance CUSTOMER1",
                "ip routing vrf CUSTOMER1",
                "vlan 20",
                "vlan 30",
                "interface Vlan20",
                "no autostate",
                "vrf CUSTOMER1",
                "ip address virtual 192.168.20.1/24",
                "interface Vlan30",
                "no autostate",
                "vrf CUSTOMER1",
                "ip address virtual 192.168.30.1/24",
                "interface Vxlan1",
                "vxlan vlan 20 vni 10020",
                "vxlan vlan 30 vni 10030",
                "vxlan vrf CUSTOMER1 vni 20120",
                f"router bgp 6511{hostname[-1]}",
                " vlan 20",
                f"rd 10.10.10.1{hostname[-1]}:20",
                "route-target both 20:20",
                "redistribute learned",
                "vlan 30",
                f"rd 10.10.10.1{hostname[-1]}:30",
                "route-target both 30:30",
                "redistribute learned",
                "vrf CUSTOMER1",
                f"rd 10.10.10.1{hostname[-1]}:20120",
                "route-target import evpn 20:120",
                "route-target export evpn 20:120",
                "route-target import evpn 30:130",
                "route-target export evpn 30:130",
                "redistribute connected",
                ]

    return vrf_config



# Save to the special location, see AEM post


if __name__ == '__main__':
    # introduce a wait period of 1 minute before executing so all switches are up and have basic hostnames
    time.sleep(60)
    hostname = get_hostname()
    switch_list = get_lldp_interfaces()

    # Standard config for all switches
    interfaces = interface_config(hostname, switch_list)
    underlay = underlay_config(hostname, switch_list)

    # Leaf specific config
    if "leaf" in hostname:
        vtep = vtep_config(hostname)
    
    # VXLAN config spine and leaf
    vxlan = vxlan_config(hostname, switch_list)

    if "leaf" in hostname:
        vrf = vxlan_vrf_config(hostname)


    # Save config to file
    with open('/mnt/flash/vxlan_config.cfg', 'w') as f:
        f.write('\n'.join(interfaces))
        f.write('\n'.join(underlay))
        if "leaf" in hostname:
            f.write('\n'.join(vtep))    
        f.write('\n'.join(vxlan))
        if "leaf" in hostname:
            f.write('\n'.join(vrf))
        # Remove VXLAN AEM
        f.write("\nno event-handler VXLAN_CONFIG")


    subprocess.Popen(["/usr/bin/FastCli", "-p 15", "-c", "copy flash:vxlan_config.cfg running-config"], stdout=subprocess.PIPE).communicate()[0]
    subprocess.Popen(["/usr/bin/FastCli", "-p 15", "-c", "wr mem"], stdout=subprocess.PIPE).communicate()[0]
    # Reload for multi-agent service
    subprocess.Popen(["/usr/bin/FastCli", "-p 15", "-c", "reload in 1 force reason VXLAN service multi-agent"], stdout=subprocess.PIPE).communicate()[0]
