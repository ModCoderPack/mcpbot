from BotBase import BotBase, BotHandler
from Database import Database

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

    def onStartUp(self):
        self.db.connect()

    def onShuttingDown(self):
        self.db.disconnect()

    def sqlrequest(self, bot, sender, dest, cmd, args):
        sql = ' '.join(args)
        val = self.db.execute(sql)

        for entry in val:
            self.sendNotice(sender.nick, str(entry))

########################################################################################################################
def main():
    bot = MCPBot()
    BotHandler.addBot(bot)
    BotHandler.runAll()

if __name__ == "__main__":
    main()