# Mapa sítě (16. 11. 2026 18:27:08)
Zařízení: 45 · spojů: 53 · ─ kabel, ⇢ bezdrát, [id] typ "název"

```
[inet1] Internet (WAN) "Internet" · přípojka:FTTH (GPON) · isp:Ukázkový ISP · rychlost:1000/500 Mb/s · veřejná ip:203.0.113.10 (statická) · místo:Technická místnost
└─ Optika ?→PON → [ont1] Modem / ONT "ONT" · místo:Technická místnost · porty:Linka (DSL/ONT/koax) PON, LAN · 1G 1
   └─ Cat6 1→WAN → [router1] Router "Router" · ip:10.0.10.1 · model:Ukázkový router 10G · místo:Technická místnost · vlany:10 Domácí 10.0.10.0/24, 20 IoT 10.0.20.0/24, 30 Kamery 10.0.30.0/24, 40 Hosté 10.0.40.0/24, 50 Práce 10.0.50.0/24 · porty:WAN · 2.5G, WAN · 1G WAN2, Uplink · SFP+ 10G SFP1, LAN · 1G · síť Domácí 1–4
      ├─ Cat6 WAN2→1 → [lte1] Modem / ONT "LTE modem" · ip:192.168.8.1 · místo:Technická místnost · pozn:Záložní připojení, router na něj přepne při výpadku optiky · porty:LAN · 1G 1
      │  └─ Jiné (LTE) → [inet2] Internet (WAN) "Internet záloha" · přípojka:LTE · isp:Ukázkový operátor · rychlost:150/50 Mb/s · veřejná ip:CGNAT · místo:Technická místnost
      └─ Cat6a SFP1→SFP1 (10G) → [sw1] Switch "Switch rack" · ip:10.0.10.2 · poe rozpočet W:180 · model:16port PoE+ s 4× SFP+ · místo:Technická místnost · porty:Uplink · SFP+ 10G SFP1, LAN · SFP+ 10G · síť Domácí SFP2,SFP3,SFP4, LAN · 1G · PoE+ · síť Domácí 1–6, LAN · 1G · PoE+ · síť IoT 7,8, LAN · 1G · PoE · síť Kamery 9–12, LAN · 1G · síť Domácí 13–16 · vlan≈Domácí, IoT, Kamery, Hosté (tag), Práce (tag)
         ├─ Optika SFP3→SFP1 (Venkovní optika do garáže, 40 m) → [sw3] Switch "Switch garáž" · ip:10.0.10.9 · poe rozpočet W:60 · model:5port PoE+ s SFP · místo:Garáž · porty:Uplink · SFP 1G SFP1, LAN · 1G · PoE+ · síť Kamery 1,2, LAN · 1G · síť IoT 3–5 · vlan≈Kamery, IoT, Domácí
         │  ├─ Cat6 1→? → [cam4] Kamera "Kamera garáž" · ip:10.0.30.14 · místo:Garáž · vlan≈Kamery
         │  ├─ Cat6 3→? → [ev1] IoT zařízení "Wallbox" · ip:10.0.20.30 · místo:Garáž · vlan≈IoT
         │  └─ Cat6 4→? → [fve1] IoT zařízení "Střídač FVE" · ip:10.0.20.31 · místo:Garáž · vlan≈IoT
         ├─ Cat6 1→1 → [ap1] Wi-Fi AP / mesh "AP přízemí" · mesh:hlavní (controller) · ip:10.0.10.11 · model:Wi-Fi 7 AP · místo:Obývák s kuchyní · porty:Uplink · 2.5G 1 · wifi:Domov (2.4+5 GHz, vlan Domácí), Domov-IoT (2.4 GHz, vlan IoT), Domov-Host (2.4+5 GHz, vlan Hosté), Práce (5 GHz, vlan Práce) · vlan≈Domácí, IoT (tag), Hosté (tag), Práce (tag)
         │  ├⇢ Wi-Fi mesh (páteř) [5 GHz, 1200 Mb/s] → [ap3] Wi-Fi AP / mesh "AP zahrada" · mesh:satelit (node) · ip:10.0.10.13 · model:Venkovní Wi-Fi AP · místo:Zahrada · pozn:Bez kabelu, páteř přes mesh · wifi:Domov (2.4+5 GHz, vlan Domácí), Domov-IoT (2.4 GHz, vlan IoT) · vlan≈Domácí, IoT (tag), Hosté (tag), Práce (tag)
         │  │  └⇢ Wi-Fi 2.4 GHz → [sprink1] IoT zařízení "Zavlažování" · ip:10.0.20.43 · místo:Zahrada · vlan:IoT
         │  ├⇢ Wi-Fi 5 GHz → [phone1] Telefon / tablet "Telefon (táta)" · ip:10.0.10.101 · místo:Ložnice · vlan≈Domácí
         │  ├⇢ Wi-Fi 2.4 GHz → [audio1] Audio / repro "Repro obývák" · ip:10.0.20.40 · místo:Obývák s kuchyní · vlan:IoT
         │  └⇢ Wi-Fi 2.4 GHz → [robot1] IoT zařízení "Robotický vysavač" · ip:10.0.20.41 · místo:Obývák s kuchyní · vlan:IoT
         ├─ Cat6 2→1 → [ap2] Wi-Fi AP / mesh "AP 1. patro" · mesh:satelit (node) · ip:10.0.10.12 · model:Wi-Fi 7 AP · místo:Schodiště · porty:Uplink · 2.5G 1 · wifi:Domov (2.4+5 GHz, vlan Domácí), Domov-IoT (2.4 GHz, vlan IoT), Domov-Host (2.4+5 GHz, vlan Hosté), Práce (5 GHz, vlan Práce) · vlan≈Domácí, IoT (tag), Hosté (tag), Práce (tag)
         │  ├⇢ Wi-Fi 6 GHz → [phone2] Telefon / tablet "Telefon (máma)" · ip:10.0.10.102 · místo:Ložnice · vlan≈Domácí
         │  ├⇢ Wi-Fi 5 GHz → [tab1] Telefon / tablet "Tablet děti" · ip:10.0.10.103 · místo:Dětský pokoj · vlan≈Domácí
         │  ├⇢ Wi-Fi 5 GHz → [tv2] Televize "Televize ložnice" · ip:10.0.10.105 · místo:Ložnice · vlan≈Domácí
         │  └⇢ Wi-Fi 5 GHz → [guest1] Telefon / tablet "Telefon hosta" · ip:10.0.40.100 · místo:Schodiště · vlan:Hosté
         ├─ Cat6 4× 13→1, 14→2, 15→3, 16→4 → [patch1] Patch panel "Patch panel" · místo:Technická místnost · pozn:Porty 1–4 vedou do pracovny, obýváku a chodby · porty:LAN 1–12 · vlan≈Domácí, Práce (tag)
         │  ├─ Cat6 ?→1 → [sw2] Switch "Switch pracovna" · ip:10.0.10.3 · model:8port 2.5G · místo:Pracovna · porty:Uplink · 2.5G 1, LAN · 2.5G · síť Práce 2–5, LAN · 1G · síť Domácí 6–8 · vlan≈Domácí, Práce
         │  │  ├─ Cat6 2→? → [pc1] Počítač "Pracovní PC" · ip:10.0.50.20 · místo:Pracovna · vlan≈Práce
         │  │  ├─ Cat6 3→? → [nb1] Notebook "Pracovní notebook" · ip:10.0.50.21 · místo:Pracovna · pozn:V dokovací stanici, jinak na Wi-Fi Práce · vlan≈Práce
         │  │  └─ Cat6 6→? → [p3d1] 3D tiskárna "3D tiskárna" · ip:10.0.10.40 · místo:Pracovna · vlan≈Domácí
         │  ├─ Cat6 → [tv1] Televize "Televize obývák" · ip:10.0.10.30 · místo:Obývák s kuchyní · vlan≈Domácí
         │  ├─ Cat6 → [game1] Konzole "Konzole" · ip:10.0.10.31 · místo:Obývák s kuchyní · vlan≈Domácí
         │  └─ Cat5e → [printer1] Tiskárna "Tiskárna" · ip:10.0.10.32 · místo:Chodba · vlan≈Domácí
         ├─ Cat6 4→? → [zbc1] Zigbee koordinátor "Zigbee koordinátor" · ip:10.0.10.7 · kanál:15 · místo:Chodba · pozn:Ethernet s PoE, uprostřed domu kvůli dosahu · vlan≈Domácí
         │  ├⇢ Zigbee → [zs1] Senzor "Teplota obývák" · místo:Obývák s kuchyní
         │  ├⇢ Zigbee → [zs2] Senzor "Pohyb chodba" · místo:Chodba
         │  ├⇢ Zigbee → [zs3] Senzor "Dveře vchod" · místo:Chodba
         │  └⇢ Zigbee → [zl1] IoT zařízení "Světla obývák" · místo:Obývák s kuchyní
         ├─ Cat6 7→? → [tbr1] Thread / Matter hub "Thread border router" · ip:10.0.20.3 · kanál:25 · místo:Obývák s kuchyní · vlan≈IoT
         │  ├⇢ Thread (Matter) → [th1] IoT zařízení "Termostat" · místo:Obývák s kuchyní
         │  └⇢ Thread (Matter) → [th2] Senzor "Vlhkost koupelna" · místo:Koupelna
         ├─ Cat6 3→? → [srv1] Server / HA "Home Assistant" · ip:10.0.10.6 · model:Mini PC · místo:Technická místnost · vlan≈Domácí
         ├─ Cat6a SFP2→SFP1 (10G) → [nas1] NAS "NAS" · ip:10.0.10.5 · model:4-bay NAS · místo:Technická místnost · pozn:Nahrává kamery (NVR) a zálohuje počítače · porty:LAN · SFP+ 10G SFP1, LAN · 1G 1,2 · vlan≈Domácí
         │  └─ USB → [ups1] UPS (záložní zdroj) "UPS rack" · výkon:1500 · výdrž min:25 · ip:10.0.10.4 · model:1500 VA, rack 2U · místo:Technická místnost · pozn:Při výpadku proudu pošle NAS přes USB povel k vypnutí · vlan≈Domácí
         ├─ Cat6 9→? → [cam1] Kamera "Kamera vjezd" · ip:10.0.30.11 · místo:Zahrada · vlan≈Kamery
         ├─ Cat6 10→? → [cam2] Kamera "Kamera zahrada" · ip:10.0.30.12 · místo:Zahrada · vlan≈Kamery
         └─ Cat6 11→? → [cam3] Kamera "Kamera terasa" · ip:10.0.30.13 · místo:Zahrada · vlan≈Kamery
```

