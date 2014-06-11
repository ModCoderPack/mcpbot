import psycopg2
import sqlite3
import sys
import os
import Logger

logger = Logger.getLogger("Migration", "migration.log", "migration-err.log")

tables = [
    "classes",
    "commits",
    "config",
    "fields",
    "fieldshist",
    "fieldslk",
    "interfaceslk",
    "methods",
    "methodshist",
    "methodslk",
    "packages",
    "versions"
]

def main(dbfile):
    logger.info("Starting migration")
    logger.info("Reading SQLite database")

    sqlitedata = {}

    conn = sqlite3.connect(dbfile)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    for table in tables:
        logger.info("\tTABLE %s"%table)
        cursor.execute("SELECT * FROM %s;"%table)
        sqlitedata[table] = cursor.fetchall()

    cursor.close()
    conn.close()

if __name__ == "__main__":
    if not len(sys.argv) == 2:
        logger.error("Please specify a SQLITE db file")
        sys.exit(1)

    if not os.path.exists(sys.argv[1]):
        logger.error("File does not exist")
        sys.exit(1)

    main(sys.argv[1])

