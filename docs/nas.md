# Server: mapa na NAS (Docker)

Cíl: `mapa.html` se otevře ze serveru v prohlížeči na libovolném počítači v síti. Data leží na serveru a mají zálohy. Server umí proskenovat síť a porovnat výsledek s mapou.
Editor zůstává jeden soubor bez závislostí a dá se používat i bez serveru (složka 📁 nebo jen prohlížeč).

Návod je psaný pro Synology (Container Manager), ale server je obyčejný Docker kontejner a poběží na libovolném Linuxu.

## Rozhodnutí v kostce

| Otázka | Volba | Proč |
|---|---|---|
| Backend | **Python + FastAPI** (uvicorn), jeden soubor `server/app.py` | Malý a čitelný kód, sken je stejně volání `nmap`. |
| network.md | **generuje prohlížeč** (`md()`), server ho jen uloží | Logika zůstane na jednom místě. Server data nikdy sám nemění, takže md nemůže zastarat. |
| Párování skenu | **v prohlížeči**, server vrací jen seznam nalezených | Porovnání potřebuje strom, VLANy a typy zařízení, a ty zná editor. |
| Síť kontejneru | `network_mode: host` + `cap_add: NET_RAW, NET_ADMIN` | ARP sken funguje jen na vlastním L2 segmentu, z bridge sítě Dockeru by viděl jen sebe. |
| Přístup | jen z LAN/VPN, bez přesměrování portu z internetu, **přihlášení heslem**, 2FA (TOTP) volitelně | Data obsahují IP, MAC a firewall. Basic auth 2FA neumí, proto vlastní přihlašovací stránka a cookie. |

## Úložiště v editoru

Editor má tři úložiště se stejným rozhraním (`name`, `get() → {net, lay} | null`, `put({net, lay, md})`): `stLocal` (localStorage), `stDir` (složka) a `stHttp` (server).

- Při startu: když stránka běží přes `http(s)` a `GET api/health` odpoví, editor pracuje se serverem a tlačítko 📁 ukáže `🖧 NAS`. Jinak vše funguje lokálně (složka z IndexedDB nebo prohlížeč).
- `stLocal` se zapisuje vždy jako záloha.
- **Souběžné úpravy** (víc počítačů): `get` vrátí i `rev` (otisk obsahu `net` + `lay`), `put` ho posílá v `If-Match`. Když se data mezitím změnila jinde, server vrátí `409` a editor obě verze třícestně sloučí (zařízení, spoje a prostory po polích). Kdyby to nešlo, stavový řádek nabídne „Načíst z NAS“ (zahodí místní změny) nebo „Přepsat NAS mou verzí“.

## Objekty

Data jsou po objektech (dům, chata, kancelář…). Každý objekt má složku `data/<id>/` s vlastními soubory a zálohami. Editor bez `?o=` v adrese ukáže přehled objektů a objekt otevírá jako `mapa.html?o=<id>`. Data v prohlížeči (localStorage) má po objektech s příponou `@id`.

Na prázdném serveru se při prvním otevření přehledu založí prázdný objekt „Domov“ (označený „tady je NAS“) a objekt „Ukázka“ s fiktivní sítí ze složky `ukazka/`. Pro anglický prohlížeč jsou to „Home“ a „Demo“ ze složky `ukazka-en/`. Ukázku jde kdykoli založit znovu příkazem `python app.py demo` (`demo cs` / `demo en`).

## Jazyk

Přihlašovací a nastavovací stránka jsou česky nebo anglicky: platí ruční volba z editoru (cookie `netmapLang`, editor ji nastaví po přepnutí jazyka), jinak první jazyk prohlížeče (`Accept-Language`; cs/sk = čeština, jinak angličtina). Na přihlašovací stránce je přepínač CZ/EN. Příkazy v terminálu (`passwd`, `2fa`, `demo`) mluví podle `NETMAP_LANG` (`cs`/`en`), jinak podle `LANG`, bez nich anglicky.

## API

Všechno je pod `/api/` a data se posílají jako text (stejné soubory jako ve složce `data/`).

