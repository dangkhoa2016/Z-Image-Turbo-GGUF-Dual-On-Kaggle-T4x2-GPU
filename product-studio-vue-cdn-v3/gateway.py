import os,time,secrets,hmac,hashlib,json,collections,sqlite3,re
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from fastapi import FastAPI,Request
from fastapi.responses import Response,JSONResponse,HTMLResponse
ROOT=Path(__file__).resolve().parent
UPSTREAM="http://127.0.0.1:18788"
PASSWORD=os.environ["VUE_STUDIO_PASSWORD"]
API_KEY=os.environ["STUDIO_INTERNAL_KEY"]
SESSIONS={}
ATTEMPTS=collections.defaultdict(list)
TTL=8*3600
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
def security():
 return {"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer","X-Frame-Options":"DENY"}
def authed(req):
 token=req.cookies.get("zs_session","")
 key=hashlib.sha256(token.encode()).hexdigest() if token else ""
 now=time.time()
 return SESSIONS.get(key,0)>now
def origin_ok(req):
 origin=req.headers.get("origin","")
 if not origin:return False
 parsed=urlsplit(origin)
 return parsed.scheme in ("https","http") and parsed.netloc==req.headers.get("host")
def error(code,msg):
 return JSONResponse({"detail":msg},status_code=code,headers=security())
@app.get("/")
def home():return Response(status_code=302,headers={"Location":"/studio/"})
@app.get("/studio/")
def ui():return HTMLResponse((ROOT/"index.html").read_text(),headers=security())
@app.get("/studio/app.js")
def js():return Response((ROOT/"app.js").read_bytes(),media_type="text/javascript",headers=security())
@app.get("/auth/session")
def current(req:Request):
 return JSONResponse({"authenticated":authed(req)},headers=security())
@app.post("/auth/login")
async def login(req:Request):
 if not origin_ok(req):return error(403,"Origin rejected")
 if req.headers.get("content-type","").split(";")[0]!="application/json":return error(415,"JSON required")
 raw=await req.body()
 if len(raw)>1024:return error(413,"Request too large")
 try:
  obj=json.loads(raw);password=obj["password"]
  if not isinstance(password,str):raise ValueError()
 except Exception:return error(400,"Invalid request")
 who=req.headers.get("cf-connecting-ip") or (req.client.host if req.client else "unknown")
 now=time.time();ATTEMPTS[who]=[t for t in ATTEMPTS[who] if now-t<300]
 if len(ATTEMPTS[who])>=8:return error(429,"Too many attempts; try later")
 if not hmac.compare_digest(password,PASSWORD):
  ATTEMPTS[who].append(now)
  return error(401,"Incorrect password")
 ATTEMPTS.pop(who,None)
 token=secrets.token_urlsafe(48)
 SESSIONS[hashlib.sha256(token.encode()).hexdigest()]=now+TTL
 resp=JSONResponse({"authenticated":True},headers=security())
 resp.set_cookie("zs_session",token,max_age=TTL,secure=True,httponly=True,samesite="strict",path="/")
 return resp
@app.post("/auth/logout")
async def logout(req:Request):
 if not origin_ok(req):return error(403,"Origin rejected")
 token=req.cookies.get("zs_session","")
 SESSIONS.pop(hashlib.sha256(token.encode()).hexdigest(),None)
 resp=JSONResponse({"authenticated":False},headers=security())
 resp.delete_cookie("zs_session",path="/",secure=True,httponly=True,samesite="strict")
 return resp
@app.get("/v1/studio/jobs/{job_id}/prompt")
def image_prompt(req:Request,job_id:str):
 if not authed(req):return error(401,"Login required")
 if not re.fullmatch(r"[0-9a-f-]{36}",job_id):return error(400,"Invalid job ID")
 db_path=os.environ["ZIMAGE_STUDIO_DB"]
 with sqlite3.connect("file:"+db_path+"?mode=ro",uri=True,timeout=8) as c:
  row=c.execute("SELECT prompt,state FROM jobs WHERE id=?",(job_id,)).fetchone()
 if row is None:return error(404,"Job not found")
 if row[1]!="completed":return error(409,"Image not completed")
 return JSONResponse({"job_id":job_id,"prompt":row[0]},headers=security())
@app.api_route("/v1/{path:path}",methods=["GET","POST"])
async def proxy(req:Request,path:str):
 if not authed(req):return error(401,"Login required")
 import re
 valid=(req.method=="GET" and path=="jobs") or (req.method=="POST" and path=="jobs") or (req.method=="GET" and bool(re.fullmatch(r"jobs/[0-9a-f-]{36}",path))) or (req.method=="POST" and bool(re.fullmatch(r"jobs/[0-9a-f-]{36}/cancel",path))) or (req.method=="GET" and bool(re.fullmatch(r"studio/jobs/[0-9a-f-]{36}/(image|result)",path)))
 if not valid:return error(404,"Not found")
 if req.method=="POST":
  if not origin_ok(req):return error(403,"Origin rejected")
  if req.headers.get("content-type","").split(";")[0]!="application/json":return error(415,"JSON required")
 body=await req.body()
 if len(body)>8192:return error(413,"Request too large")
 upstream_headers={"Authorization":"Bearer "+API_KEY}
 if req.method=="POST":
  upstream_headers["Content-Type"]="application/json"
  if req.headers.get("idempotency-key"):upstream_headers["Idempotency-Key"]=req.headers["idempotency-key"][:128]
 async with httpx.AsyncClient(timeout=60,trust_env=False) as client:
  try:r=await client.request(req.method,UPSTREAM+"/v1/"+path,params=req.query_params,content=body,headers=upstream_headers)
  except httpx.RequestError:return error(502,"GPU service unavailable")
 return Response(r.content,status_code=r.status_code,media_type=r.headers.get("content-type","application/json"),headers=security())
