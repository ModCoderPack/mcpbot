import psycopg2.extras
from ConfigHandler import AdvConfigParser
import Logger
from contextlib import closing
import JsonHelper

logger = Logger.getLogger('push_versions_to_db', 'push_versions_to_db.log', 'push_versions_to_db_err.log')
configfile = 'bot.cfg'

def execute(conn, request, arguments=None, cursor_type=psycopg2.extras.DictCursor):
    with closing(conn.cursor(cursor_factory=cursor_type)) as cursor:
        try:
            if arguments:
                bound_request = cursor.mogrify(request, arguments)
            else:
                bound_request = request

            logger.info(bound_request)
            cursor.execute(bound_request)
            retval = cursor.fetchall()
            conn.commit()

            return retval, None
        except Exception as e:
            conn.rollback()
            logger.error(e)
            return None, e

config = AdvConfigParser()
config.read(configfile)
exports_json_url = config.get('EXPORT', 'EXPORTS_JSON_URL', '')

dbhost = config.get('DATABASE', 'HOST', "")
dbport = config.geti('DATABASE', 'PORT', "0")
dbuser = config.get('DATABASE', 'USER', "")
dbname = config.get('DATABASE', 'NAME', "")
dbpass = config.get('DATABASE', 'PASS', "")

conn = psycopg2.connect(database=dbname, user=dbuser, password=dbpass, host=dbhost, port=dbport)

sqlrequest = 'select mcp.add_available_version(%s, %s, %s);'
json_data = JsonHelper.get_remote_json(exports_json_url)
for mc_version, channels in json_data.items():
    for version_type, versions in channels.items():
        for version_code in versions:
            execute(conn, sqlrequest, (mc_version, version_type, str(version_code)))
# execute(conn, 'commit;')