| Metoda | Cesta | Co dělá |
|---|---|---|
| GET | `/api/objects` | `[{id, name, desc, nas, devices, changed}]`, objekt s NAS první, pak podle názvu |
| POST | `/api/objects` | `{name, desc?}` → `201` a údaje nového objektu; id vznikne z názvu (bez diakritiky, `chata-lipno`, obsazené dostane `-2`) |
| GET | `/api/objects/{id}` | údaje jednoho objektu |
| PATCH | `/api/objects/{id}` | `{name?, desc?, nas?, img?}` (img = vlastní obrázek náhledu jako data URL do 500 kB, `''` = náhled z topologie): přejmenování (id se nemění), popisek, značka NAS (smí mít jen jeden objekt) |
| DELETE | `/api/objects/{id}` | přesune složku do `data/_deleted/<id>_<čas>/` |
| GET | `/api/objects/{id}/data` | `{net, lay, rev}`, nebo `404`, když data ještě nejsou |
| PUT | `/api/objects/{id}/data` | tělo `{net, lay, md}`, hlavička `If-Match: rev` → `{rev}` / `409` |
| GET | `/api/objects/{id}/backups` | seznam záloh `[{id, at, size}]` |
| GET | `/api/objects/{id}/backups/{bid}` | `{net, lay}` zálohy |
| POST | `/api/objects/{id}/backups` | záloha současné verze hned (editor ji dělá před obnovou) → `{id}`; shodnou s poslední zálohou nezdvojí |
| DELETE | `/api/objects/{id}/backups/{bid}` | smazání zálohy |
| POST | `/api/objects/{id}/scan` | spustí sken (jeden najednou), `202`; jen objekt s NAS, jinak `403` |
| GET | `/api/objects/{id}/scan` | `{state: idle/running, at, hosts: [{ip, mac, name, vendor}]}` |
| GET | `/api/health` | pro Docker healthcheck (jediné bez přihlášení) |
| POST | `/api/login` | `{user, pass, code?}` → cookie `netmap_s`; `401` / `{need: 'code'}` |
| POST | `/api/logout` | smaže relaci |

Cesty bez objektu (`/api/data`, `/api/backups…`, `/api/scan`) platí pro objekt označený „tady je NAS“.

Statické soubory: `/` → `mapa.html` ze složky připojené jako volume. Nová verze editoru = přepsat soubor, bez přestavby image. `/docs` (OpenAPI) je vypnuté, aby nic nešlo bez přihlášení.

Server před zápisem zkontroluje, že `net` a `lay` jsou platný JSON (`net` má `devices`). Zapisuje atomicky (`*.tmp` a pak `os.replace`), takže výpadek uprostřed zápisu soubory nepoškodí.

## Přihlášení a 2FA

- Bez platné relace vrací server místo `/` malou přihlašovací stránku a API odpovídá `401`.
- Účet je jeden, uložený v `config/auth.json` (mimo `data/`, takže se nezálohuje spolu s mapou a nedostane se do exportu): `{user, hash, totp?}`. Heslo je hashované přes `hashlib.scrypt` se solí.
- Nastavení se dělá z příkazové řádky kontejneru (Container Manager → Terminál, nebo `docker exec -it netmap …`):
  - `python app.py passwd`: nastaví jméno a heslo (aspoň 10 znaků) a odhlásí všechny relace; dokud heslo není, server ukazuje jen nastavovací stránku;
  - `python app.py 2fa on`: vygeneruje tajný klíč, vypíše `otpauth://` odkaz a QR kód pro aplikaci (Google Authenticator, Aegis, 1Password…). 2FA se zapne až po zadání prvního platného kódu;
  - `python app.py 2fa off`: 2FA vypne;
  - `python app.py demo`: založí objekt „Ukázka“ s fiktivní sítí.
- TOTP podle RFC 6238 (30 s, 6 číslic, tolerance ±1 krok), bez knihovny.
- Relace: náhodný token v cookie `HttpOnly`, `SameSite=Strict` (a `Secure` za HTTPS), platnost 30 dní, přežije restart kontejneru (`config/sessions.json`).
- Ochrana proti hádání: po 5 špatných pokusech z jedné IP čeká další pokus 1 minutu, s každou další chybou se čekání zdvojnásobí.
- Když relace vyprší, editor přesměruje na přihlášení. Neuložené změny jsou v localStorage a po přihlášení se uloží.

## Soubory na serveru

```
netmap/
  docker-compose.yml
  server/        app.py, Dockerfile, requirements.txt
  ukazka/        network.json, layout.json (ukázková síť pro objekt „Ukázka“)
  ukazka-en/     totéž anglicky (objekt „Demo“)
  www/           mapa.html
  config/        auth.json, sessions.json
  data/
    domov/       meta.json ({name, desc, nas}), network.json, layout.json, network.md
      backup/    2026-11-20_143005/{network.json, layout.json, network.md}
    ukazka/      … další objekty stejně
    scan/        last.json (sken je jeden pro celý server)
    _deleted/    smazané objekty
```

## Zálohy

- Každý objekt má vlastní zálohy (`data/<id>/backup/`).
- Editor ukládá 0,7 s po každé změně, proto se záloha nedělá při každém zápisu: server zkopíruje **předchozí** verzi do `backup/<čas>/` jen na začátku úprav, tj. když se data aspoň 30 minut neměnila (`BACKUP_IDLE`). Jedny úpravy = jedna záloha. Záloha shodná s poslední se nedělá.
- Nechávají se 4 nejnovější zálohy (`BACKUP_KEEP`).
- Obnova je v editoru: ⋯ → 🕘 Zálohy (porovnání se současnou verzí, obnovu jde vrátit Ctrl+Z).
- Celá složka `netmap/` může navíc jít do Hyper Backup nebo snapshotů Btrfs. To je mimo aplikaci.

