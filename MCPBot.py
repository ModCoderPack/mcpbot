# coding=utf-8
from BotBase import BotBase, BotHandler
from Database import Database, is_integer
from optparse import OptionParser
import time
from datetime import timedelta, datetime, time as time_class
import threading
import export_csv
from MavenHandler import MavenHandler
import zipfile, os
import psycopg2.extras

__version__ = "0.8.0"

class MCPBot(BotBase):
    def __init__(self, configfile=None, nspass=None, backupcfg=False):
        super(MCPBot, self).__init__(configfile=configfile, nspass=nspass, backupcfg=backupcfg)

        self.dbhost = self.config.get('DATABASE', 'HOST', "")
        self.dbport = self.config.geti('DATABASE', 'PORT', "0")
        self.dbuser = self.config.get('DATABASE', 'USER', "")
        self.dbname = self.config.get('DATABASE', 'NAME', "")
        self.dbpass = self.config.get('DATABASE', 'PASS', "")

        self.exception_str_blacklist = set(self.config.get('DATABASE', 'EXCEPTION_STR_BLACKLIST', '').split(';') if self.config.get('DATABASE', 'EXCEPTION_STR_BLACKLIST', 'CONTEXT:;PL/pgSQL function;SQL statement "select', 'If an exception line contains any of these strings it will be excluded from user feedback. Separate entries with ;').strip() else [])

        if '' in self.exception_str_blacklist: self.exception_str_blacklist.remove('')

        self.base_export_path = self.config.get('EXPORT', 'BASE_EXPORT_PATH', '.', 'Base OS path where all export files will live.')
        self.test_export_period = self.config.geti('EXPORT', 'TEST_EXPORT_PERIOD', '30', 'How often in minutes to run the test CSV export. Use 0 to disable.')
        self.test_export_path = self.config.get('EXPORT', 'TEST_EXPORT_PATH', 'testcsv', 'Path under BASE_EXPORT_PATH to write the test CSV files to.')
        self.stable_export_path = self.config.get('EXPORT', 'STABLE_EXPORT_PATH', 'stablecsv', 'Path under BASE_EXPORT_PATH to write the stable CSV files to.')
        self.test_export_url = self.config.get('EXPORT', 'TEST_EXPORT_URL', 'http://mcpbot.bspk.rs/testcsv/')
        self.maven_repo_url = self.config.get('EXPORT', 'MAVEN_REPO_URL', 'http://files.minecraftforge.net/maven/manage/upload/de/oceanlabs/mcp/')
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

        self.maven_upload_time = None
        self.processMavenTimeString(self.maven_upload_time_str)

        self.db = Database(self.dbhost, self.dbport, self.dbuser, self.dbname, self.dbpass, self)

        #self.registerCommand('sql', self.sqlRequest, ['db_admin'], 1, 999, "<sql command>", "Executes a raw SQL command.", False)

        self.registerCommand('version',  self.getVersion, ['any'], 0, 0, "", "Gets info about the current version.", allowpub=True)
        self.registerCommand('versions', self.getVersion, ['any'], 0, 0, "", "Gets info about versions that are available in the database.", allowpub=True)
        self.registerCommand('testcsv',  self.getTestCSVURL, ['any', 'mcp_team'], 0, 1, "", "Gets the URL for the running export of staged changes.", allowpub=True)
        self.registerCommand('exports',  self.getExportsURL, ['any'], 0, 0, '', 'Gets the URL where all mapping exports can be found.', allowpub=True)
        self.registerCommand('commit',   self.commitMappings,['mcp_team'], 0, 1, '[<srg_name>|method|field|param]', 'Commits staged mapping changes. If SRG name is specified only that member will be committed. If method/field/param is specified only that member type will be committed. Give no arguments to commit all staged changes.')
        self.registerCommand('maventime',self.setMavenTime,['mcp_team'], 1, 1, '<HH:MM>', 'Changes the time that the Maven upload will occur using 24 hour clock format.')

        self.registerCommand('gp',       self.getParam,   ['any'], 1, 2, "[[<class>.]<method>.]<name> [<version>]", "Returns method parameter information. Defaults to current version. Version can be for MCP or MC. Obf class and method names not supported.", allowpub=True)
        self.registerCommand('gf',       self.getMember,  ['any'], 1, 2, "[<class>.]<name> [<version>]",            "Returns field information. Defaults to current version. Version can be for MCP or MC.", allowpub=True)
        self.registerCommand('gm',       self.getMember,  ['any'], 1, 2, "[<class>.]<name> [<version>]",            "Returns method information. Defaults to current version. Version can be for MCP or MC.", allowpub=True)
        self.registerCommand('gc',       self.getClass,   ['any'], 1, 2, "<class> [<version>]",                     "Returns class information. Defaults to current version. Version can be for MCP or MC.", allowpub=True)
        self.registerCommand('find',     self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns any entries matching a regex pattern. Only returns complete matches.", allowpub=True)
        self.registerCommand('findc',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns class entries matching a regex pattern. Only returns complete matches.", allowpub=True)
        self.registerCommand('findf',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns field entries matching a regex pattern. Only returns complete matches.", allowpub=True)
        self.registerCommand('findm',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns method entries matching a regex pattern. Only returns complete matches.", allowpub=True)
        self.registerCommand('findp',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns parameter entries matching a regex pattern. Only returns complete matches.", allowpub=True)
        self.registerCommand('findall',  self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns any entries matching a regex pattern. Allows partial matches to be returned.", allowpub=True)
        self.registerCommand('findallc', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns class entries matching a regex pattern. Allows partial matches to be returned.", allowpub=True)
        self.registerCommand('findallf', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns field entries matching a regex pattern. Allows partial matches to be returned.", allowpub=True)
        self.registerCommand('findallm', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns method entries matching a regex pattern. Allows partial matches to be returned.", allowpub=True)
        self.registerCommand('findallp', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns parameter entries matching a regex pattern. Allows partial matches to be returned.", allowpub=True)
        self.registerCommand('uf',       self.listMembers,['any'], 1, 1, "<class>",                                 "Returns a list of unnamed fields for a given class. Use DCC if the list is long.", allowpub=True)
        self.registerCommand('um',       self.listMembers,['any'], 1, 1, "<class>",                                 "Returns a list of unnamed methods for a given class. Use DCC if the list is long.", allowpub=True)
        self.registerCommand('up',       self.listMembers,['any'], 1, 1, "<class>",                                 "Returns a list of unnamed method parameters for a given class. Use DCC if the list is long.", allowpub=True)
        self.registerCommand('undo',     self.undoChange, ['any', 'undo_any'], 1, 1, "<srg name>",                  "Undoes the last *STAGED* name change to a given method/field/param. By default you can only undo your own changes.")
        self.registerCommand('redo',     self.undoChange, ['any', 'undo_any'], 1, 1, "<srg name>",                  "Redoes the last *UNDONE* staged change to a given method/field/param. By default you can only redo your own changes.")

        self.registerCommand('sf',  self.setMember,  ['any'],        2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG field specified. SRG index can also be used.", allowpub=True)
        self.registerCommand('fsf', self.setMember,  ['maintainer', 'mcp_team'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG field specified. SRG index can also be used.", allowpub=True)
        self.registerCommand('sm',  self.setMember,  ['any'],        2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG method specified. SRG index can also be used.", allowpub=True)
        self.registerCommand('fsm', self.setMember,  ['maintainer', 'mcp_team'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG method specified. SRG index can also be used.", allowpub=True)
        self.registerCommand('sp',  self.setMember,  ['any'],        2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG method parameter specified. SRG index can also be used.", allowpub=True)
        self.registerCommand('fsp', self.setMember,  ['maintainer', 'mcp_team'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG method parameter specified. SRG index can also be used.", allowpub=True)

        self.registerCommand('lockf',   self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given field from being edited. SRG index can also be used.")
        self.registerCommand('lockm',   self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given method from being edited. SRG index can also be used.")
        self.registerCommand('lockp',   self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Locks the given method parameter from being edited. SRG index can also be used.")
        self.registerCommand('unlockf', self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Unlocks the given field to allow editing. SRG index can also be used.")
        self.registerCommand('unlockm', self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Unlocks the given method to allow editing. SRG index can also be used.")
        self.registerCommand('unlockp', self.setLocked,  ['lock_control'], 1, 1, "<srg name>", "Unlocks the given method parameter to allow editing. SRG index can also be used.")

        # Legacy commands that only show a notice
        self.registerCommand('gcf',  self.legacyNotice, ['any'], 1, 1,   "", "", showhelp=False, allowpub=True)
        self.registerCommand('gsf',  self.legacyNotice, ['any'], 1, 1,   "", "", showhelp=False, allowpub=True)
        self.registerCommand('gcm',  self.legacyNotice, ['any'], 1, 1,   "", "", showhelp=False, allowpub=True)
        self.registerCommand('gsm',  self.legacyNotice, ['any'], 1, 1,   "", "", showhelp=False, allowpub=True)
        self.registerCommand('scf',  self.legacyNotice, ['any'], 2, 999, "", "", showhelp=False, allowpub=True)
        self.registerCommand('ssf',  self.legacyNotice, ['any'], 2, 999, "", "", showhelp=False, allowpub=True)
        self.registerCommand('scm',  self.legacyNotice, ['any'], 2, 999, "", "", showhelp=False, allowpub=True)
        self.registerCommand('ssm',  self.legacyNotice, ['any'], 2, 999, "", "", showhelp=False, allowpub=True)
        self.registerCommand('fscf', self.legacyNotice, ['any'], 2, 999, "", "", showhelp=False, allowpub=True)
        self.registerCommand('fssf', self.legacyNotice, ['any'], 2, 999, "", "", showhelp=False, allowpub=True)
        self.registerCommand('fscm', self.legacyNotice, ['any'], 2, 999, "", "", showhelp=False, allowpub=True)
        self.registerCommand('fssm', self.legacyNotice, ['any'], 2, 999, "", "", showhelp=False, allowpub=True)

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


    def processMavenTimeString(self, timestr):
        if timestr:
            if len(timestr.split(':')) > 1:
                upload_hour, _, upload_minute = timestr.partition(':')
            else:
                upload_hour = timestr
                upload_minute = '0'

            self.maven_upload_time = time_class(int(upload_hour), int(upload_minute), 0)
            if self.maven_upload_time_str != timestr:
                self.maven_upload_time_str = timestr
                self.config.set('EXPORT', 'MAVEN_UPLOAD_TIME', timestr, 'The approximate time that the maven upload will take place daily. Will happen within TEST_EXPORT_PERIOD / 2 minutes of this time. Use H:MM format, with 24 hour clock.')
                self.updateConfig()


    def isValid24HourTimeStr(self, timestr):
        splitted = timestr.split(':')
        if len(splitted) > 2:
            return False
        if not is_integer(splitted[0]) or not (0 <= int(splitted[0]) < 24):
            return False
        if len(splitted) == 2 and (not is_integer(splitted[1]) or not (0 <= int(splitted[1] < 60))):
            return False
        return True


    def setMavenTime(self, bot, sender, dest, cmd, args):
        self.sendNotice(sender.nick, '===§B Maven Time Change §N===')
        if not self.isValid24HourTimeStr(args[0]):
            self.sendNotice(sender.nick, '%s is not a valid time string!' % args[0])
        else:
            self.processMavenTimeString(args[0])
            self.sendNotice(sender.nick, 'Maven upload time has been changed to %s' % args[0])


    def exportTimer(self):
        if not self.next_export:
            self.next_export = time.time()

        self.next_export += (self.test_export_period * 60)
        now = datetime.now()

        self.logger.info('Running test CSV export.')
        export_csv.do_export(self.dbhost, self.dbport, self.dbname, self.dbuser, self.dbpass, test_csv=True,
                             export_path=os.path.normpath(os.path.join(self.base_export_path, self.test_export_path)))
        self.last_export = time.time()

        try:
            if self.maven_upload_time:
                min_upload_time = datetime.combine(now.date(), self.maven_upload_time) - timedelta(minutes=self.test_export_period/2)
                max_upload_time = datetime.combine(now.date(), self.maven_upload_time) + timedelta(minutes=self.test_export_period/2)
                if min_upload_time <= now <= max_upload_time:
                    self.doMavenPush(isSnapshot=True, now=now)
        except Exception as e:
            self.logger.error(e)

        if self.test_export_period > 0:
            self.test_export_thread = threading.Timer(self.next_export - time.time(), self.exportTimer)
            self.test_export_thread.start()


    def getTestCSVURL(self, bot, sender, dest, cmd, args):
        if dest == self.nick:
            dest = sender.nick

        if len(args) == 1 and args[0].lower() == 'export' \
                and sender.regnick.lower() in self.authUsers and 'mcp_team' in self.authUsers[sender.regnick.lower()]:
            self.logger.info('Running forced test CSV export.')
            export_csv.do_export(self.dbhost, self.dbport, self.dbname, self.dbuser, self.dbpass, test_csv=True,
                                 export_path=os.path.normpath(os.path.join(self.base_export_path, self.test_export_path)))
            self.last_export = time.time()
            self.sendMessage(dest, 'Test CSV files exported to %s' % self.test_export_url)
        elif len(args) == 1 and args[0].lower() == 'reset' \
                and sender.regnick.lower() in self.authUsers and 'mcp_team' in self.authUsers[sender.regnick.lower()]:
            self.logger.info('Resetting test CSV export schedule.')
            if self.test_export_thread:
                self.test_export_thread.cancel()
            self.next_export = None
            self.exportTimer()
            self.sendMessage(dest, 'Test CSV files exported to %s' % self.test_export_url)
        elif len(args) == 1 and args[0].lower() in ['export', 'reset']:
            self.sendNotice(sender.nick, 'You do not have permission to use this function.')
        else:
            if self.last_export:
                self.sendOutput(dest, self.test_export_url + ' (Updated %s ago)' % getDurationStr(time.time() - self.last_export))
            else:
                self.sendOutput(dest, self.test_export_url + ' (Last export time unknown)')


    def getExportsURL(self, bot, sender, dest, cmd, args):
        if dest == self.nick:
            dest = sender.nick

        self.sendOutput(dest, 'Semi-live (every %d min), Snapshot (daily ~%s EST), and Stable (committed) MCPBot mapping exports can be found here: %s' % (self.test_export_period, self.maven_upload_time_str, self.test_export_url))


    def doMavenPush(self, isSnapshot, now):
        basePath = self.base_export_path
        if isSnapshot:
            typeStr = '[TEST CSV]'
            csvPath = self.test_export_path
            chanStr = self.maven_snapshot_channel
            stdZipStr = self.maven_snapshot_path
            nodocZipStr = self.maven_snapshot_nodoc_path
        else:
            typeStr = '[STABLE CSV]'
            csvPath = self.stable_export_path
            chanStr = self.maven_stable_channel
            stdZipStr = self.maven_stable_path
            nodocZipStr = self.maven_stable_nodoc_path

        self.logger.info("%s Pushing mappings to Forge Maven." % typeStr)

        result, status = self.db.getVersionPromotions(1, psycopg2.extras.RealDictCursor)
        if status:
            self.logger.error(status)
            self.sendPrimChanMessage('%s Database error occurred getting version info, Maven upload skipped.' % typeStr)
            self.sendPrimChanOpNotice(status)
        else:
            result[0]['date'] = now.strftime('%Y%m%d')

            stdCSVPath = os.path.normpath(os.path.join(basePath, csvPath))
            stdZipDir = stdZipStr % result[0]
            stdZipName = (stdZipDir.replace('/', '-') + '.zip')
            stdZipDirPath = os.path.normpath(os.path.join(basePath, stdZipDir))

            nodocCSVPath = os.path.normpath(os.path.join(stdCSVPath, 'nodoc'))
            nodocZipDir = nodocZipStr % result[0]
            nodocZipName = (nodocZipDir.replace('/', '-') + '.zip')
            nodocZipDirPath = os.path.normpath(os.path.join(basePath, nodocZipDir))

            chanStr = chanStr % result[0]

            self.logger.info('%s Running CSV no-doc export.' % typeStr)
            export_csv.do_export(self.dbhost, self.dbport, self.dbname, self.dbuser, self.dbpass, test_csv=isSnapshot,
                                 export_path=nodocCSVPath, no_doc=True)

            zipCSVContents(stdCSVPath, stdZipDirPath, stdZipName)
            zipCSVContents(nodocCSVPath, nodocZipDirPath, nodocZipName)

            self.sendPrimChanMessage("%s Pushing %s mappings to Forge Maven." % (typeStr, chanStr))

            tries = 0
            success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                    stdZipName, local_path=stdZipDirPath, remote_path=stdZipDir, logger=self.logger)
            while tries < self.upload_retry_count and not success:
                tries += 1
                self.sendPrimChanOpNotice('%s WARNING: Upload attempt failed. Trying again in 3 minutes.' % typeStr)
                time.sleep(180)
                success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                        stdZipName, local_path=stdZipDirPath, remote_path=stdZipDir, logger=self.logger)

            if success and tries == 0:
                self.logger.info('Maven upload successful.')
                self.sendPrimChanMessage('%s Maven upload successful for %s (mappings = "%s" in build.gradle).' %
                                         (typeStr, stdZipName, chanStr))
            elif success and tries > 0:
                self.logger.info('Maven upload successful after %d %s.' % (tries, 'retry' if tries == 1 else 'retries'))
                self.sendPrimChanMessage('%s Maven upload successful for %s (mappings = "%s" in build.gradle) after %d %s.' %
                                         (typeStr, stdZipName, chanStr, tries, 'retry' if tries == 1 else 'retries'))
            else:
                self.logger.error('Maven upload failed after %d retries.' % tries)
                self.sendPrimChanMessage('%s ERROR: Maven upload failed after %d retries!' % (typeStr, tries))

            if success:
                self.sendPrimChanOpNotice(success)
                tries = 0
                success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                        nodocZipName, local_path=nodocZipDirPath, remote_path=nodocZipDir, logger=self.logger)
                while tries < self.upload_retry_count and not success:
                    tries += 1
                    self.logger.warning('Upload attempt failed. Trying again in 3 minutes.')
                    time.sleep(180)
                    success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                            nodocZipName, local_path=nodocZipDirPath, remote_path=nodocZipDir, logger=self.logger)

                if success and tries == 0:
                    self.logger.info('Maven upload successful.')
                elif success and tries > 0:
                    self.logger.info('Maven upload successful after %d %s.' % (tries, 'retry' if tries == 1 else 'retries'))
                else:
                    self.logger.error('Maven upload failed after %d retries.' % tries)

                if success:
                    self.sendPrimChanOpNotice(success)
                    self.sendPrimChanMessage('Semi-live (every %d min), Snapshot (daily ~%s EST), and Stable (committed) MCPBot mapping exports can be found here: %s' % (self.test_export_period, self.maven_upload_time_str, self.test_export_url))


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
        self.sendOutput(dest, "§BNOTICE: The legacy command §U%s§N§B is no longer supported, please use §U%s§N§B instead." % (cmd['command'], self.legacyCommandMap[cmd['command']]))


    # Getters

    def getVersion(self, bot, sender, dest, cmd, args):
        limit = 1
        if cmd['command'][-1:] == 's': limit = 0
        val, status = self.db.getVersions(limit)
        self.sendVersionResults(sender, dest, val, status)


    def getParam(self, bot, sender, dest, cmd, args):
        val, status = self.db.getParam(args)
        self.sendParamResults(sender, dest, val, status)


    def getMember(self, bot, sender, dest, cmd, args):
        member_type = 'field'
        if cmd['command'] == 'gm': member_type = 'method'
        val, status = self.db.getMember(member_type, args)
        self.sendMemberResults(sender, dest, val, status, limit=10)


    def getClass(self, bot, sender, dest, cmd, args):
        val, status = self.db.getClass(args)
        self.sendClassResults(sender, dest, val, status)


    def findKey(self, bot, sender, dest, cmd, args):
        args[0] = "^" + args[0] + "$"
        self.findAllKey(bot, sender, dest, cmd, args)


    def findAllKey(self, bot, sender, dest, cmd, args):
        showAll = cmd['command'][-1] in ('d', 'l')
        showFields = cmd['command'][-1] == 'f'
        showMethods = cmd['command'][-1] == 'm'
        showParams = cmd['command'][-1] == 'p'
        showClasses = cmd['command'][-1] == 'c'
        limit = 5 if showAll else 10

        if showAll or showFields:
            self.sendOutput(dest, "+++§B FIELDS §N+++")
            val, status = self.db.findInTable('field', args)
            self.sendMemberResults(sender, dest, val, status, limit, summary=True)

        if showAll or showMethods:
            if showAll:
                self.sendOutput(dest, " ")
            self.sendOutput(dest, "+++§B METHODS §N+++")
            val, status = self.db.findInTable('method', args)
            self.sendMemberResults(sender, dest, val, status, limit, summary=True)

        if showAll or showParams:
            if showAll:
                self.sendOutput(dest, " ")
            self.sendOutput(dest, "+++§B METHOD PARAMS §N+++")
            val, status = self.db.findInTable('method_param', args)
            self.sendParamResults(sender, dest, val, status, limit, summary=True)

        if showAll or showClasses:
            if showAll:
                self.sendOutput(dest, " ")
            self.sendOutput(dest, "+++§B CLASSES §N+++")
            val, status = self.db.findInTable('class', args)
            self.sendClassResults(sender, dest, val, status, limit, summary=True)


    def listMembers(self, bot, sender, dest, cmd, args):
        if cmd['command'][-1] == 'f':
            self.sendOutput(dest, "+++§B UNNAMED %sS FOR %s §N+++" % ('FIELD', args[0]))
            val, status = self.db.getUnnamed('field', args)
            self.sendMemberResults(sender, dest, val, status, 10, summary=True, is_unnamed=True)
        elif cmd['command'][-1] == 'm':
            self.sendOutput(dest, "+++§B UNNAMED %sS FOR %s §N+++" % ('METHOD', args[0]))
            val, status = self.db.getUnnamed('method', args)
            self.sendMemberResults(sender, dest, val, status, 10, summary=True, is_unnamed=True)
        else:
            self.sendOutput(dest, "+++§B UNNAMED %sS FOR %s §N+++" % ('METHOD PARAM', args[0]))
            val, status = self.db.getUnnamed('method_param', args)
            self.sendParamResults(sender, dest, val, status, 10, summary=True, is_unnamed=True)


    # Setters

    def setLocked(self, bot, sender, dest, cmd, args):
        member_type = 'method'
        is_lock = cmd['command'][0] == 'l'
        if cmd['command'].find('f') > -1: member_type = 'field'
        elif cmd['command'].find('p') > -1: member_type = 'method_param'
        val, status = self.db.setMemberLock(member_type, is_lock, cmd['command'], sender, args)
        self.sendSetLockResults(member_type, sender, dest, val, status, args[0], is_lock)


    def undoChange(self, bot, sender, dest, cmd, args):
        can_undo_any = sender.regnick.lower() in self.authUsers and 'undo_any' in self.authUsers[sender.regnick.lower()]
        is_undo = cmd['command'] == 'undo'
        if args[0].startswith('func_'): member_type = 'method'
        elif args[0].startswith('field_'): member_type = 'field'
        else: member_type = 'method_param'
        val, status = self.db.doMemberUndo(member_type, is_undo, can_undo_any, cmd['command'], sender, args)
        self.sendUndoResults(member_type, sender, dest, val, status, args[0], cmd['command'])


    def setMember(self, bot, sender, dest, cmd, args):
        member_type = 'method'
        if cmd['command'].find('sf') > -1: member_type = 'field'
        elif cmd['command'].find('sp') > -1: member_type = 'method_param'
        bypass_lock = sender.regnick.lower() in self.authUsers and 'lock_control' in self.authUsers[sender.regnick.lower()]
        is_forced = cmd['command'][0] == 'f'
        if is_forced:
            self.sendOutput(dest, "§R!!! CAREFUL, YOU ARE FORCING AN UPDATE TO A %s !!!" % member_type.upper().replace('_', ' '))
        val, status = self.db.setMember(member_type, is_forced, bypass_lock, cmd['command'], sender, args)
        self.sendSetMemberResults(member_type, sender, dest, val, status, args[0])


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
            elif args[0].lower() == 'method' or args[0].lower() == 'methods':
                member_type = 'method'
                srg_name = None
            elif args[0].lower() == 'field' or args[0].lower() == 'fields':
                member_type = 'field'
                srg_name = None
            elif args[0].lower() == 'param' or args[0].lower() == 'params':
                member_type = 'method_param'
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
                export_csv.do_export(self.dbhost, self.dbport, self.dbname, self.dbuser, self.dbpass, test_csv=False,
                                     export_path=os.path.normpath(os.path.join(self.base_export_path, self.stable_export_path)))
                self.doMavenPush(isSnapshot=False, now=datetime.now())


    # Send Results

    def sendVersionResults(self, sender, dest, val, status):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if len(val) > 1:
            self.sendOutput(dest, "===§B Available Versions §N===")
        else:
            self.sendOutput(dest, "===§B Current Version §N===")

        # these padding values are 6 higher than the actual data padding values since we have to account for the IRC formatting codes
        self.sendOutput(dest, '{:^19}'.format('§UMCP Version§N') + '{:^19}'.format('§UMC Version§N') + '{:^19}'.format('§URelease Type§N'))

        for i, entry in enumerate(val):
            self.sendOutput(dest, "{mcp_version_code:^13}".format(**entry) + "{mc_version_code:^13}".format(**entry) + "{mc_version_type_code:^13}".format(**entry))


    def sendParamResults(self, sender, dest, val, status, limit=0, summary=False, is_unnamed=False):
        if status:
            self.sendNotice(sender.nick, "§B" + str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendOutput(dest, "§BNo results found.")
            return

        toQueue = []
        summary = summary or len(val) > 5

        for i, entry in enumerate(val):
            if not summary:
                if entry['is_locked']: locked = 'LOCKED'
                else: locked = 'UNLOCKED'
                header =                    "===§B MC {mc_version_code}: {class_pkg_name}/{class_srg_name}.{method_mcp_name}.{mcp_name} §U" + locked + "§N ==="
                self.sendOutput(dest,        header.format(**entry))
                if 'srg_member_base_class' in entry and entry['srg_member_base_class'] != entry['class_srg_name']:
                    self.sendOutput(dest,   "§UBase Class§N : {obf_member_base_class} §B=>§N {srg_member_base_class}".format(**entry))
                if entry['srg_name'] != entry['mcp_name']:
                    self.sendOutput(dest,   "§UName§N       : {srg_name} §B=>§N {mcp_name}".format(**entry))
                else:
                    self.sendOutput(dest,   "§UName§N       : {srg_name}".format(**entry))
                if entry['method_srg_name'] != entry['method_mcp_name']:
                    self.sendOutput(dest,   "§UMethod§N     : {class_obf_name}.{method_obf_name} §B=>§N {class_srg_name}.{method_srg_name} §B=>§N {class_srg_name}.{method_mcp_name}".format(**entry))
                else:
                    self.sendOutput(dest,   "§UMethod§N     : {class_obf_name}.{method_obf_name} §B=>§N {class_srg_name}.{method_srg_name}".format(**entry))
                if entry['method_obf_descriptor'] != entry['method_srg_descriptor']:
                    self.sendOutput(dest,   "§UDescriptor§N : {method_obf_descriptor} §B=>§N {method_srg_descriptor}".format(**entry))
                else:
                    self.sendOutput(dest,   "§UDescriptor§N : {method_obf_descriptor}".format(**entry))
                self.sendOutput(dest,       "§UComment§N    : {comment}".format(**entry))
                if entry['irc_nick']:
                    self.sendOutput(dest,   "§ULast Change§N: {last_modified_ts} ({irc_nick})".format(**entry))
                else:
                    self.sendOutput(dest,   "§ULast Change§N: {last_modified_ts}".format(**entry))

                if not i == len(val) - 1:
                    self.sendOutput(dest,   " ".format(**entry))
            else:
                if is_unnamed:
                    msg = "{method_mcp_name}.{mcp_name} §B[§N {srg_descriptor} §B]".format(**entry)
                else:
                    msg = "{class_srg_name}.{method_srg_name}.{srg_name} §B[§N {srg_descriptor} §B] =>§N {class_srg_name}.{method_mcp_name}.{mcp_name} §B[§N {java_type_code} §B]".format(**entry)

                if i < limit or sender.dccSocket:
                    self.sendOutput(dest, msg)
                else:
                    toQueue.append(msg)

        if len(toQueue) > 0:
            self.sendOutput(dest, "§B+ §N%(count)d§B more. Please use the %(cmd_char)sdcc command to see the full list or %(cmd_char)smore to see %(more)d queued entries." %
                            {'count': len(toQueue), 'cmd_char': self.cmdChar, 'more': self.moreCount})
            sender.clearMsgQueue()
            for msg in toQueue:
                sender.addToMsgQueue(msg)


    def sendMemberResults(self, sender, dest, val, status, limit=0, summary=False, is_unnamed=False):
        if status:
            self.sendNotice(sender.nick, "§B" + str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendOutput(dest, "§BNo results found.")
            return

        toQueue = []
        summary = summary or len(val) > 5

        for i, entry in enumerate(val):
            if not summary:
                if entry['is_locked']: locked = 'LOCKED'
                else: locked = 'UNLOCKED'
                header =                            "===§B MC {mc_version_code}: {class_pkg_name}/{class_srg_name}.{mcp_name} ({class_obf_name}.{obf_name}) §U" + locked + "§N ==="
                self.sendOutput(dest,        header.format(**entry))
                if 'srg_member_base_class' in entry and entry['srg_member_base_class'] != entry['class_srg_name']:
                    self.sendOutput(dest,    "§UBase Class§N : {obf_member_base_class} §B=>§N {srg_member_base_class}".format(**entry))
                if entry['srg_name'] != entry['mcp_name']:
                    self.sendOutput(dest,    "§UName§N       : {obf_name} §B=>§N {srg_name} §B=>§N {mcp_name}".format(**entry))
                else:
                    self.sendOutput(dest,    "§UName§N       : {obf_name} §B=>§N {srg_name}".format(**entry))
                if entry['obf_descriptor'] != entry['srg_descriptor']:
                    self.sendOutput(dest,    "§UDescriptor§N : {obf_descriptor} §B=>§N {srg_descriptor}".format(**entry))
                else:
                    self.sendOutput(dest,    "§UDescriptor§N : {obf_descriptor}".format(**entry))
                self.sendOutput(dest,        "§UComment§N    : {comment}".format(**entry))
                if 'srg_params' in entry and entry['srg_params']:
                    self.sendOutput(dest,    "§USRG Params§N : {srg_params}".format(**entry))
                    self.sendOutput(dest,    "§UMCP Params§N : {mcp_params}".format(**entry))
                if entry['irc_nick']:
                    self.sendOutput(dest,   "§ULast Change§N: {last_modified_ts} ({irc_nick})".format(**entry))
                else:
                    self.sendOutput(dest,   "§ULast Change§N: {last_modified_ts}".format(**entry))

                if not i == len(val) - 1:
                    self.sendOutput(dest, " ".format(**entry))
            else:
                if is_unnamed:
                    msg = "{srg_name} §B[§N {srg_descriptor} §B]".format(**entry)
                elif entry['srg_descriptor'].find('(') == 0:
                    msg = "{class_obf_name}.{obf_name} §B=>§N {class_srg_name}.{mcp_name}{srg_descriptor} §B[§N {srg_name} §B]".format(**entry)
                else:
                    msg = "{class_obf_name}.{obf_name} §B=>§N {class_srg_name}.{mcp_name} §B[§N {srg_name} §B]".format(**entry)

                if i < limit or sender.dccSocket:
                    self.sendOutput(dest, msg)
                else:
                    toQueue.append(msg)

        if len(toQueue) > 0:
            self.sendOutput(dest, "§B+ §N%(count)d§B more. Please use the %(cmd_char)sdcc command to see the full list or %(cmd_char)smore to see %(more)d queued entries." %
                            {'count': len(toQueue), 'cmd_char': self.cmdChar, 'more': self.moreCount})
            sender.clearMsgQueue()
            for msg in toQueue:
                sender.addToMsgQueue(msg)


    def sendClassResults(self, sender, dest, val, status, limit=0, summary=False):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendOutput(dest, "§BNo results found.")
            return

        toQueue = []
        summary = summary or len(val) > 3

        for i, entry in enumerate(val):
            if not summary:
                self.sendOutput(dest,            "===§B MC {mc_version_code}: {srg_name} §N===".format(**entry))
                self.sendOutput(dest,            "§UNotch§N        : {obf_name}".format(**entry))
                self.sendOutput(dest,            "§UName§N         : {pkg_name}/{srg_name}".format(**entry))
                if entry['super_srg_name'] :
                    self.sendOutput(dest,        "§USuper§N        : {super_obf_name} §B=>§N {super_srg_name}".format(**entry))
                if entry['outer_srg_name'] :
                    self.sendOutput(dest,        "§UOuter§N        : {outer_obf_name} §B=>§N {outer_srg_name}".format(**entry))
                if entry['srg_interfaces'] :
                    self.sendOutput(dest,        "§UInterfaces§N   : {srg_interfaces}".format(**entry))
                if entry['srg_extending']:
                    extending = entry['srg_extending'].split(", ")
                    for iclass in range(0, len(extending), 5):
                        self.sendOutput(dest,    "§UExtending§N    : {extended}".format(extended=' '.join(extending[iclass:iclass+5])))
                if entry['srg_implementing']:
                    implementing = entry['srg_implementing'].split(", ")
                    for iclass in range(0, len(implementing), 5):
                        self.sendOutput(dest,    "§UImplementing§N : {implementing}".format(implementing=' '.join(implementing[iclass:iclass+5])))

                if not i == len(val) - 1:
                    self.sendOutput(dest, " ".format(**entry))

            else:
                msg = "{obf_name} §B=>§N {pkg_name}/{srg_name}".format(**entry)

                if i < limit or sender.dccSocket:
                    self.sendOutput(dest, msg)
                else:
                    toQueue.append(msg)

        if len(toQueue) > 0:
            self.sendOutput(dest, "§B+ §N%(count)d§B more. Please use the %(cmd_char)sdcc command to see the full list or %(cmd_char)smore to see %(more)d queued entries." %
                            {'count': len(toQueue), 'cmd_char': self.cmdChar, 'more': self.moreCount})
            sender.clearMsgQueue()
            for msg in toQueue:
                sender.addToMsgQueue(msg)


    # Setter results

    def sendSetLockResults(self, member_type, sender, dest, val, status, srg_name, is_lock):

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


    def sendUndoResults(self, member_type, sender, dest, val, status, srg_name, command):
        if member_type == 'method_param':
            member_type_disp = 'Method Param'
        else:
            member_type_disp = member_type[0].upper() + member_type[1:]

        if command == 'undo':
            notice = "===§B Undo last *STAGED* change to %s: %s §N===%s" % (member_type_disp, srg_name, os.linesep)
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
                    self.sendOutput(dest, notice + "§BName§N     : {old_mcp_name} §B=>§N {new_mcp_name}{EOL}".format(EOL = os.linesep, **row)
                                                        + "§BOld desc§N : {old_mcp_desc}{EOL}".format(EOL = os.linesep, **row)
                                                        + "§BNew desc§N : {new_mcp_desc}".format(**row))
            else:
                self.sendOutput(dest, notice + "§BERROR: Unhandled error %d when %sing a member change. Please report this to a member of the MCP team along with the command you executed." % (result['result'], command))


    def sendSetMemberResults(self, member_type, sender, dest, val, status, srg_name):
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
                    self.sendOutput(dest, notice + "§BName§N     : {old_mcp_name} §B=>§N {new_mcp_name}{EOL}".format(EOL = os.linesep, **row)
                                                        + "§BOld desc§N : {old_mcp_desc}{EOL}".format(EOL = os.linesep, **row)
                                                        + "§BNew desc§N : {new_mcp_desc}".format(**row))
            else:
                self.sendOutput(dest, notice + "§BERROR: Unhandled error %d when processing a member change. Please report this to a member of the MCP team along with the command you executed." % result)


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
                    elif line.strip() == '':
                        wasRemoved = True
                        break

                if not wasRemoved:
                    kept += line + os.linesep

            return kept.lstrip(os.linesep), removed.lstrip(os.linesep)
        else:
            return strexcp, None


########################################################################################################################


def zipCSVContents(srcPath, targetPath, targetfilename):
    if not os.path.exists(targetPath):
        try:
            os.makedirs(targetPath)
        except OSError:
            if not os.path.isdir(targetPath):
                raise

    with zipfile.ZipFile(os.path.normpath(os.path.join(targetPath, targetfilename)), 'w', compression=zipfile.ZIP_DEFLATED) as zfile:
        for item in [item for item in os.listdir(srcPath) if os.path.isfile(os.path.join(srcPath, item)) and item.endswith('.csv')]:
            zfile.write(os.path.join(srcPath, item), arcname=item)


def getDurationStr(timesecs):
    formatstr = ''
    y = divmod(timesecs, 31536000)  # years
    w = divmod(y[1], 604800)        # weeks
    d = divmod(w[1], 86400)         # days
    h = divmod(d[1], 3600)          # hours
    m = divmod(h[1], 60)            # minutes
    s = m[1]                        # seconds
    if y[0] == 1: formatstr += '%d year ' % y[0]
    elif y[0] > 1: formatstr += '%d years ' % y[0]
    if w[0] == 1: formatstr += '%d week ' % w[0]
    elif w[0] > 1: formatstr += '%d weeks ' % w[0]
    if d[0] == 1: formatstr += '%d day ' % d[0]
    elif d[0] > 1: formatstr += '%d days ' % d[0]
    if h[0] == 1: formatstr += '%d hour ' % h[0]
    elif h[0] > 1: formatstr += '%d hours ' % h[0]
    if m[0] == 1: formatstr += '%d minute ' % m[0]
    elif m[0] > 1: formatstr += '%d minutes ' % m[0]
    if s == 1: formatstr += '%d second' % s
    elif s > 1: formatstr += '%d seconds' % s
    return formatstr

def main():

    parser = OptionParser(version='%prog ' + __version__,
                          usage="%prog [options]")
    parser.add_option('-N', '--ns-pass', default=None, help='The NICKSERV password to use.')
    parser.add_option('-C', '--config', default=None, help='The config filename to use.')
    parser.add_option('-B', '--backup-config', default=False, action='store_true', help='Creates a backup of the config file prior to running [default: %default]')
    parser.add_option('-W', '--wait', default='15', help='Number of seconds to wait when attempting to restore the IRC connection [default: %default]')
    parser.add_option('-M', '--max-reconnects', default='10', help='Maximum number of times to attempt to restore the IRC connection [default: %default]')
    parser.add_option('-R', '--reset-attempts-time', default='300', help='Minimum number of seconds that must pass before resetting the number of attempted reconnects [default: %default]')

    options, args = parser.parse_args()

    BotHandler(MCPBot(configfile=options.config, nspass=options.ns_pass, backupcfg=options.backup_config),
               reconnect_wait=int(options.wait), reset_attempt_secs=int(options.reset_attempts_time),
               max_reconnects=int(options.max_reconnects))\
        .start().run()

    print('Fin')


if __name__ == "__main__":
    main()
