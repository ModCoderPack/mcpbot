# coding=utf-8
from BotBase import BotBase, BotHandler
from Database import Database
import re

class MCPBot(BotBase):
    def __init__(self):
        super(MCPBot, self).__init__()

        self.dbhost = self.getConfig('DATABASE', 'HOST', "")
        self.dbport = int(self.getConfig('DATABASE', 'PORT', "0"))
        self.dbuser = self.getConfig('DATABASE', 'USER', "")
        self.dbname = self.getConfig('DATABASE', 'NAME', "")
        self.dbpass = self.getConfig('DATABASE', 'PASS', "")

        self.db = Database(self.dbhost, self.dbport, self.dbuser, self.dbname, self.dbpass, self)

        self.registerCommand('sqlrequest', self.sqlRequest, ['admin'], 1, 999, "<sql command>", "Execute a raw SQL command.")
        self.registerCommand('gf',         self.getField,   ['admin'], 1, 1,   "[class.]<name>","Returns the given field  information.")
        self.registerCommand('gm',         self.getMethod,  ['admin'], 1, 1,   "[class.]<name>","Returns the given method information.")
        self.registerCommand('gc',         self.getClass,   ['admin'], 1, 1,   "<class>",       "Returns the given class  information.")
        self.registerCommand('find',       self.findKey,    ['admin'], 1, 1,   "<pattern>",     "Returns all entries with the given pattern in MCP.")

    def onStartUp(self):
        self.db.connect()

    def onShuttingDown(self):
        self.db.disconnect()

    def sqlRequest(self, bot, sender, dest, cmd, args):
        sql = ' '.join(args)

        val, status = self.db.execute(sql)

        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if len(val) > 0:
            for entry in val:
                self.sendNotice(sender.nick, dict(entry))
        else:
            self.sendNotice(sender.nick, "No result found.")



    def getField(self, bot, sender, dest, cmd, args):
        val, status = self.db.getMember('field', args[0])
        self.sendMemberResults(sender, val, status)

    def getMethod(self, bot, sender, dest, cmd, args):
        val, status = self.db.getMember('method', args[0])
        self.sendMemberResults(sender, val, status)

    def getClass(self, bot, sender, dest, cmd, args):
        val, status = self.db.getClass(args[0])
        self.sendClassResults(sender, val, status)

    def findKey(self, bot, sender, dest, cmd, args):
        self.sendNotice(sender.nick, "+++ FIELDS +++")
        val, status = self.db.findInTable('field', args[0])
        self.sendMemberResults(sender, val, status, summary=True)

        self.sendNotice(sender.nick, " ")
        self.sendNotice(sender.nick, "+++ METHODS +++")
        val, status = self.db.findInTable('method', args[0])
        self.sendMemberResults(sender, val, status, summary=True)

        self.sendNotice(sender.nick, " ")
        self.sendNotice(sender.nick, "+++ CLASSES +++")
        val, status = self.db.findInTable('class', args[0])
        self.sendClassResults(sender, val, status, summary=True)


    def sendMemberResults(self, sender, val, status, summary=False):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendNotice(sender.nick, "No result found.")
            return

        if (not summary and len(val) > 5 and not sender.dccSocket) or (summary and len(val) > 20 and not sender.dccSocket):
            self.sendNotice(sender.nick, "Too many results ( %d ). Please use DCC."%len(val))
            return

        for i, entry in enumerate(val):
            if not summary:
                srgindex = re.search('_([0-9]+)_', entry['srg_name']).groups()[0]
                self.sendNotice(sender.nick, "=== §B{class_srg_name}.{mcp_name}§N ===".format(**entry))
                self.sendNotice(sender.nick, "§UIndex§N      : {srg_index}".format(srg_index=srgindex))
                self.sendNotice(sender.nick, "§UNotch§N      : {class_obf_name}.{obf_name}".format(**entry))
                self.sendNotice(sender.nick, "§USrg§N        : {class_pkg_name}/{class_srg_name}.{srg_name}".format(**entry))
                self.sendNotice(sender.nick, "§UMCP§N        : {class_pkg_name}/{class_srg_name}.{mcp_name}".format(**entry))
                self.sendNotice(sender.nick, "§UDescriptor§N : {obf_descriptor} §B|§N {srg_descriptor}".format(**entry))
                if 'srg_params' in entry:
                    self.sendNotice(sender.nick, "§UParameters§N : {srg_params} §B|§N {mcp_params}".format(**entry))
                self.sendNotice(sender.nick, "§UComment§N    : {comment}".format(**entry))

                if not i == len(val) - 1:
                    self.sendNotice(sender.nick, " ".format(**entry))
            else:
                self.sendNotice(sender.nick, "{class_obf_name}.{obf_name} => {class_srg_name}.{mcp_name} [ {srg_name} ]".format(**entry))


    def sendClassResults(self, sender, val, status, summary=False):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendNotice(sender.nick, "No result found.")
            return

        if (not summary and len(val) > 5 and not sender.dccSocket) or (summary and len(val) > 20 and not sender.dccSocket):
            self.sendNotice(sender.nick, "Too many results ( %d ). Please use DCC."%len(val))
            return


        for ientry, entry in enumerate(val):
            if not summary:
                self.sendNotice(sender.nick, "=== §B{srg_name}§N ===".format(**entry))
                self.sendNotice(sender.nick, "§UNotch§N        : {obf_name}".format(**entry))
                self.sendNotice(sender.nick, "§UName§N         : {pkg_name}/{srg_name}".format(**entry))
                if entry['super_srg_name'] : self.sendNotice(sender.nick, "§USuper§N        : {super_obf_name} | {super_srg_name}".format(**entry))
                if entry['outer_srg_name'] : self.sendNotice(sender.nick, "§UOuter§N        : {outer_obf_name} | {outer_srg_name}".format(**entry))
                if entry['srg_interfaces'] : self.sendNotice(sender.nick, "§UInterfaces§N   : {srg_interfaces}".format(**entry))
                if entry['srg_extending']:
                    extending = entry['srg_extending'].split(", ")
                    for iclass in range(0, len(extending), 5):
                        self.sendNotice(sender.nick, "§UExtending§N    : {extended}".format(extended=' '.join(extending[iclass:iclass+5])))
                if entry['srg_implementing']:
                    implementing = entry['srg_implementing'].split(", ")
                    for iclass in range(0, len(implementing), 5):
                        self.sendNotice(sender.nick, "§UImplementing§N : {implementing}".format(implementing=' '.join(implementing[iclass:iclass+5])))

                if not ientry == len(val) - 1:
                    self.sendNotice(sender.nick, " ".format(**entry))

            else:
                self.sendNotice(sender.nick, "{obf_name} => {pkg_name}/{srg_name}".format(**entry))

########################################################################################################################
def main():
    bot = MCPBot()
    BotHandler.addBot(bot)
    BotHandler.runAll()

if __name__ == "__main__":
    main()