"""Stránky přihlášení a nastavení. Každá je ve dvou jazycích (LOGIN_HTML['cs'|'en']), vybírá je
api.req_lang. Přepínač CZ/EN vpravo nahoře zapíše volbu stejně jako editor (cookie netmapLang
a localStorage) a stránku obnoví."""

from .config import LANGS, PW_MIN

PAGE = '''<!doctype html><html lang="LANG"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TITLE</title>
<style>
:root{--bg:#f4f5f7;--pn:#fff;--tx:#1d2330;--mu:#6b7280;--bd:#d6d9e0;--ac:#2563eb;--er:#c2410c}
@media (prefers-color-scheme:dark){:root{--bg:#14171d;--pn:#1d2129;--tx:#e6e8ec;--mu:#9aa1ad;--bd:#343a46;--ac:#60a5fa;--er:#fb923c}}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--tx);font:15px system-ui,sans-serif}
form,.box{background:var(--pn);border:1px solid var(--bd);border-radius:10px;padding:24px;width:min(320px,calc(100vw - 32px));box-sizing:border-box}
h1{font-size:18px;margin:0 0 16px}
label{display:block;font-size:13px;color:var(--mu);margin:10px 0 4px}
input{width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--bd);border-radius:6px;background:var(--bg);color:var(--tx);font:inherit}
button{margin-top:16px;width:100%;padding:9px;border:0;border-radius:6px;background:var(--ac);color:#fff;font:inherit;cursor:pointer}
#lang{position:fixed;top:12px;right:12px;width:auto;margin:0;padding:4px 9px;background:var(--pn);color:var(--tx);border:1px solid var(--bd);font-size:13px}
#msg{color:var(--er);font-size:13px;min-height:18px;margin-top:10px}
code{font-size:13px}
[hidden]{display:none!important}
</style></head><body>
<button id="lang" type="button" title="SWITCH">OTHER</button>
BODY
<script>
document.getElementById('lang').onclick = () => {
  const l = 'LANG' == 'cs' ? 'en' : 'cs';
  document.cookie = 'netmapLang=' + l + '; path=/; max-age=31536000; samesite=strict';
  try { localStorage.setItem('netmapLang', JSON.stringify(l)); } catch {}
  location.reload();
};
</script></body></html>'''

PT = {
    'cs': {
        'TITLE': 'Mapa sítě', 'OTHER': 'EN', 'SWITCH': 'English',
        'user': 'Jméno', 'pass': 'Heslo', 'code': 'Kód z aplikace (2FA)', 'go': 'Přihlásit',
        'needcode': 'Zadej šestimístný kód z aplikace.',
        'wait': 'Moc pokusů, zkus to znovu za ${j.wait} s.', 'wrong': 'Špatné jméno, heslo nebo kód.',
        'server': 'Chyba serveru (',
        'setup1': 'Účet ještě není nastavený. Jednorázový kód najdeš v protokolu kontejneru '
                  '(Container Manager → Kontejner → netmap → Protokol, jinde <code>docker logs netmap</code>).',
        'scode': 'Kód z protokolu', 'pass2': 'Heslo znovu', 'pmin': 'aspoň PW_MIN znaků', 'create': 'Založit účet',
        'nomatch': 'Hesla se neshodují.', 'short': 'Heslo musí mít aspoň PW_MIN znaků.',
        'wcode': 'Kód nesedí. Po restartu kontejneru platí nový.',
    },
    'en': {
        'TITLE': 'Network map', 'OTHER': 'CZ', 'SWITCH': 'Čeština',
        'user': 'User name', 'pass': 'Password', 'code': 'Code from the app (2FA)', 'go': 'Sign in',
        'needcode': 'Enter the 6-digit code from your app.',
        'wait': 'Too many attempts, try again in ${j.wait} s.', 'wrong': 'Wrong user name, password or code.',
        'server': 'Server error (',
        'setup1': 'The account is not set up yet. The one-time code is in the container log '
                  '(Synology: Container Manager → Container → netmap → Log, elsewhere <code>docker logs netmap</code>).',
        'scode': 'Code from the log', 'pass2': 'Password again', 'pmin': 'at least PW_MIN characters',
        'create': 'Create account', 'nomatch': 'The passwords do not match.',
        'short': 'The password must have at least PW_MIN characters.',
        'wcode': 'Wrong code. After a container restart a new one applies.',
    },
}

# Přihlášení ve dvou krocích: pole pro kód 2FA se ukáže, až server odpoví 'code' (jméno a heslo sedí).
LOGIN = '''<form id="f">
<h1>🖧 {TITLE}</h1>
<label>{user}<input name="user" autocomplete="username" required autofocus></label>
<label>{pass}<input name="pass" type="password" autocomplete="current-password" required></label>
<label id="c" hidden>{code}<input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6"></label>
<button>{go}</button>
<div id="msg"></div>
</form>
<script>
const f = document.getElementById('f'), msg = document.getElementById('msg'), c = document.getElementById('c');
f.onsubmit = async e => {
  e.preventDefault();
  msg.textContent = '';
  const b = Object.fromEntries(new FormData(f));
  const r = await fetch('api/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
  const j = await r.json().catch(() => ({}));
  if (r.ok) return location.reload();
  if (j.error == 'code') {
    c.hidden = false;
    f.code.required = true;
    f.code.focus();
    msg.textContent = '{needcode}';
  } else if (j.wait) msg.textContent = `{wait}`;
  else msg.textContent = r.status == 401 ? '{wrong}' : '{server}' + r.status + ').';
  if (!c.hidden) f.code.value = '';
};
</script>'''

# První účet: kód z protokolu kontejneru (api.setup_banner), jméno a heslo. Pak rovnou přihlášení.
SETUP = '''<form id="f">
<h1>🖧 {TITLE}</h1>
<p style="font-size:13px;color:var(--mu);margin:0">{setup1}</p>
<label>{scode}<input name="code" inputmode="numeric" autocomplete="off" required autofocus></label>
<label>{user}<input name="user" autocomplete="username" value="admin" required maxlength="60"></label>
<label>{pass} ({pmin})<input name="pass" type="password" autocomplete="new-password" required minlength="PW_MIN"></label>
<label>{pass2}<input name="pass2" type="password" autocomplete="new-password" required></label>
<button>{create}</button>
<div id="msg"></div>
</form>
<script>
const f = document.getElementById('f'), msg = document.getElementById('msg');
f.onsubmit = async e => {
  e.preventDefault();
  const b = Object.fromEntries(new FormData(f));
  if (b.pass != b.pass2) return msg.textContent = '{nomatch}';
  msg.textContent = '';
  delete b.pass2;
  const r = await fetch('api/setup', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
  const j = await r.json().catch(() => ({}));
  if (r.ok || r.status == 409) location.reload();
  else if (j.wait) msg.textContent = `{wait}`;
  else if (r.status == 401) msg.textContent = '{wcode}';
  else msg.textContent = j.error == 'short' ? '{short}' : '{server}' + r.status + ').';
};
</script>'''


def page(lang, body):
    s = PAGE.replace('BODY', body).replace('LANG', lang)
    for k, v in PT[lang].items():
        s = s.replace(k if k.isupper() else '{' + k + '}', v)
    return s.replace('PW_MIN', str(PW_MIN))


LOGIN_HTML = {g: page(g, LOGIN.replace('{TITLE}', PT[g]['TITLE'])) for g in LANGS}
SETUP_HTML = {g: page(g, SETUP.replace('{TITLE}', PT[g]['TITLE'])) for g in LANGS}
