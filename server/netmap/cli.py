"""Příkazová řádka: python -m netmap passwd | 2fa on | 2fa off. Běžně se účet nastavuje v editoru
(⋯ → 🔐 Účet), tohle je nouzová cesta: zapomenuté heslo, ztracený telefon s kódy.
Nepotřebuje FastAPI (neimportuje api.py). Jazyk: NETMAP_LANG=cs|en, jinak podle LANG
(cs/sk = čeština, jinak angličtina)."""

import getpass
import os
import sys

from .auth import account_set, auth, totp_new, totp_set, totp_step, totp_url
from .config import CONFIG, ISSUER, PW_MIN, lang_of

CLI_LANG = lang_of(os.environ.get('NETMAP_LANG'), os.environ.get('LANG', '').split('.')[0].replace('_', '-'))
USAGE = 'python -m netmap passwd | 2fa on | 2fa off'


def tl(cs, en):
    """Hláška v jazyce příkazové řádky."""
    return cs if CLI_LANG == 'cs' else en


def cli_passwd():
    a = auth() or {}
    user = input(tl('Jméno', 'User name') + f' [{a.get("user", "admin")}]: ').strip() or a.get('user', 'admin')
    while True:
        p1 = getpass.getpass(tl(f'Nové heslo (aspoň {PW_MIN} znaků): ', f'New password (at least {PW_MIN} characters): '))
        if len(p1) < PW_MIN:
            print(tl('Heslo je moc krátké.', 'The password is too short.'))
            continue
        if p1 != getpass.getpass(tl('Heslo znovu: ', 'Password again: ')):
            print(tl('Hesla se neshodují.', 'The passwords do not match.'))
            continue
        break
    account_set(user, p1)  # změna hesla odhlásí všechny
    print(tl('Heslo nastavené, všechny relace jsou odhlášené.', 'Password set, all sessions are signed out.'))


def cli_2fa(on):
    a = auth()
    if not a:
        sys.exit(tl('Nejdřív nastav heslo: python -m netmap passwd', 'Set a password first: python -m netmap passwd'))
    if not on:
        totp_set(None)
        print(tl('2FA je vypnuté.', '2FA is off.'))
        return
    secret = totp_new()
    url = totp_url(a['user'], secret, ISSUER[CLI_LANG])
    print(tl('Naskenuj QR kód v aplikaci (Google Authenticator, Aegis, 1Password…):\n',
             'Scan the QR code in an authenticator app (Google Authenticator, Aegis, 1Password…):\n'))
    try:
        import qrcode  # volitelné: bez něj se vypíše jen klíč a odkaz
        q = qrcode.QRCode(border=1)
        q.add_data(url)
        q.print_ascii(invert=True)
    except ImportError:
        pass
    print(tl(f'\nNebo zadej ručně klíč: {secret}\nOdkaz: {url}\n', f'\nOr enter the key manually: {secret}\nLink: {url}\n'))
    for _ in range(3):
        if totp_step(secret, input(tl('Kód z aplikace: ', 'Code from the app: '))) is not None:
            totp_set(secret)
            print(tl('2FA je zapnuté.', '2FA is on.'))
            return
        print(tl('Kód nesedí.', 'Wrong code.'))
    sys.exit(tl('2FA zůstává vypnuté.', '2FA stays off.'))


def drop_root():
    """Terminál kontejneru běží jako root: soubory má zapisovat stejný uživatel jako server.
    Start (entrypoint.sh) mu předal složku config/, proto se bere její vlastník."""
    if not hasattr(os, 'geteuid') or os.geteuid() != 0 or not CONFIG.is_dir():
        return
    st = CONFIG.stat()
    if st.st_uid == 0:
        return
    os.setgroups([])
    os.setgid(st.st_gid)
    os.setuid(st.st_uid)


def main(argv=None):
    drop_root()
    cmd = sys.argv[1:] if argv is None else argv
    if cmd == ['passwd']:
        cli_passwd()
    elif cmd in (['2fa', 'on'], ['2fa', 'off']):
        cli_2fa(cmd[1] == 'on')
    else:
        sys.exit(tl('Použití: ', 'Usage: ') + USAGE)
