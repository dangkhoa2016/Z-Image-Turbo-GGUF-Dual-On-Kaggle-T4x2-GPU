if P23_ENABLE_OPTIONAL_WEB_APPS:
    import hashlib, tarfile, shutil, urllib.request, http.server, socketserver, threading, re
    from pathlib import Path
    GALLERY_NAME="zimage-gallery-170-watermarked-public-v1.0.0.tar.gz"
    EXPECTED_SHA256="acb2997ac8430ba239d8afadcfb8d17c7ff09634e00299f3bf8d2161681b207e"
    URL="https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/"+GALLERY_NAME
    ARCHIVE=Path("/kaggle/working")/GALLERY_NAME
    GROOT=Path("/kaggle/working/zimage-gallery-showcase")
    STAGE=Path("/kaggle/working/.zimage-gallery-170-staging")
    ready={}
    def file_sha256(path):
        h=hashlib.sha256()
        with path.open("rb") as f:
            for piece in iter(lambda:f.read(1024*1024),b""): h.update(piece)
        return h.hexdigest()
    def restore_approved_galleries():
        if not ARCHIVE.is_file() or file_sha256(ARCHIVE)!=EXPECTED_SHA256:
            urllib.request.urlretrieve(URL,ARCHIVE)
        assert file_sha256(ARCHIVE)==EXPECTED_SHA256,"Gallery archive SHA256 mismatch"
        if not GROOT.exists():
            assert not STAGE.exists(),"Incomplete staging directory"
            STAGE.mkdir()
            try:
                with tarfile.open(ARCHIVE,"r:gz") as tf:
                    for member in tf:
                        assert member.isfile() or member.isdir(),"Unsupported TAR entry"
                        dest=(STAGE/member.name).resolve()
                        assert dest.is_relative_to(STAGE.resolve()),"Unsafe TAR path"
                        if member.isdir():dest.mkdir(parents=True,exist_ok=True)
                        else:
                            dest.parent.mkdir(parents=True,exist_ok=True)
                            with tf.extractfile(member) as src,dest.open("wb") as dst:shutil.copyfileobj(src,dst)
                extracted=STAGE/"zimage-gallery-170"
                assert extracted.is_dir() and not GROOT.exists()
                extracted.rename(GROOT)
            finally: shutil.rmtree(STAGE,ignore_errors=True)
        checksums=(GROOT/"SHA256SUMS.txt").read_text().splitlines()
        assert len(checksums)>170,"Incomplete gallery checksum manifest"
        for line in checksums:
            expected,rel=line.split("  ",1)
            path=(GROOT/rel).resolve()
            assert path.is_relative_to(GROOT.resolve()) and path.is_file(),"Missing gallery asset: "+rel
            assert file_sha256(path)==expected,"Gallery checksum mismatch: "+rel
        assert len(list((GROOT/"gallery-48/images").glob("*.png")))==48
        assert len(list((GROOT/"gallery-122/output").rglob("*.png")))==122
        assert len(list((GROOT/"gallery-48/thumbs").glob("*.webp")))==40
        assert (GROOT/"gallery-48/index.html").is_file()
        assert (GROOT/"gallery-122/all-122-gallery/index.html").is_file()
        ready.update({"quality":18881,"benchmark":18882})
        print("GALLERY_170_SHA256_VERIFIED: 48 quality PNG + 122 benchmark PNG + 40 WebP thumbnails")
    try:
        restore_approved_galleries()
    except Exception as exc:
        ready.clear()
        print("OPTIONAL_GALLERY_170_UNAVAILABLE",type(exc).__name__,str(exc)[:250])
    if ready:
        from urllib.parse import urlsplit
        from functools import partial
        gallery_urls={}
        class GalleryHandler(http.server.SimpleHTTPRequestHandler):
            ROOTS={"quality":GROOT/"gallery-48","benchmark":GROOT/"gallery-122"}
            def __init__(self,*args,gallery_kind,**kwargs):
                self.gallery_kind=gallery_kind
                super().__init__(*args,directory=str(self.ROOTS[gallery_kind]),**kwargs)
            def translate_path(self,path):
                route=urlsplit(path).path
                if self.gallery_kind=="benchmark" and not route.startswith("/output/"):
                    route="/all-122-gallery"+route
                return super().translate_path(route)
            def do_GET(self):
                route=urlsplit(self.path).path
                if route in ("/","/index.html"):
                    rel="index.html" if self.gallery_kind=="quality" else "all-122-gallery/index.html"
                    html=(self.ROOTS[self.gallery_kind]/rel).read_text(encoding="utf-8")
                    html=html.replace("/gallery-48/index.html",gallery_urls.get("quality","/"))
                    html=html.replace("/gallery-122/all-122-gallery/index.html",gallery_urls.get("benchmark","/"))
                    # Adapt the bundled gallery navigation to the two live tunnel URLs.
                    # Keep archive bytes and release checksums unchanged.
                    navigation_js=(
                        "function urlTo(g){\n"
                        " const root=g===\"48\"?"+repr(gallery_urls.get("quality","/"))+":"+repr(gallery_urls.get("benchmark","/"))+";\n"
                        " return root+\"?lang=\"+lang;\n"
                        "}"
                    )
                    html,replaced=re.subn(r"function urlTo\(g\)\s*\{[\s\S]*?\n\}",lambda m:navigation_js,html,count=1)
                    assert replaced==1,"Expected one archived urlTo(g) navigation function"
                    assert "function urlTo(g)" in html
                    if gallery_urls.get("quality") and gallery_urls.get("benchmark"):
                        assert gallery_urls["quality"] in html and gallery_urls["benchmark"] in html
                    body=html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type","text/html; charset=utf-8")
                    self.send_header("Content-Length",str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    return super().do_GET()
        class ReusableServer(socketserver.ThreadingTCPServer):
            allow_reuse_address=True
        gallery_servers={}
        for kind,port in (("quality",18881),("benchmark",18882)):
            server=ReusableServer(("127.0.0.1",port),partial(GalleryHandler,gallery_kind=kind))
            threading.Thread(target=server.serve_forever,daemon=True).start()
            gallery_servers[kind]=server
            assert urllib.request.urlopen("http://127.0.0.1:"+str(port)+"/",timeout=5).status==200
        print("GALLERY_SERVERS_READY quality=18881 benchmark=18882")
    else:
        print("GALLERY_SERVERS_SKIPPED")
else:
    print("P23_OPTIONAL_UI_SKIPPED: static galleries (enable P23_ENABLE_OPTIONAL_WEB_APPS to run)")
