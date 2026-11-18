# Server: mapa na NAS (Docker)

Cíl: `mapa.html` se otevře ze serveru v prohlížeči na libovolném počítači v síti. Data leží na serveru a mají zálohy. Server umí proskenovat síť a porovnat výsledek s mapou.
Editor zůstává jeden soubor bez závislostí a dá se používat i bez serveru (složka 📁 nebo jen prohlížeč).

Návod je psaný pro Synology (Container Manager), ale server je obyčejný Docker kontejner a poběží na libovolném Linuxu.

## Rozhodnutí v kostce

| Otázka | Volba | Proč |
|---|---|---|
| Backend | **Python + FastAPI** (uvicorn), balíček `server/netmap/` | Malý a čitelný kód, sken je stejně volání `nmap`. Moduly: `config`, `store`, `auth`, `objects`, `backups`, `scan`, `pages`, `api` (jediný s FastAPI) a `cli` (příkazy bez FastAPI). |
| network.md | **generuje prohlížeč** (`md()`), server ho jen uloží | Logika zůstane na jednom místě. Server data nikdy sám nemění, takže md nemůže zastarat. |
| Párování skenu | **v prohlížeči**, server vrací jen seznam nalezených | Porovnání potřebuje strom, VLANy a typy zařízení, a ty zná editor. |
| Síť kontejneru | `network_mode: host` + `cap_add: NET_RAW` | ARP sken funguje jen na vlastním L2 segmentu, z bridge sítě Dockeru by viděl jen sebe. |
| Přístup | jen z LAN/VPN, bez přesměrování portu z internetu, **přihlášení heslem**, 2FA (TOTP) volitelně | Data obsahují IP, MAC a firewall. Basic auth 2FA neumí, proto vlastní přihlašovací stránka a cookie. |

## Úložiště v editoru

Editor má tři úložiště se stejným rozhraním (`name`, `get() → {net, lay} | null`, `put({net, lay, md})`): `stLocal` (localStorage), `stDir` (složka) a `stHttp` (server).

- Při startu: když stránka běží přes `http(s)` a `GET api/health` odpoví, editor pracuje se serverem a tlačítko 📁 ukáže `🖧 NAS`. Jinak vše funguje lokálně (složka z IndexedDB nebo prohlížeč).
- `stLocal` se zapisuje vždy jako záloha.
- Když server data objektu nemá (nový server, smazaná složka), ale v prohlížeči zůstala mapa z dřívějška, editor ji nezobrazí jako uloženou ani sám nenahraje: začne prázdnou mapou a stavový řádek nabídne „Nahrát na NAS“ / „Zahodit“. Výjimkou jsou první změny nového objektu, které se ještě nepodařilo odeslat; ty se pošlou.
- **Souběžné úpravy** (víc počítačů): `get` vrátí i `rev` (otisk obsahu `net` + `lay`), `put` ho posílá v `If-Match`. Když se data mezitím změnila jinde, server vrátí `409` a editor obě verze třícestně sloučí (zařízení, spoje a prostory po polích). Kdyby to nešlo, stavový řádek nabídne „Načíst z NAS“ (zahodí místní změny) nebo „Přepsat NAS mou verzí“.

## Objekty

Data jsou po objektech (dům, chata, kancelář…). Každý objekt má složku `data/<id>/` s vlastními soubory a zálohami. Editor bez `?o=` v adrese ukáže přehled objektů a objekt otevírá jako `mapa.html?o=<id>`. Data v prohlížeči (localStorage) má po objektech s příponou `@id`.

Na prázdném serveru se při prvním otevření přehledu založí prázdný objekt „Domov“ (označený „tady je NAS“) a objekt „Ukázka“ s fiktivní sítí ze složky `ukazka/`. Pro anglický prohlížeč jsou to „Home“ a „Demo“ ze složky `ukazka-en/`. Ukázka se zakládá jen takhle jednou; kdo ji smaže, už se nevrátí.

