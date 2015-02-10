#################################################################################
#
# export_csv.py
# Exports all committed changes (or staged changes with -T option).
#
# Author: bspkrs
#
#################################################################################

__author__ = "bspkrs (bspkrs@gmail.com)"
__version__ = "0.3.0"

from optparse import OptionParser
import psycopg2
import psycopg2.extras
import csv
from sys import exit
import os
from contextlib import closing
import Logger
try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser


exports = \
    [
        {   'csvfile': "methods.csv", # searge, name, side, desc
            'columns': ['searge', 'name', 'side', 'desc'],
            'query': """select m.srg_name as searge, m.mcp_name as name,
                    (case when m.is_on_client and not m.is_on_server then 0 when not m.is_on_client and m.is_on_server then 1 else 2 end) as side,
                    m.comment || (case when p.desc is not null then '\\n \\n' || p.desc else '' end) as desc
                from mcp.method m
                left join (
                        select mp.method_pid, string_agg('@param ' || mp.mcp_name || ' ' || mp.comment, '\\n' order by mp.param_number) as desc
                        from mcp.method_param mp
                        where mp.srg_name ~ 'p_i?[0-9]+_'
                            and mp.mcp_version_pid = %(mcp_version)s
                            and mp.mcp_name is not null and mp.comment is not null
                        group by mp.method_pid
                        ) p on p.method_pid = m.method_pid
                where m.srg_name ~ 'func_[0-9]+_[a-zA-Z]+'
                    and m.mcp_version_pid = %(mcp_version)s
                    and m.mcp_name is not null
                order by m.srg_name"""
        },

        {   'csvfile': "fields.csv", # searge, name, side, desc
            'columns': ['searge', 'name', 'side', 'desc'],
            'query': """select f.srg_name as searge, f.mcp_name as name,
                    (case when f.is_on_client and not f.is_on_server then 0 when not f.is_on_client and f.is_on_server then 1 else 2 end) as side,
                    f.comment as desc
                from mcp.field f
                where f.srg_name ~ 'field_[0-9]+_[a-zA-Z]+'
                    and f.mcp_version_pid = %(mcp_version)s
                    and f.mcp_name is not null
                order by f.srg_name;"""
        },

        {   'csvfile': "params.csv", # param, name, side
            'columns': ['param', 'name', 'side'],
            'query': """select mp.srg_name as param, mp.mcp_name as name,
                    (case when m.is_on_client and not m.is_on_server then 0 when not m.is_on_client and m.is_on_server then 1 else 2 end) as side
                from mcp.method_param mp
                join mcp.method m on m.method_pid = mp.method_pid
                where mp.srg_name ~ 'p_i?[0-9]+_'
                    and mp.mcp_version_pid = %(mcp_version)s
                    and mp.mcp_name is not null
                order by mp.srg_name;"""
        },
    ]

exports_nodoc = \
    [
        {   'csvfile': exports[0]['csvfile'], 'columns': exports[0]['columns'],
            'query': """select m.srg_name as searge, m.mcp_name as name,
                    (case when m.is_on_client and not m.is_on_server then 0 when not m.is_on_client and m.is_on_server then 1 else 2 end) as side,
                    '' as desc
                from mcp.method m
                where m.srg_name ~ 'func_[0-9]+_[a-zA-Z]+'
                    and m.mcp_version_pid = %(mcp_version)s
                    and m.mcp_name is not null
                order by m.srg_name"""
        },

        {   'csvfile': exports[1]['csvfile'], 'columns': exports[1]['columns'],
            'query': exports[1]['query'].replace('f.comment', "''")
        },

        exports[2],
    ]

