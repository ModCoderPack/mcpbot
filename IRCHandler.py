# coding=utf-8
import threading
import Logger
import re
import os
import traceback
import time
from   collections import OrderedDict

EOL = os.linesep
CTCPTAG = chr(1)

###########################################################################################################

class Sender(object):
    def __init__(self, sender):
        self.nick    = ""
        self.regnick = ""
        self.ident = ""
        self.host  = ""
        self.auth  = -1
        self.authEvent  = threading.Event()
        self.whoisEvent = threading.Event()
        self.dccSocket = None
        self.lastAuth  = 0

        self.ctcpData  = {}
        self.ctcpEvent = {}

        self.__msgQueue__ = []
        self.lastMoreCmd = time.time() - 30

        if not '!' in sender:
            self.nick = sender[1:]
        else:
            self.nick  = sender.split('!')[0][1:]
            self.ident = sender.split('!')[1].split('@')[0]
            self.host  = sender.split('!')[1].split('@')[1]

    def __repr__(self):
        return "%s!%s@%s"%(self.nick, self.ident, self.host)

    def __eq__(self, other):
        return self.nick == other.nick and self.ident == other.ident and self.host == other.host
    
    def __ne__(self, other):
        return self.nick != other.nick or  self.ident != other.ident or  self.host != other.host

    def toString(self):
        return "%s!%s@%s"%(self.nick, self.ident, self.host)

    def unauthenticate(self):
        self.auth = -1
        self.regnick = ""
        self.authEvent.clear()
        self.whoisEvent.clear()        

    def authenticate(self, level):
        self.auth = level
        self.authEvent.set()
        self.lastAuth = time.time()

    def addToMsgQueue(self, msg):
        if self.__msgQueue__:
            self.__msgQueue__.append(msg)
        else:
            self.__msgQueue__ = [msg]

    def hasQueuedMsgs(self):
        return self.__msgQueue__ and len(self.__msgQueue__) > 0

    def getQueuedMsgCount(self):
        return len(self.__msgQueue__) if self.__msgQueue__ else 0

    def popQueuedMsg(self):
        if self.hasQueuedMsgs():
            return self.__msgQueue__.pop(0)
        else:
            return None

    def clearMsgQueue(self):
        self.__msgQueue__ = []

###########################################################################################################

class CmdGenerator(object):

    @classmethod
    def getPASS(cls, password):
        return "PASS {password}".format(password=password) + EOL

    @classmethod
    def getNICK(cls, oldnick, nick):
        return "NICK {nick}{eol}".format(nick = nick, eol = EOL)

    @classmethod
    def getUSER(cls, nick):
        return "USER {username} {hostname} {servername} :{realname}".format(nick = nick,
                                                                            username=nick,
                                                                            hostname="none",
                                                                            servername="none",
                                                                            realname=nick) + EOL

    @classmethod
    def getPONG(cls, msg):
        return "PONG {msg}".format(msg=msg) + EOL

    @classmethod
    def getJOIN(cls, channel, key=None):
        if key:
            return "JOIN {channel}; {key}".format(channel=channel, key=key) + EOL
        else:
            return "JOIN {channel}".format(channel=channel) + EOL

    @classmethod
    def getNOTICE(cls, dest, msg):
        ret_val = ''
        for line in msg.split('\n'):
            if line and line.strip('\r') != '':
                ret_val += "NOTICE {dest} :{msg}".format(dest = dest, msg = line.strip('\r')) + EOL
        return ret_val

    @classmethod
    def getPRIVMSG(cls, dest, msg):
        ret_val = ''
        for line in msg.split('\n'):
            if line and line.strip('\r') != '':
                ret_val += "PRIVMSG {dest} :{msg}".format(dest = dest, msg = line.strip('\r')) + EOL
        return ret_val

    @classmethod
    def getCTCP(cls, msg):
        return "%s%s%s"%(CTCPTAG,msg,CTCPTAG)

    @classmethod
    def getWHOIS(cls, nick):
        return "WHOIS {nick}".format(nick = nick) + EOL

    @classmethod
    def getDCCCHAT(cls, dest, addr, port, use_ssl):
        if use_ssl:
            ctcpmsg = CmdGenerator.getCTCP("DCC SCHAT chat {addr} {port}".format(addr=CmdGenerator.conv_ip_std_long(addr), port=port))
        else:
            ctcpmsg = CmdGenerator.getCTCP("DCC CHAT chat {addr} {port}".format(addr=CmdGenerator.conv_ip_std_long(addr), port=port))
        privmsg = CmdGenerator.getPRIVMSG(dest, ctcpmsg)
        return privmsg

    @classmethod
    def conv_ip_long_std(cls, longip):
        try:
            ip = long(longip)
        except ValueError:
            return longip
        if ip >= 2 ** 32:
            return longip
        address = [str(ip >> shift & 0xFF) for shift in [24, 16, 8, 0]]
        return '.'.join(address)

    @classmethod
    def conv_ip_std_long(cls, stdip):
        address = stdip.split('.')
        if len(address) != 4:
            return 0
        longip = 0
        for part, shift in zip(address, [24, 16, 8, 0]):
            try:
                ip_part = int(part)
            except ValueError:
                return stdip
            if ip_part >= 2 ** 8:
                return stdip
            longip += ip_part << shift
        return longip

