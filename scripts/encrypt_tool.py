#!/usr/bin/env python3
"""
Wraps the Aircraft Comparison tool in a login page for publication on GitHub Pages.

The complete tool is compressed (gzip) and encrypted with AES-256-GCM. The key is derived from
account + password with PBKDF2-SHA256 (600,000 iterations), so the published index.html contains
no readable tool content and no password: without the right account and password it cannot be
decrypted. The browser derives the same key, decrypts and opens the tool (Web Crypto API).

Usage (the account and password are asked for, never stored):
    pip install cryptography
    python3 encrypt_tool.py --in "Aircraft Comparison V1.0.html" --out index.html

Run this every time a new version of the tool is published, then upload the new index.html.
market_data.js is NOT encrypted (public AvBuyer listings), so the daily Action needs no password.
"""
import argparse, base64, getpass, gzip, os, sys
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERATIONS = 600_000
HERE = os.path.dirname(os.path.abspath(__file__))

LOGIN_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Aircraft Comparison V1.0 – FLYINGGROUP</title>
<style>
:root{--fg:#58001B;--line:#EADDE1;--rose:#FAF4F6;--ink:#1F1F1F;--grey:#7a6f72}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--rose);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Calibri,Arial,sans-serif;color:var(--ink);padding:16px}
.card{background:#fff;border:1px solid var(--line);border-radius:14px;box-shadow:0 10px 40px rgba(88,0,27,.08);width:100%;max-width:380px;padding:34px 30px 28px}
.logo{display:block;height:34px;margin:0 auto 18px}
h1{font-size:13px;letter-spacing:.32em;text-transform:uppercase;text-align:center;font-weight:600;color:var(--fg);margin:0 0 26px}
label{display:block;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;font-weight:700;color:var(--grey);margin:0 0 6px}
input{width:100%;font-size:14px;padding:11px 12px;border:1px solid var(--line);border-radius:8px;margin-bottom:16px;outline:none}
input:focus{border-color:var(--fg);box-shadow:0 0 0 3px rgba(88,0,27,.08)}
button{width:100%;background:var(--fg);color:#fff;border:0;border-radius:8px;padding:12px;font-size:12px;letter-spacing:.14em;text-transform:uppercase;font-weight:700;cursor:pointer}
button:disabled{opacity:.6;cursor:wait}
.msg{min-height:18px;font-size:12px;color:#b42318;text-align:center;margin-top:12px}
.foot{font-size:10.5px;color:var(--grey);text-align:center;margin-top:18px;letter-spacing:.08em}
</style></head><body>
<form class="card" id="f" autocomplete="on">
  <img class="logo" src="__LOGO__" alt="FLYINGGROUP">
  <h1>Aircraft Comparison</h1>
  <label for="acc">Account</label>
  <input id="acc" name="username" autocomplete="username" required autofocus>
  <label for="pw">Password</label>
  <input id="pw" name="password" type="password" autocomplete="current-password" required>
  <button id="go" type="submit">Sign in</button>
  <div class="msg" id="msg"></div>
  <div class="foot">FLYINGGROUP · CONFIDENTIAL</div>
</form>
<script>
const SALT="__SALT__", IV="__IV__", IT=__IT__, CT="__CT__";
const b64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
async function openWith(key){
  const ct=await (await fetch('data:application/octet-stream;base64,'+CT)).arrayBuffer();
  const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:b64(IV)},key,ct);
  const html=await new Response(new Blob([pt]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
  try{ const raw=new Uint8Array(await crypto.subtle.exportKey('raw',key)); sessionStorage.setItem('fgac_key',btoa(String.fromCharCode(...raw))); }catch(e){}
  document.open(); document.write(html); document.close();
}
async function deriveKey(acc,pw){
  const km=await crypto.subtle.importKey('raw',new TextEncoder().encode(acc.trim().toUpperCase()+'\n'+pw),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',salt:b64(SALT),iterations:IT,hash:'SHA-256'},km,{name:'AES-GCM',length:256},true,['decrypt']);
}
const msg=document.getElementById('msg'), go=document.getElementById('go');
if(!window.crypto||!crypto.subtle||!window.DecompressionStream){ msg.textContent='This browser is not supported. Use a recent Chrome, Edge, Safari or Firefox.'; go.disabled=true; }
(async()=>{ try{ const k=sessionStorage.getItem('fgac_key'); if(k){ msg.style.color='#7a6f72'; msg.textContent='Opening…';
  await openWith(await crypto.subtle.importKey('raw',b64(k),{name:'AES-GCM'},true,['decrypt'])); } }catch(e){ try{sessionStorage.removeItem('fgac_key')}catch(_){} msg.textContent=''; msg.style.color=''; } })();
document.getElementById('f').addEventListener('submit',async e=>{
  e.preventDefault(); go.disabled=true; msg.style.color='#7a6f72'; msg.textContent='Checking…';
  try{ await openWith(await deriveKey(document.getElementById('acc').value,document.getElementById('pw').value)); }
  catch(err){ msg.style.color=''; msg.textContent='Account or password is not correct.'; go.disabled=false; document.getElementById('pw').select(); }
});
</script>
</body></html>
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True, help="the plain tool HTML")
    ap.add_argument("--out", default="index.html")
    ap.add_argument("--logo", default=os.path.join(HERE, "login_logo.png"))
    a = ap.parse_args()
    account = os.environ.get("FG_ACCOUNT") or input("Account: ")
    password = os.environ.get("FG_PASSWORD") or getpass.getpass("Password: ")
    if not account.strip() or not password:
        sys.exit("Account and password are required")
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS).derive(
        (account.strip().upper() + "\n" + password).encode("utf-8"))
    data = gzip.compress(open(a.src, "rb").read(), compresslevel=9, mtime=0)
    ct = AESGCM(key).encrypt(iv, data, None)
    logo = "data:image/png;base64," + base64.b64encode(open(a.logo, "rb").read()).decode() if os.path.exists(a.logo) else ""
    page = (LOGIN_HTML.replace("__LOGO__", logo).replace("__SALT__", base64.b64encode(salt).decode())
            .replace("__IV__", base64.b64encode(iv).decode()).replace("__IT__", str(ITERATIONS))
            .replace("__CT__", base64.b64encode(ct).decode()))
    open(a.out, "w", encoding="utf-8").write(page)
    print(f"Wrote {a.out}: {len(page)/1e6:.1f} MB (tool {os.path.getsize(a.src)/1e6:.1f} MB, encrypted)")

if __name__ == "__main__":
    main()
