#!/usr/bin/python

from collections import Counter
import subprocess
import sys
import time

# Delay for a 60 seconds
time.sleep(60)
output = subprocess.Popen(["/usr/bin/FastCli", "-c", "show lldp neigh"], stdout=subprocess.PIPE).communicate()[0]
out2 = list(iter(output.decode().split()))

# Count interfaces for spine
lookup = ["Ethernet1", "Ethernet2", "Ethernet3", "Ethernet4"]
all_counts = Counter(out2)
counts = {k: all_counts[k] for k in lookup}
print(f"all counts {all_counts}")
print(f"counts {counts}")
print(f"counts {counts.values()}")

# Determine if spine or leaf
for value in counts.values():
    print(value)
    if value >= 4:
        switch = "spine"
        break
    else:
        switch = "leaf"

# Determine spine number
for key, value in counts.items():
    if value >= 4:
        spine_num = key[8:]
        break

# Assing spine number hostname and IP
if switch == "spine":
    hostname = "spine{}".format(spine_num)
    ip_addr = "172.17.3.10{}".format(spine_num)

# Determine and assign leaf hostname and IP
if switch == "leaf":
    out3 = list(iter(output.decode().splitlines()))
    intnum = out3[8].split()[2][8:]
    hostname = "leaf{}".format(intnum)
    ip_addr = "172.17.3.{}".format(intnum)


# Add AEM for vxlan python script
# download python script from tftp
# create AEM


# Create startup-config file
f = open("/mnt/flash/startup-config", "w")
f.write("\nhostname {}".format(hostname))
f.write("\ninterface Management1\nip address {}/24".format(ip_addr))
f.write("\nip routing")
f.write("\nip route 0.0.0.0/0 172.17.3.254")
# Remove AEM ZTP1
f.write("\nno event-handler ZTP1")
# Add AEM for VXLAN
f.write("\nevent-handler VXLAN_CONFIG")
f.write("\ntrigger on-startup-config")
# Reload switch to run VXLAN AEM
f.write("\n action bash python3 /mnt/flash/AEM_VXLAN_DeviceReady.py; `FastCli -p 15 -c 'reload in 1 force reason VXLAN Configuration'`")

f.close()
sys.exit( 0 )
