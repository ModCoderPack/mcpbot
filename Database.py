import psycopg2
import psycopg2.extras
import Logger


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

    def execute(self, request):
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            try:
                cursor.execute(request)
                retval = cursor.fetchall()
                self.conn.commit()

                return retval, None
            except Exception as e:
                self.conn.rollback()
                return None, e

    def executeGet(self, request, arguments):
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            try:
                cursor.execute(request, arguments)
                retval = cursor.fetchall()
                return retval, None
            except Exception as e:
                self.conn.rollback()
                return None, e

    def getmember(self, table, member):
        membertype = {'field':'field', 'method':'func'}[table]

        splitted = member.split('.')
        if len(splitted) == 1:
            sqlrequest = """SELECT * FROM mcp.%s WHERE is_current=TRUE
                                                   AND (   srg_name LIKE %%(imember)s
                                                        OR mcp_name=%%(member)s
                                                        OR srg_name=%%(member)s)"""%(table + "_vw")
            self.logger.debug(sqlrequest)
            return self.executeGet(sqlrequest, {'imember':membertype + "_" + member + '_%','member':member})
        else:
            sqlrequest = """SELECT * FROM mcp.%s WHERE is_current=TRUE
                                                   AND ((class_srg_name=%%(class)s AND mcp_name=%%(member)s)
                                                     OR (class_srg_name=%%(class)s AND srg_name=%%(member)s)
                                                     OR (class_obf_name=%%(class)s AND obf_name=%%(member)s))"""%(table + "_vw")
            self.logger.debug(sqlrequest)
            return self.executeGet(sqlrequest, {'class':splitted[0], 'member':splitted[1]})
