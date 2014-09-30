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

        self.exception_str_blacklist = set(self.config.get('DATABASE', 'EXCEPTION_STR_BLACKLIST', '').split(';') if self.config.get('DATABASE', 'EXCEPTION_STR_BLACKLIST', 'CONTEXT:;PL/pgSQL function;SQL statement "select', 'If an exception line contains any of these strings it will be excluded from user feedback. Separate entries with ;').strip() else [])

        if '' in self.exception_str_blacklist: self.exception_str_blacklist.remove('')

        self.test_export_period = self.config.geti('EXPORT', 'TEST_EXPORT_PERIOD', '30', 'How often in minutes to run the test CSV export. Use 0 to disable.')
        self.test_export_path = self.config.get('EXPORT', 'TEST_EXPORT_PATH', 'testcsv', 'Relative path to write the test CSV files to.')
        self.test_export_url = self.config.get('EXPORT', 'TEST_EXPORT_URL', 'http://mcpbot.bspk.rs/testcsv/')
        self.maven_repo_url = self.config.get('EXPORT', 'MAVEN_REPO_URL', 'http://files.minecraftforge.net/maven/manage/upload/de/ocean-labs/mcp/', )
        self.maven_repo_user = self.config.get('EXPORT', 'MAVEN_REPO_USER', 'mcp')
        self.maven_repo_pass = self.config.get('EXPORT', 'MAVEN_REPO_PASS', '')
        self.maven_snapshot_path = self.config.get('EXPORT', 'MAVEN_SNAPSHOT_PATH', 'mcp_snapshot/%(date)s-%(mc_version_code)s')
        self.maven_snapshot_channel = self.config.get('EXPORT', 'MAVEN_SNAPSHOT_CHANNEL', 'snapshot_%(date)s')
        self.maven_snapshot_nodoc_path = self.config.get('EXPORT', 'MAVEN_SNAPSHOT_NODOC_PATH', self.maven_snapshot_path.replace('mcp_snapshot', 'mcp_snapshot_nodoc'))
        self.maven_stable_path = self.config.get('EXPORT', 'MAVEN_STABLE_PATH', 'mcp_stable/%(version_control_pid)s-%(mc_version_code)s')
        self.maven_stable_channel = self.config.get('EXPORT', 'MAVEN_STABLE_CHANNEL', 'stable_%(version_control_pid)s')
        self.maven_stable_nodoc_path = self.config.get('EXPORT', 'MAVEN_STABLE_NODOC_PATH', self.maven_stable_path.replace('mcp_stable', 'mcp_stable_nodoc'))
        self.maven_upload_time_str = self.config.get('EXPORT', 'MAVEN_UPLOAD_TIME', '3:00', 'The approximate time that the maven upload will take place daily. Will happen within TEST_EXPORT_PERIOD / 2 minutes of this time. Use H:MM format, with 24 hour clock.')
        self.upload_retry_count = self.config.geti('EXPORT', 'UPLOAD_RETRY_COUNT', '3', 'Number of times to retry the maven upload if it fails. Attempts will be made 3 minutes apart.')
        self.last_export = None
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
        self.registerCommand('testcsv',  self.getTestCSVURL, ['any', 'mcp_team'], 0, 1, "", "Gets the URL for the running export of staged changes.")
        self.registerCommand('commit',   self.commitMappings,['mcp_team'], 0, 1, '[<srg_name>|method|field|param]', 'Commits staged mapping changes. If SRG name is specified only that member will be committed. If method/field/param is specified only that member type will be committed. Give no arguments to commit all staged changes.')

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

        self.registerCommand('lockf',   self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given field from being edited. SRG index can also be used.")
        self.registerCommand('lockm',   self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given method from being edited. SRG index can also be used.")
        self.registerCommand('lockp',   self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given method parameter from being edited. SRG index can also be used.")
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

        self.legacyCommandMap = {'gcc': 'gc', 'gsc': 'gc', 'gcf': 'gf', 'gsf' : 'gf',  'gcm' : 'gm',  'gsm' : 'gm',  'scf' : 'sf',
                                 'ssf': 'sf', 'scm': 'sm', 'ssm': 'sm', 'fscf': 'fsf', 'fssf': 'fsf', 'fscm': 'fsm', 'fssm': 'fsm'}


    def onStartUp(self):
        super(MCPBot, self).onStartUp()
        self.db.connect()
        if self.test_export_period > 0:
            self.exportTimer()


    def onShuttingDown(self):
        if self.isRunning:
            self.db.disconnect()
            if self.test_export_thread:
                self.test_export_thread.cancel()

            super(MCPBot, self).onShuttingDown()


    def exportTimer(self):
        if not self.next_export:
            self.next_export = time.time()

        self.next_export += (self.test_export_period * 60)
        now = datetime.now()

        self.logger.info('Running test CSV export.')
        export_csv.do_export(self.dbhost, self.dbport, self.dbname, self.dbuser, self.dbpass, test_csv=True, export_path=self.test_export_path)
        self.last_export = time.time()

        if self.maven_upload_time:
            min_upload_time = datetime.combine(now.date(), self.maven_upload_time) - timedelta(minutes=self.test_export_period/2)
            max_upload_time = datetime.combine(now.date(), self.maven_upload_time) + timedelta(minutes=self.test_export_period/2)
            if min_upload_time <= now <= max_upload_time:
                self.doMavenPush(now)

        self.test_export_thread = threading.Timer(self.next_export - time.time(), self.exportTimer)
        self.test_export_thread.start()


    def getTestCSVURL(self, bot, sender, dest, cmd, args):
        if len(args) == 1 and args[0] == 'export' \
                and sender.regnick.lower() in self.authUsers and 'mcp_team' in self.authUsers[sender.regnick.lower()]:
            self.logger.info('Running forced test CSV export.')
            export_csv.do_export(self.dbhost, self.dbport, self.dbname, self.dbuser, self.dbpass, test_csv=True, export_path=self.test_export_path)
            self.last_export = time.time()
            self.sendMessage(dest, 'Test CSV files exported to %s' % self.test_export_url)
        elif len(args) == 1 and args[0] == 'export':
            self.sendNotice(sender, 'You do not have permission to use this function.')
        else:
            if self.last_export:
                self.sendMessage(dest, self.test_export_url + ' (Updated %s ago)' % getDurationStr(time.time() - self.last_export))
            else:
                self.sendMessage(dest, self.test_export_url + ' (Last export time unknown)')


    # TODO: combine this method with the copy below it
    def doMavenPush(self, now):
        self.logger.info("Pushing nightly snapshot mappings to Forge Maven.")
        self.sendPrimChanMessage("[TEST CSV] Pushing nightly snapshot mappings to Forge Maven.")
        result, status = self.db.getVersions(1, psycopg2.extras.RealDictCursor)
        if status:
            self.logger.error(status)
            self.sendPrimChanMessage('[TEST CSV] Database error occurred, Maven upload skipped.')
            self.sendPrimChanOpNotice(status)
        else:
            self.logger.info('Running test CSV no-doc export.')
            export_csv.do_export(self.dbhost, self.dbport, self.dbname, self.dbuser, self.dbpass, test_csv=True, export_path=self.test_export_path + '_nodoc', no_doc=True)

            result[0]['date'] = now.strftime('%Y%m%d')
            zip_name = (self.maven_snapshot_path.replace('/', '-') + '.zip') % result[0]
            zip_name_nodoc = (self.maven_snapshot_nodoc_path.replace('/', '-') + '.zip') % result[0]
            zipContents(self.test_export_path, zip_name)
            zipContents(self.test_export_path + '_nodoc', zip_name_nodoc)

            tries = 0
            success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                    zip_name, remote_path=self.maven_snapshot_path % result[0], logger=self.logger)
            while tries < self.upload_retry_count and not success:
                tries += 1
                self.sendPrimChanOpNotice('[TEST CSV] WARNING: Upload attempt failed. Trying again in 3 minutes.')
                time.sleep(180)
                success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                        zip_name, remote_path=self.maven_snapshot_path % result[0], logger=self.logger)

            if success and tries == 0:
                self.logger.info('Maven upload successful.')
                self.sendPrimChanMessage('[TEST CSV] Maven upload successful for %s (mappings = "%s" in build.gradle).' %
                                         (zip_name, self.maven_snapshot_channel % result[0]))
            elif success and tries > 0:
                self.logger.info('Maven upload successful after %d %s.' % (tries, 'retry' if tries == 1 else 'retries'))
                self.sendPrimChanMessage('[TEST CSV] Maven upload successful for %s (mappings = "%s" in build.gradle) after %d %s.' %
                                         (zip_name,  self.maven_snapshot_channel % result[0], tries, 'retry' if tries == 1 else 'retries'))
            else:
                self.logger.error('Maven upload failed after %d retries.' % tries)
                self.sendPrimChanMessage('[TEST CSV] ERROR: Maven upload failed after %d retries!' % tries)

            if success:
                self.sendPrimChanOpNotice(success)
                tries = 0
                success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                        zip_name_nodoc, remote_path=self.maven_snapshot_nodoc_path % result[0], logger=self.logger)
                while tries < self.upload_retry_count and not success:
                    tries += 1
                    self.logger.warning('Upload attempt failed. Trying again in 3 minutes.')
                    time.sleep(180)
                    success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                            zip_name_nodoc, remote_path=self.maven_snapshot_nodoc_path % result[0], logger=self.logger)

                if success and tries == 0:
                    self.logger.info('Maven upload successful.')
                elif success and tries > 0:
                    self.logger.info('Maven upload successful after %d %s.' % (tries, 'retry' if tries == 1 else 'retries'))
                else:
                    self.logger.error('Maven upload failed after %d retries.' % tries)

                if success:
                    self.sendPrimChanOpNotice(success)

    # TODO: combine this method with the one above it
    def doStableMavenPush(self, now):
        self.logger.info("Pushing stable mappings to Forge Maven.")
        self.sendPrimChanMessage("[STABLE CSV] Pushing stable mappings to Forge Maven.")
        result, status = self.db.getVersionPromotions(1, psycopg2.extras.RealDictCursor)
        if status:
            self.logger.error(status)
            self.sendPrimChanMessage('[STABLE CSV] Database error occurred, Maven upload skipped.')
            self.sendPrimChanOpNotice(status)
        else:
            self.logger.info('Running stable CSV no-doc export.')
            export_csv.do_export(self.dbhost, self.dbport, self.dbname, self.dbuser, self.dbpass, test_csv=False, export_path=self.maven_stable_nodoc_path % result[0], no_doc=True)

            result[0]['date'] = now.strftime('%Y%m%d')
            zip_name = (self.maven_stable_path.replace('/', '-') + '.zip') % result[0]
            zip_name_nodoc = (self.maven_stable_nodoc_path.replace('/', '-') + '.zip') % result[0]
            zipContents(self.maven_stable_path % result[0], zip_name)
            zipContents(self.maven_stable_nodoc_path % result[0], zip_name_nodoc)

            tries = 0
            success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                    zip_name, remote_path=self.maven_stable_path % result[0], logger=self.logger)
            while tries < self.upload_retry_count and not success:
                tries += 1
                self.sendPrimChanOpNotice('[STABLE CSV] WARNING: Upload attempt failed. Trying again in 3 minutes.')
                time.sleep(180)
                success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                        zip_name, remote_path=self.maven_stable_path % result[0], logger=self.logger)

            if success and tries == 0:
                self.logger.info('Maven upload successful.')
                self.sendPrimChanMessage('[STABLE CSV] Maven upload successful for %s (mappings = "%s" in build.gradle).' %
                                         (zip_name, self.maven_stable_channel % result[0]))
            elif success and tries > 0:
                self.logger.info('Maven upload successful after %d %s.' % (tries, 'retry' if tries == 1 else 'retries'))
                self.sendPrimChanMessage('[STABLE CSV] Maven upload successful for %s (mappings = "%s" in build.gradle) after %d %s.' %
                                         (zip_name, self.maven_stable_channel % result[0], tries, 'retry' if tries == 1 else 'retries'))
            else:
                self.logger.error('Maven upload failed after %d retries.' % tries)
                self.sendPrimChanMessage('[STABLE CSV] ERROR: Maven upload failed after %d retries!' % tries)

            if success:
                self.sendPrimChanOpNotice(success)
                tries = 0
                success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                        zip_name_nodoc, remote_path=self.maven_stable_nodoc_path % result[0], logger=self.logger)
                while tries < self.upload_retry_count and not success:
                    tries += 1
                    self.logger.warning('Upload attempt failed. Trying again in 3 minutes.')
                    time.sleep(180)
                    success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                            zip_name_nodoc, remote_path=self.maven_stable_nodoc_path % result[0], logger=self.logger)

                if success and tries == 0:
                    self.logger.info('Maven upload successful.')
                elif success and tries > 0:
                    self.logger.info('Maven upload successful after %d %s.' % (tries, 'retry' if tries == 1 else 'retries'))
                else:
                    self.logger.error('Maven upload failed after %d retries.' % tries)

                if success:
                    self.sendPrimChanOpNotice(success)


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
            self.sendNotice(sender.nick, "§R!!! CAREFUL, YOU ARE FORCING AN UPDATE TO A %s !!!" % member_type.upper().replace('_', ' '))
        val, status = self.db.setMember(member_type, is_forced, bypass_lock, cmd['command'], sender, args)
        self.sendSetMemberResults(member_type, sender, val, status, args[0])


    def commitMappings(self, bot, sender, dest, cmd, args):
        if len(args) > 0:
            if args[0].startswith('func_'):
                member_type = 'method'
                srg_name = args[0]
            elif args[0].startswith('field_'):
                member_type = 'field'
                srg_name = args[0]
            elif args[0].startswith('p_'):
                member_type = 'method_param'
                srg_name = args[0]
            elif args[0] == 'method' or args[0] == 'methods':
                member_type = 'method'
                srg_name = None
            elif args[0] == 'field' or args[0] == 'fields':
                member_type = 'method'
                srg_name = None
            elif args[0] == 'param' or args[0] == 'params':
                member_type = 'method'
                srg_name = None
            else:
                self.sendNotice(sender.nick, 'Argument does not appear to be a valid SRG name or member type.')
                return
        else:
            member_type = None
            srg_name = None

        val, status = self.db.doCommit(member_type, cmd['command'], sender, args, srg_name)
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return
        else:
            self.sendPrimChanMessage("===§B Mappings Commit §N===")
            self.sendPrimChanMessage(val[0][0])
            result, status = self.db.getVersionPromotions(1, psycopg2.extras.RealDictCursor)
            if status:
                self.logger.error(status)
                self.sendPrimChanMessage('[STABLE CSV] Database error occurred, Maven upload skipped.')
                self.sendPrimChanOpNotice(status)
            else:
                self.logger.info('Running stable CSV export.')
                export_csv.do_export(self.dbhost, self.dbport, self.dbname, self.dbuser, self.dbpass, test_csv=False, export_path=self.maven_stable_path % result[0])
                self.doStableMavenPush(datetime.now())


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

        if member_type == 'method_param':
            member_type_disp = 'Method Param'
        else:
            member_type_disp = member_type[0].upper() + member_type[1:]

        if is_lock:
            notice = "===§B Lock %s: %s §N===%s" % (member_type_disp, srg_name, os.linesep)
        else:
            notice = "===§B Unlock %s: %s §N===%s" % (member_type_disp, srg_name, os.linesep)

        if status:
            self.reportDbException(sender, notice, status)
            return

        for result in val:
            if result['result'] > 0:
                self.sendNotice(sender.nick, notice + "§BLocked status§N : %s" % str(is_lock))
            else:
                self.sendNotice(sender.nick, notice + "§BERROR: Unhandled error %d when locking/unlocking a member. Please report this to a member of the MCP team along with the command you executed." % result['result'])


    def sendUndoResults(self, member_type, sender, val, status, srg_name, command):
        if member_type == 'method_param':
            member_type_disp = 'Method Param'
        else:
            member_type_disp = member_type[0].upper() + member_type[1:]

        if command == 'undo':
            notice = "===§B Undo last *STAGED* change to %s: %s §N===\n" % (member_type_disp, srg_name)
        else:
            notice = "===§B Redo last *UNDONE* staged change to %s: %s §N===%s" % (member_type_disp, srg_name, os.linesep)

        if status:
            self.reportDbException(sender, notice, status)
            return

        for result in val:
            if result['result'] > 0:
                change, status = self.db.getMemberChange(member_type, result['result'])
                if status:
                    self.reportDbException(sender, notice, status)
                    return

                for row in change:
                    self.sendNotice(sender.nick, notice + "§BName§N     : {old_mcp_name} §B=>§N {new_mcp_name}{EOL}".format(EOL = os.linesep, **row)
                                                        + "§BOld desc§N : {old_mcp_desc}{EOL}".format(EOL = os.linesep, **row)
                                                        + "§BNew desc§N : {new_mcp_desc}".format(**row))
            else:
                self.sendNotice(sender.nick, notice + "§BERROR: Unhandled error %d when %sing a member change. Please report this to a member of the MCP team along with the command you executed." % (result['result'], command))


    def sendSetMemberResults(self, member_type, sender, val, status, srg_name):
        if member_type == 'method_param':
            member_type_disp = 'Method Param'
        else:
            member_type_disp = member_type[0].upper() + member_type[1:]

        notice = "===§B Set %s: %s §N===%s" % (member_type_disp, srg_name, os.linesep)

        if status:
            self.reportDbException(sender, notice, status)
            return

        for result in val:
            if result['result'] > 0:
                change, status = self.db.getMemberChange(member_type, result['result'])
                if status:
                    self.reportDbException(sender, notice, status)
                    return

                for row in change:
                    self.sendNotice(sender.nick, notice + "§BName§N     : {old_mcp_name} §B=>§N {new_mcp_name}{EOL}".format(EOL = os.linesep, **row)
                                                        + "§BOld desc§N : {old_mcp_desc}{EOL}".format(EOL = os.linesep, **row)
                                                        + "§BNew desc§N : {new_mcp_desc}".format(**row))
            else:
                self.sendNotice(sender.nick, notice + "§BERROR: Unhandled error %d when processing a member change. Please report this to a member of the MCP team along with the command you executed." % result)


    def reportDbException(self, sender, prefix, status):
        userMsg, removed = self.stripExceptionContext(str(status))
        self.sendNotice(sender.nick, prefix + userMsg)
        if removed:
            self.logger.error(os.linesep + str(type(status)) + ' : ' + str(status))


    def stripExceptionContext(self, strexcp):
        if strexcp:
            kept = ''
            removed = ''
            for line in [line.strip('\r') for line in strexcp.split('\n')]:
                wasRemoved = False
                for marker in self.exception_str_blacklist:
                    if line.find(marker) > -1:
                        removed += line + os.linesep
                        wasRemoved = True
                        break

                if not wasRemoved:
                    kept += line + os.linesep

            return kept.lstrip(os.linesep), removed.lstrip(os.linesep)
        else:
            return strexcp, None


