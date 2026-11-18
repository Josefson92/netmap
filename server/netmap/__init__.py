"""Mapa domácí sítě: malý server pro NAS (Docker, např. Synology).

Server:          uvicorn netmap.api:app --host 0.0.0.0 --port 8780
Příkazová řádka: python -m netmap passwd | 2fa on | 2fa off

Moduly: config (cesty, limity, jazyk), store (soubory), auth (heslo, TOTP, relace, hádání hesla),
objects (objekty a ukázka), backups, scan (nmap), update (kontrola nové verze), pages (přihlášení, nastavení), api (FastAPI)
a cli (příkazy). FastAPI importuje jen api, takže příkazová řádka běží i bez něj.

Návrh je v docs/nas.md. Server data nikdy sám nemění: network.md generuje prohlížeč.
"""
