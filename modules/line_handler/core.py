import codecs, re

RE_ISUPPORT_ESCAPE = re.compile(r"\\x(\d\d)", re.I)
RE_MODES = re.compile(r"[-+]\w+")

def ping(event):
    event["server"].send_pong(event["args"][0])

def handle_001(event):
    event["server"].socket.enable_write_throttle()
    event["server"].name = event["source"].hostmask
    event["server"].set_own_nickname(event["args"][0])
    event["server"].send_whois(event["server"].nickname)
    event["server"].send_mode(event["server"].nickname)
    event["server"].connected = True

def handle_005(events, event):
    isupport_list = event["args"][1:-1]
    isupport = {}

    for i, item in enumerate(isupport_list):
        key, sep, value = item.partition("=")
        if value:
            for match in RE_ISUPPORT_ESCAPE.finditer(value):
                char = codecs.decode(match.group(1), "hex").decode("ascii")
                value.replace(match.group(0), char)

        if sep:
            isupport[key] = value
        else:
            isupport[key] = None
    event["server"].isupport.update(isupport)

    if "NAMESX" in isupport and not event["server"].has_capability_str(
            "multi-prefix"):
        event["server"].send("PROTOCTL NAMESX")

    if "PREFIX" in isupport:
        modes, symbols = isupport["PREFIX"][1:].split(")", 1)
        event["server"].prefix_symbols.clear()
        event["server"].prefix_modes.clear()
        for symbol, mode in zip(symbols, modes):
            event["server"].prefix_symbols[symbol] = mode
            event["server"].prefix_modes[mode] = symbol

    if "CHANMODES" in isupport:
        modes = isupport["CHANMODES"].split(",", 3)
        event["server"].channel_list_modes = list(modes[0])
        event["server"].channel_paramatered_modes = list(modes[1])
        event["server"].channel_setting_modes = list(modes[2])
        event["server"].channel_modes = list(modes[3])
    if "CHANTYPES" in isupport:
        event["server"].channel_types = list(isupport["CHANTYPES"])
    if "CASEMAPPING" in isupport:
        event["server"].case_mapping = isupport["CASEMAPPING"]
    if "STATUSMSG" in isupport:
        event["server"].statusmsg = list(isupport["STATUSMSG"])

    events.on("received.005").call(isupport=isupport,
        server=event["server"])

def handle_004(event):
    event["server"].version = event["args"][2]

def motd_start(event):
    event["server"].motd_lines.clear()
def motd_line(event):
    event["server"].motd_lines.append(event["args"][1])

def _own_modes(server, modes):
    mode_chunks = RE_MODES.findall(modes)
    for chunk in mode_chunks:
        remove = chunk[0] == "-"
        for mode in chunk[1:]:
            server.change_own_mode(remove, mode)

def mode(events, event):
    user = event["server"].get_user(event["source"].nickname)
    target = event["args"][0]
    is_channel = target[0] in event["server"].channel_types
    if is_channel:
        channel = event["server"].channels.get(target)
        modes = event["args"][1]
        args  = event["args"][2:]

        channel.parse_modes(modes, args[:])

        events.on("received.mode.channel").call(modes=modes, mode_args=args,
            channel=channel, server=event["server"], user=user)
    elif event["server"].is_own_nickname(target):
        modes = event["args"][1]
        _own_modes(event["server"], modes)

        events.on("self.mode").call(modes=modes, server=event["server"])
        event["server"].send_who(event["server"].nickname)

def handle_221(event):
    _own_modes(event["server"], event["args"][1])

def invite(events, event):
    target_channel = event["args"][1]
    user = event["server"].get_user(event["source"].nickname)
    target_user = event["server"].get_user(event["args"][0])
    events.on("received.invite").call(user=user, target_channel=target_channel,
        server=event["server"], target_user=target_user)

def handle_352(event):
    nickname = event["args"][5]
    username = event["args"][2]
    hostname = event["args"][3]

    if event["server"].is_own_nickname(nickname):
        event["server"].username = username
        event["server"].hostname = hostname

    target = event["server"].get_user(nickname)
    target.username = username
    target.hostname = hostname

def handle_354(event):
    if event["args"][1] == "111":
        nickname = event["args"][4]
        username = event["args"][2]
        hostname = event["args"][3]
        realname = event["args"][6]
        account = event["args"][5]

        if event["server"].is_own_nickname(nickname):
            event["server"].username = username
            event["server"].hostname = hostname
            event["server"].realname = realname

        target = event["server"].get_user(nickname)
        target.username = username
        target.hostname = hostname
        target.realname = realname
        if not account == "0":
            target.identified_account = account
        else:
            target.identified_account = None

def handle_433(event):
    new_nick = "%s|" % event["server"].connection_params.nickname
    event["server"].send_nick(new_nick)