## Porty (port→zařízení, ⚡ = PoE, VLAN: porty síť + tag tagované)
- [ont1] "ONT": 1→router1, PON→inet1
- [lte1] "LTE modem": 1→router1
- [router1] "Router": SFP1→sw1, WAN→ont1, WAN2→lte1 · volné: 1–4 · VLAN: 1–4 Domácí; SFP1 Domácí + tag IoT,Kamery,Hosté,Práce
- [sw1] "Switch rack": 1⚡→ap1 12W, 2⚡→ap2 12W, 3⚡→srv1, 4⚡→zbc1 3W, 7⚡→tbr1 3W, 9⚡→cam1 6W, 10⚡→cam2 6W, 11⚡→cam3 6W, 13→patch1, 14→patch1, 15→patch1, 16→patch1, SFP1→router1, SFP2→nas1, SFP3→sw3 · volné: 5,6,8,12,SFP4 · PoE odběr 48/180 W · VLAN: 1,2 Domácí + tag IoT,Hosté,Práce; 3–6,14–16,SFP2,SFP4 Domácí; 7,8 IoT; 9–12 Kamery; 13 Domácí + tag Práce; SFP1 Domácí + tag IoT,Kamery,Hosté,Práce; SFP3 Domácí + tag IoT,Kamery
- [patch1] "Patch panel": 1→sw1, 2→sw1, 3→sw1, 4→sw1 · volné: 5–12
- [nas1] "NAS": SFP1→sw1 · volné: 1,2
- [ap1] "AP přízemí": 1→sw1 12W
- [ap2] "AP 1. patro": 1→sw1 12W
- [sw2] "Switch pracovna": 1→patch1, 2→pc1, 3→nb1, 6→p3d1 · volné: 4,5,7,8 · VLAN: 1 Domácí + tag Práce; 2–5 Práce; 6–8 Domácí
- [sw3] "Switch garáž": 1⚡→cam4 6W, 3→ev1, 4→fve1, SFP1→sw1 · volné: 2,5 · PoE odběr 6/60 W · VLAN: 1,2 Kamery; 3–5 IoT; SFP1 Domácí + tag IoT,Kamery

