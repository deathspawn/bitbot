import json, string, re, typing
from src import utils

ASCII_UPPER = string.ascii_uppercase
ASCII_LOWER = string.ascii_lowercase
STRICT_RFC1459_UPPER = ASCII_UPPER+r'\[]'
STRICT_RFC1459_LOWER = ASCII_LOWER+r'|{}'
RFC1459_UPPER = STRICT_RFC1459_UPPER+"^"
RFC1459_LOWER = STRICT_RFC1459_LOWER+"~"

# case mapping lowercase/uppcase logic
def _multi_replace(s: str,
        chars1: typing.Iterable[str],
        chars2: typing.Iterable[str]) -> str:
    for char1, char2 in zip(chars1, chars2):
        s = s.replace(char1, char2)
    return s
def lower(case_mapping: str, s: str) -> str:
    if case_mapping == "ascii":
        return _multi_replace(s, ASCII_UPPER, ASCII_LOWER)
    elif case_mapping == "rfc1459":
        return _multi_replace(s, RFC1459_UPPER, RFC1459_LOWER)
    elif case_mapping == "strict-rfc1459":
        return _multi_replace(s, STRICT_RFC1459_UPPER, STRICT_RFC1459_LOWER)
    else:
        raise ValueError("unknown casemapping '%s'" % case_mapping)

# compare a string while respecting case mapping
def equals(case_mapping: str, s1: str, s2: str) -> bool:
    return lower(case_mapping, s1) == lower(case_mapping, s2)

class IRCHostmask(object):
    def __init__(self, nickname: str, username: str, hostname: str,
            hostmask: str):
        self.nickname = nickname
        self.username = username
        self.hostname = hostname
        self.hostmask = hostmask
    def __repr__(self):
        return "IRCHostmask(%s)" % self.__str__()
    def __str__(self):
        return self.hostmask

def seperate_hostmask(hostmask: str) -> IRCHostmask:
    nickname, _, username = hostmask.partition("!")
    username, _, hostname = username.partition("@")
    return IRCHostmask(nickname, username, hostname, hostmask)

class IRCArgs(object):
    def __init__(self, args: typing.List[str]):
        self._args = args

    def get(self, index: int) -> typing.Optional[str]:
        if len(self._args) > index:
            return self._args[index]
        return None

    def __repr__(self):
        return "IRCArgs(%s)" % self._args
    def __len__(self) -> int:
        return len(self._args)
    def __getitem__(self, index) -> str:
        return self._args[index]


class IRCLine(object):
    def __init__(self, tags: dict, prefix: typing.Optional[str], command: str,
            args: IRCArgs, has_arbitrary: bool):
        self.tags = tags
        self.prefix = prefix
        self.command = command
        self.args = args
        self.has_arbitrary = has_arbitrary

MESSAGE_TAG_ESCAPED = [r"\:", r"\s", r"\\", r"\r", r"\n"]
MESSAGE_TAG_UNESCAPED = [";", " ", "\\", "\r", "\n"]
def message_tag_escape(s):
    return _multi_replace(s, MESSAGE_TAG_UNESCAPED, MESSAGE_TAG_ESCAPED)
def message_tag_unescape(s):
    return _multi_replace(s, MESSAGE_TAG_ESCAPED, MESSAGE_TAG_UNESCAPED)

def parse_line(line: str) -> IRCLine:
    tags = {}
    prefix = typing.Optional[IRCHostmask]
    command = None

    if line[0] == "@":
        tags_prefix, line = line[1:].split(" ", 1)

        if tags_prefix[0] == "{":
            tags_prefix = message_tag_unescape(tags_prefix)
            tags = json.loads(tags_prefix)
        else:
            for tag in filter(None, tags_prefix.split(";")):
                tag, sep, value = tag.partition("=")
                if sep:
                    tags[tag] = message_tag_unescape(value)
                else:
                    tags[tag] = None

    line, arb_sep, arbitrary_split = line.partition(" :")
    has_arbitrary = bool(arb_sep)
    arbitrary = None # type: typing.Optional[str]
    if has_arbitrary:
        arbitrary = arbitrary_split

    if line[0] == ":":
        prefix_str, line = line[1:].split(" ", 1)
        prefix = seperate_hostmask(prefix_str)

    args = []
    command, sep, line = line.partition(" ")
    if sep:
        args = line.split(" ")

    if arbitrary:
        args.append(arbitrary)

    return IRCLine(tags, prefix, command, IRCArgs(args), has_arbitrary)