test_exports = \
    [
        {   'csvfile': "methods.csv", # searge, name, side, desc
            'columns': ['searge', 'name', 'side', 'desc'],
            'query': """select m.srg_name as searge, coalesce(sm.new_mcp_name, m.mcp_name) as name,
                    (case when m.is_on_client and not m.is_on_server then 0 when not m.is_on_client and m.is_on_server then 1 else 2 end) as side,
                    coalesce(sm.new_mcp_desc, m.comment) || (case when p.desc is not null then '\\n \\n' || p.desc else '' end) as desc
                from mcp.method m
                left join mcp.staged_method sm
                    on sm.staged_method_pid = m.staged_method_pid
                left join (
                        select mp.method_pid, string_agg('@param ' || coalesce(smp.new_mcp_name, mp.mcp_name) || ' ' || coalesce(smp.new_mcp_desc, mp.comment), '\\n' order by mp.param_number) as desc
                        from mcp.method_param mp
                        left join mcp.staged_method_param smp
                            on smp.staged_method_param_pid = mp.staged_method_param_pid
                        where mp.srg_name ~ 'p_i?[0-9]+_'
                            and mp.mcp_version_pid = %(mcp_version)s
                            and coalesce(mp.mcp_name, smp.new_mcp_name) is not null and coalesce(mp.comment, smp.new_mcp_desc) is not null
                        group by mp.method_pid
                        ) p on p.method_pid = m.method_pid
                where m.srg_name ~ 'func_[0-9]+_[a-zA-Z]+'
                    and m.mcp_version_pid = %(mcp_version)s
                    and (m.mcp_name is not null or sm.new_mcp_name is not null)
                order by m.srg_name;"""
        },

        {   'csvfile': "fields.csv", # searge, name, side, desc
            'columns': ['searge', 'name', 'side', 'desc'],
            'query': """select f.srg_name as searge, coalesce(sf.new_mcp_name, f.mcp_name) as name,
                    (case when f.is_on_client and not f.is_on_server then 0 when not f.is_on_client and f.is_on_server then 1 else 2 end) as side,
                    coalesce(sf.new_mcp_desc, f.comment) as desc
                from mcp.field f
                left join mcp.staged_field sf
                    on sf.staged_field_pid = f.staged_field_pid
                where f.srg_name ~ 'field_[0-9]+_[a-zA-Z]+'
                    and f.mcp_version_pid = %(mcp_version)s
                    and (f.mcp_name is not null or sf.new_mcp_name is not null)
                order by f.srg_name;"""
        },

        {   'csvfile': "params.csv", # param, name, side
            'columns': ['param', 'name', 'side'],
            'query': """select mp.srg_name as param, coalesce(sm.new_mcp_name, mp.mcp_name) as name,
                    (case when m.is_on_client and not m.is_on_server then 0 when not m.is_on_client and m.is_on_server then 1 else 2 end) as side
                from mcp.method_param mp
                join mcp.method m on m.method_pid = mp.method_pid
                left join mcp.staged_method_param sm
                    on sm.staged_method_param_pid = mp.staged_method_param_pid
                where mp.srg_name ~ 'p_i?[0-9]+_'
                    and mp.mcp_version_pid = %(mcp_version)s
                    and (mp.mcp_name is not null or sm.new_mcp_name is not null)
                order by mp.srg_name;"""
        },
    ]

test_exports_nodoc = \
    [
        {   'csvfile': test_exports[0]['csvfile'], 'columns': test_exports[0]['columns'],
            'query': """select m.srg_name as searge, coalesce(sm.new_mcp_name, m.mcp_name) as name,
                    (case when m.is_on_client and not m.is_on_server then 0 when not m.is_on_client and m.is_on_server then 1 else 2 end) as side,
                    '' as desc
                from mcp.method m
                left join mcp.staged_method sm
                    on sm.staged_method_pid = m.staged_method_pid
                where m.srg_name ~ 'func_[0-9]+_[a-zA-Z]+'
                    and m.mcp_version_pid = %(mcp_version)s
                    and (m.mcp_name is not null or sm.new_mcp_name is not null)
                order by m.srg_name"""
        },

        {   'csvfile': test_exports[1]['csvfile'], 'columns': test_exports[1]['columns'],
            'query': test_exports[1]['query'].replace('coalesce(sf.new_mcp_desc, f.comment)', "''")
        },

        test_exports[2],
    ]


