from .constantpool import NameAndType
from .accessflags import FieldAccessFlags
from .descriptor import FieldDescriptor


__all__ = ['Field']


class Field(object):
    def __init__(self, name, descriptor, access_flags=None):
        self.name = name
        self.descriptor = FieldDescriptor(descriptor)
        self.access_flags = FieldAccessFlags(access_flags)

    @property
    def key(self):
        return NameAndType(self.name, self.descriptor)

    def __str__(self):
        result = ''
        if str(self.access_flags):
            result += str(self.access_flags) + ' '
        if self.descriptor.full_descriptor:
            result += self.descriptor.full_descriptor + ' '
        result += self.name
        return result
