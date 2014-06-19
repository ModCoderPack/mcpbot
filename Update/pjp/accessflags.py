from collections import namedtuple


__all__ = ['ClassAccessFlags', 'InnerClassAccessFlags', 'FieldAccessFlags', 'MethodAccessFlags']


class Error(Exception):
    pass


class AccessFlagsError(Error):
    pass


_ACCESS_FLAGS = namedtuple('AccessFlags', ['access_flags'])

_ALL_ACCESS_FLAGS = {
    'public': 0x0001,
    'private': 0x0002,
    'protected': 0x0004,
    'static': 0x0008,
    'final': 0x0010,
    'super': 0x0020,
    'syncronised': 0x0020,
    'volatile': 0x0040,
    'bridge': 0x0040,
    'transient': 0x0080,
    'varargs': 0x0080,
    'native': 0x0100,
    'interface': 0x0200,
    'abstract': 0x0400,
    'strictfp': 0x0800,
    'synthetic': 0x1000,
    'annotation': 0x2000,
    'enum': 0x4000,
}


class AccessFlags(_ACCESS_FLAGS):
    _allowed_flags = []
    _access_level_mask = _ALL_ACCESS_FLAGS['public'] | _ALL_ACCESS_FLAGS['private'] | _ALL_ACCESS_FLAGS['protected']

    def __new__(cls, access_flags=None):
        if access_flags is None:
            access_flags = 0
        cls.allowed_mask = reduce(lambda x, y: x | _ALL_ACCESS_FLAGS[y], cls._allowed_flags, 0)
        unknown_flags = access_flags & ~cls.allowed_mask
        if unknown_flags:
            raise AccessFlagsError("unknown flags %d in '%s'" % (unknown_flags, cls.__name__))
        return _ACCESS_FLAGS.__new__(cls, access_flags)

    def __init__(self, access_flags=None):
        self.is_none = access_flags is None

    def __eq__(self, other):
        if self.is_none:
            return False
        try:
            if other.is_none:
                return False
            return self.access_flags == other.access_flags
        except AttributeError:
            return self.access_flags == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.access_flags)

    def __repr__(self):
        access_flags = self.access_flags
        if self.is_none:
            access_flags = None
        return "%s(%s)" % (type(self).__name__, access_flags)

    def __str__(self):
        return ' '.join([flag for flag in self._allowed_flags if self.access_flags & _ALL_ACCESS_FLAGS[flag]])

    def __getattr__(self, name):
        if name.startswith('is_'):
            flag_name = name[3:]
            if flag_name in _ALL_ACCESS_FLAGS:
                if flag_name not in self._allowed_flags:
                    raise AccessFlagsError("'%s' not in '%s'" % (flag_name, type(self).__name__))
                return bool(self.access_flags & _ALL_ACCESS_FLAGS[flag_name])
        raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, name))

    @property
    def access_level(self):
        return self.access_flags & self._access_level_mask

    @property
    def value(self):
        return self.access_flags


class ClassAccessFlags(AccessFlags):
    _allowed_flags = ['public', 'final', 'super', 'interface', 'abstract', 'synthetic', 'annotation', 'enum']


class InnerClassAccessFlags(AccessFlags):
    _allowed_flags = ['public', 'private', 'protected', 'static', 'final', 'super', 'interface', 'abstract',
                      'synthetic', 'annotation', 'enum']


class FieldAccessFlags(AccessFlags):
    _allowed_flags = ['public', 'private', 'protected', 'static', 'final', 'volatile', 'transient', 'synthetic',
                      'enum']


class MethodAccessFlags(AccessFlags):
    _allowed_flags = ['public', 'private', 'protected', 'static', 'final', 'syncronised', 'bridge', 'varargs',
                      'native', 'abstract', 'strictfp', 'synthetic']