## Jazyk

Přihlašovací a nastavovací stránka jsou česky nebo anglicky: platí ruční volba z editoru (cookie `netmapLang`, editor ji nastaví po přepnutí jazyka), jinak první jazyk prohlížeče (`Accept-Language`; cs/sk = čeština, jinak angličtina). Na přihlašovací stránce je přepínač CZ/EN. Nouzové příkazy v terminálu (`passwd`, `2fa`) mluví podle `NETMAP_LANG` (`cs`/`en`), jinak podle `LANG`, bez nich anglicky.

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
| GET | `/api/health` | pro Docker healthcheck (bez přihlášení, stejně jako login, setup a logout; verzi neprozrazuje) |
| GET | `/api/version` | `{version, check, at, latest, url}`: verze serveru a novější vydání na GitHubu (`latest` jen když je novější) |
| POST | `/api/login` | `{user, pass, code?}` → cookie `netmap_s`; `401` / `{need: 'code'}` |
| POST | `/api/setup` | první účet: `{code, user, pass}` (kód z protokolu kontejneru) → cookie `netmap_s`; `401` špatný kód, `400` krátké heslo, `409` účet už je |
| POST | `/api/logout` | smaže relaci |

Cesty bez objektu (`/api/data`, `/api/backups…`, `/api/scan`) platí pro objekt označený „tady je NAS“.

Statické soubory: `/` → `www/mapa.html`, když je připojená, jinak editor z image. `/docs` (OpenAPI) je vypnuté, aby nic nešlo bez přihlášení.

Server před zápisem zkontroluje, že `net` a `lay` jsou platný JSON (`net` má `devices`). Zapisuje atomicky (`*.tmp` a pak `os.replace`), takže výpadek uprostřed zápisu soubory nepoškodí.

## Přihlášení a 2FA

- Bez platné relace vrací server místo `/` malou přihlašovací stránku a API odpovídá `401`.
- Účet je jeden, uložený v `config/auth.json` (mimo `data/`, takže se nezálohuje spolu s mapou a nedostane se do exportu): `{user, hash, totp?}`. Heslo je hashované přes `hashlib.scrypt` se solí (N=2^15, r=8, p=3 podle OWASP; parametry jsou v hashi).
- **První účet se zakládá v prohlížeči:** dokud účet není, server při startu vypíše do protokolu kontejneru jednorázový kód (`1234-5678-9012`) a místo editoru ukazuje formulář kód + jméno + heslo. Kdo stránku jen vidí v síti, účet bez kódu nezaloží; špatný kód se počítá jako špatné přihlášení. Po založení je uživatel rovnou přihlášený a kód přestane platit (nový vznikne až restartem bez účtu).
- **Účet se dál spravuje v editoru:** ⋯ → 🔐 Účet (v přehledu objektů tlačítko 🔐 Účet). Každá změna chce současné heslo; špatné se počítá jako špatné přihlášení.
  - Změna jména a hesla (aspoň 10 znaků) odhlásí ostatní zařízení, tenhle prohlížeč dostane novou relaci.
  - Zapnutí 2FA: server vygeneruje tajný klíč a ukáže QR kód (a klíč k ručnímu opsání) pro aplikaci s kódy (Google Authenticator, Aegis, 1Password…). Klíč server nikam neukládá, dokud se nezadá první platný kód.
  - Vypnutí 2FA chce i platný kód z aplikace.
  - API: `GET /api/account` (`{user, totp, min}`), `POST /api/account/password` `{pass, user, new}`, `POST /api/account/2fa/new` `{pass}` → `{secret, url, qr}`, `/2fa/on` `{pass, secret, code}`, `/2fa/off` `{pass, code}`. Chyby jsou `403` (`wrong` = heslo, `code` = kód), aby je editor nebral jako vypršelou relaci.
