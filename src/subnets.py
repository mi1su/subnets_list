import ipaddress
import urllib.request
import json
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

def get_networks_from_url(name, url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')
            
            if name == 'aws' or url.endswith('.json'):
                data = json.loads(content)
                res = []
                if 'prefixes' in data:
                    res += [p['ip_prefix'] for p in data['prefixes']]
                if 'ipv6_prefixes' in data:
                    res += [p['ipv6_prefix'] for p in data['ipv6_prefixes']]
                return res
            
            return content.splitlines()
    except Exception as e:
        print(f"Warning: Could not load {name} from {url} - {e}")
        return []

def fast_aggregate(ip_set):
    """Sorts and collapses networks."""
    if not ip_set: return []
    nets = []
    for n in ip_set:
        try:
            nets.append(ipaddress.ip_network(n.strip(), strict=False))
        except: continue
    nets.sort()
    return [str(n) for n in ipaddress.collapse_addresses(nets)]

def main():
    ipv4_set = set()
    ipv6_set = set()

    # 1. Fetch from official URL lists
    print("Loading official CIDR lists...")
    for name, url in URLS.items():
        ips = get_networks_from_url(name, url)
        for ip in ips:
            if ':' in ip: ipv6_set.add(ip)
            else: ipv4_set.add(ip)

    if os.path.exists(AS_CONFIG):
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
                    if len(parts) < 2: continue
                    asn = parts[1][2:] if parts[1].lower().startswith('as') else parts[1]
                    if asn in target_asns:
                        if ':' in parts[0]: ipv6_set.add(parts[0])
                        else: ipv4_set.add(parts[0])

    # 3. Collapse and Save
    print("Collapsing networks...")
    os.makedirs('subnets', exist_ok=True)
    
    v4_list = fast_aggregate(ipv4_set)
    v6_list = fast_aggregate(ipv6_set)
    
    total_count = len(v4_list) + len(v6_list)

    with open('subnets/ipv4.lst', 'w') as f: f.write('\n'.join(v4_list))
    with open('subnets/ipv6.lst', 'w') as f: f.write('\n'.join(v6_list))

    print(f"Success! Total: {total_count} (IPv4: {len(v4_list)}, IPv6: {len(v6_list)})")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)