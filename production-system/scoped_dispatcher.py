"""Session-scoped dispatcher preserving existing dispatcher contracts."""
from contextlib import closing
from http_dispatcher import Dispatcher,connect
class ScopedDispatcher(Dispatcher):
 def __init__(self,adapters,session_id,**kwargs):
  if not session_id or not session_id.startswith("b112-"):raise ValueError("invalid session")
  self.session_id=session_id
  super().__init__(adapters,**kwargs)
 def claim(self,slot):
  # Narrow the inherited algorithm to the session job snapshot.
  import time
  from mock_dispatcher import event
  with closing(connect()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    occupied=c.execute("SELECT 1 FROM jobs WHERE worker_id=? AND state IN ('running','uncertain')",(slot,)).fetchone()
    if occupied:c.execute("COMMIT");return None
    row=c.execute("""SELECT j.*,m.prompt_id FROM jobs j
      JOIN b113_session_jobs sj ON sj.job_id=j.id
      JOIN b14_prompt_map m ON m.prompt=j.prompt
      WHERE j.state='queued' AND sj.session_id=?
      ORDER BY j.created_at,j.id LIMIT 1""",(self.session_id,)).fetchone()
    if row is None:c.execute("COMMIT");return None
    n=c.execute("""UPDATE jobs SET state='running',worker_id=?,attempt=attempt+1,
      lease_owner=?,lease_deadline=?,updated_at=? WHERE id=? AND state='queued'""",
      (slot,self.owner,time.time()+self.lease,time.time(),row["id"])).rowcount
    if n!=1:raise RuntimeError("lost session claim")
    event(c,row["id"],f"SESSION_CLAIM_{slot}")
    c.execute("COMMIT");return dict(row)
   except BaseException:c.execute("ROLLBACK");raise
 def drain(self,timeout=15):
  # Existing drain() tests global queued-map state; active prompts admitted
  # after freeze are blocked by b113 admission, other queued prompts have no map.
  return super().drain(timeout=timeout)
