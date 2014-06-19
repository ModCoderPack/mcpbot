from collections import namedtuple


__all__ = ['ConstantPool', 'ConstantType', 'ConstantRefError', 'NameAndType', 'NameAndSignature', 'EntryRef']

_NAME_AND_TYPE = namedtuple('NameAndType', ['name', 'descriptor'])
_NAME_AND_SIGNATURE = namedtuple('NameAndSignature', ['name', 'descriptor'])
_ENTRY_REF = namedtuple('EntryRef', ['class_', 'name_and_type'])


# pylint: disable-msg=W0232

class NameAndType(_NAME_AND_TYPE):
    def __str__(self):
        return '%s:%s' % (self.name, self.descriptor)


class NameAndSignature(_NAME_AND_SIGNATURE):
    def __str__(self):
        return '%s:%s' % (self.name, self.descriptor)


class EntryRef(_ENTRY_REF):
    def __str__(self):
        return '%s.%s' % (self.class_, self.name_and_type)


class Error(Exception):
    pass


class ConstantRefError(Error):
    """Invalid constant pool reference"""
    pass


class ConstantType(object):
    DUMMY = 0
    UTF8 = 1
    INTEGER = 3
    FLOAT = 4
    LONG = 5
    DOUBLE = 6
    CLASS = 7
    STRING = 8
    FIELD_REF = 9
    METHOD_REF = 10
    INTERFACE_METHOD_REF = 11
    NAME_AND_TYPE = 12
    METHOD_HANDLE = 15
    METHOD_TYPE = 16
    INVOKE_DYNAMIC = 18


class ConstantPool(list):
    def __init__(self, parent):
        list.__init__(self)
        self._parent = parent
        self.read_data = parent.read_data

        constant_pool_count, = self.read_data('>H')
        # pool is indexed from 1 so add a placeholder
        entry = ConstantDummy(self)
        self.append(entry)
        for _ in range(constant_pool_count - 1):
            # if previous entry was a long or double add a placeholder, relies on the initial placeholder
            # above to init entry
            if entry.wide_entry:
                entry = ConstantDummy(self)
            else:
                tag, = self.read_data('>B')
                entry = _CONSTANT_TYPE[tag][0](self)
            self.append(entry)

    def ref(self, index, types=None):
        try:
            if types is not None:
                if self[index].tag not in types:
                    types_str = ','.join([_CONSTANT_TYPE[t][1] for t in types])
                    raise ConstantRefError("'%s' not in [%s]" % (self[index].tag_type, types_str))
            return self[index].value
        except IndexError:
            raise ConstantRefError('invalid constant index')

    def tag(self, index):
        try:
            return self[index].tag
        except IndexError:
            raise ConstantRefError('invalid constant index')


class ConstantBase(object):
    tag = None
    wide_entry = False
    name = None
    descriptor = None
    value = None

    def __init__(self, parent):
        self._parent = parent
        self.constant_pool = parent
        self.read_data = parent.read_data

    @property
    def tag_type(self):
        return _CONSTANT_TYPE[self.tag][1]

    def __str__(self):
        return '%s(%s)' % (self.tag_type, self.value)


class ConstantDummy(ConstantBase):
    tag = ConstantType.DUMMY


class ConstantUTF8(ConstantBase):
    tag = ConstantType.UTF8

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        length, = self.read_data('>H')
        self.value, = self.read_data('>%ss' % length)


class ConstantInteger(ConstantBase):
    tag = ConstantType.INTEGER

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self.value, = self.read_data('>i')


class ConstantFloat(ConstantBase):
    tag = ConstantType.FLOAT

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self.value, = self.read_data('>f')


class ConstantLong(ConstantBase):
    tag = ConstantType.LONG
    wide_entry = True

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self.value, = self.read_data('>q')


class ConstantDouble(ConstantBase):
    tag = ConstantType.DOUBLE
    wide_entry = True

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self.value, = self.read_data('>d')


