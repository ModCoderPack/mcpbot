# coding=utf-8

import Logger
import AsyncSocket
import asyncore
import ConfigParser
import DCCSocket
import threading
import datetime
import json
from IRCHandler import CmdHandler,CmdGenerator,Sender,Color, EOL
from ConfigHandler import AdvConfigParser

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
    def __init__(self, configfile = None, nspass = None):
        self.configfile = configfile if configfile else 'bot.cfg'
        self.config     = AdvConfigParser()
        self.config.read(self.configfile)

        self.nspass     = nspass

        self.host       = self.config.get('SERVER', 'HOST', '')
        self.port       = self.config.geti('SERVER', 'PORT', '6667')
        self.channels   = set(self.config.get('SERVER','CHANNELS', "").split(';') if self.config.get('SERVER','CHANNELS', "").strip() else [])
        self.floodLimit = self.config.getf('SERVER', 'FLOODLIMIT', "0.75", 'Min delay between two line sending.')
        self.servpass   = self.config.get('SERVER', 'PASSWORD', "", 'Server password')

        self.nickserv   = self.config.get('NICKSERV', 'NICKSERV', "NickServ", 'Nick of the nick server used for auth purposes')
        self.nickAuth   = self.config.get('NICKSERV', 'NICKAUTH', "PRIVMSG {nickserv} :acc {nick}", 'Command to use to determine the ACC level of a user')
        self.authRegex  = self.config.get('NICKSERV', 'AUTHREGEX',"(?P<nick>.+) ACC (?P<level>[0-9])", 'Regexp to parse the ACC answer')
        self.nsmarker   = self.config.get('NICKSERV', 'NSMARKER', "This nickname is registered", 'Regexp to parse in the nickserv msg when the nick need to be identified')
        self.nsreply    = self.config.get('NICKSERV', 'NSREPLY',  "PRIVMSG {nickserv} :identify {nspass}", 'Reply to an identify request')

        self.nick        = self.config.get('BOT', 'NICK', "PyBot")
        self.cmdChar     = self.config.get('BOT', 'CMDCHAR', "*")
        self.autoInvite  = self.config.getb('BOT', 'AUTOACCEPT', "true", 'Automatically accept invites ?')
        self.autoJoin    = self.config.getb('BOT', 'AUTOJOIN', "true", 'Automatically join channels in the chan list ?')
        self.lognormal   = self.config.get('BOT', 'LOGNORMAL', "botlog.log")
        self.logerrors   = self.config.get('BOT', 'LOGERRORS', "errors.log")

        self.allowunregistered = self.config.getb('AUTH', 'ALLOWUNREGISTERED', "true", 'Can users without a registered nick emit commands ?')
        self.authtimeout       = self.config.geti('AUTH', 'TIMEOUT', "60", 'Authentication refresh delay in seconds. Auth will be considered valid for this period.')

        self.dccActive         = self.config.getb('DCC', 'ACTIVE',    "true")
        self.dccAllowAnon      = self.config.getb('DCC', 'ALLOWANON', "false", 'Can users connect via DCC if the user is not properly IP identified ?')

        self.logger = Logger.getLogger("%s-%s-%s"%(__name__, self.nick, self.host) , self.lognormal, self.logerrors)

        # We collect the list of groups (<group> = <authorised commands separated by ;>)
        self.groups = {}
        for option in self.config.options('GROUPS'):
            self.groups[option]             = json.loads(self.config.get('GROUPS',option))
            self.groups[option]['commands'] = set(self.groups[option]['commands'])

        # We collect the list of users (<user> = <groups authorised separated by ;>)
        self.authUsers = {}
        for option in self.config.options('USERS'):
            self.authUsers[option] = set(self.config.get('USERS',option).lower().split(';') if self.config.get('USERS',option).strip() else [])

        self.banList = {}
        for option in self.config.options('BANLIST'):
            self.banList[option] = set(self.config.get('BANLIST',option).lower().split(';') if self.config.get('BANLIST',option).strip() else [])

        self.logger.debug("Users  : %s"%self.authUsers)
        self.logger.debug("Groups : %s"%self.groups)

        self.updateConfig()

        self.users     = {}
        self.usersInfo = {}

        self.isIdentified = False   #Turn to true when nick/ident commands are sent
        self.isReady      = False   #Turn to true after RPL_ENDOFMOTD. Every join/nick etc commands should be sent once this is True.

        self.socket = AsyncSocket.AsyncSocket(self, self.host, self.port, self.floodLimit)
        self.dccSocket = DCCSocket.DCCSocket(self)
        self.cmdHandler = CmdHandler(self, self.socket)         

        self.registerCommand('dcc',       self.requestDCC, ['any'],   0, 0, "",              "Requests a DCC connection to the bot.")

        self.registerCommand('useradd',  self.useradd,   ['admin'], 2, 2, "<user> <group>","Adds user to group.")
        self.registerCommand('userrm',   self.userrm,    ['admin'], 2, 2, "<user> <group>","Removes user from group.")
        self.registerCommand('userget',  self.userget,   ['admin'], 1, 1, "<user>",        "Returns list of groups for this user.")
        self.registerCommand('userall',  self.userall,   ['admin'], 0, 0, "",              "Returns a list of groups and users.")
        
        self.registerCommand('groupadd',  self.groupadd,   ['admin'], 2, 2, "<group> <cmd>", "Adds command to group.")
        self.registerCommand('grouprm',   self.grouprm,    ['admin'], 2, 2, "<group> <cmd>", "Remove command from group.")
        self.registerCommand('groupget',  self.groupget,   ['admin'], 0, 0, "",              "Returns a list of groups and commands.")
        self.registerCommand('groupmeta', self.groupmeta,  ['admin'], 3, 999, "<group> <key> <value>", "Add a value to a group key")


        self.registerCommand('banadd', self.banadd, ['admin'], 2, 2, "<user|host> <cmd>", "Bans the user from using the specified command.")
        self.registerCommand('banrm',  self.banrm,  ['admin'], 2, 2, "<user|host> <cmd>", "Remove a ban on an user.")
        self.registerCommand('banget', self.banget, ['admin'], 1, 1, "<user|host>",       "Returns the ban list for the given user.")
        self.registerCommand('banall', self.banall, ['admin'], 0, 0, "",                  "Returns a complete dump of the ban table.")

        self.registerCommand('sendraw',   self.sendRawCmd, ['admin'], 0, 999, "<irccmd>",    "Send a raw IRC cmd.")

        self.registerCommand('help',      self.helpcmd,    ['any'],   0, 0, "",              "This help message.")

    # User handling commands
    def useradd(self, bot, sender, dest, cmd, args):
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

    def userrm(self, bot, sender, dest, cmd, args):
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
            return

        self.authUsers[user].remove(group)
        bot.sendNotice(sender.nick, "Done")
        self.updateConfig()

    def userget(self, bot, sender, dest, cmd, args):
        user  = args[0].lower()

        if not user in self.authUsers:
            bot.sendNotice(sender.nick, "User %s is not registered"%args[0])
            return

        msg = "%s : %s"%(args[0], ", ".join(self.authUsers[user]))
        bot.sendNotice(sender.nick, msg)        

    def userall(self, bot, sender, dest, cmd, args):
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

    # Ban handling
    def banadd(self, bot, sender, dest, cmd, args):
        user    = args[0].lower()
        command = args[1].lower()

        if not user in self.banList:
            self.banList[user] = set()

        self.banList[user].add(command)
        bot.sendNotice(sender.nick, "Done")
        self.updateConfig()

    def banget(self, bot, sender, dest, cmd, args):
        user  = args[0].lower()

        if not user in self.banList:
            bot.sendNotice(sender.nick, "User %s is not banned"%args[0])
            return

        msg = "%s : %s"%(args[0], ", ".join(self.banList[user]))
        bot.sendNotice(sender.nick, msg)

    def banall(self, bot, sender, dest, cmd, args):
        for user in self.banList:
            msg = "%s : %s"%(user, ", ".join(self.banList[user]))
            bot.sendNotice(sender.nick, msg)

    def banrm(self, bot, sender, dest, cmd, args):
        user    = args[0].lower()
        command = args[1].lower()

        if not user in self.banList:
            bot.sendNotice(sender.nick, "User %s is not registered"%args[0])
            return

        if not command in self.banList[user]:
            bot.sendNotice(sender.nick, "User %s in not banned from using %s"%(args[0],command))
            return

        self.banList[user].remove(command)
        bot.sendNotice(sender.nick, "Done")
        self.updateConfig()


    # Group handling commands
    def groupadd(self, bot, sender, dest, cmd, args):
        group  = args[0].lower()
        cmd    = args[1].lower()

        if not group in self.groups:
            self.groups[group] = {'commands':set()}

        self.groups[group]['commands'].add(cmd)
        bot.sendNotice(sender.nick, "Done")
        self.updateConfig()

    def grouprm(self, bot, sender, dest, cmd, args):
        group  = args[0].lower()
        cmd    = args[1].lower()        

        if not group in self.groups:
            bot.sendNotice(sender.nick, "Group %s does not exist"%group)
            return

        if not cmd in self.groups[group]['commands']:
            bot.sendNotice(sender.nick, "Command %s not in group %s"%(cmd, group))
            return

        self.groups[group]['commands'].remove(cmd)
        if len(self.groups[group]['commands']) == 0:
            del self.groups[group]

        bot.sendNotice(sender.nick, "Done")
        self.updateConfig()

    def groupget(self, bot, sender, dest, cmd, args):
        for group,cmds in self.groups.items():
            bot.sendNotice(sender.nick, "%s : %s"%(group, cmds))

    def groupmeta(self, bot, sender, dest, cmd, args):
        group  = args[0].lower()
        key    = args[1].lower()

        try:
            value  = eval(" ".join(args[2:]))
        except Exception as e:
            bot.sendNotice(sender.nick, "Exception : %s"%e)
            return

        if not group in self.groups:
            bot.sendNotice(sender.nick, "Group %s does not exist"%group)
            return

        self.groups[group][key] = value

        bot.sendNotice(sender.nick, "Done")
        self.updateConfig()

    # Default help command
    def helpcmd(self, bot, sender, dest, cmd, args):
        maxcmdlen    = len(max(self.cmdHandler.commands.keys(), key=len))
        maxargslen   = len(max([i['descargs'] for i in self.cmdHandler.commands.values()], key=len))

        formatstr = "§B%%%ds %%%ds§N : %%s"%(maxcmdlen * -1, maxargslen * -1)

        for cmd, cmdval in self.cmdHandler.commands.items():
            if not cmdval['showhelp']:
                continue
            if 'any' in cmdval['groups']:
                bot.sendNotice(sender.nick, formatstr%(cmd, cmdval['descargs'], cmdval['desccmd']))
            elif sender.nick.lower() in self.authUsers:
                groups = self.authUsers[sender.nick.lower()]
                if 'admin' in groups:
                    bot.sendNotice(sender.nick, formatstr%(cmd, cmdval['descargs'], cmdval['desccmd']))
                elif len(groups.intersection(set(cmdval['groups']))) > 0:
                    bot.sendNotice(sender.nick, formatstr%(cmd, cmdval['descargs'], cmdval['desccmd']))

    # DCC Request command, in by default
    def requestDCC(self, bot, sender, dest, cmd, args):
        if self.dccActive:
            host, port = self.dccSocket.getAddr()
            if self.dccSocket.addPending(sender):
                self.sendRaw(CmdGenerator.getDCCCHAT(sender.nick, host, port))
        else:
            self.sendNotice(sender.nick, "DCC is not active on this bot.")

    # Raw command sender
    def sendRawCmd(self, bot, sender, dest, cmd, args):
        self.sendRaw(" ".join(args) + EOL)

    # Config update
    def updateConfig(self):
        fp = open(self.configfile, 'w')
        if hasattr(self, "channels"):
            self.config.set('SERVER', 'CHANNELS', ';'.join(self.channels))

        if not hasattr(self, "groups") or not hasattr(self, "users"): return

        # We remove the missing commands from the config file
        for group,data in self.groups.items():
            nullCommands = []

            for cmd in data['commands']:
                if not cmd in self.cmdHandler.commands:
                    nullCommands.append(cmd)
            for cmd in nullCommands:
                data['commands'].remove(cmd)
        
        # We clean up the groups by removing those without commands
        nullGroups = []
        for group,data in self.groups.items():
            if not len(data['commands']) > 0:
                nullGroups.append(group)
        
        for group in nullGroups:
            self.groups.pop(group, None)
            self.config.remove_option('GROUPS', group)
        
        # We write down groups
        for group, data in self.groups.items():
            data['commands'] = list(data['commands'])
            self.config.set('GROUPS',group, json.dumps(data))
            data['commands'] = set(data['commands'])

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

        # We clean up the banlist
        nullBans = []
        for user, bans in self.banList.items():
            if not len(bans) > 0:
                nullBans.append(user)

        for ban in nullBans:
            self.banList.pop(ban, None)
            self.config.remove_option('BANLIST', user)

        # We write down the ban list
        for user, bans in self.banList.items():
            self.config.set('BANLIST',user, ';'.join(bans))

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
        msgColor = Color.doColors(str(msg))
        if target in self.users and self.users[target].dccSocket != None:
            self.users[target].dccSocket.sendMsg(msgColor)
        else:
            self.sendRaw(CmdGenerator.getNOTICE(target, msgColor))
            
    def sendMessage(self, target, msg):
        msgColor = Color.doColors(str(msg))
        if target in self.users and self.users[target].dccSocket != None:
            self.users[target].dccSocket.sendMsg(msgColor)
        else:
            self.sendRaw(CmdGenerator.getPRIVMSG(target, msgColor))

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
                break
            except Exception:
                pass
        
        if not retval:
            self.logger.error("Error while parsing time %s"%self.usersInfo[target].ctcpData['TIME'])
        
        retval = datetime.datetime(2014, retval.month, retval.day, retval.hour, retval.minute, retval.second)
        self.usersInfo[target].ctcpData['TIME'] = retval
        
        return self.usersInfo[target].ctcpData['TIME']

    #EVENT REGISTRATION METHODS (ONE PER RECOGNISE IRC COMMAND)
    def registerCommand(self, command, callback, groups, minarg, maxarg, descargs = "", desccmd = "", showhelp = True):
        self.cmdHandler.registerCommand(command, callback, groups, minarg, maxarg, descargs, desccmd, showhelp)
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
