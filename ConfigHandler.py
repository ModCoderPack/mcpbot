from ConfigParser import RawConfigParser, DEFAULTSECT, NoSectionError, NoOptionError

try:
    from collections import OrderedDict as _default_dict
except ImportError:
    # fallback for setup.py which hasn't yet built _collections
    _default_dict = dict

class AdvConfigParser(RawConfigParser):

    def __init__(self, defaults=None, dict_type=_default_dict, allow_no_value=False):
        RawConfigParser.__init__(self, defaults=defaults, dict_type=dict_type, allow_no_value=allow_no_value)
        self._comments = self._dict()

    def add_section(self, section):
        if not section in self._comments:
            self._comments[section] = self._dict()

        if not section in self._sections:
            RawConfigParser.add_section(self, section)

    def set(self, section, option, value=None, comment=None):
        if not section in self._sections or not section in self._comments:
            self.add_section(section)

        RawConfigParser.set(self, section, option, value)
        self._comments[section][self.optionxform(option)] = comment

    def setcomment(self, section, option, comment):
        if not section in self._sections or not section in self._comments:
            self.add_section(section)
        self._comments[section][self.optionxform(option)] = comment

    def get(self, section, option, default=None, comment=None):
        self.add_section(section)

        if not self.has_option(section, option):
            self.set(section, option, default, comment)

        self.setcomment(section, option, comment)

        return RawConfigParser.get(self, section, option)

    def options(self, section):
        self.add_section(section)
        return RawConfigParser.options(self, section)

    def _get(self, section, conv, option, default=None, comment=None):
        return conv(self.get(section, option, default, comment))

    def geti(self, section, option, default=None, comment=None):
        return self._get(section, int, option, default, comment)

    def getf(self, section, option, default=None, comment=None):
        return self._get(section, float, option, default, comment)

    def getb(self, section, option, default=None, comment=None):
        return self._get(section, bool, option, default, comment)

    def write(self, fp):
        """Write an .ini-format representation of the configuration state."""
        if self._defaults:
            fp.write("[%s]\n" % DEFAULTSECT)
            for (key, value) in self._defaults.items():
                fp.write("%s = %s\n" % (key, str(value).replace('\n', '\n\t')))
            fp.write("\n")
        for section in self._sections:
            fp.write("[%s]\n" % section)
            for (key, value) in self._sections[section].items():
                option = key

                if key == "__name__":
                    continue
                if (value is not None) or (self._optcre == self.OPTCRE):
                    key = " = ".join((key, str(value).replace('\n', '\n\t')))

                if section in self._comments and option in self._comments[section] and self._comments[section][option]:
                    fp.write("#%s\n" % (self._comments[section][option]))

                fp.write("%s\n" % (key))
            fp.write("\n")