REGEX_COLOR = re.compile("%s(?:(\d{1,2})(?:,(\d{1,2}))?)?" % utils.consts.COLOR)

def color(s: str, foreground: utils.consts.IRCColor,
        background: utils.consts.IRCColor=None) -> str:
    foreground_s = str(foreground.irc).zfill(2)
    background_s = ""
    if background:
        background_s = ",%s" % str(background.irc).zfill(2)

    return "%s%s%s%s%s" % (utils.consts.COLOR, foreground_s, background_s, s,
        utils.consts.COLOR)

def bold(s: str) -> str:
    return "%s%s%s" % (utils.consts.BOLD, s, utils.consts.BOLD)

def underline(s: str) -> str:
    return "%s%s%s" % (utils.consts.UNDERLINE, s, utils.consts.UNDERLINE)

def strip_font(s: str) -> str:
    s = s.replace(utils.consts.BOLD, "")
    s = s.replace(utils.consts.ITALIC, "")
    s = REGEX_COLOR.sub("", s)
    s = s.replace(utils.consts.COLOR, "")
    return s

FORMAT_TOKENS = [
    utils.consts.BOLD,
    utils.consts.RESET
]
def _color_tokens(s: str) -> typing.List[str]:
    is_color = False
    foreground = ""
    background = ""
    matches = [] # type: typing.List[str]

    for char in s:
        if is_color:
            if char.isdigit():
                if background:
                    background += char
                else:
                    foreground += char
                continue
            elif char == ",":
                background += char
                continue
            else:
                matches.append("\x03%s%s" % (foreground, background))
                is_color = False
                foreground = ""
                background = ""

        if char == utils.consts.COLOR:
            if is_color:
                matches.append(char)
            else:
                is_color = True
        elif char in FORMAT_TOKENS:
            matches.append(char)
    return matches

def to_ansi_colors(s: str) -> str:
    color = False
    color_bold = False
    bold = False

    for token in _color_tokens(s):
        replace = ""
        type = token[0]

        if type == utils.consts.COLOR:
            match = REGEX_COLOR.match(token)
            foreground_match = match.group(1)
            if foreground_match:
                code = int(foreground_match.lstrip("0") or "0")
                foreground = utils.consts.COLOR_CODES[code]

                if color_bold and not foreground.color_bold and not bold:
                    color_bold = False
                    replace += utils.consts.ANSI_BOLD_RESET

                color = True
                foreground_s = str(foreground.ansi).zfill(2)
                if foreground.color_bold:
                    color_bold = True
                    foreground_s = "%s;1" % foreground_s
                replace += utils.consts.ANSI_FORMAT % foreground_s
            else:
                if color:
                    replace += utils.consts.ANSI_COLOR_RESET
                    if color_bold and not bold:
                        replace += utils.consts.ANSI_BOLD_RESET
                color = False
                color_bold = False
        elif type == utils.consts.BOLD:
            if bold:
                if not color_bold:
                    replace += utils.consts.ANSI_BOLD_RESET
            else:
                replace += utils.consts.ANSI_BOLD
            bold = not bold
        elif type == utils.consts.RESET:
            replace += utils.consts.ANSI_RESET

        s = s.replace(token, replace, 1)

    return s + utils.consts.ANSI_RESET

OPT_STR = typing.Optional[str]
class IRCConnectionParameters(object):
    def __init__(self, id: int, alias: OPT_STR, hostname: str, port: int,
            password: OPT_STR, tls: bool, ipv4: bool, bindhost: OPT_STR,
            nickname: str, username: OPT_STR, realname: OPT_STR,
            args: typing.Dict[str, str]={}):
        self.id = id
        self.alias = alias
        self.hostname = hostname
        self.port = port
        self.tls = tls
        self.ipv4 = ipv4
        self.bindhost = bindhost
        self.password = password
        self.nickname = nickname
        self.username = username
        self.realname = realname
        self.args = args

class CTCPMessage(object):
    def __init__(self, command: str, message: str):
        self.command = command
        self.message = message
def parse_ctcp(s: str) -> typing.Optional[CTCPMessage]:
    ctcp = s.startswith("\x01")
    if s.startswith("\x01"):
        ctcp_command, sep, ctcp_message = s[1:].partition(" ")
        if message.endswith("\x01"):
            message = message[:-1]
        return CTCPMessage(ctcp_command, ctcp_message)

    return None
