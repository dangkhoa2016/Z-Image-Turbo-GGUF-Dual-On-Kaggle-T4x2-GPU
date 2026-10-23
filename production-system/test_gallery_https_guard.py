#!/usr/bin/env python3
"""Exercise the actual production notebook HTTPS guard without external calls."""
import ast
import json
import socket
import textwrap
import types
import urllib.error
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from kaggle_production_demo import engine_notebook
nb=engine_notebook(ROOT)
cell="".join(nb["cells"][22]["source"])
assert cell.count("        gallery_public_https_status = {}")==1
assert cell.count('    else:\n        print("GALLERY_TUNNELS_SKIPPED')==1
start=cell.index("        gallery_public_https_status = {}")
end=cell.index('    else:\n        print("GALLERY_TUNNELS_SKIPPED',start)
script=textwrap.dedent(cell[start:end])
ast.parse(script)

urls={"quality":"https://quality.trycloudflare.com",
      "benchmark":"https://benchmark.trycloudflare.com"}
html="".join(urls.values())
class Response:
    def __init__(self,status=200,body=html):
        self.status=status
        self.body=body.encode()
    def read(self):
        return self.body
    def __enter__(self):
        return self
    def __exit__(self,*_):
        return False

def exercise(opener):
    output=[]
    delays=[]
    lib=types.SimpleNamespace(
        request=types.SimpleNamespace(urlopen=opener),
        error=urllib.error,
    )
    env={"gallery_urls":urls.copy(),"urllib":lib,
         "time":types.SimpleNamespace(sleep=delays.append),
         "print":lambda *a,**k: output.append(" ".join(map(str,a)))}
    exec(compile(script,"public-https-subset","exec"),env)
    return env["gallery_public_https_status"],output,delays

# Both public DNS resolutions fail; local gallery prerequisite succeeded.
def dns(*a,**k):
    raise urllib.error.URLError(socket.gaierror(-2,"Name or service not known"))
state,output,delays=exercise(dns)
assert state=={"quality":"PENDING_BROWSER_VERIFICATION",
               "benchmark":"PENDING_BROWSER_VERIFICATION"}
assert len(delays)==6
assert any("PUBLIC_GALLERIES_E2E_STATUS PENDING_BROWSER_VERIFICATION" in l
           for l in output)
assert not any("GALLERY_CROSS_DOMAIN_NAV_HTTPS_PASS" in l for l in output)

state,output,delays=exercise(lambda *a,**k:Response())
assert all(v=="VERIFIED_FROM_KAGGLE" for v in state.values())
assert len(delays)==0
assert len([x for x in output if "GALLERY_CROSS_DOMAIN_NAV_HTTPS_PASS" in x])==2

# 503 response is not public success and requires separate browser validation.
state,output,delays=exercise(lambda *a,**k:Response(status=503))
assert all(v=="PENDING_BROWSER_VERIFICATION" for v in state.values())

# An actual reachable HTML page with broken cross-gallery links MUST stop.
try:
    exercise(lambda *a,**k:Response(body="Broken gallery navigation"))
except AssertionError as exc:
    assert "GALLERY_CROSS_DOMAIN_NAV_PUBLIC_CONTENT_INVALID" in str(exc)
else:
    raise AssertionError("BROKEN_NAVIGATION_WRONGLY_ACCEPTED")

# Unexpected application bugs must never be converted to DNS pending.
try:
    exercise(lambda *a,**k: (_ for _ in ()).throw(ValueError("unexpected")))
except ValueError:
    pass
else:
    raise AssertionError("UNEXPECTED_APPLICATION_ERROR_WRONGLY_IGNORED")

# Transient DNS failure followed by confirmed HTTPS success: VERIFIED.
count=[0]
def recovering(*a,**k):
    count[0]+=1
    if count[0]==1: raise urllib.error.URLError("temporary DNS")
    return Response()
state,output,delays=exercise(recovering)
assert count[0]==3 and len(delays)==1
assert all(v=="VERIFIED_FROM_KAGGLE" for v in state.values())

print("GALLERY_PUBLIC_HTTPS_CPU_PASS dns_pending_nonfatal http503_pending "
      "valid200_verified invalid_html_fatal unexpected_error_fatal retry_recovery")
