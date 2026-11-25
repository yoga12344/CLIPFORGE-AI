import sqlite3
import json

conn = sqlite3.connect('backend/storage/clipforge_data/database/clipforge.db')
c = conn.cursor()

job_ids = [
    '8ec210be-a44f-4fba-b8f4-0036df57c7f6',
    'e5056ffa-4ec6-4d45-9ab4-a4b5c61399e2',
    'b8687d21-2032-4f5d-95f4-3d6e57ebdddc',
    '187a3f22-59a7-4e12-95a2-f36e36302183'
]

for jid in job_ids:
    row = c.execute("SELECT id, job_type, status, error_message, params, result_data, project_id FROM jobs WHERE id = ?", (jid,)).fetchone()
    print("=" * 60)
    print(f"Job: {row[0]} ({row[1]}) -> {row[2]}")
    print(f"Project ID: {row[6]}")
    print(f"Error: {row[3]}")
    print(f"Params: {row[4]}")
    print(f"Result: {row[5]}")

print("\nChecking composition_renders table for any rows:")
c_renders = c.execute("SELECT id, composition_id, status FROM composition_renders LIMIT 5").fetchall()
print("Composition renders in DB:", c_renders)

print("\nChecking videos table columns and rows:")
c.execute("PRAGMA table_info(videos)")
print("Video columns:", [r[1] for r in c.fetchall()])
vids = c.execute("SELECT id, project_id, file_path FROM videos LIMIT 5").fetchall()
print("Sample videos:", vids)

print("\nChecking highlight_candidates table for project 08153cd6-915f-418c-aff5-8263dd2903d0:")
c.execute("PRAGMA table_info(highlight_candidates)")
print("Candidate cols:", [r[1] for r in c.fetchall()])
hc = c.execute("SELECT id, video_id, title, score, status FROM highlight_candidates LIMIT 5").fetchall()
print("Highlight candidates in DB:", hc)

print("\nChecking clips table for project 08153cd6-915f-418c-aff5-8263dd2903d0:")
clips = c.execute("SELECT id, project_id, title FROM clips WHERE project_id = '08153cd6-915f-418c-aff5-8263dd2903d0'").fetchall()
print("Clips for project:", clips)
