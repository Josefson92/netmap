# Anglická ukázka: ukazka/network.json -> ukazka-en/network.json (názvy, poznámky, sítě, SSID, prostory, firewall).
# Použití: python tools/ukazka-en.py  (po změně ukazka/; nový český text doplnit do M, jinak skript skončí se seznamem).
# layout.json a network.md pak udělá editor: načíst ukazka-en/ v angličtině, 🧭 Uspořádat, inet2 vedle LTE modemu, uložit.
import json, re, sys
from pathlib import Path
R = Path(__file__).resolve().parent.parent
M = {
 # VLAN a SSID
 'Domácí': 'Home', 'Kamery': 'Cameras', 'Hosté': 'Guests', 'Práce': 'Work',
 'Domov': 'Home', 'Domov-IoT': 'Home-IoT', 'Domov-Host': 'Home-Guest',
 # prostory
 'Suterén': 'Basement', 'Přízemí': 'Ground floor', '1. patro': '1st floor', 'Technická místnost': 'Utility room',
 'Obývák s kuchyní': 'Living room & kitchen', 'Chodba': 'Hallway', 'Koupelna': 'Bathroom', 'Pracovna': 'Office',
 'Ložnice': 'Bedroom', 'Dětský pokoj': "Kids' room", 'Schodiště': 'Staircase', 'Zahrada': 'Garden', 'Garáž': 'Garage',
 # zařízení
 'Internet záloha': 'Internet backup', 'Ukázkový ISP': 'Example ISP', 'Ukázkový operátor': 'Example carrier',
 '203.0.113.10 (statická)': '203.0.113.10 (static)', 'Ukázkový router 10G': 'Example router 10G',
 '16port PoE+ s 4× SFP+': '16-port PoE+ with 4× SFP+', '8port 2.5G': '8-port 2.5G', '5port PoE+ s SFP': '5-port PoE+ with SFP',
 'Venkovní Wi-Fi AP': 'Outdoor Wi-Fi AP',
 'Zigbee koordinátor': 'Zigbee coordinator', 'AP přízemí': 'AP ground floor', 'AP 1. patro': 'AP 1st floor', 'AP zahrada': 'AP garden',
 'Kamera vjezd': 'Camera driveway', 'Kamera zahrada': 'Camera garden', 'Kamera terasa': 'Camera terrace', 'Kamera garáž': 'Camera garage',
 'Switch pracovna': 'Switch office', 'Pracovní PC': 'Work PC', 'Pracovní notebook': 'Work laptop', '3D tiskárna': '3D printer',
 'Přepěťovka pracovna': 'Surge protector office', 'Televize obývák': 'TV living room', 'Konzole': 'Game console', 'Tiskárna': 'Printer',
 'Přepěťovka obývák': 'Surge protector living room', 'Switch garáž': 'Switch garage', 'Střídač FVE': 'Solar inverter',
 'Telefon (táta)': 'Phone (dad)', 'Telefon (máma)': 'Phone (mum)', 'Tablet děti': 'Kids tablet', 'Televize ložnice': 'TV bedroom',
 'Repro obývák': 'Speaker living room', 'Robotický vysavač': 'Robot vacuum', 'Zavlažování': 'Sprinklers', 'Telefon hosta': "Guest's phone",
 'Teplota obývák': 'Temperature living room', 'Pohyb chodba': 'Motion hallway', 'Dveře vchod': 'Front door', 'Světla obývák': 'Lights living room',
 'Termostat': 'Thermostat', 'Vlhkost koupelna': 'Humidity bathroom',
 # poznámky
 'Záložní připojení, router na něj přepne při výpadku optiky': 'Backup connection, the router fails over to it when the fibre goes down',
 'Při výpadku proudu pošle NAS přes USB povel k vypnutí': 'On a power cut it tells the NAS over USB to shut down',
 'Porty 1–4 vedou do pracovny, obýváku a chodby': 'Ports 1–4 run to the office, living room and hallway',
 'Nahrává kamery (NVR) a zálohuje počítače': 'Records the cameras (NVR) and backs up the computers',
 'Ethernet s PoE, uprostřed domu kvůli dosahu': 'Ethernet with PoE, in the middle of the house for range',
 'Bez kabelu, páteř přes mesh': 'No cable, mesh backhaul',
 'V dokovací stanici, jinak na Wi-Fi Práce': 'In the docking station, otherwise on the Work Wi-Fi',
 'Venkovní optika do garáže, 40 m': 'Outdoor fibre to the garage, 40 m',
 # firewall
 'HA ovládá IoT': 'HA controls IoT', 'Home Assistant musí vidět chytrá zařízení': 'Home Assistant must see the smart devices',
 'NAS nahrává kamery': 'NAS records cameras', 'RTSP streamy pro NVR': 'RTSP streams for the NVR',
 'Domácí STOP do IoT a Kamer': 'Home STOP to IoT and Cameras', 'Musí být pod výjimkami pro HA a NAS': 'Must be below the exceptions for HA and NAS',
 'Tisk z práce': 'Printing from Work', 'Výjimka musí být nad zákazem': 'The exception must be above the block',
 'Práce jen do internetu': 'Work only to the internet', 'Pracovní zařízení nevidí domácí síť': 'Work devices cannot see the home network',
 'IoT STOP do Domácí': 'IoT STOP to Home', 'Kamery NTP': 'Cameras NTP', 'Čas pro kamery': 'Time for the cameras',
 'Kamery STOP Internet': 'Cameras STOP internet', 'Hosté jen do internetu': 'Guests only to the internet',
 'Starý server': 'Old server', 'Vypnuté, server už neexistuje': 'Disabled, the server no longer exists',
 'WireGuard na router': 'WireGuard to the router', 'Vzdálený přístup do domácí sítě': 'Remote access to the home network',
 'Ukázková pravidla. Pořadí = priorita, první shoda vyhrává.': 'Example rules. Order = priority, the first match wins.',
}
# hodnoty ukládané česky (role portu, rychlost, PoE, mesh, pásma, akce firewallu, druh prostoru) a odkazy
KEEP = {'id', 't', 'wan', 'mrole', 'r', 's', 'poe', 'a', 'band', 'bands', 'k', 'ar', 'par', 'p', 'ic', 'pb', 'pa'}
CZ = re.compile(r'[áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]')
miss = set()


