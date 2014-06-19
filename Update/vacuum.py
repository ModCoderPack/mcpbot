#!/usr/bin/env python
import argparse
import sqlite3
import time


def vacuum(db_name):
    totaltime = time.time()

    db_con = sqlite3.connect(db_name)

    db_con.execute("VACUUM")

    print '> Done in %.2f seconds' % (time.time() - totaltime)


def main():
    parser = argparse.ArgumentParser(description='Vacuum database')
    parser.add_argument('-d', '--database', help='database file', default='database.sqlite')
    args = parser.parse_args()
    vacuum(args.database)


if __name__ == '__main__':
    main()
