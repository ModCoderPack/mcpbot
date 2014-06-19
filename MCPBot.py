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

        # TODO: remove this!
        self.registerCommand('sqlrequest', self.sqlRequest, ['admin'], 1, 999, "<sql command>",                     "Executes a raw SQL command.")

        self.registerCommand('version',    self.getVersion, ['any'],   0, 0,   "",                                  "Gets info about the current version.")
        self.registerCommand('versions',   self.getVersion, ['any'],   0, 0,   "",                                  "Gets info about versions that are available in the database.")
        self.registerCommand('gp',         self.getParam,   ['any'],   1, 2,   "[[class.]method.]<name> [version]", "Returns method parameter information. Defaults to current version. Version can be for MCP or MC. Obf class and method names not supported.")
        self.registerCommand('gf',         self.getMember,  ['any'],   1, 2,   "[class.]<name> [version]",          "Returns field information. Defaults to current version. Version can be for MCP or MC.")
        self.registerCommand('gm',         self.getMember,  ['any'],   1, 2,   "[class.]<name> [version]",          "Returns method information. Defaults to current version. Version can be for MCP or MC.")
        self.registerCommand('gc',         self.getClass,   ['any'],   1, 2,   "<class> [version]",                 "Returns class information. Defaults to current version. Version can be for MCP or MC.")
        self.registerCommand('find',       self.findKey,    ['any'],   1, 2,   "<regex pattern>",                   "Returns entries matching a regex pattern. Only returns complete matches.")
        self.registerCommand('findall',    self.findAllKey, ['any'],   1, 2,   "<regex pattern>",                   "Returns entries matching a regex pattern. Allows partial matches to be returned.")

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

    def getVersion(self, bot, sender, dest, cmd, args):
        limit = 1
        if cmd['command'][-1:] == 's': limit = 0
        val, status = self.db.getVersions(limit)
        self.sendVersionResults(sender, val, status)

    def getParam(self, bot, sender, dest, cmd, args):
        val, status = self.db.getParam(args)
        self.sendParamResults(sender, val, status)

    def getMember(self, bot, sender, dest, cmd, args):
        member_type = 'field'
        if cmd['command'] == 'gm': member_type = 'method'
        val, status = self.db.getMember(member_type, args)
        self.sendMemberResults(sender, val, status)

    def getClass(self, bot, sender, dest, cmd, args):
        val, status = self.db.getClass(args)
        self.sendClassResults(sender, val, status)

    def findKey(self, bot, sender, dest, cmd, args):
        args[0] = "^" + args[0] + "$"
        self.findAllKey(bot, sender, dest, cmd, args)

    def findAllKey(self, bot, sender, dest, cmd, args):
        self.sendNotice(sender.nick, "+++§B FIELDS §N+++")
        val, status = self.db.findInTable('field', args)
        self.sendMemberResults(sender, val, status, summary=True)

        self.sendNotice(sender.nick, " ")
        self.sendNotice(sender.nick, "+++§B METHODS §N+++")
        val, status = self.db.findInTable('method', args)
        self.sendMemberResults(sender, val, status, summary=True)

        self.sendNotice(sender.nick, " ")
        self.sendNotice(sender.nick, "+++§B METHOD PARAMS §N+++")
        val, status = self.db.findInTable('param', args)
        self.sendParamResults(sender, val, status, summary=True)

        self.sendNotice(sender.nick, " ")
        self.sendNotice(sender.nick, "+++§B CLASSES §N+++")
        val, status = self.db.findInTable('class', args)
        self.sendClassResults(sender, val, status, summary=True)


    def sendVersionResults(self, sender, val, status):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if len(val) > 1:
            self.sendNotice(sender.nick, "===§B Avalable Versions §N===")
        else:
            self.sendNotice(sender.nick, "===§B Current Version §N===")

        # these padding values are 6 higher than the actual data padding values since we have to account for the IRC formatting codes
        self.sendNotice(sender.nick, '{:^19}'.format('§UMCP Version§N') + '{:^19}'.format('§UMC Version§N') + '{:^19}'.format('§URelease Type§N'))

        for i, entry in enumerate(val):
            self.sendNotice(sender.nick, "{mcp_version_code:^13}".format(**entry) + "{mc_version_code:^13}".format(**entry) + "{mc_version_type_code:^13}".format(**entry))


    def sendParamResults(self, sender, val, status, summary=False):
        if status:
            self.sendNotice(sender.nick, "§B" + str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendNotice(sender.nick, "§BNo results found.")
            return

        if (not summary and len(val) > 5 and not sender.dccSocket) or (summary and len(val) > 20 and not sender.dccSocket):
            self.sendNotice(sender.nick, "§BToo many results (§N %(count)d §B). Please use the %(cmd_char)sdcc command and try again." % {'count': len(val), 'cmd_char': self.cmdChar})
            return

        for i, entry in enumerate(val):
            if not summary:
                self.sendNotice(sender.nick,        "===§B MC {mc_version_code}: {class_srg_name}.{method_mcp_name}.{mcp_name} §N===".format(**entry))
                self.sendNotice(sender.nick,        "§UIndex§N      : {srg_index}".format(**entry))
                if entry['srg_method_base_class'] != entry['class_srg_name']:
                    self.sendNotice(sender.nick,    "§UBase Class§N : {obf_method_base_class} §B=>§N {srg_method_base_class}".format(**entry))
                self.sendNotice(sender.nick,        "§UMethod§N     : {class_obf_name}.{method_obf_name} §B=>§N {class_pkg_name}/{class_srg_name}.{method_srg_name}".format(**entry))
                self.sendNotice(sender.nick,        "§UDescriptor§N : {method_obf_descriptor} §B=>§N {method_srg_descriptor}".format(**entry))
                self.sendNotice(sender.nick,        "§USrg§N        : {obf_descriptor} {srg_name}".format(**entry))
                self.sendNotice(sender.nick,        "§UMCP§N        : {srg_descriptor} {mcp_name}".format(**entry))
                if entry['java_type_code']:
                    self.sendNotice(sender.nick,    "§UJava Type§N  : {java_type_code}".format(**entry))


                if not i == len(val) - 1:
                    self.sendNotice(sender.nick, " ".format(**entry))
            else:
                self.sendNotice(sender.nick, "{class_srg_name}.{method_srg_name}.{srg_name} §B[§N {srg_descriptor} §B] =>§N {class_srg_name}.{method_mcp_name}.{mcp_name} §B[§N {srg_descriptor} §B]".format(**entry))


    def sendMemberResults(self, sender, val, status, summary=False):
        if status:
            self.sendNotice(sender.nick, "§B" + str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendNotice(sender.nick, "§BNo results found.")
            return

        if (not summary and len(val) > 5 and not sender.dccSocket) or (summary and len(val) > 20 and not sender.dccSocket):
            self.sendNotice(sender.nick, "§BToo many results (§N %(count)d §B). Please use the %(cmd_char)sdcc command and try again." % {'count': len(val), 'cmd_char': self.cmdChar})
            return

        for i, entry in enumerate(val):
            if not summary:
                self.sendNotice(sender.nick,        "===§B MC {mc_version_code}: {class_srg_name}.{mcp_name} §N===".format(**entry))
                self.sendNotice(sender.nick,        "§UIndex§N      : {srg_index}".format(**entry))
                if 'srg_method_base_class' in entry and entry['srg_method_base_class'] != entry['class_srg_name']:
                    self.sendNotice(sender.nick,    "§UBase Class§N : {obf_method_base_class} §B=>§N {srg_method_base_class}".format(**entry))
                self.sendNotice(sender.nick,        "§UNotch§N      : {class_obf_name}.{obf_name}".format(**entry))
                self.sendNotice(sender.nick,        "§USrg§N        : {class_pkg_name}/{class_srg_name}.{srg_name}".format(**entry))
                self.sendNotice(sender.nick,        "§UMCP§N        : {class_pkg_name}/{class_srg_name}.{mcp_name}".format(**entry))
                self.sendNotice(sender.nick,        "§UDescriptor§N : {obf_descriptor} §B=>§N {srg_descriptor}".format(**entry))
                if 'srg_params' in entry:
                    self.sendNotice(sender.nick,    "§UParameters§N : {srg_params} §B=>§N {mcp_params}".format(**entry))
                self.sendNotice(sender.nick,        "§UComment§N    : {comment}".format(**entry))

                if not i == len(val) - 1:
                    self.sendNotice(sender.nick, " ".format(**entry))
            else:
                self.sendNotice(sender.nick, "{class_obf_name}.{obf_name} §B=>§N {class_srg_name}.{mcp_name} §B[§N {srg_name} §B]".format(**entry))


    def sendClassResults(self, sender, val, status, summary=False):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendNotice(sender.nick, "§BNo results found.")
            return

        if (not summary and len(val) > 5 and not sender.dccSocket) or (summary and len(val) > 20 and not sender.dccSocket):
            self.sendNotice(sender.nick, "§BToo many results (§N %(count)d §B). Please use the %(cmd_char)sdcc command and try again." % {'count': len(val), 'cmd_char': self.cmdChar})
            return


        for ientry, entry in enumerate(val):
            if not summary:
                self.sendNotice(sender.nick,            "===§B MC {mc_version_code}: {srg_name} §N===".format(**entry))
                self.sendNotice(sender.nick,            "§UNotch§N        : {obf_name}".format(**entry))
                self.sendNotice(sender.nick,            "§UName§N         : {pkg_name}/{srg_name}".format(**entry))
                if entry['super_srg_name'] :
                    self.sendNotice(sender.nick,        "§USuper§N        : {super_obf_name} §B=>§N {super_srg_name}".format(**entry))
                if entry['outer_srg_name'] :
                    self.sendNotice(sender.nick,        "§UOuter§N        : {outer_obf_name} §B=>§N {outer_srg_name}".format(**entry))
                if entry['srg_interfaces'] :
                    self.sendNotice(sender.nick,        "§UInterfaces§N   : {srg_interfaces}".format(**entry))
                if entry['srg_extending']:
                    extending = entry['srg_extending'].split(", ")
                    for iclass in range(0, len(extending), 5):
                        self.sendNotice(sender.nick,    "§UExtending§N    : {extended}".format(extended=' '.join(extending[iclass:iclass+5])))
                if entry['srg_implementing']:
                    implementing = entry['srg_implementing'].split(", ")
                    for iclass in range(0, len(implementing), 5):
                        self.sendNotice(sender.nick,    "§UImplementing§N : {implementing}".format(implementing=' '.join(implementing[iclass:iclass+5])))

                if not ientry == len(val) - 1:
                    self.sendNotice(sender.nick, " ".format(**entry))

            else:
                self.sendNotice(sender.nick, "{obf_name} §B~>§N {pkg_name}/{srg_name}".format(**entry))

########################################################################################################################
def main():
    bot = MCPBot()
    BotHandler.addBot(bot)
    BotHandler.runAll()

if __name__ == "__main__":
    main()