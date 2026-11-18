"""Sken sítě. Jen ručně z editoru, jeden najednou. nmap -sn (ping sken): ve vlastní síti NAS jde
přes ARP, takže vrátí i MAC a výrobce. Párování s mapou dělá editor (zná strom, VLANy a typy zařízení)."""

import ipaddress
import os
import socket
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime

from .config import NMAP, SCAN_LAST, SCAN_MAX, SCAN_TIMEOUT
from .store import read_json, write_json

_scan = {'state': 'idle'}
_scan_lock = threading.Lock()


def default_net():
    """Síť NAS (/24) podle adresy, ze které jde provoz ven. Nic se neposílá, UDP connect jen vybere rozhraní."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1', 9))
            ip = s.getsockname()[0]
    except OSError:
        return []
    return [str(ipaddress.ip_network(ip + '/24', strict=False))]


def scan_nets():
    """SCAN_NETS = sítě oddělené čárkou nebo mezerou; jen platné IPv4 sítě, nejvýš /22 (1024 adres)."""
    raw = os.environ.get('SCAN_NETS', '').replace(',', ' ').split()
    nets = []
    for n in raw:
        try:
            net = ipaddress.ip_network(n, strict=False)
        except ValueError:
            continue
        if net.version == 4 and net.num_addresses <= SCAN_MAX:
            nets.append(str(net))
    return nets or default_net()


def nmap_cmd(nets):
    """Příkaz nmapu. Server neběží jako root: nmap má v Dockeru jen schopnost cap_net_raw
    (setcap), a aby ji použil (ARP), musí dostat --privileged."""
    cmd = [NMAP, '-sn', '-oX', '-']
    if hasattr(os, 'geteuid') and os.geteuid() != 0:
        cmd.append('--privileged')
    return cmd + nets


def parse_nmap(xml):
    """XML z nmap -oX → [{ip, mac, vendor, name}] jen pro zařízení, která odpověděla."""
    hosts = []
    for h in ET.fromstring(xml).iter('host'):
        st = h.find('status')
        if st is None or st.get('state') != 'up':
            continue
        r = {}
        for a in h.iter('address'):
            if a.get('addrtype') == 'ipv4':
                r['ip'] = a.get('addr')
            elif a.get('addrtype') == 'mac':
                r['mac'] = a.get('addr', '').lower()
                if a.get('vendor'):
                    r['vendor'] = a.get('vendor')
        hn = h.find('hostnames/hostname')
        if hn is not None and hn.get('name'):
            r['name'] = hn.get('name')
        if r.get('ip'):
            hosts.append(r)
    hosts.sort(key=lambda r: ipaddress.ip_address(r['ip']))
    return hosts


def scan_run(nets):
    """Běží ve vlákně. Výsledek (i chyba) jde do data/scan/last.json, ať ho editor najde i po obnovení."""
    at = datetime.now().isoformat(timespec='seconds')
    res = {'at': at, 'nets': nets, 'hosts': []}
    t = time.time()
    try:
        p = subprocess.run(nmap_cmd(nets), capture_output=True, text=True, timeout=SCAN_TIMEOUT)
        if p.returncode:
            raise RuntimeError(p.stderr.strip()[:300] or f'nmap skončil s kódem {p.returncode}')
        res['hosts'] = parse_nmap(p.stdout)
    except FileNotFoundError:
        res['error'] = 'nmap není nainstalovaný'
    except subprocess.TimeoutExpired:
        res['error'] = f'sken trval déle než {SCAN_TIMEOUT} s'
    except (RuntimeError, ET.ParseError) as e:
        res['error'] = str(e)
    res['secs'] = round(time.time() - t, 1)
    write_json(SCAN_LAST, res)
    with _scan_lock:
        _scan.clear()
        _scan['state'] = 'idle'


def scan_start():
    """False = sken už běží."""
    with _scan_lock:
        if _scan.get('state') == 'running':
            return False
        nets = scan_nets()
        _scan.update(state='running', since=datetime.now().isoformat(timespec='seconds'), nets=nets)
    threading.Thread(target=scan_run, args=(nets,), daemon=True).start()
    return True


def scan_state():
    with _scan_lock:
        s = dict(_scan)
    if s['state'] == 'idle':
        s.update(read_json(SCAN_LAST, {}))
        s.setdefault('nets', scan_nets())
    return s
