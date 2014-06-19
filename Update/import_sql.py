#!/usr/bin/env python
import argparse
from contextlib import closing
import sqlite3
import time
import os


def import_sql(db_name, sql_file, force):
    totaltime = time.time()

    if force:
        try:
            os.stat(db_name)
        except OSError:
            pass
        else:
            try:
                os.remove(db_name)
            except OSError:
                raise Exception('Failed to remove existing database')

    db_con = sqlite3.connect(db_name)

    with db_con:
        db_con.execute("PRAGMA foreign_keys = ON")
        cur = db_con.cursor()
        with open(sql_file, 'r') as sql:
            cur.executescript(sql.read())

    with closing(db_con.cursor()) as cur:
        cur.execute("VACUUM")

    print '> Done in %.2f seconds' % (time.time() - totaltime)


def main():
    parser = argparse.ArgumentParser(description='Import sql file')
    parser.add_argument('sql_file')
    parser.add_argument('-d', '--database', help='database file', default='database.sqlite')
    parser.add_argument('-f', '--force', action='store_true', default=False, help='overwrite existing database')
    args = parser.parse_args()
    import_sql(args.database, args.sql_file, args.force)


if __name__ == '__main__':
    main()
