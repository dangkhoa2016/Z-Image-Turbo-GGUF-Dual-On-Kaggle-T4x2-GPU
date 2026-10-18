"""Single-tenant Vue Studio gateway backed by the private artifact API.
Loopback-only service. Never expose parallel admission routes or backend credentials.
"""
from pathlib import Path
import sys
from fastapi import Depends,HTTPException
HERE=Path(__file__).resolve().parent
PRIVATE_STORE=HERE.parent/"private-artifact-store"
sys.path.insert(0,str(PRIVATE_STORE))
import tenant_api as t

app=t.app
@app.get("/v1/studio/jobs/{job_id}/image")
def studio_image(job_id:str,owner:str=Depends(t.tenant)):
    return t.get_image(job_id,owner)

@app.get("/v1/studio/jobs/{job_id}/result")
def studio_result(job_id:str,owner:str=Depends(t.tenant)):
    with t.connect() as c:
        row=t.owner_job(c,job_id,owner)
    if row["state"]!="completed":raise HTTPException(409,"Not completed")
    try:
        data=t.store.get(job_id,owner)
    except LookupError:
        raise HTTPException(404,"Image not published")
    import hashlib
    if hashlib.sha256(data).hexdigest()!=row["output_sha256"]:
        raise HTTPException(503,"Receipt mismatch")
    return {"job_id":job_id,"sha256":row["output_sha256"],"worker_id":row["worker_id"],
            "image_url":f"/v1/studio/jobs/{job_id}/image","status":"completed"}
