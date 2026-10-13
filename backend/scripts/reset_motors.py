import sqlite3

con = sqlite3.connect("hydracontrol.db")
cur = con.cursor()
cur.execute("UPDATE motors SET status = 'OFF' WHERE status IN ('STOPPING', 'STARTING')")
con.commit()
print("Updated rows:", cur.rowcount)
for row in cur.execute("SELECT motor_code, status FROM motors"):
    print("Motor:", row)
con.close()