## Patra
- Suterén: prostory Technická místnost; zařízení inet1, inet2, ont1, lte1, router1, ups1, sw1, patch1, nas1, srv1
- Přízemí: prostory Obývák s kuchyní, Chodba, Koupelna, Garáž; zařízení zbc1, tbr1, ap1, cam4, tv1, game1, printer1, surge1, sw3, ev1, fve1, audio1, robot1, zs1, zs2, zs3, zl1, th1, th2
- 1. patro: prostory Pracovna, Ložnice, Dětský pokoj, Schodiště; zařízení ap2, sw2, pc1, nb1, p3d1, surge2, phone1, phone2, tab1, tv2, guest1

## Napájení (zdroj ⚡→ spotřebič)
- [surge2] Přepěťová ochrana "Přepěťovka pracovna" · zásuvek:8 · absorpce J:2500 · místo:Pracovna
- [surge1] Přepěťová ochrana "Přepěťovka obývák" · zásuvek:6 · absorpce J:2000 · místo:Obývák s kuchyní
- ups1 ⚡→ ont1 Napájení DC (adaptér)
- ups1 ⚡→ lte1 Napájení DC (adaptér)
- ups1 ⚡→ router1 Napájení 230 V
- ups1 ⚡→ sw1 Napájení 230 V
- ups1 ⚡→ nas1 Napájení 230 V
- ups1 ⚡→ srv1 Napájení 230 V
- surge1 ⚡→ tv1 Napájení 230 V
- surge2 ⚡→ pc1 Napájení 230 V

