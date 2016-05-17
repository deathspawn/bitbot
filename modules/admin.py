

class Module(object):
    def __init__(self, bot):
        self.bot = bot
        bot.events.on("received").on("command").on("changenickname"
            ).hook(self.change_nickname, permission="changenickname",
            min_args=1, help="Change my nickname", usage="<nickname>")
        bot.events.on("received").on("command").on("raw"
            ).hook(self.raw, permission="raw", min_args=1,
            help="Send a raw IRC line through the bot",
            usage="<raw line>")

    def change_nickname(self, event):
        nickname = event["args_split"][0]
        event["server"].send_nick(nickname)

    def raw(self, event):
        event["server"].send(event["args"])
