# coding=utf-8
from BotBase import BotBase, BotHandler
from Database import Database
from optparse import OptionParser
import time
from datetime import timedelta, datetime, time as time_class
import threading
import export_csv
from MavenHandler import MavenHandler
import zipfile, os
import psycopg2.extras

__version__ = "0.5.0"

class MCPBot(BotBase):
    def __init__(self, nspass):
        super(MCPBot, self).__init__(nspass=nspass)

        self.dbhost = self.config.get('DATABASE', 'HOST', "")
        self.dbport = self.config.geti('DATABASE', 'PORT', "0")
        self.dbuser = self.config.get('DATABASE', 'USER', "")
        self.dbname = self.config.get('DATABASE', 'NAME', "")
        self.dbpass = self.config.get('DATABASE', 'PASS', "")

        self.primary_channel = self.config.get('BOT', 'PRIMARY_CHANNEL', '#mcpbot', 'Important bot messages will be sent to this channel.')

        self.test_export_period = self.config.geti('EXPORT', 'TEST_EXPORT_PERIOD', '30', 'How often in minutes to run the test CSV export. Use 0 to disable.')
        self.test_export_path = self.config.get('EXPORT', 'TEST_EXPORT_PATH', 'testcsv', 'Relative path to write the test CSV files to.')
        self.test_export_url = self.config.get('EXPORT', 'TEST_EXPORT_URL', 'http://mcpbot.bspk.rs/testcsv/')
        self.maven_repo_url = self.config.get('EXPORT', 'MAVEN_REPO_URL', 'http://files.minecraftforge.net/maven/manage/upload/de/ocean-labs/mcp/', )
        self.maven_repo_user = self.config.get('EXPORT', 'MAVEN_REPO_USER', 'mcp')
        self.maven_repo_pass = self.config.get('EXPORT', 'MAVEN_REPO_PASS', '')
        self.maven_snapshot_path = self.config.get('EXPORT', 'MAVEN_SNAPSHOT_PATH', 'mcp_snapshot/%(date)s-%(mc_version_code)s')
        self.maven_stable_path = self.config.get('EXPORT', 'MAVEN_STABLE_PATH', 'mcp_stable/%(version_control_pid)s-%(mc_version_code)s')
        self.maven_upload_time_str = self.config.get('EXPORT', 'MAVEN_UPLOAD_TIME', '3:00', 'The approximate time that the maven upload will take place daily. Will happen within TEST_EXPORT_PERIOD / 2 minutes of this time. Use H:MM format, with 24 hour clock.')
        self.upload_retry_count = self.config.geti('EXPORT', 'UPLOAD_RETRY_COUNT', '3', 'Number of times to retry the maven upload if it fails. Attempts will be made 5 minutes apart.')
        self.next_export = None
        self.test_export_thread = None

        if self.maven_upload_time_str:
            if len(self.maven_upload_time_str.split(':')) > 1:
                upload_hour, _, upload_minute = self.maven_upload_time_str.partition(':')
            else:
                upload_hour = self.maven_upload_time_str
                upload_minute = '0'

            self.maven_upload_time = time_class(int(upload_hour), int(upload_minute), 0)
        else:
            self.maven_upload_time = None

        self.db = Database(self.dbhost, self.dbport, self.dbuser, self.dbname, self.dbpass, self)

        #self.registerCommand('sql', self.sqlRequest, ['db_admin'], 1, 999, "<sql command>", "Executes a raw SQL command.", False)

        self.registerCommand('version',  self.getVersion, ['any'], 0, 0, "", "Gets info about the current version.")
        self.registerCommand('versions', self.getVersion, ['any'], 0, 0, "", "Gets info about versions that are available in the database.")
        self.registerCommand('testcsv',  self.getTestCSVURL, ['any'], 0, 0, "", "Gets the URL for the running export of staged changes.")

        self.registerCommand('gp',       self.getParam,   ['any'], 1, 2, "[[<class>.]<method>.]<name> [<version>]", "Returns method parameter information. Defaults to current version. Version can be for MCP or MC. Obf class and method names not supported.")
        self.registerCommand('gf',       self.getMember,  ['any'], 1, 2, "[<class>.]<name> [<version>]",            "Returns field information. Defaults to current version. Version can be for MCP or MC.")
        self.registerCommand('gm',       self.getMember,  ['any'], 1, 2, "[<class>.]<name> [<version>]",            "Returns method information. Defaults to current version. Version can be for MCP or MC.")
        self.registerCommand('gc',       self.getClass,   ['any'], 1, 2, "<class> [<version>]",                     "Returns class information. Defaults to current version. Version can be for MCP or MC.")
        self.registerCommand('find',     self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns any entries matching a regex pattern. Only returns complete matches.")
        self.registerCommand('findc',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns class entries matching a regex pattern. Only returns complete matches.")
        self.registerCommand('findf',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns field entries matching a regex pattern. Only returns complete matches.")
        self.registerCommand('findm',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns method entries matching a regex pattern. Only returns complete matches.")
        self.registerCommand('findp',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns parameter entries matching a regex pattern. Only returns complete matches.")
        self.registerCommand('findall',  self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns any entries matching a regex pattern. Allows partial matches to be returned.")
        self.registerCommand('findallc', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns class entries matching a regex pattern. Allows partial matches to be returned.")
        self.registerCommand('findallf', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns field entries matching a regex pattern. Allows partial matches to be returned.")
        self.registerCommand('findallm', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns method entries matching a regex pattern. Allows partial matches to be returned.")
        self.registerCommand('findallp', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns parameter entries matching a regex pattern. Allows partial matches to be returned.")
        self.registerCommand('uf',       self.listMembers,['any'], 1, 1, "<class>",                                 "Returns a list of unnamed fields for a given class. Use DCC if the list is long.")
        self.registerCommand('um',       self.listMembers,['any'], 1, 1, "<class>",                                 "Returns a list of unnamed methods for a given class. Use DCC if the list is long.")
        self.registerCommand('up',       self.listMembers,['any'], 1, 1, "<class>",                                 "Returns a list of unnamed method parameters for a given class. Use DCC if the list is long.")
        self.registerCommand('undo',     self.undoChange, ['any', 'undo_any'], 1, 1, "<srg name>",                  "Undoes the last *STAGED* name change to a given method/field/param. By default you can only undo your own changes.")
        self.registerCommand('redo',     self.undoChange, ['any', 'undo_any'], 1, 1, "<srg name>",                  "Redoes the last *UNDONE* staged change to a given method/field/param. By default you can only redo your own changes.")

        self.registerCommand('sf',  self.setMember,  ['any'],        2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG field specified. SRG index can also be used.")
        self.registerCommand('fsf', self.setMember,  ['maintainer'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG field specified. SRG index can also be used.")
        self.registerCommand('sm',  self.setMember,  ['any'],        2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG method specified. SRG index can also be used.")
        self.registerCommand('fsm', self.setMember,  ['maintainer'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG method specified. SRG index can also be used.")
        self.registerCommand('sp',  self.setMember,  ['any'],        2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG method parameter specified. SRG index can also be used.")
        self.registerCommand('fsp', self.setMember,  ['maintainer'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG method parameter specified. SRG index can also be used.")

        self.registerCommand('lockf',  self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given field from being edited. SRG index can also be used.")
        self.registerCommand('lockm',  self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given method from being edited. SRG index can also be used.")
        self.registerCommand('lockp',  self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given method parameter from being edited. SRG index can also be used.")
        self.registerCommand('unlockf', self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Unlocks the given field to allow editing. SRG index can also be used.")
        self.registerCommand('unlockm', self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Unlocks the given method to allow editing. SRG index can also be used.")
        self.registerCommand('unlockp', self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Unlocks the given method parameter to allow editing. SRG index can also be used.")

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
        super(MCPBot, self).onStartUp()
        self.db.connect()
        if self.test_export_period > 0:
            self.exportTimer()


    def onShuttingDown(self):
        if self.isRunning:
            super(MCPBot, self).onShuttingDown()
            self.db.disconnect()
            if self.test_export_thread:
                self.test_export_thread.cancel()


    def exportTimer(self):
        if not self.next_export:
            self.next_export = time.time()

        self.next_export += (self.test_export_period * 60)
        now = datetime.now()

        self.logger.info('Running test CSV export.')
        export_csv.do_export(self.dbhost, self.dbport, self.dbname, self.dbuser, self.dbpass, test_csv=True, export_path=self.test_export_path)

        if self.maven_upload_time:
            min_upload_time = datetime.combine(now.date(), self.maven_upload_time) - timedelta(minutes=self.test_export_period/2)
            max_upload_time = datetime.combine(now.date(), self.maven_upload_time) + timedelta(minutes=self.test_export_period/2)
            if min_upload_time <= now <= max_upload_time:
                self.logger.info("Pushing nightly snapshot mappings to Forge Maven.")
                self.sendMessage(self.primary_channel, "[TEST CSV] Pushing nightly snapshot mappings to Forge Maven.")
                result, status = self.db.getVersions(1, psycopg2.extras.RealDictCursor)
                if status:
                    self.logger.error(status)
                    return

                result[0]['date'] = now.strftime('%Y%m%d')
                zip_name = (self.maven_snapshot_path.replace('/', '-') + '.zip') % result[0]
                zipContents(self.test_export_path, zip_name)

                tries = 0
                success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                        zip_name, remote_path=self.maven_snapshot_path % result[0], logger=self.logger)
                while tries < self.upload_retry_count and not success:
                    tries += 1
                    self.sendMessage(self.primary_channel, '[TEST CSV] WARNING: Upload attempt failed. Trying again in 3 minutes.')
                    time.sleep(180)
                    success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                            zip_name, remote_path=self.maven_snapshot_path % result[0], logger=self.logger)

                if success and tries == 0:
                    self.logger.info('Maven upload successful.')
                    self.sendMessage(self.primary_channel, '[TEST CSV] Maven upload successful.')
                elif success and tries > 0:
                    self.logger.info('Maven upload successful after %d %s.' % (tries, 'retry' if tries == 1 else 'retries'))
                    self.sendMessage(self.primary_channel, '[TEST CSV] Maven upload successful after %d %s.' % (tries, 'retry' if tries == 1 else 'retries'))
                else:
                    self.logger.error('Maven upload failed after %d retries.' % tries)
                    self.sendMessage(self.primary_channel, '[TEST CSV] ERROR: Maven upload failed after %d retries!' % tries)

        self.test_export_thread = threading.Timer(self.next_export - time.time(), self.exportTimer)
        self.test_export_thread.start()


    def getTestCSVURL(self, bot, sender, dest, cmd, args):
        self.sendMessage(dest, self.test_export_url)


    # def sqlRequest(self, bot, sender, dest, cmd, args):
    #     sql = ' '.join(args)
    #
    #     val, status = self.db.execute(sql)
    #
    #     if status:
    #         self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
    #         return
    #
    #     if len(val) > 0:
    #         for entry in val:
    #             self.sendNotice(sender.nick, dict(entry)):
    #     else:
    #         self.sendNotice(sender.nick, "No result found.")


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
        showAll = cmd['command'][-1] in ('d', 'l')
        showFields = cmd['command'][-1] == 'f'
        showMethods = cmd['command'][-1] == 'm'
        showParams = cmd['command'][-1] == 'p'
        showClasses = cmd['command'][-1] == 'c'
        limit = 5 if showAll else 20

        if showAll or showFields:
            self.sendNotice(sender.nick, "+++§B FIELDS §N+++")
            val, status = self.db.findInTable('field', args)
            self.sendMemberResults(sender, val, status, limit, summary=True)

        if showAll or showMethods:
            if showAll:
                self.sendNotice(sender.nick, " ")
            self.sendNotice(sender.nick, "+++§B METHODS §N+++")
            val, status = self.db.findInTable('method', args)
            self.sendMemberResults(sender, val, status, limit, summary=True)

        if showAll or showParams:
            if showAll:
                self.sendNotice(sender.nick, " ")
            self.sendNotice(sender.nick, "+++§B METHOD PARAMS §N+++")
            val, status = self.db.findInTable('method_param', args)
            self.sendParamResults(sender, val, status, limit, summary=True)

        if showAll or showClasses:
            if showAll:
                self.sendNotice(sender.nick, " ")
            self.sendNotice(sender.nick, "+++§B CLASSES §N+++")
            val, status = self.db.findInTable('class', args)
            self.sendClassResults(sender, val, status, limit, summary=True)


    def listMembers(self, bot, sender, dest, cmd, args):
        if cmd['command'][-1] == 'f':
            self.sendNotice(sender.nick, "+++§B UNNAMED %sS FOR %s §N+++" % ('FIELD', args[0]))
            val, status = self.db.getUnnamed('field', args)
            self.sendMemberResults(sender, val, status, 10, summary=True, is_unnamed=True)
        elif cmd['command'][-1] == 'm':
            self.sendNotice(sender.nick, "+++§B UNNAMED %sS FOR %s §N+++" % ('METHOD', args[0]))
            val, status = self.db.getUnnamed('method', args)
            self.sendMemberResults(sender, val, status, 10, summary=True, is_unnamed=True)
        else:
            self.sendNotice(sender.nick, "+++§B UNNAMED %sS FOR %s §N+++" % ('METHOD PARAM', args[0]))
            val, status = self.db.getUnnamed('method_param', args)
            self.sendParamResults(sender, val, status, 10, summary=True, is_unnamed=True)


    # Setters

    def setLocked(self, bot, sender, dest, cmd, args):
        member_type = 'method'
        is_lock = cmd['command'][0] == 'l'
        if cmd['command'].find('f') > -1: member_type = 'field'
        elif cmd['command'].find('p') > -1: member_type = 'method_param'
        val, status = self.db.setMemberLock(member_type, is_lock, cmd['command'], sender, args)
        self.sendSetLockResults(member_type, sender, val, status, args[0], is_lock)


    def undoChange(self, bot, sender, dest, cmd, args):
        # self.sendNotice(sender.nick, "Coming Soon™")
        can_undo_any = sender.regnick.lower() in self.authUsers and 'undo_any' in self.authUsers[sender.regnick.lower()]
        is_undo = cmd['command'] == 'undo'
        if args[0].startswith('func_'): member_type = 'method'
        elif args[0].startswith('field_'): member_type = 'field'
        else: member_type = 'method_param'
        val, status = self.db.doMemberUndo(member_type, is_undo, can_undo_any, cmd['command'], sender, args)
        self.sendUndoResults(member_type, sender, val, status, args[0], cmd['command'])


    def setMember(self, bot, sender, dest, cmd, args):
        member_type = 'method'
        if cmd['command'].find('sf') > -1: member_type = 'field'
        elif cmd['command'].find('sp') > -1: member_type = 'method_param'
        # should be safe to assume the user is in authUsers since we made it to the callback ... NOPE
        bypass_lock = sender.regnick.lower() in self.authUsers and 'lock_control' in self.authUsers[sender.regnick.lower()]
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
            self.sendNotice(sender.nick, "===§B Available Versions §N===")
        else:
            self.sendNotice(sender.nick, "===§B Current Version §N===")

        # these padding values are 6 higher than the actual data padding values since we have to account for the IRC formatting codes
        self.sendNotice(sender.nick, '{:^19}'.format('§UMCP Version§N') + '{:^19}'.format('§UMC Version§N') + '{:^19}'.format('§URelease Type§N'))

        for i, entry in enumerate(val):
            self.sendNotice(sender.nick, "{mcp_version_code:^13}".format(**entry) + "{mc_version_code:^13}".format(**entry) + "{mc_version_type_code:^13}".format(**entry))


    def sendParamResults(self, sender, val, status, limit=0, summary=False, is_unnamed=False):
        if status:
            self.sendNotice(sender.nick, "§B" + str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendNotice(sender.nick, "§BNo results found.")
            return

        for i, entry in enumerate(val):
            if not summary:
                if entry['is_locked']: locked = 'LOCKED'
                else: locked = 'UNLOCKED'
                header =                            "===§B MC {mc_version_code}: {class_pkg_name}/{class_srg_name}.{method_mcp_name}.{mcp_name} §U" + locked + "§N ==="
                self.sendNotice(sender.nick,        header.format(**entry))
                if 'srg_member_base_class' in entry and entry['srg_member_base_class'] != entry['class_srg_name']:
                    self.sendNotice(sender.nick,    "§UBase Class§N : {obf_member_base_class} §B=>§N {srg_member_base_class}".format(**entry))
                if entry['srg_name'] != entry['mcp_name']:
                    self.sendNotice(sender.nick,        "§UName§N       : {srg_name} §B=>§N {mcp_name}".format(**entry))
                else:
                    self.sendNotice(sender.nick,        "§UName§N       : {srg_name}".format(**entry))
                if entry['method_srg_name'] != entry['method_mcp_name']:
                    self.sendNotice(sender.nick,        "§UMethod§N     : {class_obf_name}.{method_obf_name} §B=>§N {class_srg_name}.{method_srg_name} §B=>§N {class_srg_name}.{method_mcp_name}".format(**entry))
                else:
                    self.sendNotice(sender.nick,        "§UMethod§N     : {class_obf_name}.{method_obf_name} §B=>§N {class_srg_name}.{method_srg_name}".format(**entry))
                if entry['method_obf_descriptor'] != entry['method_srg_descriptor']:
                    self.sendNotice(sender.nick,    "§UDescriptor§N : {method_obf_descriptor} §B=>§N {method_srg_descriptor}".format(**entry))
                else:
                    self.sendNotice(sender.nick,    "§UDescriptor§N : {method_obf_descriptor}".format(**entry))
                self.sendNotice(sender.nick,        "§UComment§N    : {comment}".format(**entry))


                if not i == len(val) - 1:
                    self.sendNotice(sender.nick, " ".format(**entry))
            else:
                if i < limit or sender.dccSocket:
                    if is_unnamed:
                        self.sendNotice(sender.nick, "{method_mcp_name}.{mcp_name} §B[§N {srg_descriptor} §B]".format(**entry))
                    else:
                        self.sendNotice(sender.nick, "{class_srg_name}.{method_srg_name}.{srg_name} §B[§N {srg_descriptor} §B] =>§N {class_srg_name}.{method_mcp_name}.{mcp_name} §B[§N {java_type_code} §B]".format(**entry))
                elif i == limit:
                    self.sendNotice(sender.nick, "§B+ §N%(count)d§B more. Please use the %(cmd_char)sdcc command to see the full list." % {'count': len(val) - i, 'cmd_char': self.cmdChar})
                    return


    def sendMemberResults(self, sender, val, status, limit=0, summary=False, is_unnamed=False):
        if status:
            self.sendNotice(sender.nick, "§B" + str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendNotice(sender.nick, "§BNo results found.")
            return

        for i, entry in enumerate(val):
            if not summary:
                if entry['is_locked']: locked = 'LOCKED'
                else: locked = 'UNLOCKED'
                header =                            "===§B MC {mc_version_code}: {class_pkg_name}/{class_srg_name}.{mcp_name} ({class_obf_name}.{obf_name}) §U" + locked + "§N ==="
                self.sendNotice(sender.nick,        header.format(**entry))
                if 'srg_member_base_class' in entry and entry['srg_member_base_class'] != entry['class_srg_name']:
                    self.sendNotice(sender.nick,    "§UBase Class§N : {obf_member_base_class} §B=>§N {srg_member_base_class}".format(**entry))
                if entry['srg_name'] != entry['mcp_name']:
                    self.sendNotice(sender.nick,    "§UName§N       : {obf_name} §B=>§N {srg_name} §B=>§N {mcp_name}".format(**entry))
                else:
                    self.sendNotice(sender.nick,    "§UName§N       : {obf_name} §B=>§N {srg_name}".format(**entry))
                if entry['obf_descriptor'] != entry['srg_descriptor']:
                    self.sendNotice(sender.nick,    "§UDescriptor§N : {obf_descriptor} §B=>§N {srg_descriptor}".format(**entry))
                else:
                    self.sendNotice(sender.nick,    "§UDescriptor§N : {obf_descriptor}".format(**entry))
                self.sendNotice(sender.nick,        "§UComment§N    : {comment}".format(**entry))
                if 'srg_params' in entry and entry['srg_params']:
                    self.sendNotice(sender.nick,    "§USRG Params§N : {srg_params}".format(**entry))
                    self.sendNotice(sender.nick,    "§UMCP Params§N : {mcp_params}".format(**entry))

                if not i == len(val) - 1:
                    self.sendNotice(sender.nick, " ".format(**entry))
            else:
                if i < limit or sender.dccSocket:
                    if is_unnamed:
                        self.sendNotice(sender.nick, "{srg_name} §B[§N {srg_descriptor} §B]".format(**entry))
                    else:
                        self.sendNotice(sender.nick, "{class_obf_name}.{obf_name} §B=>§N {class_srg_name}.{mcp_name} §B[§N {srg_name} §B]".format(**entry))
                elif i == limit:
                    self.sendNotice(sender.nick, "§B+ §N%(count)d§B more. Please use the %(cmd_char)sdcc command to see the full list." % {'count': len(val) - i, 'cmd_char': self.cmdChar})
                    return


    def sendClassResults(self, sender, val, status, limit=0, summary=False):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendNotice(sender.nick, "§BNo results found.")
            return

        for i, entry in enumerate(val):
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

                if not i == len(val) - 1:
                    self.sendNotice(sender.nick, " ".format(**entry))

            else:
                if i < limit or sender.dccSocket:
                    self.sendNotice(sender.nick, "{obf_name} §B=>§N {pkg_name}/{srg_name}".format(**entry))
                elif i == limit:
                    self.sendNotice(sender.nick, "§B+ §N%(count)d§B more. Please use the %(cmd_char)sdcc command to see the full list." % {'count': len(val) - i, 'cmd_char': self.cmdChar})
                    return


    # Setter results

    def sendSetLockResults(self, member_type, sender, val, status, srg_name, is_lock):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if member_type == 'method_param':
            member_type_disp = 'Method Param'
        else:
            member_type_disp = member_type[0].upper() + member_type[1:]

        if is_lock:
            self.sendNotice(sender.nick, "===§B Lock %s: %s §N===" % (member_type_disp, srg_name))
        else:
            self.sendNotice(sender.nick, "===§B Unlock %s: %s §N===" % (member_type_disp, srg_name))

        for result in val:
            if result['result'] > 0:
                self.sendNotice(sender.nick, "§BLocked status§N : %s" % str(is_lock))
            elif result['result'] == 0:
                self.sendNotice(sender.nick, "§BERROR: SRG Name/Index specified is not a valid %s in the current version." % member_type_disp)
            elif result['result'] == -1:
                self.sendNotice(sender.nick, "§BERROR: Invalid Member Type %s specified. Please report this to a member of the MCP team." % member_type_disp)
            elif result['result'] == -2:
                self.sendNotice(sender.nick, "§BERROR: Ambiguous request: multiple %ss would be affected." % member_type_disp)
            elif result['result'] == -3:
                if is_lock:
                    self.sendNotice(sender.nick, "§BNOTICE: This %s is already locked." % member_type_disp)
                else:
                    self.sendNotice(sender.nick, "§BNOTICE: This %s is already unlocked." % member_type_disp)
            else:
                self.sendNotice(sender.nick, "§BERROR: Unhandled error %d when locking/unlocking a member. Please report this to a member of the MCP team along with the command you executed." % result['result'])


    def sendUndoResults(self, member_type, sender, val, status, srg_name, command):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if member_type == 'method_param':
            member_type_disp = 'Method Param'
        else:
            member_type_disp = member_type[0].upper() + member_type[1:]

        if command == 'undo':
            self.sendNotice(sender.nick, "===§B Undo last *STAGED* change to %s: %s §N===" % (member_type_disp, srg_name))
        else:
            self.sendNotice(sender.nick, "===§B Redo last *UNDONE* staged change to %s: %s §N===" % (member_type_disp, srg_name))

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
            elif result['result'] == 0:
                self.sendNotice(sender.nick, "§BERROR: SRG Name/Index specified is not a valid %s in the current version." % member_type_disp)
            elif result['result'] == -1:
                self.sendNotice(sender.nick, "§BERROR: Invalid Member Type %s specified. Please report this to a member of the MCP team." % member_type_disp)
            elif result['result'] == -2:
                self.sendNotice(sender.nick, "§BERROR: Ambiguous request: multiple %ss would be affected." % member_type_disp)
            elif result['result'] == -3:
                self.sendNotice(sender.nick, "§BERROR: Nothing to %s." % command)
            elif result['result'] == -4:
                self.sendNotice(sender.nick, "§BWARNING: You do not have permission to %s others' changes." % command)
            else:
                self.sendNotice(sender.nick, "§BERROR: Unhandled error %d when %sing a member change. Please report this to a member of the MCP team along with the command you executed." % (result['result'], command))


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

            elif result['result'] == 0:
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
                self.sendNotice(sender.nick, "§BERROR: The new name specified is not a valid Java identifier or contains invalid characters (yes, we are blocking Unicode; names must not start with a number and can contain A-Z, a-z, 0-9, _ and $).")
            elif result['result'] == -8:
                self.sendNotice(sender.nick, "§BERROR: The new name specified is a Java keyword or literal.")
            elif result['result'] == -9:
                self.sendNotice(sender.nick, "§BERROR: The new name specified is too long (limit of 32 characters).")
            elif result['result'] == -10:
                self.sendNotice(sender.nick, "§BERROR: Constructor names cannot be changed.")
            elif result['result'] == -11:
                self.sendNotice(sender.nick, "§BWARNING: Final static field names should use all uppercase letters.")
            elif result['result'] == -12:
                self.sendNotice(sender.nick, "§BWARNING: Do not begin method, non-final-static field, or parameter names with an uppercase letter.")
            elif result['result'] == -13:
                self.sendNotice(sender.nick, "§BWARNING: New parameter name duplicates a class field name within scope. Use fsp if you are ABSOLUTELY sure that it won't cause issues. We will find you and crucify you if you break shit...")
            elif result['result'] == -14:
                self.sendNotice(sender.nick, "§BWARNING: New parameter name is reserved for use by the JAD-style local field renaming process.")
            else:
                self.sendNotice(sender.nick, "§BERROR: Unhandled error %d when processing a member change. Please report this to a member of the MCP team along with the command you executed." % result['result'])


########################################################################################################################


def zipContents(path, targetfilename=None):
    if not targetfilename: targetfilename = path.replace('/', '_') + '.zip'
    with zipfile.ZipFile(targetfilename, 'w', compression=zipfile.ZIP_DEFLATED) as zfile:
        files = os.listdir(path)
        for item in [item for item in files if os.path.isfile(path + '/' + item) and item.endswith('.csv')]:
            zfile.write(path + '/' + item, arcname=item)


def main():

    parser = OptionParser(version='%prog ' + __version__,
                          usage="%prog [options]")
    parser.add_option('-N', '--ns-pass', help='required: the NICKSERV password to use')
    parser.add_option('-W', '--wait', default='15', help='number of seconds to wait when attempting to restore the IRC connection [default: %default]')
    parser.add_option('-M', '--max-reconnects', default='10', help='maximum number of times to attempt to restore the IRC connection [default: %default]')
    parser.add_option('-R', '--reset-attempts-time', default='300', help='minimum number of seconds that must pass before resetting the number of attempted reconnects [default: %default]')

    options, args = parser.parse_args()

    if not options.ns_pass:
        parser.print_help()
        exit()

    restart = True
    reconnect_wait = int(options.wait)
    reset_attempt_limit = int(options.reset_attempts_time)
    max_reconnects = int(options.max_reconnects)
    last_start = 0
    reconnect_attempts = 0
    throttle_sleep_time = 60

    while restart:
        bot = MCPBot(nspass = options.ns_pass)

        if last_start != 0 and reconnect_attempts != 0:
            bot.logger.warning('Attempting IRC reconnection in %d seconds...' % reconnect_wait)
            time.sleep(reconnect_wait)

        BotHandler.addBot('mcpbot', bot)

        try:
            BotHandler.startAll()
            last_start = time.time()
            BotHandler.loop()
        except SystemExit as e:
            bot = BotHandler.remBot('mcpbot')

            if bot and bot.logger and not bot.isTerminating:
                logger = bot.logger

                if e.code == 404:
                    logger.warning('IRC connection was lost.')

                    if time.time() - last_start > reset_attempt_limit:
                        reconnect_attempts = 0
                        throttle_sleep_time = 60

                    reconnect_attempts += 1
                    restart = reconnect_attempts <= max_reconnects
                elif e.code == 500:
                    logger.info('Sleeping for %d seconds before further reconnect attempts.' % throttle_sleep_time)
                    time.sleep(throttle_sleep_time)

                    if throttle_sleep_time < reset_attempt_limit:
                        throttle_sleep_time += 10
                else:
                    raise e
            else:
                raise e


if __name__ == "__main__":
    main()