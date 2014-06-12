# coding=utf-8
from BotBase import BotBase, BotHandler
from Database import Database
import psycopg2

class MCPBot(BotBase):
    def __init__(self):
        super(MCPBot, self).__init__()

        self.dbhost = self.getConfig('DATABASE', 'HOST', "")
        self.dbport = int(self.getConfig('DATABASE', 'PORT', "0"))
        self.dbuser = self.getConfig('DATABASE', 'USER', "")
        self.dbname = self.getConfig('DATABASE', 'NAME', "")
        self.dbpass = self.getConfig('DATABASE', 'PASS', "")

        self.db = Database(self.dbhost, self.dbport, self.dbuser, self.dbname, self.dbpass, self)

        self.registerCommand('sqlrequest', self.sqlrequest, ['admin'], 1, 999, "Execute a raw SQL command.")
        self.registerCommand('gf',         self.getfield,   ['admin'], 1, 1,   "<field_notch|field_index|field_name> : Returns the given field information.")
        self.registerCommand('gm',         self.getmethod,  ['admin'], 1, 1,   "<field_notch|field_index|field_name> : Returns the given field information.")

    def onStartUp(self):
        self.db.connect()

    def onShuttingDown(self):
        self.db.disconnect()

    def sqlrequest(self, bot, sender, dest, cmd, args):
        sql = ' '.join(args)

        val, status = self.db.execute(sql)

        if status != None:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if len(val) > 0:
            for entry in val:
                self.sendNotice(sender.nick, dict(entry))
        else:
            self.sendNotice(sender.nick, "No result found.")

    def getfield(self, bot, sender, dest, cmd, args):
        val, status = self.db.getmember('field', args[0])
        self.sendResults(bot, sender, val, status)

    def getmethod(self, bot, sender, dest, cmd, args):
        val, status = self.db.getmember('method', args[0])
        self.sendResults(bot, sender, val, status)

    def sendResults(self, bot, sender, val, status):
        if status != None:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if len(val) > 0:
            #self.sendNotice(sender.nick, val[0].keys())

            for entry in val:
                self.sendNotice(sender.nick, " ".format(**entry))
                self.sendNotice(sender.nick, "=== §B{class_srg_name}.{mcp_name}§N ===".format(**entry))
                self.sendNotice(sender.nick, "§UDescriptor§N : {obf_descriptor} §B|§N {srg_descriptor}".format(**entry))
                self.sendNotice(sender.nick, "§UNames§N      : {obf_name} §B|§N {srg_name} §B|§N {mcp_name}".format(**entry))
                self.sendNotice(sender.nick, "§UComment§N    : {comment}".format(**entry))
        else:
            self.sendNotice(sender.nick, "No result found.")

########################################################################################################################
def main():
    bot = MCPBot()
    BotHandler.addBot(bot)
    BotHandler.runAll()

if __name__ == "__main__":
    main()