- **Nouzová cesta z příkazové řádky** (zapomenuté heslo, ztracený telefon s kódy): Container Manager → Terminál, nebo `docker exec -it netmap …`. Příkazy běží jako root, ale soubory zapisují pod stejným uživatelem jako server (vlastník složky `config/`):
  - `python -m netmap passwd`: nastaví jméno a heslo a odhlásí všechny relace;
  - `python -m netmap 2fa off`: 2FA vypne (`2fa on` ho zapne s QR kódem v terminálu).
- TOTP podle RFC 6238 (30 s, 6 číslic, tolerance ±1 krok), bez knihovny.
- Relace: náhodný token v cookie `HttpOnly`, `SameSite=Strict` (a `Secure` za HTTPS), platnost 30 dní, přežije restart kontejneru (`config/sessions.json`).
- Přihlášení má dva kroky: formulář chce jméno a heslo, a když sedí a 2FA je zapnuté, server odpoví `401 {error: 'code'}` a stránka ukáže pole pro kód. Tím prozradí, že heslo sedělo (vědomý ústupek pohodlí; hádání hesla i kódu dál brzdí ochrana níž). Špatné jméno, heslo nebo kód je jen „špatně“ bez rozlišení. Kód jde použít jen jednou.
- Ochrana proti hádání: po 5 špatných pokusech z jedné IP čeká další pokus 1 minutu, s každou další chybou se čekání zdvojnásobí. Navíc platí celkový limit 30 chyb za minutu ze všech adres dohromady.
- Změny (POST, PUT, PATCH, DELETE) přijímá server jen z vlastní stránky (`Sec-Fetch-Site`, starší prohlížeče `Origin`). Samotné `SameSite=Strict` nestačí, protože jiná aplikace na stejném NAS je pro prohlížeč týž „site“.
- Velikost požadavku je omezená a tělo se čte po částech (přihlášení 4 kB, údaje objektu 1 MB, mapa 20 MB).
- Hlavička `Content-Security-Policy`: stránka nenačte nic cizího a nemůže nic posílat jinam než na server.
- Když relace vyprší, editor přesměruje na přihlášení. Neuložené změny jsou v localStorage a po přihlášení se uloží.

## Soubory na serveru

```
netmap/          složka projektu (na Synology např. docker/netmap)
  docker-compose.yml
  www/           volitelně vlastní mapa.html (má přednost před editorem z image)
  config/        auth.json, sessions.json
  data/
    domov/       meta.json ({name, desc, nas}), network.json, layout.json, network.md
      backup/    2026-11-20_143005/{network.json, layout.json, network.md}
    ukazka/      … další objekty stejně
    scan/        last.json (sken je jeden pro celý server)
    _deleted/    smazané objekty
```

Editor, server a ukázkové sítě (`ukazka/`, `ukazka-en/`) jsou v image, kopie repozitáře na serveru není potřeba. Složky `data/` a `config/` musí na Synology existovat předem (viz Nasazení), jinde je Docker vytvoří sám.

## Zálohy

- Každý objekt má vlastní zálohy (`data/<id>/backup/`).
- Editor ukládá 0,7 s po každé změně, proto se záloha nedělá při každém zápisu: server zkopíruje **předchozí** verzi do `backup/<čas>/` jen na začátku úprav, tj. když se data aspoň 30 minut neměnila (`BACKUP_IDLE`). Jedny úpravy = jedna záloha. Záloha shodná s poslední se nedělá.
- Nechávají se 4 nejnovější zálohy (`BACKUP_KEEP`).
- Obnova je v editoru: ⋯ → 🕘 Zálohy (porovnání se současnou verzí, obnovu jde vrátit Ctrl+Z).
- Celá složka `netmap/` může navíc jít do Hyper Backup nebo snapshotů Btrfs. To je mimo aplikaci.

## Docker

