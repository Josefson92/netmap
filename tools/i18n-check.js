// Kontrola překladu mapa.html: které české texty nemají anglický překlad ve slovníku EN a které klíče EN se nepoužívají.
// Spuštění: node tools/i18n-check.js [--json]   (--json vypíše chybějící klíče jako JSON objekt k doplnění)
// Klíče se berou z: řetězců v prvním argumentu tr(…), statického HTML v <body> (text, title, placeholder),
// popisků konstant (T, L, AK, FL, LY, zástupné texty LF, THEMES, hodnoty WAN, MR, BANDS, PRL, PSP, PPOE) a názvů skupin ikon ICG.
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'mapa.html'), 'utf8');
const scripts = [...src.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const enScript = scripts.find(s => /const EN = \{/.test(s));
const icScript = scripts.find(s => /const ICG = \[/.test(s));
const main = scripts.find(s => /function tr\(/.test(s));
const EN = new Function(enScript + '; return EN;')();
const ICG = new Function(icScript + '; return ICG;')();

const keys = new Map();  // klíč → kde se vzal
const add = (k, from) => { if (k && /[\p{L}]/u.test(k) && !keys.has(k)) keys.set(k, from); };

// 1) tr(…) a trK(…): všechny řetězcové literály v prvním argumentu (i v tr(a ? 'x' : 'y'))
const off = src.slice(0, src.indexOf(main)).split('\n').length - 1;  // čísla řádků v celém souboru
const lineOf = i => off + main.slice(0, i).split('\n').length;
for (const m of main.matchAll(/\btrK?\(/g)) {  // trK = text v konstantě, přeloží se až při zobrazení
  if (main.slice(main.lastIndexOf('\n', m.index), m.index).includes('// ')) continue;  // v komentáři
  let i = m.index + m[0].length, depth = 0, q = null, cur = '', arg = [];
  for (; i < main.length; i++) {
    const c = main[i];
    if (q) {
      if (c == '\\') { cur += main[++i]; continue; }
      if (c == q) { arg.push(cur); cur = ''; q = null; continue; }
      if (q == '`' && c == '$' && main[i + 1] == '{') { arg.push(null); }  // šablona s ${} jako klíč nesmí být
      cur += c;
      continue;
    }
    if (c == "'" || c == '"' || c == '`') { q = c; continue; }
    if (c == '(' || c == '{' || c == '[') depth++;
    else if (c == ')' || c == '}' || c == ']') { if (!depth) break; depth--; }
    else if (c == ',' && !depth) break;
  }
  if (arg.includes(null)) console.log(`⚠ ř. ${lineOf(m.index)}: tr() se šablonou \${…}, použij {parametr}`);
  for (const k of arg) if (k != null) add(k, 'tr ř. ' + lineOf(m.index));
}

// 2) statické HTML v <body> před prvním skriptem
const body = src.slice(src.indexOf('<body>'), src.indexOf('<script>', src.indexOf('<body>')));
const unent = s => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&amp;/g, '&');
for (const m of body.matchAll(/\s(?:title|placeholder)="([^"]*)"/g)) add(unent(m[1]).trim(), 'html');
for (const m of body.replace(/<svg[\s\S]*?<\/svg>/g, '').matchAll(/>([^<]+)</g)) add(unent(m[1]).trim(), 'html');

// 3) konstanty: kód sekce „konstanty“ se vyhodnotí bez zbytku aplikace
const c0 = main.indexOf('// ---------- konstanty ----------'), c1 = main.indexOf('// ---------- drobné');
const C = new Function('vlOpts', main.slice(c0, c1) + '; return {T, L, AK, FL, LY, LF, WAN, MR, BANDS, PRL, PSP, PPOE};')(() => []);
for (const v of Object.values(C.T)) add(v[0], 'T');
for (const v of Object.values(C.L)) add(v[0], 'L');
for (const v of Object.values(C.AK)) add(v[1], 'AK');
for (const v of Object.values(C.FL)) add(v, 'FL');
for (const v of Object.values(C.LY)) add(v, 'LY');
for (const v of Object.values(C.LF)) for (const c of v) add(c[1], 'LF');
for (const k of ['WAN', 'MR', 'BANDS', 'PRL', 'PSP', 'PPOE']) for (const v of C[k]) add(v, k);
const th = main.match(/const THEMES = (\{.*\});/);
for (const v of Object.values(new Function('return ' + th[1])())) add(v[1], 'THEMES');
for (const [h] of ICG) add(h, 'ICG');

// výsledek
const miss = [...keys].filter(([k]) => !(k in EN));
const unused = Object.keys(EN).filter(k => !keys.has(k));
if (process.argv.includes('--json')) {
  console.log(JSON.stringify(Object.fromEntries(miss.map(([k]) => [k, ''])), null, 1));
} else {
  console.log(`klíčů ${keys.size}, přeloženo ${keys.size - miss.length}, chybí ${miss.length}, nepoužité ${unused.length}`);
  for (const [k, f] of miss) console.log('CHYBÍ  ' + JSON.stringify(k) + '   (' + f + ')');
  for (const k of unused) console.log('NAVÍC  ' + JSON.stringify(k));
}
process.exitCode = miss.length ? 1 : 0;
