"""B3 private artifact boundary, CPU-only. NOT an off-host durable store or HTTP endpoint."""
from pathlib import Path
from io import BytesIO
from PIL import Image
import hashlib,os,re,sqlite3,stat,tempfile,time,uuid

OWNER_PATTERN=re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
MAX_BYTES=16*1024*1024

class Store:
    def __init__(self, root):
        self.root=Path(root).absolute()
        if self.root.is_symlink():raise ValueError("symlink store root")
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(self.root,0o700)
        self.objects=self.root/"objects"
        if self.objects.is_symlink():raise ValueError("symlink objects")
        self.objects.mkdir(exist_ok=True,mode=0o700)
        os.chmod(self.objects,0o700)
        self.db=self.root/"artifact-index.sqlite3"
        if self.db.is_symlink():raise ValueError("symlink database")
        with self._db() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS artifact (
              job_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, digest TEXT NOT NULL,
              byte_count INTEGER NOT NULL, created_utc REAL NOT NULL)""")
        os.chmod(self.db,0o600)

    def _db(self):
        c=sqlite3.connect(self.db,timeout=15)
        c.execute("PRAGMA busy_timeout=15000")
        c.execute("PRAGMA synchronous=FULL")
        return c

    @staticmethod
    def _ident(job_id, owner):
        try:
            if str(uuid.UUID(job_id))!=job_id:raise ValueError()
        except (ValueError,TypeError,AttributeError):
            raise ValueError("canonical UUID required") from None
        if not isinstance(owner,str) or not OWNER_PATTERN.fullmatch(owner):
            raise ValueError("invalid owner identifier")

    @staticmethod
    def _validate_png(data):
        if not isinstance(data,bytes) or not 0<len(data)<=MAX_BYTES:raise ValueError("invalid PNG byte length")
        try:
            with Image.open(BytesIO(data)) as im:
                if im.format!="PNG" or im.size!=(1024,1024):raise ValueError("expected 1024x1024 PNG")
                im.verify()
        except (OSError,SyntaxError) as exc:
            raise ValueError("PNG verification failed") from exc

    def _object(self,digest):
        folder=self.objects/digest[:2]
        if folder.is_symlink():raise RuntimeError("symlink object directory blocked")
        folder.mkdir(mode=0o700,exist_ok=True)
        os.chmod(folder,0o700)
        p=folder/(digest+".png")
        if p.is_symlink():raise RuntimeError("symlink artifact blocked")
        return p

    def _checked_data(self,digest):
        p=self._object(digest)
        fd=os.open(p,os.O_RDONLY | getattr(os,"O_NOFOLLOW",0))
        with os.fdopen(fd,"rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):raise RuntimeError("artifact not a regular file")
            data=f.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES or hashlib.sha256(data).hexdigest()!=digest:
            raise RuntimeError("artifact integrity failure")
        return data

    def put(self,job_id,owner_id,png_bytes):
        self._ident(job_id,owner_id)
        self._validate_png(png_bytes)
        digest=hashlib.sha256(png_bytes).hexdigest()
        with self._db() as c:
            c.execute("BEGIN IMMEDIATE")
            old=c.execute("SELECT owner_id,digest FROM artifact WHERE job_id=?",(job_id,)).fetchone()
            if old:
                if old!=(owner_id,digest):raise LookupError("conflicting or unauthorized job")
                self._checked_data(digest)
                return {"job_id":job_id,"sha256":digest,"bytes":len(png_bytes),"idempotent":True}
            path=self._object(digest)
            fd,temp=tempfile.mkstemp(prefix=".pending-",dir=path.parent)
            try:
                os.fchmod(fd,0o600)
                with os.fdopen(fd,"wb") as f:
                    f.write(png_bytes);f.flush();os.fsync(f.fileno())
                try:os.link(temp,path,follow_symlinks=False)
                except FileExistsError:pass
                self._checked_data(digest)
                # Persist directory entry before committing the database receipt.
                dfd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(dfd)
                finally:os.close(dfd)
            finally:
                if os.path.exists(temp):os.unlink(temp)
            c.execute("INSERT INTO artifact VALUES (?,?,?,?,?)",
                      (job_id,owner_id,digest,len(png_bytes),time.time()))
        return {"job_id":job_id,"sha256":digest,"bytes":len(png_bytes),"idempotent":False}

    def get(self,job_id,owner_id):
        self._ident(job_id,owner_id)
        with self._db() as c:
            row=c.execute("SELECT digest FROM artifact WHERE job_id=? AND owner_id=?",
                          (job_id,owner_id)).fetchone()
        if row is None:raise LookupError("artifact not found")
        return self._checked_data(row[0])
