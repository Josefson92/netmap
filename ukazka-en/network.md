# Network map (11/17/2026, 11:39:58 AM)
Devices: 45 · links: 45 · ─ cable, ⇢ wireless, [id] type "name"

```
[inet1] Internet (WAN) "Internet" · connection:FTTH (GPON) · isp:Example ISP · speed:1000/500 Mb/s · public ip:203.0.113.10 (static) · location:Basement › Utility room
└─ Fiber ?→PON → [ont1] Modem / ONT "ONT" · location:Basement › Utility room · ports:Line (DSL/ONT/coax) PON, LAN · 1G 1
   └─ Cat6 1→WAN → [router1] Router "Router" · ip:10.0.10.1 · model:Example router 10G · location:Basement › Utility room · vlans:10 Home 10.0.10.0/24, 20 IoT 10.0.20.0/24, 30 Cameras 10.0.30.0/24, 40 Guests 10.0.40.0/24, 50 Work 10.0.50.0/24 · ports:WAN · 2.5G, WAN · 1G WAN2, Uplink · SFP+ 10G SFP1, LAN · 1G · network Home 1–4
      ├─ Cat6 WAN2→1 → [lte1] Modem / ONT "LTE modem" · ip:192.168.8.1 · location:Basement › Utility room · note:Backup connection, the router fails over to it when the fibre goes down · ports:LAN · 1G 1
      │  └─ Other (LTE) → [inet2] Internet (WAN) "Internet backup" · connection:LTE · isp:Example carrier · speed:150/50 Mb/s · public ip:CGNAT · location:Basement › Utility room
      └─ Cat6a SFP1→SFP1 (10G) → [sw1] Switch "Switch rack" · ip:10.0.10.2 · poe budget W:180 · model:16-port PoE+ with 4× SFP+ · location:Basement › Utility room · ports:Uplink · SFP+ 10G SFP1, LAN · SFP+ 10G · network Home SFP2,SFP3,SFP4, LAN · 1G · PoE+ · network Home 1–6, LAN · 1G · PoE+ · network IoT 7,8, LAN · 1G · PoE · network Cameras 9–12, LAN · 1G · network Home 13–16 · vlan≈Home, IoT, Cameras, Guests (tag), Work (tag)
         ├─ Fiber SFP3→SFP1 (Outdoor fibre to the garage, 40 m) → [sw3] Switch "Switch garage" · ip:10.0.10.9 · poe budget W:60 · model:5-port PoE+ with SFP · location:Garage · ports:Uplink · SFP 1G SFP1, LAN · 1G · PoE+ · network Cameras 1,2, LAN · 1G · network IoT 3–5 · vlan≈Cameras, IoT, Home
         │  ├─ Cat6 1→? → [cam4] Camera "Camera garage" · ip:10.0.30.14 · location:Garage · vlan≈Cameras
         │  ├─ Cat6 3→? → [ev1] IoT device "Wallbox" · ip:10.0.20.30 · location:Garage · vlan≈IoT
         │  └─ Cat6 4→? → [fve1] IoT device "Solar inverter" · ip:10.0.20.31 · location:Garage · vlan≈IoT
         ├─ Cat6 1→1 → [ap1] Wi-Fi AP / mesh "AP ground floor" · mesh:main (controller) · ip:10.0.10.11 · model:Wi-Fi 7 AP · location:Ground floor › Living room & kitchen · ports:Uplink · 2.5G 1 · wifi:Home (2.4+5 GHz, vlan Home), Home-IoT (2.4 GHz, vlan IoT), Home-Guest (2.4+5 GHz, vlan Guests), Work (5 GHz, vlan Work) · vlan≈Home, IoT (tag), Guests (tag), Work (tag)
         │  └⇢ Wi-Fi mesh (backhaul) [5 GHz, 1200 Mb/s] → [ap3] Wi-Fi AP / mesh "AP garden" · mesh:satellite (node) · ip:10.0.10.13 · model:Outdoor Wi-Fi AP · location:Garden · note:No cable, mesh backhaul · wifi:Home (2.4+5 GHz, vlan Home), Home-IoT (2.4 GHz, vlan IoT) · vlan≈Home, IoT (tag), Guests (tag), Work (tag)
         ├─ Cat6 2→1 → [ap2] Wi-Fi AP / mesh "AP 1st floor" · mesh:satellite (node) · ip:10.0.10.12 · model:Wi-Fi 7 AP · location:1st floor › Staircase · ports:Uplink · 2.5G 1 · wifi:Home (2.4+5 GHz, vlan Home), Home-IoT (2.4 GHz, vlan IoT), Home-Guest (2.4+5 GHz, vlan Guests), Work (5 GHz, vlan Work) · vlan≈Home, IoT (tag), Guests (tag), Work (tag)
         ├─ Cat6 4× 13→1, 14→2, 15→3, 16→4 → [patch1] Patch panel "Patch panel" · location:Basement › Utility room · note:Ports 1–4 run to the office, living room and hallway · ports:LAN 1–12 · vlan≈Home, Work (tag)
         │  ├─ Cat6 ?→1 → [sw2] Switch "Switch office" · ip:10.0.10.3 · model:8-port 2.5G · location:1st floor › Office · ports:Uplink · 2.5G 1, LAN · 2.5G · network Work 2–5, LAN · 1G · network Home 6–8 · vlan≈Home, Work
         │  │  ├─ Cat6 2→? → [pc1] Computer "Work PC" · ip:10.0.50.20 · location:1st floor › Office · vlan≈Work
         │  │  ├─ Cat6 3→? → [nb1] Laptop "Work laptop" · ip:10.0.50.21 · location:1st floor › Office · note:In the docking station, otherwise on the Work Wi-Fi · vlan≈Work
         │  │  └─ Cat6 6→? → [p3d1] 3D printer "3D printer" · ip:10.0.10.40 · location:1st floor › Office · vlan≈Home
         │  ├─ Cat6 → [tv1] TV "TV living room" · ip:10.0.10.30 · location:Ground floor › Living room & kitchen · vlan≈Home
         │  ├─ Cat6 → [game1] Console "Game console" · ip:10.0.10.31 · location:Ground floor › Living room & kitchen · vlan≈Home
         │  └─ Cat5e → [printer1] Printer "Printer" · ip:10.0.10.32 · location:Ground floor › Hallway · vlan≈Home
         ├─ Cat6 4→? → [zbc1] Zigbee coordinator "Zigbee coordinator" · ip:10.0.10.7 · channel:15 · location:Ground floor › Hallway · note:Ethernet with PoE, in the middle of the house for range · vlan≈Home
         │  ├⇢ Zigbee → [zs1] Sensor "Temperature living room" · location:Ground floor › Living room & kitchen
         │  ├⇢ Zigbee → [zs2] Sensor "Motion hallway" · location:Ground floor › Hallway
         │  ├⇢ Zigbee → [zs3] Sensor "Front door" · location:Ground floor › Hallway
         │  └⇢ Zigbee → [zl1] IoT device "Lights living room" · location:Ground floor › Living room & kitchen
         ├─ Cat6 7→? → [tbr1] Thread / Matter hub "Thread border router" · ip:10.0.20.3 · channel:25 · location:Ground floor › Living room & kitchen · vlan≈IoT
         │  ├⇢ Thread (Matter) → [th1] IoT device "Thermostat" · location:Ground floor › Living room & kitchen
         │  └⇢ Thread (Matter) → [th2] Sensor "Humidity bathroom" · location:Ground floor › Bathroom
         ├─ Cat6 3→? → [srv1] Server / HA "Home Assistant" · ip:10.0.10.6 · model:Mini PC · location:Basement › Utility room · vlan≈Home
         ├─ Cat6a SFP2→SFP1 (10G) → [nas1] NAS "NAS" · ip:10.0.10.5 · model:4-bay NAS · location:Basement › Utility room · note:Records the cameras (NVR) and backs up the computers · ports:LAN · SFP+ 10G SFP1, LAN · 1G 1,2 · vlan≈Home
         │  └─ USB → [ups1] UPS (backup power) "UPS rack" · power:1500 · runtime min:25 · ip:10.0.10.4 · model:1500 VA, rack 2U · location:Basement › Utility room · note:On a power cut it tells the NAS over USB to shut down
         ├─ Cat6 9→? → [cam1] Camera "Camera driveway" · ip:10.0.30.11 · location:Garden · vlan≈Cameras
         ├─ Cat6 10→? → [cam2] Camera "Camera garden" · ip:10.0.30.12 · location:Garden · vlan≈Cameras
         └─ Cat6 11→? → [cam3] Camera "Camera terrace" · ip:10.0.30.13 · location:Garden · vlan≈Cameras
```

