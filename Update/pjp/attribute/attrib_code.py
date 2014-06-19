from .attrib_base import AttributeBase, AttributeLengthError
from ..attributetable import AttributeTable
from ..class_ import Class
from ..constantpool import ConstantType


__all__ = ['AttributeCode']


class AttributeCode(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        self.max_stack, = self.read_data('>H')
        self.max_locals, = self.read_data('>H')

        # TODO: parse bytecode array
        code_length, = self.read_data('>I')
        self.code, = self.read_data('>%ss' % code_length)

        exception_table_length, = self.read_data('>H')
        self.exception_table = []
        for _ in range(exception_table_length):
            self.exception_table.append(_CodeExceptionEntry(self, *self.read_data('>4H')))

        self.attributes = AttributeTable(self)

        expected_length = (2 + 2 + 4 + code_length + 2 + exception_table_length * 4 * 2 +
                           self.attributes.length)
        if self.length != expected_length:
            raise AttributeLengthError

    def __str__(self):
        return '%s(%d)' % (self.type, len(self.code))


class _CodeExceptionEntry(object):
    def __init__(self, parent, start_pc, end_pc, handler_pc, catch_type_index):
        self._parent = parent
        self.constant_pool = parent.constant_pool
        self.start_pc = start_pc
        self.end_pc = end_pc
        self.handler_pc = handler_pc
        self._catch_type_index = catch_type_index
        if self._catch_type_index:
            self.catch_type = Class(self.constant_pool.ref(catch_type_index, [ConstantType.CLASS]))
        else:
            self.catch_type = None

    def __str__(self):
        return self.catch_type
