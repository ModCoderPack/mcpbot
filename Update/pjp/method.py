from .constantpool import NameAndType
from .accessflags import MethodAccessFlags
from .descriptor import MethodDescriptor


__all__ = ['Method']


class Method(object):
    def __init__(self, name, descriptor, access_flags=None):
        self.name = name
        self.descriptor = MethodDescriptor(descriptor)
        self.access_flags = MethodAccessFlags(access_flags)

    @property
    def key(self):
        return NameAndType(self.name, self.descriptor)

    def __str__(self):
        result = ''
        if str(self.access_flags):
            result += str(self.access_flags) + ' '
        if self.descriptor.full_return:
            result += self.descriptor.full_return + ' '
        result += self.name + '(' + ', '.join(self.descriptor.full_arguments) + ')'
        return result