## Wi-Fi (SSID and its clients, Wi-Fi is not drawn as a link)
- "Home" (2.4+5 GHz · vlan Home · broadcast by ap1, ap2, ap3)
  - [phone1] Phone / tablet "Phone (dad)" · ip:10.0.10.101 · ssid:Home · location:1st floor › Bedroom · vlan≈Home
  - [phone2] Phone / tablet "Phone (mum)" · ip:10.0.10.102 · ssid:Home · bands:2.4+5+6 GHz · location:1st floor › Bedroom · vlan≈Home
  - [tab1] Phone / tablet "Kids tablet" · ip:10.0.10.103 · ssid:Home · location:1st floor › Kids' room · vlan≈Home
  - [tv2] TV "TV bedroom" · ip:10.0.10.105 · ssid:Home · location:1st floor › Bedroom · vlan≈Home
- "Home-IoT" (2.4 GHz · vlan IoT · broadcast by ap1, ap2, ap3)
  - [audio1] Audio / speaker "Speaker living room" · ip:10.0.20.40 · ssid:Home-IoT · location:Ground floor › Living room & kitchen · vlan≈IoT
  - [robot1] IoT device "Robot vacuum" · ip:10.0.20.41 · ssid:Home-IoT · location:Ground floor › Living room & kitchen · vlan≈IoT
  - [sprink1] IoT device "Sprinklers" · ip:10.0.20.43 · ssid:Home-IoT · location:Garden · vlan≈IoT