########################################################################################################################


def zipContents(path, targetfilename=None):
    if not targetfilename: targetfilename = path.replace('/', '_') + '.zip'
    with zipfile.ZipFile(targetfilename, 'w', compression=zipfile.ZIP_DEFLATED) as zfile:
        files = os.listdir(path)
        for item in [item for item in files if os.path.isfile(path + '/' + item) and item.endswith('.csv')]:
            zfile.write(path + '/' + item, arcname=item)


def getDurationStr(timeint):
    if 1 <= timeint % 60 < 2: formatstr = '%S second'
    else: formatstr = '%S seconds'

    if 59 < timeint < 120: formatstr = '%M minute ' + formatstr
    else: formatstr = '%M minutes ' + formatstr

    if 3599 < timeint < 7200: formatstr = '%H hour ' + formatstr
    else: formatstr = '%H hours ' + formatstr

    return ' '.join([s.lstrip('0') if len(s) > 1 else s for s in time.strftime(formatstr, time.gmtime(timeint)).lstrip(' hours0').lstrip(' minutes0').replace('00', '0').split(' ')])

def main():

    parser = OptionParser(version='%prog ' + __version__,
                          usage="%prog [options]")
    parser.add_option('-N', '--ns-pass', default=None, help='the NICKSERV password to use')
    parser.add_option('-W', '--wait', default='15', help='number of seconds to wait when attempting to restore the IRC connection [default: %default]')
    parser.add_option('-M', '--max-reconnects', default='10', help='maximum number of times to attempt to restore the IRC connection [default: %default]')
    parser.add_option('-R', '--reset-attempts-time', default='300', help='minimum number of seconds that must pass before resetting the number of attempted reconnects [default: %default]')

    options, args = parser.parse_args()

    restart = True
    reconnect_wait = int(options.wait)
    reset_attempt_limit = int(options.reset_attempts_time)
    max_reconnects = int(options.max_reconnects)
    last_start = 0
    reconnect_attempts = 0

    # TODO: Move reconnect stuff to BotHandler
    while restart:
        bot = MCPBot(nspass = options.ns_pass)

        if last_start != 0 and reconnect_attempts != 0:
            bot.logger.warning('Attempting IRC reconnection in %d seconds...' % reconnect_wait)
            time.sleep(reconnect_wait)

        BotHandler.addBot('mcpbot', bot)

        BotHandler.startAll()
        last_start = time.time()
        BotHandler.loop()

        bot = BotHandler.remBot('mcpbot')

        if bot and bot.logger and not bot.isTerminating:
            logger = bot.logger
            logger.warning('IRC connection was lost.')

            if time.time() - last_start > reset_attempt_limit:
                reconnect_attempts = 0

            reconnect_attempts += 1
            restart = reconnect_attempts <= max_reconnects
        elif bot and bot.isTerminating:
            restart = False

    print('Fin')


if __name__ == "__main__":
    main()