###########################################################################################################

class Color(object):
    colors = {
        '§B': '\x02',
        '§U': '\x1f',
        '§R': '\x16',
        '§N': '\x0f',
        '§C': '\x03',
    }

    @classmethod
    def doColors(cls, text):
        out_text = text
        for code, char in cls.colors.items():
            out_text = out_text.replace(code, char)
        return out_text

###########################################################################################################

def getDurationStr(timeint):
    formatstr = '%M:%S'
    if timeint >= 3600:
        formatstr = '%H:%M:%S'

    return time.strftime(formatstr, time.gmtime(timeint))

class CmdHandler(object):
    def __init__(self, bot, socket):
        self.bot     = bot
        self.socket  = socket
        self.sender  = ""
        self.cmd     = ""
        self.params  = []
        self.logger  = Logger.getLogger("%s-%s-%s"%(__name__, self.bot.nick, self.bot.host)+".CmdHandler", bot.lognormal, bot.logerrors)
        self.commands  = OrderedDict()
        self.callbacks = {}
        self.irccmds   = {
        'PING':   {'callback':self.onPING},
        'NOTICE': {'callback':self.onNOTICE},
        'PRIVMSG':{'callback':self.onPRIVMSG},
        'INVITE': {'callback':self.onINVITE},
        'JOIN':   {'callback':self.onJOIN},
        'PART':   {'callback':self.onPART},
        'MODE':   {'callback':self.onMODE},
        'KICK':   {'callback':self.onKICK},                                                
        'QUIT':   {'callback':self.onQUIT},              
        'KILL':   {'callback':self.onKILL},
        'NICK':   {'callback':self.onNICK},
        }

        self.rplcmds = {
        001 : {'name':'RPL_WELCOME',       'callback':self.onRPL_WELCOME},
        311 : {'name':'RPL_WHOISUSER',     'callback':self.onRPL_WHOISUSER},
        312 : {'name':'RPL_WHOISSERVER',   'callback':self.onRPL_WHOISSERVER},
        317 : {'name':'RPL_WHOISIDLE',     'callback':self.onRPL_WHOISIDLE},
        319 : {'name':'RPL_WHOISCHANNELS', 'callback':self.onRPL_WHOISCHANNELS},
        330 : {'name':'RPL_WHOISACCOUNT',  'callback':self.onRPL_WHOISACCOUNT},
        376 : {'name':'RPL_ENDOFMOTD',     'callback':self.onRPL_ENDOFMOTD},

        }

        self.monitor_thread = None
        self.last_event_time = time.time()
        self.next_event_check = time.time()
        if self.bot.monitorevents:
            self.monitorEvents()

    def monitorEvents(self):
        delta = time.time() - self.last_event_time
        if delta >= self.bot.monitortimeout:
            self.logger.warning('Event Monitor: time since last event (%s) exceeds timeout (%s).' % (getDurationStr(delta), getDurationStr(self.bot.monitortimeout)))
            self.bot.onShuttingDown()
        else:
            self.logger.debug('Event Monitor: time since last event: %s' % getDurationStr(delta))
            self.next_event_check = self.next_event_check + self.bot.monitorperiod
            self.monitor_thread = threading.Timer(self.next_event_check - time.time(), self.monitorEvents)
            self.monitor_thread.start()

    def registerCommand(self, command, callback, groups, minarg, maxarg, descargs = None, desccmd = None, showhelp = True):
        if not groups:
            groups = ['any']

        self.commands[command.lower()] = {'command':command.lower(), 'callback':callback, 'groups':groups, 'minarg':minarg, 'maxarg':maxarg, 'descargs':descargs, 'desccmd':desccmd, 'showhelp':showhelp}
        for group in groups:
            if not group in self.bot.groups:
                #self.bot.groups[group]= set()
                self.bot.groups[group] = {'commands':set()}
            self.bot.groups[group]['commands'].add(command.lower())

        self.bot.updateConfig()

    def registerEvent(self, event, callback):
        if not event in self.callbacks.keys():
            self.callbacks[event] = []
        self.callbacks[event].append(callback)

    def handleEvents(self, event, sender, params):
        self.last_event_time = time.time()
        if event in self.callbacks:
           for callback in self.callbacks[event]:
                cmdThread = threading.Thread(target=self.threadedEvent, name="%s:%s"%(sender.toString(),event), args=(event, callback, self.bot, sender, params))
                cmdThread.start()

    def threadedEvent(self, event, callback, bot, sender, params):
        try:    
            callback(bot, sender, params)
        except Exception as e:
            self.logger.error("Error while handling event [ %s ] with params %s from user [ %s ]"%(event, params, sender))
            self.logger.error("%s"%e)
            for line in traceback.format_exc().split('\n'):
                self.logger.error(line)            

    def parseCmd(self, msg):
        self.last_event_time = time.time()
        msg = msg.strip()

        if msg == "":
            return

        elems = msg.split()

        if elems[0][0] == ':':
            self.sender = Sender(elems[0])
            elems.pop(0)
        else:
            self.sender = Sender("")

        self.cmd = elems[0]

        if len(elems) > 1:
            self.params = elems[1:]

        try:
            cmd = int(self.cmd)
            self.onNUMERICAL(self.sender, cmd, self.params)
            return
        except Exception as e:
            pass

        if self.cmd in self.irccmds:
            try:
                self.irccmds[self.cmd]['callback'](self.sender, self.params)
            except Exception as e:
                self.logger.error("Error while handling command [ %s ] with params %s from user [ %s ]"%(self.cmd, self.params, self.sender))
                self.logger.error("%s"%e)
                for line in traceback.format_exc().split('\n'):
                    self.logger.error(line)                
        else:
            self.logger.debug("Unhandled Cmd > %s %s %s"%(self.sender, self.cmd, self.params))

    #######################################################
    #IRC Commands
    def onPING(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))
        self.bot.sendRaw(CmdGenerator.getPONG(params[0]))
        self.handleEvents('Ping', sender, params)

    def onNOTICE(self, sender, params):
        self.logger.info("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        

        #We received a notice from NickServ. We check if it is an ACC notice
        if sender.nick.lower() == self.bot.nickserv.lower():
            reMatch = re.match(self.bot.authRegex, " ".join(params[1:])[1:])
            if reMatch:
                #We check that the user exists in our tables, we setup the lvl value & unlock the command thread.
                if not reMatch.group('nick') in self.bot.users:
                    self.logger.error("Received unkown user auth level : %s %s"%(reMatch.group('nick'), reMatch.group('level')))
                else:
                    self.bot.users[reMatch.group('nick')].authenticate(int(reMatch.group('level')))
                    self.logger.info("Auth notice for %s with level %s"%(reMatch.group('nick'), reMatch.group('level')))

            reMatch = re.match(self.bot.nsmarker, " ".join(params[1:])[1:])
            if reMatch:
                self.bot.sendRaw(self.bot.nsreply.format(nickserv=self.bot.nickserv, nspass=self.bot.nspass) + EOL)

            reMatch = re.match(self.bot.nsidentify, " ".join(params[1:])[1:])
            if reMatch:
                for chan in self.bot.channels:
                    if not chan.strip() or not chan[0] == '#':
                        continue
                    self.bot.join(chan)

        dest = params[0]             #Chan or private dest
        msg  = ' '.join(params[1:])  #We stich the chat msg back together
        msg  = msg[1:]               #We remove the leading :

        if len(msg) == 0: return

        if msg[0] == CTCPTAG and msg[-1] == CTCPTAG:
            self.onCTCP(sender, dest, msg[1:-1].split())
        else:
            self.handleEvents('Notice', sender, params)

        

    def onINVITE(self, sender, params):
        self.logger.info("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))
        if self.bot.autoInvite:
            self.bot.join(params[1])
        self.handleEvents('Invite', sender, params)

    def onJOIN(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if sender.nick == self.bot.nick:
            self.logger.info("Adding chan %s to chan list"%(params[0]))
            if not params[0] in self.bot.channels:
                self.bot.channels.add(params[0])
                self.bot.updateConfig()


        self.handleEvents('Join', sender, params)

    def onPART(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if sender.nick == self.bot.nick:        
            self.logger.info("Removing chan %s from chan list"%(params[0]))
            self.bot.channels.remove(params[0])   
            self.bot.updateConfig()
        if sender.nick in self.bot.users:
            self.bot.users[sender.nick].unauthenticate()
            self.bot.users[sender.nick].whoisEvent.clear()            
        self.handleEvents('Part', sender, params)

    def onMODE(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        self.handleEvents('Mode', sender, params)

    def onKICK(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if params[1] == self.bot.nick:        
            self.logger.info("Removing chan %s from chan list"%(params[0]))
            self.bot.channels.remove(params[0])   
            self.bot.updateConfig()           
        if sender.nick in self.bot.users:
            self.bot.users[sender.nick].unauthenticate()                    
            self.bot.users[sender.nick].whoisEvent.clear()            
        self.handleEvents('Kick', sender, params)

    def onNICK(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if sender.nick in self.bot.users:
            self.bot.users[sender.nick].unauthenticate()                    
            self.bot.users[sender.nick].whoisEvent.clear()
        self.handleEvents('Nick', sender, params)

    def onQUIT(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        self.handleEvents('Quit', sender, params)

    def onKILL(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        self.handleEvents('Kill', sender, params)

    def onPRIVMSG(self, sender, params):
        dest = params[0]             #Chan or private dest
        msg  = ' '.join(params[1:])  #We stitch the chat msg back together
        msg  = msg.lstrip(':')       #We remove the leading :

        if len(msg) > 0 and (msg[0] == self.bot.cmdChar or dest == self.bot.nick):
            self.onCOMMAND(sender, dest, msg.lstrip(self.bot.cmdChar)) #We remove the cmd symbol before passing the cmd to the bot
        elif len(msg) > 0 and msg[0] == CTCPTAG and msg[-1] == CTCPTAG:
            self.onCTCP(sender, dest, msg[1:-1].split())
        else:
            self.logger.debug("%s %s"%(sender.nick, " ".join(params)))        
            self.handleEvents('Privmsg', sender, params)

    #######################################################
    # Numerical RPL handling
    def onNUMERICAL(self, sender, cmd, params):
        if int(cmd) in self.rplcmds.keys():
            self.rplcmds[cmd]['callback'](sender, params)
        else:
            self.logger.debug("%03d [S: %s] [M: %s]"%(cmd, sender.nick, " ".join(params)))
        self.handleEvents(int(cmd), sender, params)

    #RPL_001
    def onRPL_WELCOME(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        
        if self.bot.autoJoin and not self.bot.isReady:
            self.bot.isReady = True
            if not self.bot.nspass:
                for chan in self.bot.channels:
                    if not chan.strip() or not chan[0] == '#':
                        continue
                    self.bot.join(chan)

    #RPL_311
    def onRPL_WHOISUSER(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))
        
        nick = params[1]
        if nick in self.bot.usersInfo:
            self.bot.usersInfo[nick].ident = params[2]
            self.bot.usersInfo[nick].host  = params[3]
            self.bot.usersInfo[nick].whoisEvent.set()
            self.logger.debug("%s user added to user list with %s %s"%(nick, self.bot.usersInfo[nick].ident, self.bot.usersInfo[nick].host))        
        else:
            self.logger.error("%s not found in the user list"%nick)        
        
    #RPL_312
    def onRPL_WHOISSERVER(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))  

    #RPL_317
    def onRPL_WHOISIDLE(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))  

    #RPL_319
    def onRPL_WHOISCHANNELS(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))  
        
    #RPL_330
    def onRPL_WHOISACCOUNT(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))  
        if params[1] in self.bot.users:
            self.bot.users[params[1]].regnick = params[2]
            self.bot.users[params[1]].whoisEvent.set()

    #RPL_376
    def onRPL_ENDOFMOTD(self, sender, params):
        self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))

    #######################################################
    # User defined commands
    def onCOMMAND(self, sender, dest, command):
        self.logger.info("COMMAND> %s"%command)
        if command.strip() == "":
            return
        
        if not command.split()[0].lower() in self.commands.keys():
            return

        cmd  = self.commands[command.split()[0].lower()]
        args = command.split()[1:] if len(command.split()) > 1 else []
        callback = cmd['callback']

        if len(args) < cmd['minarg'] or len(args) > cmd['maxarg']:
            if cmd['descargs']:
                self.bot.sendNotice(sender.nick, "Wrong syntax : %s"%cmd['descargs'])
                return
            else:
                self.bot.sendNotice(sender.nick, "Wrong number of arguments : min = %s, max = %s"%(cmd['minarg'], cmd['maxarg']))
                return                

        #We already know this sender
        if sender.nick in self.bot.users and sender == self.bot.users[sender.nick]:
            self.logger.info("Found user %s in current users"%sender.nick)
            
            if -1 < self.bot.authtimeout < time.time() - self.bot.users[sender.nick].lastAuth:
                self.bot.users[sender.nick].unauthenticate()
            
            # If current auth is not 3, we retry to authenticate the account but resending the request and resetting the flags
            if self.bot.users[sender.nick].auth != 3:
                self.logger.info("Reauthenticating user %s"%sender.nick)
                self.bot.users[sender.nick].unauthenticate()
                self.bot.sendRaw(self.bot.nickAuth.format(nickserv=self.bot.nickserv, nick=sender.nick) + EOL)
                self.bot.sendRaw(CmdGenerator.getWHOIS(sender.nick))
            
            cmdThread = threading.Thread(target=self.threadedCommand, name=sender.toString(), args=(callback, cmd, self.bot, self.bot.users[sender.nick], dest, args))
            cmdThread.start()

        else:
            self.logger.info("Adding and authenticating user %s"%sender.nick)
            self.bot.users[sender.nick] = sender
            self.bot.sendRaw(self.bot.nickAuth.format(nickserv=self.bot.nickserv, nick=sender.nick) + EOL)
            self.bot.sendRaw(CmdGenerator.getWHOIS(sender.nick))
            
            cmdThread = threading.Thread(target=self.threadedCommand, name=sender.toString(), args=(callback, cmd, self.bot, self.bot.users[sender.nick], dest, args))
            cmdThread.start()
            
    def threadedCommand(self, callback, cmd, bot, sender, dest, args):
        try:
            #We request the AUTH level of the nick
            if not sender.authEvent.wait(10):
                bot.sendNotice(sender.nick, "Error contacting nickserv. Please retry later.")
                return

            #If we don't accept unregistered usage, we check for AUTH 3 and the WHOIS event
            if not bot.allowunregistered:
                if not sender.auth == 3:
                    bot.sendNotice(sender.nick, "You need to register your nick before using the bot.")
                    return                

            if sender.auth == 3:
                if not sender.whoisEvent.wait(10):
                    bot.sendNotice(sender.nick, "Error doing a whois. Please retry later.")
                    return
            
            #If we allow unregistered usage, we use the current nick as the registered nick for later on
            if sender.auth == 0 and bot.allowunregistered and not 'AnonUser_' in sender.nick :
                sender.regnick = sender.nick
                bot.sendNotice(sender.nick, "You should really register your nick ! Try '/msg nickserv help' to see how to do it.")

            #If we allow unregistered usage, we use the current nick as the registered nick for later on
            if sender.auth == 0 and bot.dccAllowAnon and 'AnonUser_' in sender.nick :
                sender.regnick = sender.nick
            
            #If the AUTH is not 0 (unregistered) or 3 (authenticated), it means we have a weird account, we return
            if not sender.auth in [0,3]:
                bot.sendNotice(sender.nick, "You are not properly identified")
                return

            userValid = False

            if (sender.nick.lower()    in bot.banList and cmd['command'] in bot.banList[sender.nick.lower()]) or \
               (sender.host.lower()    in bot.banList and cmd['command'] in bot.banList[sender.host.lower()]) or \
               (sender.regnick.lower() in bot.banList and cmd['command'] in bot.banList[sender.regnick.lower()]):
                bot.sendNotice(sender.nick, "You are prevented from using this command.")
                return

            if cmd['command']  in bot.groups['any']['commands']:
                userValid = True

            else:
                for group, data in bot.groups.items():
                    if cmd['command'].lower() in data['commands'] and sender.regnick.lower() in bot.authUsers:
                        if group in bot.authUsers[sender.regnick.lower()]:
                            userValid = True

            # giving admins the right to run ANY command is probably not a good idea...
            # if sender.regnick.lower() in bot.authUsers and 'admin' in bot.authUsers[sender.regnick.lower()]:
            #     userValid = True

            if userValid:
                callback(bot, sender, dest, cmd, args)
            else:
                self.logger.info("User %s with regnick %s and auth %s tried to use command %s : No enough privileges"%(sender.nick, sender.regnick, sender.auth, cmd))
                bot.sendNotice(sender.regnick, "You don't have the right to run this command")

        except Exception as e:
            self.logger.error("Error while handling command [ %s ] from user [ %s ] to [ %s ] with args [ %s ]"%(cmd, sender, dest, args))
            self.logger.error("%s"%e)
            for line in traceback.format_exc().split('\n'):
                self.logger.error(line)


    #######################################################
    # CTCP Commands
    def onCTCP(self, sender, dest, msg):
        #self.logger.debug("[S : %s] [M : %s]"%(sender.nick, " ".join(params)))        

        if msg[0] == 'VERSION':
            self.bot.sendRaw(CmdGenerator.getNOTICE(sender.nick, "MCPBot v4.0 'You were not expecting me !' by ProfMobius"))
            self.handleEvents('Version', sender, msg)

        elif msg[0] == 'USERINFO':
            self.bot.sendRaw(CmdGenerator.getNOTICE(sender.nick, "MCPBot v4.0 'You were not expecting me !' by ProfMobius"))
            self.handleEvents('Userinfo', sender, msg)            

        elif msg[0] == 'FINGER':
            self.bot.sendRaw(CmdGenerator.getNOTICE(sender.nick, "Don't do that !"))
            self.handleEvents('Finger', sender, msg)            

        elif msg[0] == 'DCC':
            if self.bot.dccActive:
                self.onDCC(sender, dest, msg)

        elif msg[0] == 'TIME' and len(msg) > 1:
            self.bot.usersInfo[sender.nick].ctcpData['TIME'] = ' '.join(msg[1:])
            self.bot.usersInfo[sender.nick].ctcpEvent['TIME'].set()

        else:
            self.handleEvents('CTCP', sender, msg)

    #######################################################
    # DCC Commands
    def onDCC(self, sender, dest, msg):
        self.logger.info("%s %s %s"%(sender, msg, CmdGenerator.conv_ip_long_std(msg[3])))
        self.bot.sendRaw(CmdGenerator.getNOTICE(sender.nick, "Don't call me, I will call you."))
        host, port = self.bot.dccSocket.getAddr()
        self.bot.dccSocket.addPending(sender)
        self.bot.sendRaw(CmdGenerator.getDCCCHAT(sender.nick, host, port))
        self.handleEvents('DCC', sender, msg)


# UNIMPLEMENTED COMMANDS :
# PASSWORD
# SERVER
# OPER
# SQUIT
# TOPIC
# NAMES
# LIST
# VERSION
# STATS
# LINKS
# TIME
# CONNECT
# TRACE
# ADMIN
# INFO
# WHO
# WHOIS
# WHOWAS
# ERROR
