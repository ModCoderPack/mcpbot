import struct

from .class_ import Class
from .constantpool import ConstantPool, ConstantType
from .interfacetable import InterfaceTable
from .fieldtable import FieldTable
from .methodtable import MethodTable
from .attributetable import AttributeTable


__all__ = ['ClassFile']


class Error(Exception):
    pass


class ParseError(Error):
    """Invalid class file"""
    pass


class ClassFile(Class):
    def __init__(self, source):
        self._source = source
        self._buffer_pos = 0

        magic, = self.read_data('>I')
        if magic != 0xCAFEBABE:
            raise ParseError('Invalid magic')

        _minor_version, _major_version = self.read_data('>HH')
        self.version = JavaVersion(_major_version, _minor_version)
        self.constant_pool = ConstantPool(self)
        access_flags, self._this_class_index, self._super_class_index = self.read_data('>3H')
        self.interfaces = InterfaceTable(self)
        self.fields = FieldTable(self)
        self.methods = MethodTable(self)
        self.attributes = AttributeTable(self)
        name = self.constant_pool.ref(self._this_class_index, [ConstantType.CLASS])
        self.this_class = Class(name, access_flags)
        if self._super_class_index:
            self.super_class = Class(self.constant_pool.ref(self._super_class_index, [ConstantType.CLASS]))
        else:
            self.super_class = Class('java/lang/Object')
        if self._buffer_pos != len(self._source):
            raise ParseError('Trailing data')
        Class.__init__(self, name, access_flags)

    def read_data(self, data_format):
        length = struct.calcsize(data_format)
        data = struct.unpack_from(data_format, self._source, self._buffer_pos)
        self._buffer_pos += length
        return data


class JavaVersion(object):
    def __init__(self, major, minor):
        self.major = major
        self.minor = minor

    def __str__(self):
        if self.major == 45 and self.minor <= 3:
            return 'JDK 1.0.2'
        else:
            return {
                45: 'JDK 1.1',
                46: 'JDK 1.2',
                47: 'JDK 1.3',
                48: 'JDK 1.4',
                49: 'J2SE 5.0',
                50: 'J2SE 6.0',
                51: 'J2SE 7.0'
            }.get(self.major, 'unknown')
