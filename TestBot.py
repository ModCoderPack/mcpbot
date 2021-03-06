import BotBase
from IRCHandler import CmdGenerator

def sendBastard(bot, sender, params):
    bot.sendNotice(sender.nick, "You bastard !")

def sayHello(bot, sender, params):
    if sender.nick != bot.nick:
        bot.sendMessage(params[0], "Hi %s o/"%sender.nick)

def sayHello2(bot, sender, dest, cmd, args):
    if sender.nick != bot.nick:
        bot.sendNotice(sender.nick, "Hi %s o/"%sender.nick)        

def whois(bot, sender, dest, cmd, args):
    bot.sendRaw(CmdGenerator.getWHOIS(args[0]))

botBase = BotBase.BotBase()
botBase.registerEventKick(sendBastard)
#bot.registerEventJoin(sayHello)
botBase.registerCommand('test', sayHello2, None, 0, 0, None)
botBase.registerCommand('whois', whois, None, 1, 1, None)
botBase.run()