## Firewall (shora dolů, první shoda vyhrává; zdroj → cíl, síť IP:port)
1. Povolit "HA ovládá IoT" vše: 10.0.10.6 → IoT (Home Assistant musí vidět chytrá zařízení)
2. Povolit "NAS nahrává kamery" TCP: 10.0.10.5 → Kamery:554 (RTSP streamy pro NVR)
3. Zakázat "Domácí STOP do IoT a Kamer" vše: Domácí → IoT, Kamery (Musí být pod výjimkami pro HA a NAS)
4. Povolit "Tisk z práce" TCP: Práce → 10.0.10.32:9100 (Výjimka musí být nad zákazem)
5. Zakázat "Práce jen do internetu" vše: Práce → Domácí, IoT, Kamery, Hosté (Pracovní zařízení nevidí domácí síť)
6. Zakázat "IoT STOP do Domácí" vše: IoT → Domácí
7. Povolit "Kamery NTP" UDP: Kamery → Internet:123 (Čas pro kamery)
8. Zakázat "Kamery STOP Internet" vše: Kamery → Internet
9. Zakázat "Hosté jen do internetu" vše: Hosté → Domácí, IoT, Kamery, Práce
10. (vypnuto) Povolit "Starý server" TCP: vše → 10.0.10.50:22 (Vypnuté, server už neexistuje)

## Přesměrování portů / UPnP (:vnější port → cílová IP:port)
- ruční "WireGuard na router" UDP :51820 → 10.0.10.1 (Vzdálený přístup do domácí sítě)
- UPnP "Konzole" UDP :3074 → 10.0.10.31

## Firewall: upozornění kontrol
- ⓘ pravidlo #10: IP 10.0.10.50 nemá v mapě žádné zařízení

## Firewall: poznámky
Ukázková pravidla. Pořadí = priorita, první shoda vyhrává.
