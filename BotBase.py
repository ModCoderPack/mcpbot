import Logger
import AsyncSocket
import asyncore
import ConfigParser
import DCCSocket
import threading
import datetime
from IRCHandler import CmdHandler,CmdGenerator,Sender

class BotHandler(object):
    botList = []

    @classmethod
    def addBot(cls, bot):
        cls.botList.append(bot)

    @classmethod
    def runAll(cls):
        cls.__startAll()
        cls.__loop()

    @classmethod
    def __loop(cls):
        try:
            asyncore.loop()
        except KeyboardInterrupt as e:
            print "Shutting down."
            for bot in cls.botList:
                bot.onShuttingDown()
        except Exception as e:
            for bot in cls.botList:
                bot.onShuttingDown()
            raise e

    @classmethod
    def __startAll(cls):
        for bot in cls.botList:
            bot.onStartUp()
            bot.connect()

class BotBase(object):
    def __init__(self, configfile = None):
        self.configfile = configfile if configfile else 'bot.cfg'
        self.config     = ConfigParser.RawConfigParser()
        self.config.read(self.configfile)

        self.host       = self.getConfig('SERVER', 'HOST', '')
        self.port       = int(self.getConfig('SERVER', 'PORT', '6667'))
        self.channels   = set(self.getConfig('SERVER','CHANNELS', "").split(';') if self.getConfig('SERVER','CHANNELS', "").strip() else [])
        self.nickAuth   = self.getConfig('SERVER', 'NICKAUTH',"PRIVMSG nickserv :acc {nick}")
        self.authRegex  = self.getConfig('SERVER', 'AUTHREGEX',"(?P<nick>.+) ACC (?P<level>[0-9])")
        self.floodLimit = float(self.getConfig('SERVER', 'FLOODLIMIT', "0.75"))
        self.servpass   = self.getConfig('SERVER', 'PASSWORD', "")        

        self.nick        = self.getConfig('BOT', 'NICK', "PyBot")
        self.cmdChar     = self.getConfig('BOT', 'CMDCHAR', "*")
        self.autoInvite  = bool(self.getConfig('BOT', 'AUTOACCEPT', "true"))
        self.autoJoin    = bool(self.getConfig('BOT', 'AUTOJOIN', "true"))
        self.lognormal   = self.getConfig('BOT', 'LOGNORMAL', "botlog.log")
        self.logerrors   = self.getConfig('BOT', 'LOGERRORS', "errors.log")
        
        self.allowunregistered = bool(self.getConfig('AUTH', 'ALLOWUNREGISTERED', "true"))
        self.authtimeout       = int(self.getConfig('AUTH', 'TIMEOUT', "60"))

        self.dccActive         = bool(self.getConfig('DCC', 'ACTIVE',    "true"))
        self.dccAllowAnon      = bool(self.getConfig('DCC', 'ALLOWANON', "false"))

        self.logger = Logger.getLogger("%s-%s-%s"%(__name__, self.nick, self.host) , self.lognormal, self.logerrors)
        
        if not self.config.has_section('GROUPS')        :
            self.config.add_section('GROUPS')
        if not self.config.has_section('USERS')        :
            self.config.add_section('USERS')
        
        # We collect the list of groups (<group> = <authorised commands separated by ;>)
        self.groups = {}
        for option in self.config.options('GROUPS'):
            self.groups[option] = set(self.config.get('GROUPS',option).lower().split(';') if self.config.get('GROUPS',option).strip() else [])

        # We collect the list of users (<user> = <groups authorised separated by ;>)
        self.authUsers = {}
        for option in self.config.options('USERS'):
            self.authUsers[option] = set(self.config.get('USERS',option).lower().split(';') if self.config.get('USERS',option).strip() else [])

        self.logger.debug("Users  : %s"%self.authUsers)
        self.logger.debug("Groups : %s"%self.groups)

        self.users      = {}
        self.usersInfo = {}

        self.isIdentified = False   #Turn to true when nick/ident commands are sent
        self.isReady      = False   #Turn to true after RPL_ENDOFMOTD. Every join/nick etc commands should be sent once this is True.

        self.socket = AsyncSocket.AsyncSocket(self, self.host, self.port, self.floodLimit)
        self.dccSocket = DCCSocket.DCCSocket(self)
        self.cmdHandler = CmdHandler(self, self.socket)         

        self.registerCommand('dcc',       self.requestDCC, ['any'],   0, 0, None)
        self.registerCommand('adduser',   self.adduser,    ['admin'], 2, 2, "adduser <user> <group>")
        self.registerCommand('rmuser',    self.rmuser,     ['admin'], 2, 2, "rmuser <user> <group>")
        self.registerCommand('getuser',   self.getuser,    ['admin'], 1, 1, "getuser <user>")        
        self.registerCommand('getusers',  self.getusers,   ['admin'], 0, 0, "getusers")
        
        self.registerCommand('addgroup',  self.addgroup,   ['admin'], 2, 2, "addgroup <group> <cmd>")
        self.registerCommand('rmgroup',   self.rmgroup,    ['admin'], 2, 2, "rmgroup <group> <cmd>")
        self.registerCommand('getgroups', self.getgroups,  ['admin'], 0, 0, "getgroups")    
        
        self.registerCommand('help',      self.helpcmd,    ['any'],   0, 0, "help")

    def getConfig(self, section, option, default):
        if not self.config.has_section(section):
            self.config.add_section(section)
        
        if self.config.has_option(section, option):
            return self.config.get(section, option)
        else:
            self.config.set(section, option, default)
            self.updateConfig()
            return self.config.get(section, option)

    # User handling commands
    def adduser(self, bot, sender, dest, cmd, args):
        user  = args[0].lower()
        group = args[1].lower()

        if not group in self.groups:
            bot.sendNotice(sender.nick, "Group %s does not exist"%args[1])
            return
        
        if not user in self.authUsers:
            self.authUsers[user] = set()

        self.authUsers[user].add(group)
        bot.sendNotice(sender.nick, "Done")
        self.updateConfig()

    def rmuser(self, bot, sender, dest, cmd, args):
        user  = args[0].lower()
        group = args[1].lower()

        if not group in self.groups:
            bot.sendNotice(sender.nick, "Group %s does not exist"%group)
            return

        if not user in self.authUsers:
            bot.sendNotice(sender.nick, "User %s is not registered"%args[0])
            return

        if not group in self.authUsers[user]:
            bot.sendNotice(sender.nick, "User %s in not part of group %s"%(args[0],group))

        self.authUsers[user].remove(group)
        bot.sendNotice(sender.nick, "Done")
        self.updateConfig()

    def getuser(self, bot, sender, dest, cmd, args):
        user  = args[0].lower()

        if not user in self.authUsers:
            bot.sendNotice(sender.nick, "User %s is not registered"%args[0])
            return

        msg = "%s : %s"%(args[0], ", ".join(self.authUsers[user]))
        bot.sendNotice(sender.nick, msg)        

    def getusers(self, bot, sender, dest, cmd, args):
        groups = {}
        for user,groupset in self.authUsers.items():
            for group in groupset:
                if not group in groups:
                    groups[group] = set()
                groups[group].add(user)
        
        maxlen    = len(max(groups.keys(), key=len))
        formatstr = "%%%ds : %%s"%(maxlen * -1)
        
        for k,v in groups.items():
            bot.sendNotice(sender.nick, formatstr%(k,list(v)))

    # Group handling commands
    def addgroup(self, bot, sender, dest, cmd, args):
        group  = args[0].lower()
        cmd    = args[1].lower()

        if not group in self.groups:
            self.groups[group] = set()

        self.groups[group].add(cmd)
        bot.sendNotice(sender.nick, "Done")
        self.updateConfig()

    def rmgroup(self, bot, sender, dest, cmd, args):
        group  = args[0].lower()
        cmd    = args[1].lower()        

        if not group in self.groups:
            bot.sendNotice(sender.nick, "Group %s does not exist"%group)

        if not cmd in self.groups[group]:
            bot.sendNotice(sender.nick, "Command %s not in group %s"%(cmd, group))

        self.groups[group].remove(cmd)
        if len(self.groups[group]) == 0:
            del self.groups[group]

        bot.sendNotice(sender.nick, "Done")
        self.updateConfig()

    def getgroups(self, bot, sender, dest, cmd, args):            
        for group,cmds in self.groups.items():
            bot.sendNotice(sender.nick, "%s : %s"%(group, ", ".join(cmds)))

    # Default help command
    def helpcmd(self, bot, sender, dest, cmd, args):
        maxlen    = len(max(self.cmdHandler.commands.keys(), key=len))
        formatstr = "%%%ds : %%s"%(maxlen * -1)
        
        for cmd, cmdval in self.cmdHandler.commands.items():
            if 'any' in cmdval['groups']:
                bot.sendNotice(sender.nick, formatstr%(cmd, cmdval['desc']))
            elif sender.nick.lower() in self.authUsers:
                groups = self.authUsers[sender.nick.lower()]
                if 'admin' in groups:
                    bot.sendNotice(sender.nick, formatstr%(cmd, cmdval['desc']))
                elif len(groups.intersection(set(cmdval['groups']))) > 0:
                    bot.sendNotice(sender.nick, formatstr%(cmd, cmdval['desc']))

    # DCC Request command, in by default
    def requestDCC(self, bot, sender, dest, cmd, args):
        if self.dccActive:
            host, port = self.dccSocket.getAddr()
            if self.dccSocket.addPending(sender):
                self.sendRaw(CmdGenerator.getDCCCHAT(sender.nick, host, port))
        else:
            self.sendNotice(sender.nick, "DCC is not active on this bot.")

    # Config update
    def updateConfig(self):
        fp = open(self.configfile, 'w')
        self.config.set('SERVER', 'CHANNELS', ';'.join(self.channels))
        
        # We remove the missing commands from the config file
        for group,commands in self.groups.items():
            nullCommands = []            
            
            for cmd in commands:
                if not cmd in self.cmdHandler.commands:
                    nullCommands.append(cmd)
            for cmd in nullCommands:
                commands.remove(cmd)
        
        # We clean up the groups by removing those without commands
        nullGroups = []
        for group,commands in self.groups.items():
            if not len(commands) > 0:
                nullGroups.append(group)
        
        for group in nullGroups:
            self.groups.pop(group, None)
            self.config.remove_option('GROUPS', group)
        
        # We write down groups
        for group,commands in self.groups.items():
            self.config.set('GROUPS',group, ';'.join(commands))

        # We clean up the users by removing those without a group
        nullUsers = []
        for user, group in self.authUsers.items():
            if not len(group) > 0:
                nullUsers.append(user)

        for user in nullUsers:
            self.authUsers.pop(user, None)
            self.config.remove_option('USERS', user)

        # We write down all the users
        for user,group in self.authUsers.items():
            self.config.set('USERS',user, ';'.join(group))

        self.config.write(fp)
        fp.close()

    def run(self):
        if self.host == "":
            self.logger.info("Please set an IRC server in the config file.")
            return

        self.onStartUp()
        self.connect()
        try:
            asyncore.loop()
        except KeyboardInterrupt as e:
            self.logger.info("Shutting down.")
            self.onShuttingDown()
        except Exception as e:
            raise e

    def connect(self):
        self.socket.doConnect()

    def onStartUp(self):
        pass

    def onShuttingDown(self):
        pass

    #IRC COMMANDS QUICK ACCESS
    def sendRaw(self, msg):
        self.socket.sendBuffer.put_nowait(msg)
        
    def join(self, chan):
        self.sendRaw(CmdGenerator.getJOIN(chan))
        
    def sendNotice(self, target, msg):
        if target in self.users and self.users[target].dccSocket != None:
            self.users[target].dccSocket.sendMsg(msg)
        else:
            self.sendRaw(CmdGenerator.getNOTICE(target, msg))
            
    def sendMessage(self, target, msg):
        if target in self.users and self.users[target].dccSocket != None:
            self.users[target].dccSocket.sendMsg(msg)
        else:
            self.sendRaw(CmdGenerator.getPRIVMSG(target, msg))

    #Some data getters
    def getUser(self, target):
        self.usersInfo[target] = Sender(":" + target)
        self.sendRaw(CmdGenerator.getWHOIS(target))

        if not self.usersInfo[target].whoisEvent.wait(10):
            return
            
        return self.usersInfo[target]

    def getTime(self, target):
        self.usersInfo[target] = Sender(":" + target)
        self.usersInfo[target].ctcpEvent['TIME'] = threading.Event()
        self.sendMessage(target, CmdGenerator.getCTCP("TIME"))

        if not self.usersInfo[target].ctcpEvent['TIME'].wait(10):
            return
        
        timePatterns = []
        timePatterns.append("%a %b %d %H:%M:%S")
        timePatterns.append("%a %b %d %H:%M:%S %Y")
        retval = None        
        
        for pattern in timePatterns:
            try:
                retval = datetime.datetime.strptime(self.usersInfo[target].ctcpData['TIME'], pattern)
                break;
            except Exception:
                pass
        
        if not retval:
            self.logger.error("Error while parsing time %s"%self.usersInfo[target].ctcpData['TIME'])
        
        retval = datetime.datetime(2014, retval.month, retval.day, retval.hour, retval.minute, retval.second)
        self.usersInfo[target].ctcpData['TIME'] = retval
        
        return self.usersInfo[target].ctcpData['TIME']

    #EVENT REGISTRATION METHODS (ONE PER RECOGNISE IRC COMMAND)
    def registerCommand(self, command, callback, groups, minarg, maxarg, desc = None):
        self.cmdHandler.registerCommand(command, callback, groups, minarg, maxarg, desc)
    def registerEventPing(self, callback):
        self.cmdHandler.registerEvent('Ping', callback)
    def registerEventKick(self, callback):
        self.cmdHandler.registerEvent('Kick', callback)
    def registerEventInvite(self, callback):
        self.cmdHandler.registerEvent('Invite', callback)
    def registerEventPrivMsg(self, callback):
        self.cmdHandler.registerEvent('Privmsg', callback)
    def registerEventNotice(self, callback):
        self.cmdHandler.registerEvent('Notice', callback)        
    def registerEventJoin(self, callback):
        self.cmdHandler.registerEvent('Join', callback)        
    def registerEventPart(self, callback):
        self.cmdHandler.registerEvent('Part', callback)
    def registerEventMode(self, callback):
        self.cmdHandler.registerEvent('Mode', callback)
    def registerEventQuit(self, callback):
        self.cmdHandler.registerEvent('Quit', callback)
    def registerEventKill(self, callback):
        self.cmdHandler.registerEvent('Kill', callback)
    def registerEventNick(self, callback):
        self.cmdHandler.registerEvent('Nick', callback)        
    def registerEventGeneric(self, event, callback):
        self.cmdHandler.registerEvent(event, callback)