- **Hotový image** `ghcr.io/josefson92/netmap` (`latest` = poslední `main`, vydání podle značek `v1.2.3` jako `:1.2.3` a `:1.2`; x86-64 i ARM64) staví GitHub Actions (`.github/workflows/image.yml`) ve veřejném repozitáři. `docker-compose.yml` ho jen stáhne, na serveru tedy není potřeba nic dalšího než tento soubor.
- Vlastní sestavení: `server/Dockerfile` (základ `python:3.12-slim`, kontext je kořen repozitáře kvůli `mapa.html`, `ukazka/` a `ukazka-en/`); v `docker-compose.yml` místo `image:` řádek `build:` z komentáře. Editor je součástí image; kdo chce jinou verzi bez nového image, připojí `./www:/app/www:ro` s vlastním `www/mapa.html`.
- **Uživatel serveru se hledá sám.** Start (`server/entrypoint.sh`) běží chvíli jako root, vytvoří `data/` a `config/` a vyzkouší zápis postupně za: vlastníka složky `data/` (když to není root), `1000:1000` a `1000:101`. Na Synology rozhoduje o právech ACL sdílené složky, ne vlastník souboru, a skupina `administrators` (GID 101) v něm má zápis, proto tam vyjde `1000:101`. Když nesmí zapisovat nikdo (čerstvé složky po rootovi bez ACL), předá je prvnímu kandidátovi. Pak soubory s jiným vlastníkem předá vybranému uživateli a server spustí pod ním přes `setpriv` (bez skupin navíc a bez schopností); v protokolu je řádek `netmap: server runs as UID:GID`. `PUID`/`PGID` v compose volbu vynutí. Když zápis nejde vůbec, kontejner skončí s vysvětlením v protokolu.
- V image je `nmap` se schopností `cap_net_raw` (setcap), server spouští `nmap --privileged`. Kontejner proto nemusí běžet jako root: kořenový souborový systém je jen ke čtení (`read_only`, `/tmp` v paměti) a z práv navíc má jen `NET_RAW`. `no-new-privileges` použít nejde, vypnul by nmapu `cap_net_raw`.
- `network_mode: host`, port **8780** (nastavitelný `PORT`). Na Synology obsazuje DSM 5000/5001 a 80/443.
- Volumes: `./data:/app/data`, `./config:/app/config`, volitelně `./www:/app/www:ro`.
- Proměnné: `PORT`, `SCAN_NETS` (co skenovat, např. `192.168.1.0/24`; bez toho /24 hlavního rozhraní, víc než /22 server odmítne), `TZ`, `NETMAP_LANG`, `NETMAP_UPDATE_CHECK` (`0` = nekontrolovat nové verze), volitelně `PUID`, `PGID`.
- Reverzní proxy (na Synology `https://netmap.<nas>` s certifikátem) je **doporučená**: kvůli přihlášení, jinak by heslo a cookie šly po síti otevřeně.

## Nasazení na Synology

Jen přes DSM, bez SSH a bez nahrávání souborů:

1. **Složky:** File Station → sdílená složka `docker` → vytvořit složku `netmap` a v ní prázdné složky `data` a `config`. Container Manager chybějící složky pro volumes sám nevytvoří a projekt skončí chybou „Bind mount failed: '…/netmap/data' does not exist“.
2. **Projekt:** Container Manager → Projekt → Vytvořit. Název `netmap`, cesta: složka `docker/netmap` z kroku 1. Zdroj „Vytvořit docker-compose.yml“ a vložit obsah [`docker-compose.yml`](../docker-compose.yml) (kdo chce, upraví `TZ` nebo `SCAN_NETS`, jinak nic). Portál Web Station nezapínat. Container Manager stáhne image a spustí ho.
3. **Účet:** Container Manager → Kontejner → `netmap` → Protokol: opsat kód pro nastavení. Otevřít `http://<adresa NAS>:8780/`, zadat kód, jméno a heslo.
4. **Firewall DSM** (jen když je zapnutý): povolit TCP 8780 z domácí sítě (a z VPN, pokud ji používáš).

