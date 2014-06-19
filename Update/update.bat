@echo off
del database.sqlite
python import_sql.py mcpbot.sql
python db_update.py 6.0 1.2.3 1.2.3
pause