logger = Logger.getLogger("Export_CSV", "export_csv.log", "export_csv-err.log")


def export_data(pgconn, query, csvfile, columns, export_path):
    pgcursor = pgconn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    pgcursor.execute("select mcp.get_current_mcp_version_pid() as mcp_version;")
    result = pgcursor.fetchall()
    mcp_version = result[0]['mcp_version']

    #logger.info("Fetching %s data..." % csvfile.rstrip('.csv'))
    pgcursor.execute(query, {'mcp_version': mcp_version})
    data = pgcursor.fetchall()
    logger.info("Writing %d rows to %s..." % (len(data), csvfile))
    with open(os.path.join(export_path, csvfile), 'wb') as f:
        w = csv.DictWriter(f, columns)
        w.writeheader()
        w.writerows(data)

    logger.debug("%d total rows exported" % len(data))
    pgcursor.close()


def do_export(dbhost, dbport, dbname, dbuser, dbpass, test_csv, export_path, no_doc=False):
    logger.info("=== Starting CSV Export ===")

    pgconn = psycopg2.connect(database=dbname, user=dbuser, password=dbpass, host=dbhost, port=dbport)

    if not os.path.exists(export_path):
        try:
            os.makedirs(export_path)
        except OSError:
            if not os.path.isdir(export_path):
                raise

    if test_csv:
        if no_doc:
            export_list = test_exports_nodoc
        else:
            export_list = test_exports
        logger.info("Exporting Test CSV data...")
    else:
        if no_doc:
            export_list = exports_nodoc
        else:
            export_list = exports
        logger.info("Exporting Committed CSV data...")

    for export in export_list:
        export_data(pgconn, export['query'], export['csvfile'], export['columns'], export_path)

    pgconn.close()


def getConfig(config, section, option, default):
    if not config.has_section(section):
        config.add_section(section)

    if config.has_option(section, option):
        return config.get(section, option)
    else:
        config.set(section, option, default)
        return config.get(section, option)


def run():
    parser = OptionParser(version='%prog ' + __version__,
                          usage="%prog [options]")
    parser.add_option('-C', '--config-only', action='store_true', default=False,
                      help='Generates the config file and exits (other options ignored) [default: %default]')
    parser.add_option('-N', '--no-doc', action='store_true', default=False,
                      help="Use this flag if you don't require comments in the csv files [default: %default]")
    parser.add_option('-P', '--export-path', default=".",
                      help="The path to export to (will be created if it doesn't exist) [default: %default]")
    parser.add_option('-T', '--test-csv', action='store_true', default=False,
                      help='Exports staged mappings as opposed to only committed mappings [default: %default]')


    options, args = parser.parse_args()
    logger.info('MCPBot CSV Export v' + __version__)

    configfile = 'export.cfg'
    logger.info('Reading config file %s...', configfile)
    config = ConfigParser.RawConfigParser()
    config.read(configfile)
    dbhost = getConfig(config, 'DATABASE', 'HOST', "localhost")
    dbport = int(getConfig(config, 'DATABASE', 'PORT', "5432"))
    dbname = getConfig(config, 'DATABASE', 'NAME', "mcpbot")
    dbuser = getConfig(config, 'DATABASE', 'USER', "postgres")
    dbpass = getConfig(config, 'DATABASE', 'PASS', "")
    fp = open(configfile, 'w')
    logger.info('Writing config file %s...', configfile)
    config.write(fp)

    if options.config_only:
        logger.info('-C or --config-only flag specified, bailing out.')
        exit()

    do_export(dbhost, dbport, dbname, dbuser, dbpass, options.test_csv, options.export_path, options.no_doc)

    logger.info("MCPBot CSV Export is Complete. Review logs for any errors.")

if __name__ == '__main__':
    run()

