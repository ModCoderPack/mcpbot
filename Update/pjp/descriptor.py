from collections import namedtuple


__all__ = ['MethodDescriptor', 'FieldDescriptor']


class Error(Exception):
    pass


class DescriptorError(Error):
    pass


_METHOD_DESCRIPTOR = namedtuple('MethodDescriptor', ['descriptor'])


class MethodDescriptor(_METHOD_DESCRIPTOR):
    def __new__(cls, descriptor):
        if descriptor[0] != '(':
            raise DescriptorError('no opening bracket')
        end_arguments = descriptor.rfind(')')
        if end_arguments == -1:
            raise DescriptorError('no terminating bracket')
        arguments = descriptor[1:end_arguments]
        return_ = descriptor[end_arguments + 1:]
        if not return_:
            raise DescriptorError('no return type')
        split_descriptor(arguments)
        split_descriptor(return_)
        return _METHOD_DESCRIPTOR.__new__(cls, descriptor)

    def __init__(self, descriptor):
        _METHOD_DESCRIPTOR.__init__(self, descriptor)
        end_arguments = self.descriptor.rfind(')')
        self.arguments = self.descriptor[1:end_arguments]
        self.return_ = self.descriptor[end_arguments + 1:]
        self.full_arguments = split_descriptor(self.arguments)
        self.full_return = split_descriptor(self.return_)[0]

    def __repr__(self):
        return "MethodDescriptor('%s')" % self.descriptor

    def __str__(self):
        return '%s(%s)' % (self.full_return, ', '.join(self.full_arguments))

    @property
    def value(self):
        return self.descriptor


_FIELD_DESCRIPTOR = namedtuple('FieldDescriptor', ['descriptor'])


class FieldDescriptor(_FIELD_DESCRIPTOR):
    def __new__(cls, descriptor):
        split_descriptor(descriptor)
        return _FIELD_DESCRIPTOR.__new__(cls, descriptor)

    def __init__(self, descriptor):
        _FIELD_DESCRIPTOR.__init__(self, descriptor)
        self.full_descriptor = split_descriptor(self.descriptor)[0]

    def __repr__(self):
        return "FieldDescriptor('%s')" % self.descriptor

    def __str__(self):
        return self.full_descriptor

    @property
    def value(self):
        return self.descriptor


def split_descriptor(descriptor):
    ret = []
    suffix = ''
    pos = 0
    while pos < len(descriptor):
        cur = descriptor[pos]
        if cur == '[':
            suffix += '[]'
        else:
            if cur == 'L':
                class_end = descriptor.find(';', pos)
                if class_end == -1:
                    raise DescriptorError('no terminating semicolon')
                ret.append(descriptor[pos + 1:class_end].replace('/', '.'))
                pos = class_end - 1
            elif cur == 'B':
                ret.append('byte')
            elif cur == 'C':
                ret.append('char')
            elif cur == 'D':
                ret.append('double')
            elif cur == 'F':
                ret.append('float')
            elif cur == 'I':
                ret.append('int')
            elif cur == 'J':
                ret.append('long')
            elif cur == 'S':
                ret.append('short')
            elif cur == 'Z':
                ret.append("boolean")
            elif cur == 'V':
                ret.append('void')
            if suffix:
                ret[-1] += suffix
                suffix = ''
        pos += 1
    return tuple(ret)
