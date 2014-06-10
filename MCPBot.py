from BotBase import BotBase
from Database import Database
import Logger

class MCPBot(BotBase):
    def __init__(self):
        super(MCPBot, self).__init__()
        self.dbhost = self.getConfig('DATABASE', 'HOST', "")
        self.dbport = int(self.getConfig('DATABASE', 'PORT', "0"))
        self.dbuser = self.getConfig('DATABASE', 'USER', "")
        self.dbname = self.getConfig('DATABASE', 'NAME', "")
        self.dbpass = self.getConfig('DATABASE', 'PASS', "")

        self.db = Database(self.dbhost, self.dbport, self.dbuser, self.dbname, self.dbpass, self)

        self.registerCommand('sqlrequest', self.sqlrequest, ['admin'], 1, 999, "Execute a raw SQL command")

    def runBot(self):
        self.db.connect()
        self.run()

    def sqlrequest(self, bot, sender, dest, cmd, args):
        sql = ' '.join(args)
        val = self.db.execute(sql)

        for entry in val:
            self.sendNotice(sender.nick, str(entry))

    def onShuttingDown(self):
        self.db.disconnect()

########################################################################################################################
def main():
    bot = MCPBot()
    bot.runBot()

if __name__ == "__main__":
    main()