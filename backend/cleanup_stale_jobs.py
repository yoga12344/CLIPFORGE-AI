import sqlite3
from datetime import datetime

conn = sqlite3.connect('backend/storage/clipforge_data/database/clipforge.db')
c = conn.cursor()
c.execute("UPDATE jobs SET status = 'failed', error_message = 'Interrupted by application restart.', stage_description = 'Interrupted', completed_at = ? WHERE status IN ('running', 'queued')", (datetime.utcnow().isoformat(),))
conn.commit()
print("Updated stale jobs:", c.rowcount)
counts = c.execute("SELECT status, count(id) FROM jobs GROUP BY status").fetchall()
print("Current job counts:", counts)
