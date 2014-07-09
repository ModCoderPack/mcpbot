# coding=utf-8
from BotBase import BotBase, BotHandler
from Database import Database
import sys
import re

class MCPBot(BotBase):
    def __init__(self, nspass):
        super(MCPBot, self).__init__(nspass=nspass)

        self.dbhost = self.config.get('DATABASE', 'HOST', "")
        self.dbport = self.config.geti('DATABASE', 'PORT', "0")
        self.dbuser = self.config.get('DATABASE', 'USER', "")
        self.dbname = self.config.get('DATABASE', 'NAME', "")
        self.dbpass = self.config.get('DATABASE', 'PASS', "")

        self.db = Database(self.dbhost, self.dbport, self.dbuser, self.dbname, self.dbpass, self)

        # TODO: remove this!
        self.registerCommand('sql', self.sqlRequest, ['db_admin'], 1, 999, "<sql command>", "Executes a raw SQL command.")

        self.registerCommand('version',  self.getVersion, ['any'], 0, 0, "", "Gets info about the current version.")
        self.registerCommand('versions', self.getVersion, ['any'], 0, 0, "", "Gets info about versions that are available in the database.")

        self.registerCommand('gp',       self.getParam,   ['any'], 1, 2, "[[<class>.]<method>.]<name> [<version>]", "Returns method parameter information. Defaults to current version. Version can be for MCP or MC. Obf class and method names not supported.")
        self.registerCommand('gf',       self.getMember,  ['any'], 1, 2, "[<class>.]<name> [<version>]",            "Returns field information. Defaults to current version. Version can be for MCP or MC.")
        self.registerCommand('gm',       self.getMember,  ['any'], 1, 2, "[<class>.]<name> [<version>]",            "Returns method information. Defaults to current version. Version can be for MCP or MC.")
        self.registerCommand('gc',       self.getClass,   ['any'], 1, 2, "<class> [<version>]",                     "Returns class information. Defaults to current version. Version can be for MCP or MC.")
        self.registerCommand('find',     self.findKey,    ['any'], 1, 2, "<regex pattern>",                         "Returns entries matching a regex pattern. Only returns complete matches.")
        self.registerCommand('findall',  self.findAllKey, ['any'], 1, 2, "<regex pattern>",                         "Returns entries matching a regex pattern. Allows partial matches to be returned.")

        self.registerCommand('sf',  self.setMember,  ['any'],        2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG field specified. SRG index can also be used.")
        self.registerCommand('fsf', self.setMember,  ['maintainer'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG field specified. SRG index can also be used.")
        self.registerCommand('sm',  self.setMember,  ['any'],        2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG method specified. SRG index can also be used.")
        self.registerCommand('fsm', self.setMember,  ['maintainer'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG method specified. SRG index can also be used.")
        self.registerCommand('sp',  self.setMember,  ['any'],        2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG method parameter specified. SRG index can also be used.")
        self.registerCommand('fsp', self.setMember,  ['maintainer'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG method parameter specified. SRG index can also be used.")

        self.registerCommand('lf',  self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given field from being edited. SRG index can also be used.")
        self.registerCommand('lm',  self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given method from being edited. SRG index can also be used.")
        self.registerCommand('lp',  self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given method parameter from being edited. SRG index can also be used.")
        self.registerCommand('ulf', self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Unlocks the given field to allow editing. SRG index can also be used.")
        self.registerCommand('ulm', self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Unlocks the given method to allow editing. SRG index can also be used.")
        self.registerCommand('ulp', self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Unlocks the given method parameter to allow editing. SRG index can also be used.")

        # Legacy commands that only show a notice
        self.registerCommand('gcf',  self.legacyNotice, ['any'], 1, 1,   "", "", False)
        self.registerCommand('gsf',  self.legacyNotice, ['any'], 1, 1,   "", "", False)
        self.registerCommand('gcm',  self.legacyNotice, ['any'], 1, 1,   "", "", False)
        self.registerCommand('gsm',  self.legacyNotice, ['any'], 1, 1,   "", "", False)
        self.registerCommand('scf',  self.legacyNotice, ['any'], 2, 999, "", "", False)
        self.registerCommand('ssf',  self.legacyNotice, ['any'], 2, 999, "", "", False)
        self.registerCommand('scm',  self.legacyNotice, ['any'], 2, 999, "", "", False)
        self.registerCommand('ssm',  self.legacyNotice, ['any'], 2, 999, "", "", False)
        self.registerCommand('fscf', self.legacyNotice, ['any'], 2, 999, "", "", False)
        self.registerCommand('fssf', self.legacyNotice, ['any'], 2, 999, "", "", False)
        self.registerCommand('fscm', self.legacyNotice, ['any'], 2, 999, "", "", False)
        self.registerCommand('fssm', self.legacyNotice, ['any'], 2, 999, "", "", False)

        self.legacyCommandMap = {'gcf':  'gf',
                                 'gsf':  'gf',
                                 'gcm':  'gm',
                                 'gsm':  'gm',
                                 'scf':  'sf',
                                 'ssf':  'sf',
                                 'scm':  'sm',
                                 'ssm':  'sm',
                                 'fscf': 'fsf',
                                 'fssf': 'fsf',
                                 'fscm': 'fsm',
                                 'fssm': 'fsm'}


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

    # Legacy command notice handler

    def legacyNotice(self, bot, sender, dest, cmd, args):
        self.sendNotice(sender.nick, "§BNOTICE: The legacy command §U%s§N§B is no longer supported, please use §U%s§N§B instead." % (cmd['command'], self.legacyCommandMap[cmd['command']]))

    # Getters

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
        val, status = self.db.findInTable('method_param', args)
        self.sendParamResults(sender, val, status, summary=True)

        self.sendNotice(sender.nick, " ")
        self.sendNotice(sender.nick, "+++§B CLASSES §N+++")
        val, status = self.db.findInTable('class', args)
        self.sendClassResults(sender, val, status, summary=True)

    # Setters

    def setLocked(self, bot, sender, dest, cmd, args):
        member_type = 'method'
        is_lock = cmd['command'][0] == 'l'
        if cmd['command'].find('f') > -1: member_type = 'field'
        elif cmd['command'].find('p') > -1: member_type = 'method_param'
        val, status = self.db.setMemberLock(member_type, is_lock, cmd['command'], sender, args)
        self.sendSetLockResults(member_type, sender, val, status, args[0], is_lock)


    def setMember(self, bot, sender, dest, cmd, args):
        member_type = 'method'
        if cmd['command'].find('sf') > -1: member_type = 'field'
        elif cmd['command'].find('sp') > -1: member_type = 'method_param'
        # should be safe to assume the user is in authUsers since we made it to the callback
        bypass_lock = 'lock_control' in self.authUsers[sender.regnick.lower()]
        is_forced = cmd['command'][0] == 'f'
        if is_forced:
            self.sendNotice(sender.nick, "§R!!! CAREFUL, YOU ARE FORCING AN UPDATE TO A NAMED %s !!!" % member_type.upper().replace('_', ' '))
        val, status = self.db.setMember(member_type, is_forced, bypass_lock, cmd['command'], sender, args)
        self.sendSetMemberResults(member_type, sender, val, status, args[0])

    # Send Results

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
                if 'srg_member_base_class' in entry and entry['srg_member_base_class'] != entry['class_srg_name']:
                    self.sendNotice(sender.nick,    "§UBase Class§N : {obf_member_base_class} §B=>§N {srg_member_base_class}".format(**entry))
                self.sendNotice(sender.nick,        "§UMethod§N     : {class_obf_name}.{method_obf_name} §B=>§N {class_pkg_name}/{class_srg_name}.{method_srg_name}".format(**entry))
                self.sendNotice(sender.nick,        "§UDescriptor§N : {method_obf_descriptor} §B=>§N {method_srg_descriptor}".format(**entry))
                self.sendNotice(sender.nick,        "§USrg§N        : {obf_descriptor} {srg_name}".format(**entry))
                self.sendNotice(sender.nick,        "§UMCP§N        : {srg_descriptor} {mcp_name}".format(**entry))
                self.sendNotice(sender.nick,        "§ULocked§N     : {is_locked}".format(**entry))
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
                if 'srg_member_base_class' in entry and entry['srg_member_base_class'] != entry['class_srg_name']:
                    self.sendNotice(sender.nick,    "§UBase Class§N : {obf_member_base_class} §B=>§N {srg_member_base_class}".format(**entry))
                self.sendNotice(sender.nick,        "§UNotch§N      : {class_obf_name}.{obf_name}".format(**entry))
                self.sendNotice(sender.nick,        "§USrg§N        : {class_pkg_name}/{class_srg_name}.{srg_name}".format(**entry))
                self.sendNotice(sender.nick,        "§UMCP§N        : {class_pkg_name}/{class_srg_name}.{mcp_name}".format(**entry))
                self.sendNotice(sender.nick,        "§ULocked§N     : {is_locked}".format(**entry))
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
                self.sendNotice(sender.nick, "{obf_name} §B=>§N {pkg_name}/{srg_name}".format(**entry))

    # Setter results

    def sendSetLockResults(self, member_type, sender, val, status, srg_name, is_lock):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if member_type == 'method_param':
            member_type = 'Method Param'
        else:
            member_type = member_type[0].upper() + member_type[1:]

        if is_lock:
            self.sendNotice(sender.nick, "===§B Lock %s: %s §N===" % (member_type, srg_name))
        else:
            self.sendNotice(sender.nick, "===§B Unlock %s: %s §N===" % (member_type, srg_name))

        for result in val:
            if result['result'] > 0:
                self.sendNotice(sender.nick, "§BLocked status§N : %s" % str(is_lock))
            elif result['result'] == 0:
                self.sendNotice(sender.nick, "§BERROR: SRG Name/Index specified is not a valid %s in the current version." % member_type)
            elif result['result'] == -1:
                self.sendNotice(sender.nick, "§BERROR: Invalid Member Type %s specified. Please report this to a member of the MCP team." % member_type)
            elif result['result'] == -2:
                self.sendNotice(sender.nick, "§BERROR: Ambiguous request: multiple %ss would be affected." % member_type)
            elif result['result'] == -3:
                if is_lock:
                    self.sendNotice(sender.nick, "§BNOTICE: This %s is already locked." % member_type)
                else:
                    self.sendNotice(sender.nick, "§BNOTICE: This %s is already unlocked." % member_type)

    def sendSetMemberResults(self, member_type, sender, val, status, srg_name):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        member_type_disp = member_type[0].upper() + member_type[1:]

        if member_type == 'method_param':
            member_type_disp = 'Method Param'

        self.sendNotice(sender.nick, "===§B Set %s: %s §N===" % (member_type_disp, srg_name))

        for result in val:
            if result['result'] > 0:
                change, status = self.db.getMemberChange(member_type, result['result'])
                if status:
                    self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
                    return

                for row in change:
                    self.sendNotice(sender.nick, "§BName§N     : {old_mcp_name} §B=>§N {new_mcp_name}".format(**row))
                    self.sendNotice(sender.nick, "§BOld desc§N : {old_mcp_desc}".format(**row))
                    self.sendNotice(sender.nick, "§BNew desc§N : {new_mcp_desc}".format(**row))

                return

            if result['result'] == 0:
                self.sendNotice(sender.nick, "§BERROR: SRG Name/Index specified is not a valid %s in the current version." % member_type_disp)
            elif result['result'] == -1:
                self.sendNotice(sender.nick, "§BERROR: Invalid Member Type %s specified. Please report this to a member of the MCP team." % member_type_disp)
            elif result['result'] == -2:
                self.sendNotice(sender.nick, "§BERROR: Ambiguous request: multiple %ss would be modified." % member_type_disp)
            elif result['result'] == -3:
                self.sendNotice(sender.nick, "§BNOTICE: The %s record for SRG Name/Index %s is locked. You do not have permission to edit locked mappings." % (member_type_disp, srg_name))
            elif result['result'] == -4:
                self.sendNotice(sender.nick, "§BWARNING: The MCP name has already been specified for this %s." % member_type_disp)
            elif result['result'] == -5:
                self.sendNotice(sender.nick, "§BNOTICE: No changes to the mapping were detected based on the arguments specified.")
            elif result['result'] == -6:
                self.sendNotice(sender.nick, "§BERROR: The new name specified conflicts with another %s name within its scope." % member_type_disp)
            elif result['result'] == -7:
                self.sendNotice(sender.nick, "§BERROR: The new name specified is not a valid Java identifier (yes, we are blocking Unicode; names must not start with a number and can contain A-Z, a-z, 0-9, _ and $).")
            elif result['result'] == -8:
                self.sendNotice(sender.nick, "§BERROR: The new name specified is a Java keyword or literal.")
            elif result['result'] == -9:
                self.sendNotice(sender.nick, "§BERROR: The new name specified is too long (limit of 32 characters).")
            elif result['result'] == -10:
                self.sendNotice(sender.nick, "§BERROR: Constructor names cannot be changed.")

########################################################################################################################
def main():
    if not len(sys.argv) == 2:
        print "Usage : MCPBot.py <nickserv password>"
        return

    bot = MCPBot(nspass = sys.argv[1])
    BotHandler.addBot(bot)
    BotHandler.runAll()

if __name__ == "__main__":
    main()