- "Home-Guest" (2.4+5 GHz · vlan Guests · broadcast by ap1, ap2)
  - [guest1] Phone / tablet "Guest's phone" · ip:10.0.40.100 · ssid:Home-Guest · location:1st floor › Staircase · vlan≈Guests
- "Work" (5 GHz · vlan Work · broadcast by ap1, ap2): no clients

## Ports (port→device, ⚡ = PoE, VLAN: ports network + tag tagged)
- [ont1] "ONT": 1→router1, PON→inet1
- [lte1] "LTE modem": 1→router1
- [router1] "Router": SFP1→sw1, WAN→ont1, WAN2→lte1 · free: 1–4 · VLAN: 1–4 Home; SFP1 Home + tag IoT,Cameras,Guests,Work
- [sw1] "Switch rack": 1⚡→ap1 12W, 2⚡→ap2 12W, 3⚡→srv1, 4⚡→zbc1 3W, 7⚡→tbr1 3W, 9⚡→cam1 6W, 10⚡→cam2 6W, 11⚡→cam3 6W, 13→patch1, 14→patch1, 15→patch1, 16→patch1, SFP1→router1, SFP2→nas1, SFP3→sw3 · free: 5,6,8,12,SFP4 · PoE draw 48/180 W · VLAN: 1,2 Home + tag IoT,Guests,Work; 3–6,14–16,SFP2,SFP4 Home; 7,8 IoT; 9–12 Cameras; 13 Home + tag Work; SFP1 Home + tag IoT,Cameras,Guests,Work; SFP3 Home + tag IoT,Cameras
- [patch1] "Patch panel": 1→sw1, 2→sw1, 3→sw1, 4→sw1 · free: 5–12
- [nas1] "NAS": SFP1→sw1 · free: 1,2
- [ap1] "AP ground floor": 1→sw1 12W
- [ap2] "AP 1st floor": 1→sw1 12W
- [sw2] "Switch office": 1→patch1, 2→pc1, 3→nb1, 6→p3d1 · free: 4,5,7,8 · VLAN: 1 Home + tag Work; 2–5 Work; 6–8 Home
- [sw3] "Switch garage": 1⚡→cam4 6W, 3→ev1, 4→fve1, SFP1→sw1 · free: 2,5 · PoE draw 6/60 W · VLAN: 1,2 Cameras; 3–5 IoT; SFP1 Home + tag IoT,Cameras

