import psycopg2
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
        self.cursor = None

        self.logger = Logger.getLogger("MCPBot.Database", self.bot.lognormal, self.bot.logerrors)

    def connect(self):
        self.conn = psycopg2.connect(database=self.db, user=self.user, password=self.pwd, host=self.host, port=self.port)
        if not self.conn:
            self.logger.error("Error while connecting to database")
            return None
        else:
            self.logger.info("Connection to database established")
            self.cursor = self.conn.cursor()
            return self.cursor

    def disconnect(self):
        self.logger.info("Committing all changes and shutting down db connection")
        self.conn.commit()
        self.cursor.close()
        self.conn.close()
        self.logger.info("Done")

    def execute(self, request):
        self.cursor.execute(request)
        retval = self.cursor.fetchall()
        self.conn.commit()

        return retval