## Docker

- Image se staví z `server/Dockerfile` (základ `python:3.12-slim`, kontext je kořen repozitáře kvůli složkám `ukazka/` a `ukazka-en/`).
- V image je `nmap`. Kontejner běží jako root kvůli raw socketům, jinak nic nepotřebuje.
- `network_mode: host`, port **8780** (nastavitelný `PORT`). Na Synology obsazuje DSM 5000/5001 a 80/443.
- Volumes: `./www:/app/www:ro`, `./data:/app/data`, `./config:/app/config`.
- Proměnné: `PORT`, `SCAN_NETS` (co skenovat, např. `192.168.1.0/24`; bez toho /24 hlavního rozhraní, víc než /22 server odmítne), `TZ`.
- Reverzní proxy (na Synology `https://netmap.<nas>` s certifikátem) je **doporučená**: kvůli přihlášení, jinak by heslo a cookie šly po síti otevřeně.

## Nasazení na Synology

1. **Složka:** na PC sestavit `netmap/` (struktura výše): `docker-compose.yml`, `server/`, `ukazka/` a `ukazka-en/` z repozitáře, `www/mapa.html`, prázdné `data/` a `config/`. V File Station otevřít sdílenou složku `docker` a složku `netmap` do ní přetáhnout. Kdo už má mapu ve složce `data/` z lokálního režimu, dá `network.json` a `layout.json` rovnou do `data/` a server je při prvním startu převede na objekt „Domov“.
2. **Projekt:** Container Manager → Projekt → Vytvořit: název `netmap`, cesta `/docker/netmap`, zdroj „Použít existující docker-compose.yml“, portál Web Station nezapínat. Image se postaví na NAS (potřebuje internet, pár minut).
3. **Heslo:** Container Manager → Kontejner → `netmap` → Podrobnosti → Terminál → Vytvořit ▾ → Spustit příkazem: `python app.py passwd`.
4. **Firewall DSM** (jen když je zapnutý): povolit TCP 8780 z domácí sítě (a z VPN, pokud ji používáš).
5. **Ověření:** `http://<adresa NAS>:8780/`, přihlásit se, otevřít objekt, něco posunout a ve File Station ověřit čas změny `data/<objekt>/layout.json`.

**Aktualizace:** nový editor = v File Station přepsat `www/mapa.html` (stačí obnovit stránku). Změna serveru = přepsat soubory v `server/`, pak Projekt → `netmap` → Akce → Zastavit, Sestavit a Spustit.

Jinde než na Synology: `docker compose up -d --build` ve složce `netmap/` a pak `docker exec -it netmap python app.py passwd`.

## Lokální test

```
docker build -t netmap-test -f server/Dockerfile .
docker run -d --name netmap-test -p 8782:8780 -v <www>:/app/www:ro -v <data>:/app/data -v <config>:/app/config netmap-test
docker exec -it netmap-test python app.py passwd
```

Pak `http://127.0.0.1:8782/`. Pro test nepoužívat skutečnou složku `data/`.

## Sken sítě a porovnání s mapou

**Sken (server):** spouští se ručně tlačítkem v editoru (⋯ → 🔍 Sken sítě…) a jen u objektu označeného „tady je NAS“. Server spustí `nmap -sn -oX - <SCAN_NETS>`. Ve vlastní síti použije nmap ARP a vrátí MAC a výrobce. Sítě za routerem (jiné VLANy) se skenují jen tehdy, když je router k serveru pustí, a pak bez MAC. Router se s mapou schválně nepropojuje (stejně jako u firewallu). Výsledek se uloží do `data/scan/last.json`.

**Porovnání (editor):** MAC se převede na tvar `aa:bb:cc:dd:ee:ff` a páruje se v tomto pořadí:
1. podle MAC (i druhého rozhraní zapsaného v poznámce zařízení);
2. když nalezené zařízení nemá MAC (jiná VLAN) nebo má **náhodnou MAC** (druhá číslice 2/6/A/E, telefony se soukromou adresou Wi-Fi), tak podle IP;
3. nakonec podle jména z DNS proti názvu, id a slovům poznámky.

Výsledek ukáže okno „🔍 Sken“ se záložkami:
- **nové**: v síti, ale ne v mapě; tlačítko „Přidat do mapy“ vytvoří zařízení s `ip`, `mac` a odhadnutým typem;
- **změněné**: stejná MAC a jiná IP, nebo stejná IP a jiná MAC; tlačítko „Převzít“ (nebo „Převzít vše“) přepíše hodnotu v mapě;
- **chybějící**: v mapě mají IP ve skenované síti, ale sken je nenašel (mohou být jen vypnuté, je to informace, ne chyba);
- **v pořádku**.

Zařízení bez IP a MAC (Zigbee, pasivní prvky, napájení) se neporovnávají.