class ConstantClass(ConstantBase):
    tag = ConstantType.CLASS

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self._name_index, = self.read_data('>H')

    @property
    def name(self):
        return self.constant_pool.ref(self._name_index, [ConstantType.UTF8])

    @property
    def value(self):
        return self.name


class ConstantString(ConstantBase):
    tag = ConstantType.STRING

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self._string_index, = self.read_data('>H')

    @property
    def string(self):
        return self.constant_pool.ref(self._string_index, [ConstantType.UTF8])

    @property
    def value(self):
        return self.string


class ConstantBaseRef(ConstantBase):
    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self._class_index, self._name_and_type_index = self.read_data('>2H')

    @property
    def class_(self):
        return self.constant_pool.ref(self._class_index, [ConstantType.CLASS])

    @property
    def name_and_type(self):
        return self.constant_pool.ref(self._name_and_type_index, [ConstantType.NAME_AND_TYPE])

    @property
    def value(self):
        return EntryRef(self.class_, self.name_and_type)


class ConstantFieldRef(ConstantBaseRef):
    tag = ConstantType.FIELD_REF


class ConstantMethodRef(ConstantBaseRef):
    tag = ConstantType.METHOD_REF


class ConstantInterfaceMethodRef(ConstantBaseRef):
    tag = ConstantType.INTERFACE_METHOD_REF


class ConstantNameAndType(ConstantBase):
    tag = ConstantType.NAME_AND_TYPE

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self._name_index, self._descriptor_index = self.read_data('>2H')

    @property
    def name(self):
        return self.constant_pool.ref(self._name_index, [ConstantType.UTF8])

    @property
    def descriptor(self):
        return self.constant_pool.ref(self._descriptor_index, [ConstantType.UTF8])

    @property
    def value(self):
        return NameAndType(self.name, self.descriptor)


class ConstantMethodHandle(ConstantBase):
    tag = ConstantType.METHOD_HANDLE

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self.reference_kind, = self.read_data('>B')
        self._reference_index, = self.read_data('>H')

    @property
    def reference(self):
        return self.constant_pool.ref(self._reference_index)


class ConstantMethodType(ConstantBase):
    tag = ConstantType.METHOD_TYPE

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self._descriptor_index, = self.read_data('>H')

    @property
    def descriptor(self):
        return self.constant_pool.ref(self._descriptor_index, [ConstantType.UTF8])


class ConstantInvokeDynamic(ConstantBase):
    tag = ConstantType.INVOKE_DYNAMIC

    def __init__(self, parent):
        ConstantBase.__init__(self, parent)
        self.bootstrap_method_attr_index, self._name_and_type_index = self.read_data('>HH')

    @property
    def name_and_type(self):
        return self.constant_pool.ref(self._name_and_type_index, [ConstantType.NAME_AND_TYPE])


_CONSTANT_TYPE = {
    ConstantType.DUMMY: (ConstantDummy, 'Dummy'),
    ConstantType.UTF8: (ConstantUTF8, 'UTF8'),
    ConstantType.INTEGER: (ConstantInteger, 'Integer'),
    ConstantType.FLOAT: (ConstantFloat, 'Float'),
    ConstantType.LONG: (ConstantLong, 'Long'),
    ConstantType.DOUBLE: (ConstantDouble, 'Double'),
    ConstantType.CLASS: (ConstantClass, 'Class'),
    ConstantType.STRING: (ConstantString, 'String'),
    ConstantType.FIELD_REF: (ConstantFieldRef, 'FieldRef'),
    ConstantType.METHOD_REF: (ConstantMethodRef, 'MethodRef'),
    ConstantType.INTERFACE_METHOD_REF: (ConstantInterfaceMethodRef, 'InterfaceMethodRef'),
    ConstantType.NAME_AND_TYPE: (ConstantNameAndType, 'NameAndType'),
    ConstantType.METHOD_HANDLE: (ConstantMethodHandle, 'MethodHandle'),
    ConstantType.METHOD_TYPE: (ConstantMethodType, 'MethodType'),
    ConstantType.INVOKE_DYNAMIC: (ConstantInvokeDynamic, 'InvokeDynamic')
}
