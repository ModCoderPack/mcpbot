from BotBase import BotBase
from Database import Database
import Logger

class MCPBot(BotBase):
    def __init__(self):
        super(MCPBot, self).__init__()
        self.db     = Database('172.245.30.34', 5432, 'postgres', 'mcpbot', 'MCPBot0', self)

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