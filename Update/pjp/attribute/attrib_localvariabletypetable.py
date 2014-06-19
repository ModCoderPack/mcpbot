from collections import OrderedDict

from .attrib_base import AttributeBase, AttributeLengthError
from ..constantpool import ConstantType, NameAndSignature


__all__ = ['AttributeLocalVariableTypeTable']


class AttributeLocalVariableTypeTable(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        table_length, = self.read_data('>H')

        expected_length = (2 + table_length * 5 * 2)
        if self.length != expected_length:
            raise AttributeLengthError

        self.local_variable_type_table = OrderedDict()
        for _ in range(table_length):
            local_variable_type = _LVTTEntry(self, *self.read_data('>5H'))
            self.local_variable_type_table[local_variable_type.key] = local_variable_type

    def __str__(self):
        return '%s(%d)' % (self.type, len(self.local_variable_type_table))


class _LVTTEntry(object):
    def __init__(self, parent, start_pc, length, name_index, signature_index, index):
        self._parent = parent
        self.constant_pool = parent.constant_pool
        self.start_pc = start_pc
        self.length = length
        self._name_index = name_index
        self._signature_index = signature_index
        self.index = index
        self.name = self.constant_pool.ref(self._name_index, [ConstantType.UTF8])
        self.signature = self.constant_pool.ref(self._signature_index, [ConstantType.UTF8])
        self.name_and_signature = NameAndSignature(self.name, self.signature)

    @property
    def key(self):
        return self.index

    def __str__(self):
        return self.name_and_signature
