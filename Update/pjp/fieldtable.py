from collections import OrderedDict

from .attributetable import AttributeTable
from .field import Field
from .constantpool import ConstantType


__all__ = ['FieldTable']


class FieldTable(OrderedDict):
    def __init__(self, parent):
        OrderedDict.__init__(self)
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        field_count, = self.read_data('>H')
        for _ in range(field_count):
            field = FieldEntry(self)
            self[field.key] = field


class FieldEntry(Field):
    def __init__(self, parent):
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        access_flags, self._name_index, self._descriptor_index = self.read_data('>3H')
        self.attributes = AttributeTable(self)
        name = self.constant_pool.ref(self._name_index, [ConstantType.UTF8])
        descriptor = self.constant_pool.ref(self._descriptor_index, [ConstantType.UTF8])
        Field.__init__(self, name, descriptor, access_flags)