## Areas (devices directly in the area)
- Basement (floor)
  - Utility room: inet1, inet2, ont1, lte1, router1, ups1, sw1, patch1, nas1, srv1
- Ground floor (floor)
  - Living room & kitchen: tbr1, ap1, tv1, game1, surge1, audio1, robot1, zs1, zl1, th1
  - Hallway: zbc1, printer1, zs2, zs3
  - Bathroom: th2
- 1st floor (floor)
  - Office: sw2, pc1, nb1, p3d1, surge2
  - Bedroom: phone1, phone2, tv2
  - Kids' room: tab1
  - Staircase: ap2, guest1
- Garden (outdoor): ap3, cam1, cam2, cam3, sprink1
- Garage (building): cam4, sw3, ev1, fve1

## Power (source ⚡→ load)
- [surge2] Surge protector "Surge protector office" · outlets:8 · absorption J:2500 · location:1st floor › Office
- [surge1] Surge protector "Surge protector living room" · outlets:6 · absorption J:2000 · location:Ground floor › Living room & kitchen
- ups1 ⚡→ ont1 Power DC (adapter)
- ups1 ⚡→ lte1 Power DC (adapter)
- ups1 ⚡→ router1 Power 230 V
- ups1 ⚡→ sw1 Power 230 V
- ups1 ⚡→ nas1 Power 230 V
- ups1 ⚡→ srv1 Power 230 V
- surge1 ⚡→ tv1 Power 230 V
- surge2 ⚡→ pc1 Power 230 V

## Firewall (top to bottom, first match wins; source → destination, network IP:port)
1. Allow "HA controls IoT" all: 10.0.10.6 → IoT (Home Assistant must see the smart devices)
2. Allow "NAS records cameras" TCP: 10.0.10.5 → Cameras:554 (RTSP streams for the NVR)
3. Deny "Home STOP to IoT and Cameras" all: Home → IoT, Cameras (Must be below the exceptions for HA and NAS)
4. Allow "Printing from Work" TCP: Work → 10.0.10.32:9100 (The exception must be above the block)
5. Deny "Work only to the internet" all: Work → Home, IoT, Cameras, Guests (Work devices cannot see the home network)
6. Deny "IoT STOP to Home" all: IoT → Home
7. Allow "Cameras NTP" UDP: Cameras → Internet:123 (Time for the cameras)
8. Deny "Cameras STOP internet" all: Cameras → Internet
9. Deny "Guests only to the internet" all: Guests → Home, IoT, Cameras, Work
10. (disabled) Allow "Old server" TCP: all → 10.0.10.50:22 (Disabled, the server no longer exists)

## Port forwarding / UPnP (:external port → destination IP:port)
- manual "WireGuard to the router" UDP :51820 → 10.0.10.1 (Remote access to the home network)
- UPnP "Game console" UDP :3074 → 10.0.10.31

## Firewall: check warnings
- ⓘ rule #10: no device on the map has IP 10.0.10.50

## Firewall: notes
Example rules. Order = priority, the first match wins.
