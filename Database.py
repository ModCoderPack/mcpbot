import psycopg2
import psycopg2.extras
from psycopg2 import DatabaseError, InterfaceError
import Logger
from contextlib import closing

class Database(object):
    def __init__(self, host, port, user, db, pwd, bot):
        self.bot  = bot
        self.host = host
        self.port = port
        self.user = user
        self.db   = db
        self.pwd  = pwd

        self.conn   = None
        #self.cursor = None

        self.logger = Logger.getLogger("MCPBot.Database", self.bot.lognormal, self.bot.logerrors)

    def connect(self):
        self.conn = psycopg2.connect(database=self.db, user=self.user, password=self.pwd, host=self.host, port=self.port)
        if not self.conn:
            self.logger.error("Error while connecting to database")
            return None
        else:
            self.logger.info("Connection to database established")
            #self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            #return self.cursor
            return self.conn

    def disconnect(self):
        self.logger.info("Committing all changes and shutting down db connection")
        self.conn.commit()
        #self.cursor.close()
        self.conn.close()
        self.logger.info("Done")


    def checkdbconn(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("select 1;")
        except (DatabaseError, InterfaceError):
            self.conn = psycopg2.connect(database=self.db, user=self.user, password=self.pwd, host=self.host, port=self.port)
            self.logger.info("*** Connection to database re-established ***")


    def execute(self, request, arguments=None):
        self.checkdbconn()
        with closing(self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)) as cursor:
            try:
                if arguments:
                    bound_request = cursor.mogrify(request, arguments)
                else:
                    bound_request = request

                self.logger.info(bound_request)
                cursor.execute(bound_request)
                retval = cursor.fetchall()
                self.conn.commit()

                return retval, None
            except Exception as e:
                self.conn.rollback()
                return None, e

    # Getters

    def getVersions(self, limit=0):
        sqlrequest = "select * from mcp.version_vw order by mcp_version_code desc "
        if limit > 0: sqlrequest += "limit " + str(limit)
        return self.execute(sqlrequest)

    def getParam(self, args):
        arg1 = args[0]
        if arg1[0] == ".": arg1 = arg1[1:]

        params = {}

        sqlrequest = "SELECT * FROM mcp.method_param_vw "
        if len(args) > 1:
            sqlrequest += "where (mc_version_code like %(version)s or mcp_version_code like %(version)s) "
            params['version'] = args[1]
        else: sqlrequest += "WHERE is_current "


        splitted = arg1.split('.')
        length = len(splitted)
        if length == 1:
            sqlrequest += "AND (srg_index = %(param)s OR mcp_name = %(param)s OR srg_name = %(param)s) "
            params['param'] = arg1
        else: # exclude srg_index if there is more than one param
            sqlrequest += "AND (mcp_name = %(param)s OR srg_name = %(param)s) "

        if length == 2:
            sqlrequest += "AND (method_srg_name = %(method)s OR method_mcp_name = %(method)s) "
            params['method'] = splitted[0]
            params['param'] = splitted[1]

        if length == 3:
            sqlrequest += "AND class_srg_name = %(class)s "
            params['class'] = splitted[0]
            params['method'] = splitted[1]
            params['param'] = splitted[2]
        else: # if the class is not specified, only return the record for the base class entry
            sqlrequest += "AND class_srg_name = srg_member_base_class "

        return self.execute(sqlrequest, params)

    def getMember(self, table, args):
        member = args[0]
        if member[0] == ".": member = member[1:]

        params = {}

        sqlrequest = "SELECT * FROM mcp.%s "%(table + "_vw")
        if len(args) > 1:
            sqlrequest += "where (mc_version_code like %(version)s or mcp_version_code like %(version)s) "
            params['version'] = args[1]
        else: sqlrequest += "WHERE is_current "

        splitted = member.split('.')
        if len(splitted) == 1:
            sqlrequest += "AND (srg_index = %(member)s OR mcp_name = %(member)s OR srg_name = %(member)s)"
            params.update({'member':member})
        else:
            sqlrequest += "AND ((class_srg_name = %(class)s AND mcp_name = %(member)s) OR (class_srg_name = %(class)s AND srg_name = %(member)s) OR(class_obf_name = %(class)s AND obf_name = %(member)s))"
            params.update({'class':splitted[0], 'member':splitted[1]})

        return self.execute(sqlrequest, params)

    def getClass(self, args):
        sqlrequest = """SELECT * FROM mcp.class_vw """
        if len(args) > 1: sqlrequest += "where (mc_version_code like %(version)s or mcp_version_code like %(version)s) "
        else: sqlrequest += "WHERE is_current "

        sqlrequest += """AND (obf_name=%(clazz)s
                         OR srg_name=%(clazz)s)"""

        if len(args) > 1: return self.execute(sqlrequest, {'clazz':args[0], 'version':args[1]})
        else: return self.execute(sqlrequest, {'clazz':args[0]})

    def findInTable(self, table, args):
        sqlrequest = "SELECT * FROM mcp.%s "%(table + '_vw')
        if len(args) > 1: sqlrequest += "where (mc_version_code like %(version)s or mcp_version_code like %(version)s) "
        else: sqlrequest += "WHERE is_current "
        sqlrequest += "AND (mcp_name ~* %(match)s OR srg_name ~* %(match)s"
        if table != 'class':
            sqlrequest += " OR srg_index ~* %(match)s) ORDER BY class_srg_name"
            if table == 'method_param':
                sqlrequest += ', srg_name'
            else:
                sqlrequest += ', mcp_name'
        else:
            sqlrequest += ") ORDER BY pkg_name, srg_name"
        if len(args) > 1: return self.execute(sqlrequest, {'match': args[0], 'version': args[1]})
        else: return self.execute(sqlrequest, {'match': args[0]})

    def getUnnamed(self, table, args):
        pkg, _, class_name = args[0].rpartition('/')
        sqlrequest = "SELECT * FROM mcp.%s WHERE is_current " % (table + '_vw')

        if pkg == '':
            sqlrequest += "AND class_srg_name = %(class_name)s "
            qry_params = {'class_name': class_name}
        else:
            sqlrequest += "AND class_srg_name = %(class_name)s AND class_pkg_name = %(pkg)s "
            qry_params = {'class_name': class_name, 'pkg': pkg}

        sqlrequest += 'AND mcp_name '

        if table == 'method':
            sqlrequest += "~ 'func_[0-9]+_[a-zA-Z]+' "
        elif table == 'field':
            sqlrequest += "~ 'field_[0-9]+_[a-zA-Z]+' "
        else:
            sqlrequest += "~ 'p_i?[0-9]+_[0-9]+_' "

        sqlrequest += 'ORDER BY srg_name'

        return self.execute(sqlrequest, qry_params)

    # Setters

    def setMemberLock(self, member_type, is_lock, command, sender, args):
        params = {'member_type': member_type, 'is_lock': is_lock, 'nick': sender.regnick.lower(),
                  'command': command, 'params': ' '.join(args), 'srg_name': args[0]}
        sqlrequest = "select mcp.set_member_lock(%(member_type)s, %(command)s, %(nick)s, %(params)s, %(srg_name)s, %(is_lock)s) as result;"
        return self.execute(sqlrequest, params)

    def setMember(self, member_type, is_forced, bypass_lock, command, sender, args):
        params = {'member_type': member_type, 'is_forced': is_forced, 'bypass_lock': bypass_lock, 'nick': sender.regnick.lower(),
                  'command': command, 'params': ' '.join(args), 'srg_name': args[0], 'new_name': args[1]}
        if len(args) > 2: params['new_desc'] = ' '.join(args[2:])
        else: params['new_desc'] = None
        sqlrequest = """select mcp.process_member_change(%(member_type)s, %(command)s, %(nick)s, %(params)s, %(srg_name)s,
                            %(new_name)s, %(new_desc)s, %(is_forced)s, %(bypass_lock)s) as result;"""
        return self.execute(sqlrequest, params)

    def getMemberChange(self, member_type, staged_pid):
        sqlrequest = "select * from mcp.staged_%(member_type)s where staged_%(member_type)s_pid = %%(staged_pid)s" % {'member_type': member_type}
        return self.execute(sqlrequest, {'staged_pid': staged_pid})