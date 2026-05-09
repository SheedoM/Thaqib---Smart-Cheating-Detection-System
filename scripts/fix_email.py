#!/usr/bin/env python3
"""
Simple script to replace `@admin.local` user emails with `@example.com` variants.
Run from the repository root: `python scripts/fix_email.py`.
"""
import sqlite3
from pathlib import Path
import sys

DB = Path("data/thaqib.db")
if not DB.exists():
    print(f"Database not found: {DB.resolve()}")
    sys.exit(1)

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id, username, email FROM users WHERE email LIKE ?", ("%@admin.local",))
rows = cur.fetchall()
if not rows:
    print("No users with '@admin.local' found.")
else:
    print(f"Found {len(rows)} user(s) to update.")
    for row in rows:
        uid = row['id']
        username = row['username']
        old_email = row['email']
        new_email = f"{username}@example.com"
        print(f"Updating {username}: {old_email} -> {new_email}")
        cur.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, uid))
    conn.commit()
    print("Done.")

conn.close()