Kdo už má mapu ve složce `data/` z lokálního režimu, dá `network.json` a `layout.json` do `netmap/data/` (File Station) a kontejner restartuje; server je převede na objekt „Domov“.

Jinde než na Synology: `docker-compose.yml` do prázdné složky, `docker compose up -d`, kód je v `docker logs netmap`.

## Verze a aktualizace

- **Verze** je v image od sestavení (`NETMAP_VERSION` = `git describe`: `v1.2.3` u vydání, `v1.2.3-4-gabc` u sestavení z `main` po něm, `dev` u vlastního sestavení). Editor ji ukáže v okně 🔐 Účet.
- **Kontrola nové verze:** server se 1× denně zeptá GitHubu na poslední vydání (`api.github.com/repos/Josefson92/netmap/releases/latest`, `server/netmap/update.py`; prohlížeč sám nikam nesahá). Když je novější, editor ukáže ve stavovém řádku a v přehledu objektů „Je dostupná verze vX (máš vY)“ s odkazem na poznámky k vydání; ✕ ho skryje do další verze. Dotaz prozradí GitHubu adresu, ze které server chodí do internetu; `NETMAP_UPDATE_CHECK: 0` kontrolu vypne.
- **Server se sám neaktualizuje** (kontejner by potřeboval přístup k Dockeru, tedy práva nad celým NAS; proto to nejde ani z terminálu kontejneru). „Sestavit“ v Container Manageru nový image nestáhne, vezme ten, který už na NAS je. `data/` a `config/` aktualizace nezmění. Automaticky to umí např. Watchtower.
- **Aktualizace na Synology přes Plánovač úloh** (bez SSH): Ovládací panel → Plánovač úloh → Vytvořit → Naplánovaná úloha → Uživatelem definovaný skript. Obecné: název např. `netmap aktualizace`, uživatel `root`, „Povoleno“ odškrtnout (jen ručně). Nastavení úlohy → skript (cesta = složka s `docker-compose.yml`):
  ```
  cd /volume1/docker/netmap && docker compose pull && docker compose up -d
  ```
  Při každé aktualizaci úlohu označit → Spustit. Když GitHub nebo internet není dostupný, `pull` selže, `&&` zbytek nespustí a běžící kontejner zůstane, jak byl.
- **Aktualizace přes SSH** (nebo jinde než na Synology): ve složce s `docker-compose.yml` `sudo docker compose pull && sudo docker compose up -d`.
- **Když image na GitHubu zmizí** (nebo NAS nemá internet): kontejner dál běží a spustí i znovu sestaví z image, který už na NAS je (compose záměrně nemá `pull_policy: always`, s ním by „Sestavit“ skončil chybou). Pro jistotu si můžeš image uložit: `docker save ghcr.io/josefson92/netmap:latest -o netmap-image.tar` (Synology: Container Manager → Image → Exportovat), zpět `docker load -i netmap-image.tar`. Mapy jsou obyčejné soubory v `data/`, editor je otevře i bez serveru (📁 složka).
- **Připnutá verze:** v `docker-compose.yml` místo `:latest` napiš `:1.0.0` (přesně tohle vydání) nebo `:1.0` (opravy v rámci 1.0). Novou verzi pak dostaneš jen ruční změnou čísla.
- **Vydání** (ve veřejném repozitáři): značka `v1.2.3` na `main` (`git push --atomic origin main v1.2.3`, aby sestavení z `main` už značku vidělo) a GitHub Release s popisem změn a postupem aktualizace. Workflow postaví `:1.2.3`, `:1.2` a `:latest`.

## Lokální test

```
docker build -t netmap-test -f server/Dockerfile .
docker run -d --name netmap-test --cap-add NET_RAW --read-only --tmpfs /tmp -p 8782:8780 -v <data>:/app/data -v <config>:/app/config netmap-test
docker logs netmap-test
```

Pak `http://127.0.0.1:8782/` a kód z protokolu. Pro test nepoužívat skutečnou složku `data/`.

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
