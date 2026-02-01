import ipaddress
import urllib.request
import os
import sys

BGP_TOOLS_URL = 'https://bgp.tools/table.txt'
AS_CONFIG = 'src/as_numbers.lst'
HEADERS = { 'User-Agent': 'github-actions[bot] (+https://github.com/mi1su/subnets_list)' }

URLS = {
    'aws': 'https://ip-ranges.amazonaws.com/ip-ranges.json',
    'cloudflare_v4': 'https://www.cloudflare.com/ips-v4',
    'cloudflare_v6': 'https://www.cloudflare.com/ips-v6',
    'discord_v4': 'https://iplist.opencck.org/?format=text&data=cidr4&site=discord.gg&site=discord.media',
    'discord_v6': 'https://iplist.opencck.org/?format=text&data=cidr6&site=discord.gg&site=discord.media',
    'telegram': 'https://core.telegram.org/resources/cidr.txt'
}

def get_networks_from_url(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"Warning: Could not load {url} - {e}")
        return []

def fast_aggregate(ip_set):
    """Sorts and collapses networks."""
    if not ip_set: return []
    nets = []
    for n in ip_set:
        try:
            nets.append(ipaddress.ip_network(n, strict=False))
        except: continue
    nets.sort()
    return [str(n) for n in ipaddress.collapse_addresses(nets)]

def main():
    ipv4_set = set()
    ipv6_set = set()

    # 1. Fetch from official URL lists
    print("Loading official CIDR lists...")
    for name, url in URLS.items():
        ips = get_networks_from_url(url)
        for ip in ips:
            ip = ip.strip()
            if not ip or ip.startswith('#'): continue
            if ':' in ip: ipv6_set.add(ip)
            else: ipv4_set.add(ip)

    # 2. Fetch from BGP table by ASNs
    if not os.path.exists(AS_CONFIG):
        print(f"Error: {AS_CONFIG} not found!")
        return

    target_asns = set()
    with open(AS_CONFIG, 'r') as f:
        for line in f:
            if ':' in line and not line.startswith('#'):
                asns = line.strip().split(':')[1].split(',')
                target_asns.update([''.join(filter(str.isdigit, a)) for a in asns])
    
    if target_asns:
        print(f"Streaming BGP table for {len(target_asns)} ASNs...")
        req = urllib.request.Request(BGP_TOOLS_URL, headers=HEADERS)
        with urllib.request.urlopen(req) as resp:
            for line in resp:
                parts = line.decode('utf-8').split()
                if len(parts) < 2:
                    continue
                asn = parts[1]
                if asn.startswith(('AS', 'as')):
                    asn = asn[2:]
                if asn in target_asns:
                    prefix = parts[0]
                    if ':' in prefix:
                        ipv6_set.add(prefix)
                    else:
                        ipv4_set.add(prefix)

    # 3. Collapse and Save
    print("Collapsing networks...")
    os.makedirs('subnets', exist_ok=True)
    
    v4_list = fast_aggregate(ipv4_set)
    v6_list = fast_aggregate(ipv6_set)
    
    total_count = len(v4_list) + len(v6_list)

    # Raw lists
    with open('subnets/ipv4.lst', 'w') as f: f.write('\n'.join(v4_list))
    with open('subnets/ipv6.lst', 'w') as f: f.write('\n'.join(v6_list))

    # Dnsmasq format (ipset)
    with open('subnets/dnsmasq_subnets.lst', 'w') as f:
        for net in v4_list:
            f.write(f"ipset=/{net}/vpn_subnets\n")

    print(f"Success! Total: {total_count} (IPv4: {len(v4_list)}, IPv6: {len(v6_list)})")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)