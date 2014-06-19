#!/usr/bin/env python
import argparse
from contextlib import closing
import csv
import os
import sqlite3
import time


def csv_export(db_name):
    totaltime = time.time()

    db = sqlite3.connect(db_name)
    db.text_factory = sqlite3.OptimizedUnicode
    db.execute("PRAGMA foreign_keys = ON")
    with db:
        with closing(db.cursor()) as cur:
            query = """
                SELECT value
                FROM config
                WHERE name=:name
            """
            cur.execute(query, {'name': 'currentversion'})
            row = cur.fetchone()
            if row is None:
                raise Exception("currentversion not set")
            else:
                version_id = row[0]

            if not os.path.exists('out'):
                os.makedirs('out')

            with open('out/methods.csv', 'wb') as method_file:
                method_writer = csv.writer(method_file, quoting=csv.QUOTE_ALL)
                method_writer.writerow(('searge', 'name', 'notch', 'sig', 'notchsig', 'classname', 'classnotch',
                                        'package', 'side', 'desc'))
                query = """
                    SELECT searge, name, notch, sig, notchsig, classname, classnotch, package, side, desc
                    FROM vmethods
                    WHERE name != classname
                      AND versionid=:version_id
                """
                cur.execute(query, {'version_id': version_id})
                rows = cur.fetchall()
                for row in rows:
                    method_writer.writerow(row)

            with open('out/fields.csv', 'wb') as field_file:
                field_writer = csv.writer(field_file, quoting=csv.QUOTE_ALL)
                field_writer.writerow(('searge', 'name', 'notch', 'sig', 'notchsig', 'classname', 'classnotch',
                                       'package', 'side', 'desc'))
                query = """
                    SELECT searge, name, notch, sig, notchsig, classname, classnotch, package, side, desc
                    FROM vfields
                    WHERE name != classname
                      AND versionid=:version_id
                """
                cur.execute(query, {'version_id': version_id})
                rows = cur.fetchall()
                for row in rows:
                    field_writer.writerow(row)

            with open('out/classes.csv', 'wb') as class_file:
                class_writer = csv.writer(class_file, quoting=csv.QUOTE_ALL)
                class_writer.writerow(('name', 'notch', 'supername', 'package', 'side'))
                query = """
                    SELECT name, notch, supername, package, side
                    FROM vclasses
                    WHERE versionid=:version_id
                """
                cur.execute(query, {'version_id': version_id})
                rows = cur.fetchall()
                for row in rows:
                    class_writer.writerow(row)

    print '> Done in %.2f seconds' % (time.time() - totaltime)


def main():
    parser = argparse.ArgumentParser(description='CSV export')
    parser.add_argument('-d', '--database', help='database file', default='database.sqlite')
    args = parser.parse_args()
    csv_export(args.database)


if __name__ == '__main__':
    main()
