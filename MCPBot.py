# coding=utf-8
from BotBase import BotBase, BotHandler
from Database import Database, is_integer
from optparse import OptionParser
import JsonHelper
import time
from datetime import timedelta, datetime, time as time_class
import threading
import export_csv
from MavenHandler import MavenHandler
import zipfile, os, re
import psycopg2.extras

__version__ = "0.10.2"

class MCPBot(BotBase):
    def __init__(self, configfile=None, backupcfg=False):
        super(MCPBot, self).__init__(configfile=configfile, backupcfg=backupcfg)

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
        self.test_export_url = self.config.get('EXPORT', 'TEST_EXPORT_URL', 'http://export.mcpbot.bspk.rs')
        self.exports_json_url = self.config.get('EXPORT', 'EXPORTS_JSON_URL', 'http://export.mcpbot.bspk.rs/versions.json')
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
        self.srg_base_url = self.config.get('EXPORT', 'SRG_BASE_URL', 'http://export.mcpbot.bspk.rs/mcp/{mc_version_code}/mcp-{mc_version_code}-srg.zip', 'Base URL for downloading SRG files.')
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
        self.registerCommand('latest',   self.getLatestMappingVersion, ['any'], 0, 2, '[snapshot|stable] [<mcversion>]', 'Gets a list of the latest mapping versions.', allowpub=True)
        self.registerCommand('commit', self.commitMappings, ['mcp_team'], 0, 1, '[<srg_name>|method|field|param]', 'Commits staged mapping changes. If SRG name is specified only that member will be committed. If method/field/param is specified only that member type will be committed. Give no arguments to commit all staged changes.', allowduringreadonly=False)
        self.registerCommand('maventime',self.setMavenTime,['mcp_team'], 0, 1, '<HH:MM>', 'Changes the time that the Maven upload will occur using 24 hour clock format.')
        self.registerCommand('pj', self.push_json_to_maven, ['mcp_team'], 0, 0, '', 'Pushes the version.json file to Maven.')

        self.registerCommand('srg',      self.getSrgUrl,  ['any'], 1, 1, '<MC Version>', 'Gets the URL of the SRG zip file for the Minecraft version specified.', allowpub=True)

        self.registerCommand('gc',       self.getClass,   ['any'], 1, 2, "<class> [<version>]",                     "Returns class information. Defaults to current version. Version can be for MCP or MC.", allowpub=True)
        self.registerCommand('gf',       self.getMember,  ['any'], 1, 2, "[<class>.]<name> [<version>]",            "Returns field information. Defaults to current version. Version can be for MCP or MC.", allowpub=True)
        self.registerCommand('gm',       self.getMember,  ['any'], 1, 2, "[<class>.]<name> [<version>]",            "Returns method information. Defaults to current version. Version can be for MCP or MC.", allowpub=True)
        self.registerCommand('gp',       self.getParam,   ['any'], 1, 2, "[[<class>.]<method>.]<name> [<version>]", "Returns method parameter information. Defaults to current version. Version can be for MCP or MC. Obf class and method names not supported.", allowpub=True)
        self.registerCommand('find',     self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns any entries matching a regex pattern. Only returns complete matches.", allowpub=True)
        self.registerCommand('findc',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns class entries matching a regex pattern. Only returns complete matches.", allowpub=True)
        self.registerCommand('findf',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns field entries matching a regex pattern. Class can be specified by separating the class name from the field name with '\\.'. Only returns complete matches.\ne.g. 'findf Minecraft\..+' (lists all fields in the Minecraft class)", allowpub=True)
        self.registerCommand('findm',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns method entries matching a regex pattern. Class can be specified by separating the class name from the method name with '\\.'. Only returns complete matches.\ne.g. 'findm Minecraft\..+' (lists all methods in the Minecraft class)", allowpub=True)
        self.registerCommand('findp',    self.findKey,    ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns parameter entries matching a regex pattern. Only returns complete matches.", allowpub=True)
        self.registerCommand('findall',  self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns any entries matching a regex pattern. Allows partial matches to be returned.", allowpub=True)
        self.registerCommand('findallc', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns class entries matching a regex pattern. Allows partial matches to be returned.", allowpub=True)
        self.registerCommand('findallf', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns field entries matching a regex pattern. Class can be specified by separating the class name from the field name with '\\.'. Allows partial matches to be returned.\ne.g. 'findallf Entity\.is' (lists all fields containing 'is' in any class containing 'Entity')", allowpub=True)
        self.registerCommand('findallm', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns method entries matching a regex pattern. Class can be specified by separating the class name from the method name with '\\.'. Allows partial matches to be returned.\ne.g. 'findallm Entity\.get' (lists all methods containing 'get' in any class containing 'Entity')", allowpub=True)
        self.registerCommand('findallp', self.findAllKey, ['any'], 1, 2, "<regex pattern> [<version>]",             "Returns parameter entries matching a regex pattern. Allows partial matches to be returned.", allowpub=True)
        self.registerCommand('fh',       self.getHistory, ['any'], 1, 1, "<srg name>|<mcp name>",                   "Gets the change history for the given field. Using MCP name allows you to search for changes to/from that name. SRG index is also accepted.", allowpub=True)
        self.registerCommand('mh',       self.getHistory, ['any'], 1, 1, "<srg name>|<mcp name>",                   "Gets the change history for the given method. Using MCP name allows you to search for changes to/from that name. SRG index is also accepted.", allowpub=True)
        self.registerCommand('ph',       self.getHistory, ['any'], 1, 1, "<srg name>|<mcp name>",                   "Gets the change history for the given method param. SRG index is also accepted.", allowpub=True)
        self.registerCommand('uf',       self.listMembers,['any'], 1, 1, "<class>",                                 "Returns a list of unnamed fields for a given class. Use DCC if the list is long.", allowpub=True)
        self.registerCommand('um',       self.listMembers,['any'], 1, 1, "<class>",                                 "Returns a list of unnamed methods for a given class. Use DCC if the list is long.", allowpub=True)
        self.registerCommand('up',       self.listMembers,['any'], 1, 1, "<class>",                                 "Returns a list of unnamed method parameters for a given class. Use DCC if the list is long.", allowpub=True)
        self.registerCommand('undo', self.undoChange, ['any', 'undo_any', 'mcp_team'], 1, 1, "<srg name>",      "Undoes the last *STAGED* name change to a given method/field/param. By default you can only undo your own changes.", allowduringreadonly=False)
        self.registerCommand('redo', self.undoChange, ['any', 'undo_any', 'mcp_team'], 1, 1, "<srg name>",      "Redoes the last *UNDONE* staged change to a given method/field/param. By default you can only redo your own changes.", allowduringreadonly=False)

        self.registerCommand('sf', self.setMember, ['any'], 2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG field specified. SRG index can also be used.", allowpub=True, allowduringreadonly=False)
        self.registerCommand('fsf', self.setMember, ['maintainer', 'mcp_team'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG field specified. SRG index can also be used.", allowpub=True, allowduringreadonly=False)
        self.registerCommand('sm', self.setMember, ['any'], 2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG method specified. SRG index can also be used.", allowpub=True, allowduringreadonly=False)
        self.registerCommand('fsm', self.setMember, ['maintainer', 'mcp_team'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG method specified. SRG index can also be used.", allowpub=True, allowduringreadonly=False)
        self.registerCommand('sp', self.setMember, ['any'], 2, 999, "<srg name> <new name> [<comment>]", "Sets the MCP name and comment for the SRG method parameter specified. SRG index can also be used.", allowpub=True, allowduringreadonly=False)
        self.registerCommand('fsp', self.setMember, ['maintainer', 'mcp_team'], 2, 999, "<srg name> <new name> [<comment>]", "Force sets the MCP name and comment for the SRG method parameter specified. SRG index can also be used.", allowpub=True, allowduringreadonly=False)

        self.registerCommand('lock', self.setLocked, ['lock_control', 'mcp_team'], 1, 1, "<srg name>", "Locks the given field/method/parameter from being edited. Full SRG name must be used.", allowduringreadonly=False)
        self.registerCommand('lockf', self.setLocked, ['lock_control', 'mcp_team'], 1, 1, "<srg name>", "Locks the given field from being edited. SRG index can also be used.", allowduringreadonly=False)
        self.registerCommand('lockm', self.setLocked, ['lock_control', 'mcp_team'], 1, 1, "<srg name>", "Locks the given method from being edited. SRG index can also be used.", allowduringreadonly=False)
        self.registerCommand('lockp', self.setLocked, ['lock_control', 'mcp_team'], 1, 1, "<srg name>", "Locks the given method parameter from being edited. SRG index can also be used.", allowduringreadonly=False)
        self.registerCommand('unlock', self.setLocked, ['lock_control', 'mcp_team'], 1, 1, "<srg name>", "Unlocks the given field/method/parameter to allow editing. Full SRG name must be used.", allowduringreadonly=False)
        self.registerCommand('unlockf', self.setLocked, ['lock_control', 'mcp_team'], 1, 1, "<srg name>", "Unlocks the given field to allow editing. SRG index can also be used.", allowduringreadonly=False)
        self.registerCommand('unlockm', self.setLocked, ['lock_control', 'mcp_team'], 1, 1, "<srg name>", "Unlocks the given method to allow editing. SRG index can also be used.", allowduringreadonly=False)
        self.registerCommand('unlockp', self.setLocked, ['lock_control', 'mcp_team'], 1, 1, "<srg name>", "Unlocks the given method parameter to allow editing. SRG index can also be used.", allowduringreadonly=False)

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

    def clone(self):
        return MCPBot(self.configfile, False)

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


    def setMavenTime(self, bot, sender, dest, cmd, args):
        self.sendNotice(sender.nick, '===§B Maven Time Change §N===')
        if args[0]:
            if not isValid24HourTimeStr(args[0]):
                self.sendNotice(sender.nick, '%s is not a valid time string!' % args[0])
            else:
                self.processMavenTimeString(args[0])
                self.sendNotice(sender.nick, 'Maven upload time has been changed to %s' % args[0])
        else:
            self.sendNotice(sender.nick, 'Maven Time: ' + self.maven_upload_time_str)



    def exportTimer(self):
        if not self.next_export:
            curtime = time.time()
            # set the next export time to a number that is a multiple of the test_export_period to keep the export times predictable
            self.next_export = curtime - (curtime % (self.test_export_period * 60))

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
            while self.next_export - time.time() <= 0:
                self.next_export += (self.test_export_period * 60)
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


    def getSrgUrl(self, bot, sender, dest, cmd, args):
        if dest == self.nick:
            dest = sender.nick

        val, status = self.db.getVersions(0)
        for entry in val:
            if entry['mc_version_code'] == args[0]:
                self.sendOutput(dest, self.srg_base_url.format(**entry))
                return

        self.sendOutput(sender.nick, 'Invalid MC version number specified.')


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
            self.logger.info('Pushing ' + stdZipName)
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
                self.logger.info('Pushing ' + nodocZipName)
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

            if success:
                self.push_json_to_maven(None, None, None, None, None)
                self.push_xml_to_maven(None, None, None, None, None)


    def push_json_to_maven(self, bot, sender, dest, cmd, args):
        # push json file to maven
        if JsonHelper.save_remote_json_to_path(self.exports_json_url,
                                                           os.path.join(self.base_export_path, 'versions.json')):
            tries = 0
            self.logger.info('Pushing versions.json')
            success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                                          'versions.json', local_path=self.base_export_path, remote_path='',
                                          logger=self.logger)
            while tries < self.upload_retry_count and not success:
                tries += 1
                self.logger.warning('*** Upload attempt failed. Trying again in 3 minutes. ***')
                time.sleep(180)
                success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                                              'versions.json', local_path=self.base_export_path, remote_path='',
                                              logger=self.logger)

            if success and tries == 0:
                self.logger.info('Maven upload successful.')
            elif success and tries > 0:
                self.logger.info('Maven upload successful after %d %s.' % (tries, 'retry' if tries == 1 else 'retries'))
            else:
                self.logger.error('*** Maven upload failed after %d retries. ***' % tries)
        else:
            self.logger.error('*** Remote JSON was not successfully retrieved. ***')


    def push_xml_to_maven(self, bot, sender, dest, cmd, args):
        # push json file to maven
        for channel in ['mcp_snapshot','mcp_stable']:
            if JsonHelper.save_remote_json_to_path('http://export.mcpbot.bspk.rs/%s/maven-metadata.xml' % channel,
                                                               os.path.join(self.base_export_path, '%s/maven-metadata.xml' % channel)):
                tries = 0
                self.logger.info('Pushing maven-metadata.xml')
                success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                                              'maven-metadata.xml', local_path=os.path.join(self.base_export_path, channel), remote_path=channel,
                                              logger=self.logger)
                while tries < self.upload_retry_count and not success:
                    tries += 1
                    self.logger.warning('*** Upload attempt failed. Trying again in 3 minutes. ***')
                    time.sleep(180)
                    success = MavenHandler.upload(self.maven_repo_url, self.maven_repo_user, self.maven_repo_pass,
                                                  'maven-metadata.xml', local_path=os.path.join(self.base_export_path, channel), remote_path=channel,
                                                  logger=self.logger)

                if success and tries == 0:
                    self.logger.info('Maven upload successful.')
                elif success and tries > 0:
                    self.logger.info('Maven upload successful after %d %s.' % (tries, 'retry' if tries == 1 else 'retries'))
                else:
                    self.logger.error('*** Maven upload failed after %d retries. ***' % tries)
            else:
                self.logger.error('*** Remote XML was not successfully retrieved. ***')


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
        self.sendVersionResults(sender, dest, val, status, limit=self.getOutputLimit(sender, dest))


    def getLatestMappingVersion(self, bot, sender, dest, cmd, args):
        mappingType = None
        version = None
        if len(args) > 0:
            if args[0].lower() in ['stable', 'snapshot']:
                mappingType = args[0].lower()
            else:
                version = args[0]

            if len(args) > 1:
                if mappingType:
                    version = args[1]
                elif args[1].lower() in ['stable', 'snapshot']:
                    mappingType = args[1].lower()

        jsonUrl = self.exports_json_url + '?limit=1'

        # if not version:
        #     val, status = self.db.getVersions(1)
        #     version = "{mc_version_code}".format(**val[0])

        if version:
            jsonUrl += '&version=' + version

        data = JsonHelper.get_remote_json(jsonUrl)
        self.sendMappingResults(sender, dest, data, mappingType, limit=self.getOutputLimit(sender, dest))



    def getParam(self, bot, sender, dest, cmd, args):
        val, status = self.db.getParam(args)
        self.sendParamResults(sender, dest, val, status, limit=self.getOutputLimit(sender, dest))


    def getMember(self, bot, sender, dest, cmd, args):
        member_type = 'field'
        if cmd['command'] == 'gm' or args[0].startswith('func_'): member_type = 'method'
        if args[0].startswith('field_'): member_type = 'field'
        val, status = self.db.getMember(member_type, args)
        self.sendMemberResults(sender, dest, val, status, limit=self.getOutputLimit(sender, dest))


    def getClass(self, bot, sender, dest, cmd, args):
        val, status = self.db.getClass(args)
        self.sendClassResults(sender, dest, val, status)


    def getHistory(self, bot, sender, dest, cmd, args):
        member_type = 'field'
        if cmd['command'] == 'mh' or args[0].startswith('func_'): member_type = 'method'
        if cmd['command'] == 'ph' or args[0].startswith('p_'): member_type = 'method_param'
        if args[0].startswith('field_'): member_type = 'field'
        if isSrgName(args[0]) or is_integer(args[0]) or member_type == 'method_param':
            val, status = self.db.getHistory(member_type, args)
            self.sendHistoryResults(member_type, sender, dest, val, status, limit=self.getOutputLimit(sender, dest))
        else:
            val, status = self.db.searchHistory(member_type, args)
            self.sendSearchHistoryResults(member_type, sender, dest, val, args[0], status, limit=self.getOutputLimit(sender, dest))


    def findKey(self, bot, sender, dest, cmd, args):
        args[0] = "^" + args[0] + "$"
        self.findAllKey(bot, sender, dest, cmd, args)


    def findAllKey(self, bot, sender, dest, cmd, args):
        showAll = cmd['command'][-1] in ('d', 'l')
        showFields = cmd['command'][-1] == 'f' or args[0].find('field_') > -1
        showMethods = cmd['command'][-1] == 'm' or args[0].find('func_') > -1
        showParams = cmd['command'][-1] == 'p' or args[0].find('p_') > -1
        showClasses = cmd['command'][-1] == 'c'
        if showAll:
            limit = self.getOutputLimit(sender, dest) / 2
        else:
            limit = self.getOutputLimit(sender, dest)

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
        limit = self.getOutputLimit(sender, dest)
        if cmd['command'][-1] == 'f':
            self.sendOutput(dest, "+++§B UNNAMED %sS FOR %s §N+++" % ('FIELD', args[0]))
            val, status = self.db.getUnnamed('field', args)
            self.sendMemberResults(sender, dest, val, status, limit, summary=True, is_unnamed=True)
        elif cmd['command'][-1] == 'm':
            self.sendOutput(dest, "+++§B UNNAMED %sS FOR %s §N+++" % ('METHOD', args[0]))
            val, status = self.db.getUnnamed('method', args)
            self.sendMemberResults(sender, dest, val, status, limit, summary=True, is_unnamed=True)
        else:
            self.sendOutput(dest, "+++§B UNNAMED %sS FOR %s §N+++" % ('METHOD PARAM', args[0]))
            val, status = self.db.getUnnamed('method_param', args)
            self.sendParamResults(sender, dest, val, status, limit, summary=True, is_unnamed=True)


    # Setters

    def setLocked(self, bot, sender, dest, cmd, args):
        member_type = None
        is_lock = cmd['command'][0] == 'l'
        if cmd['command'].find('f') > -1 or args[0].startswith('field_'): member_type = 'field'
        elif cmd['command'].find('m') > -1 or args[0].startswith('func_'): member_type = 'method'
        elif cmd['command'].find('p') > -1 or args[0].startswith('p_'): member_type = 'method_param'
        if member_type:
            val, status = self.db.setMemberLock(member_type, is_lock, cmd['command'], sender, args)
            self.sendSetLockResults(member_type, sender, dest, val, status, args[0], is_lock)
        else:
            self.sendNotice(sender.nick, '§BFull SRG name is required for the %s command.' % cmd['command'])


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

        self.setReadOnly(self, sender, dest, cmd, ['true'])
        val, status = self.db.doCommit(member_type, cmd['command'], sender, args, srg_name)
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
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

    def sendVersionResults(self, sender, dest, val, status, limit):
        if status:
            self.sendNotice(sender.nick, str(type(status)) + ' : ' + str(status))
            return

        toQueue = []

        if len(val) > 1:
            self.sendOutput(dest, "===§B Available Versions §N===")
        else:
            self.sendOutput(dest, "===§B Current Version §N===")

        # these padding values are 6 higher than the actual data padding values since we have to account for the IRC formatting codes
        self.sendOutput(dest, '{:^19}'.format('§UMCP Version§N') + '{:^19}'.format('§UMC Version§N') + '{:^19}'.format('§URelease Type§N'))

        for i, entry in enumerate(val):
            msg = "{mcp_version_code:^13}".format(**entry) + "{mc_version_code:^13}".format(**entry) + "{mc_version_type_code:^13}".format(**entry)

            if i < limit:
                self.sendOutput(dest, msg)
            else:
                toQueue.append(msg)

        if len(toQueue) > 0:
            self.sendOutput(dest, "§B+ §N%(count)d§B more. Please use %(cmd_char)smore to see %(more)d queued entries." %
                            {'count': len(toQueue), 'cmd_char': self.cmdChar, 'more': min(self.getOutputLimit(sender, dest), len(toQueue))})
            sender.clearMsgQueue()
            for msg in toQueue:
                sender.addToMsgQueue(msg)


    def sendMappingResults(self, sender, dest, data, mappingType, limit):
        toQueue = []

        if not mappingType:
            mappingTypes = ['snapshot', 'stable']
        else:
            mappingTypes = [mappingType]

        self.sendOutput(dest, "===§B Latest Mappings §N===")

        # these padding values are 6 higher than the actual data padding values since we have to account for the IRC formatting codes
        self.sendOutput(dest, '{:^19}'.format('§UMC Version§N') + '{:^29}'.format('§UForge Gradle Channel§N'))

        i = 0
        for mcversion in sorted_nicely(data.keys(), reverse=True):
            for mType in mappingTypes:
                for mapVersion in data[mcversion][mType]:
                    msg = "{:^13}".format(mcversion) + "{:^23}".format(mType + '_' + str(mapVersion))
                    if i < limit:
                        self.sendOutput(dest, msg)
                    else:
                        toQueue.append(msg)
                    i += 1

        if len(toQueue) > 0:
            self.sendOutput(dest, "§B+ §N%(count)d§B more. Please use %(cmd_char)smore to see %(more)d queued entries." %
                            {'count': len(toQueue), 'cmd_char': self.cmdChar, 'more': min(self.getOutputLimit(sender, dest), len(toQueue))})
            sender.clearMsgQueue()
            for msg in toQueue:
                sender.addToMsgQueue(msg)


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

                if i < limit:
                    self.sendOutput(dest, msg)
                else:
                    toQueue.append(msg)

        if len(toQueue) > 0:
            self.sendOutput(dest, "§B+ §N%(count)d§B more. Please use %(cmd_char)smore to see %(more)d queued entries." %
                            {'count': len(toQueue), 'cmd_char': self.cmdChar, 'more': min(self.getOutputLimit(sender, dest), len(toQueue))})
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
                is_constructor = 'is_constructor' in entry and entry['is_constructor']
                if entry['is_locked']: locked = 'LOCKED'
                else: locked = 'UNLOCKED'
                header =                     "===§B MC {mc_version_code}: {class_pkg_name}/{class_srg_name}.{mcp_name} ({class_obf_name}.{obf_name}) §U" + locked + "§N ==="
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
                if not entry['is_public']:
                    if entry['srg_descriptor'][0] == '(':
                        if is_constructor:
                            self.sendOutput(dest,"§UAT§N         : public {class_pkg_name}.{class_srg_name} ".format(**entry).replace('/', '.') + "<init>{srg_descriptor} # {mcp_name}".format(**entry))
                        else:
                            self.sendOutput(dest,"§UAT§N         : public {class_pkg_name}.{class_srg_name} ".format(**entry).replace('/', '.') + "{srg_name}{srg_descriptor} # {mcp_name}".format(**entry))
                    else:
                        self.sendOutput(dest,"§UAT§N         : public {class_pkg_name}.{class_srg_name} {srg_name} # {mcp_name}".format(**entry).replace('/', '.'))
                self.sendOutput(dest,        "§UComment§N    : {comment}".format(**entry))
                if 'srg_params' in entry and entry['srg_params']:
                    self.sendOutput(dest,    "§USRG Params§N : {srg_params}".format(**entry))
                    self.sendOutput(dest,    "§UMCP Params§N : {mcp_params}".format(**entry))
                if entry['irc_nick']:
                    self.sendOutput(dest,   "§ULast Change§N: {last_modified_ts} ({irc_nick})".format(**entry))
                else:
                    self.sendOutput(dest,   "§ULast Change§N: {last_modified_ts} (_bot_update_)".format(**entry))

                if not i == len(val) - 1:
                    self.sendOutput(dest, " ".format(**entry))
            else:
                if is_unnamed:
                    msg = "{srg_name} §B[§N {srg_descriptor} §B]".format(**entry)
                elif entry['srg_descriptor'].find('(') == 0:
                    msg = "{class_obf_name}.{obf_name} §B=>§N {class_srg_name}.{mcp_name}{srg_descriptor} §B[§N {srg_name} §B]".format(**entry)
                else:
                    msg = "{class_obf_name}.{obf_name} §B=>§N {class_srg_name}.{mcp_name} §B[§N {srg_name} §B]".format(**entry)

                if i < limit:
                    self.sendOutput(dest, msg)
                else:
                    toQueue.append(msg)

        if len(toQueue) > 0:
            self.sendOutput(dest, "§B+ §N%(count)d§B more. Please use %(cmd_char)smore to see %(more)d queued entries." %
                            {'count': len(toQueue), 'cmd_char': self.cmdChar, 'more': min(self.getOutputLimit(sender, dest), len(toQueue))})
            sender.clearMsgQueue()
            for msg in toQueue:
                sender.addToMsgQueue(msg)


    def sendHistoryResults(self, member_type, sender, dest, val, status, limit):
        if member_type == 'method_param':
            member_type_disp = 'Method Param'
        else:
            member_type_disp = member_type[0].upper() + member_type[1:]

        if status:
            self.sendNotice(sender.nick, "§B" + str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendOutput(dest, "§BNo results found.")
            return

        toQueue = []
        self.sendOutput(dest, "===§B " + member_type_disp + " History: {srg_name} §N===".format(**val[0]))

        for i, entry in enumerate(val):
            msg = "[{mc_version_code}, {status} {time_stamp}] {irc_nick}: {old_mcp_name} §B=>§N {new_mcp_name}".format(**entry)
            if entry['undo_irc_nick']:
                msg = msg + '  §B§RUndone {undo_time_stamp}: {undo_irc_nick}'.format(**entry)

            if i < limit:
                self.sendOutput(dest, msg)
            else:
                toQueue.append(msg)

        if len(toQueue) > 0:
            self.sendOutput(dest, "§B+ §N%(count)d§B more. Please use %(cmd_char)smore to see %(more)d queued entries." %
                            {'count': len(toQueue), 'cmd_char': self.cmdChar, 'more': min(self.getOutputLimit(sender, dest), len(toQueue))})
            sender.clearMsgQueue()
            for msg in toQueue:
                sender.addToMsgQueue(msg)

        # self.reply("[%s, %s] %s: %s -> %s" % (row['mcpversion'], row['timestamp'], row['nick'], row['oldname'], row['newname']))


    def sendSearchHistoryResults(self, member_type, sender, dest, val, search, status, limit):
        if member_type == 'method_param':
            member_type_disp = 'Method Param'
        else:
            member_type_disp = member_type[0].upper() + member_type[1:]

        if status:
            self.sendNotice(sender.nick, "§B" + str(type(status)) + ' : ' + str(status))
            return

        if len(val) == 0:
            self.sendOutput(dest, "§BNo results found.")
            return

        toQueue = []
        self.sendOutput(dest, "===§B " + member_type_disp + " History: " + search + " §N===".format(**val[0]))

        for i, entry in enumerate(val):
            msg = "[{mc_version_code} {class_srg_name}.{srg_name}, {status} {time_stamp}] {irc_nick}: {old_mcp_name} §B=>§N {new_mcp_name}".format(**entry)
            if entry['undo_irc_nick']:
                msg = msg + '  §B§RUndone {undo_time_stamp}: {undo_irc_nick}'.format(**entry)

            if i < limit:
                self.sendOutput(dest, msg)
            else:
                toQueue.append(msg)

        if len(toQueue) > 0:
            self.sendOutput(dest, "§B+ §N%(count)d§B more. Please use %(cmd_char)smore to see %(more)d queued entries." %
                            {'count': len(toQueue), 'cmd_char': self.cmdChar, 'more': min(self.getOutputLimit(sender, dest), len(toQueue))})
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

                if i < limit:
                    self.sendOutput(dest, msg)
                else:
                    toQueue.append(msg)

        if len(toQueue) > 0:
            self.sendOutput(dest, "§B+ §N%(count)d§B more. Please use %(cmd_char)smore to see %(more)d queued entries." %
                            {'count': len(toQueue), 'cmd_char': self.cmdChar, 'more': min(self.getOutputLimit(sender, dest), len(toQueue))})
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


def isValid24HourTimeStr(timestr):
    splitted = timestr.split(':')
    if len(splitted) > 2:
        return False
    if not is_integer(splitted[0]) or not (0 <= int(splitted[0]) < 24):
        return False
    if len(splitted) == 2 and (not is_integer(splitted[1]) or not (0 <= int(splitted[1] < 60))):
        return False
    return True


def isSrgName(name):
    return name.startswith('field_') or name.startswith('func_') or name.startswith('p_')


def sorted_nicely( l, reverse=False ):
    """ Sort the given iterable in the way that humans expect."""
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ]
    ret = sorted(l, key = alphanum_key)
    if reverse:
        ret.reverse()
    return ret


def main():

    parser = OptionParser(version='%prog ' + __version__,
                          usage="%prog [options]")
    parser.add_option('-C', '--config', default=None, help='The config filename to use.')
    parser.add_option('-B', '--backup-config', default=False, action='store_true', help='Creates a backup of the config file prior to running [default: %default]')
    parser.add_option('-W', '--wait', default='15', help='Number of seconds to wait when attempting to restore the IRC connection [default: %default]')
    parser.add_option('-M', '--max-reconnects', default='10', help='Maximum number of times to attempt to restore the IRC connection [default: %default]')
    parser.add_option('-R', '--reset-attempts-time', default='300', help='Minimum number of seconds that must pass before resetting the number of attempted reconnects [default: %default]')

    options, args = parser.parse_args()

    BotHandler(MCPBot(configfile=options.config, backupcfg=options.backup_config),
               reconnect_wait=int(options.wait), reset_attempt_secs=int(options.reset_attempts_time),
               max_reconnects=int(options.max_reconnects))\
        .start().run()

    print('Fin')


if __name__ == "__main__":
    main()