def tr(v):
    if v in M:
        return M[v]
    if ', ' in v and all(x in M or not CZ.search(x) for x in v.split(', ')):
        return ', '.join(M.get(x, x) for x in v.split(', '))
    if CZ.search(v):
        miss.add(v)
    return v


def walk(o, key=None):
    if isinstance(o, dict):
        return {k: walk(v, k) for k, v in o.items()}
    if isinstance(o, list):
        return [walk(x, key + '[]' if key else None) for x in o]  # pvl t:[…] = sítě, ne typ
    if isinstance(o, str) and key not in KEEP:
        return tr(o)
    return o


t = (R / 'ukazka' / 'network.json').read_text(encoding='utf-8')
out = walk(json.loads(t))
if miss:
    sys.exit('chybí: ' + repr(sorted(miss)))
# stejné formátování jako ukazka/network.json (řádek na zařízení, spoj, prostor, pravidlo)
lines = []
for ln in t.split('\n'):
    s = ln.rstrip(',')
    try:
        j = json.loads(s)
        lines.append(json.dumps(walk(j), ensure_ascii=False, separators=(',', ':')) + ln[len(s):])
    except ValueError:  # řádek s kusem struktury, např. "note":"…"}}
        lines.append(re.sub(r'"(\w+)":"([^"]*)"', lambda m: f'"{m[1]}":"{walk(m[2], m[1])}"', ln))
res = '\n'.join(lines)
if json.loads(res) != out:
    sys.exit('formát nesedí')
d = R / 'ukazka-en'
d.mkdir(exist_ok=True)
(d / 'network.json').write_text(res, encoding='utf-8', newline='')
print('ok')
