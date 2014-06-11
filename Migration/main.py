import psycopg2
import psycopg2.extras
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

    #Just a sample output to demonstrate row/column access
    for row in sqlitedata['versions']:
        logger.info(dict(row))
        logger.info("%s %s %s"%(row['mcpversion'], row['clientversion'], row['timestamp']))

    #Demonstration section for postgre
    conn   = psycopg2.connect(database='', user='', password='', host='', port='')
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    #If you have the table and column names.
    for row in sqlitedata['versions']:
        cursor.execute("INSERT INTO FooBar(mcpversion, clientversion, timestamp) VALUES(?,?,?)",
           row['mcpversion'], row['clientversion'], row['timestamp'] )

    #If you want to do some string substitution for the table and columns (as most DB libs only replace values)
    #Insert is still sanitized on the VALUES this way, but it offers more flexibility for the tables/columns
    for row in sqlitedata['versions']:
        cursor.execute("INSERT INTO %s(%s, %s, %s) VALUES(?,?,?)"%('tablename', 'column1', 'column2', 'column3'),
           row['mcpversion'], row['clientversion'], row['timestamp'] )
    conn.commit()

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

