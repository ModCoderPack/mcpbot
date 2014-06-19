from collections import OrderedDict

from .attributetable import AttributeTable
from .method import Method
from .constantpool import ConstantType


__all__ = ['MethodTable']


class MethodTable(OrderedDict):
    def __init__(self, parent):
        OrderedDict.__init__(self)
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        method_count, = self.read_data('>H')
        for _ in range(method_count):
            method = MethodEntry(self)
            self[method.key] = method


class MethodEntry(Method):
    def __init__(self, parent):
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        access_flags, self._name_index, self._descriptor_index = self.read_data('>3H')
        self.attributes = AttributeTable(self)
        name = self.constant_pool.ref(self._name_index, [ConstantType.UTF8])
        descriptor = self.constant_pool.ref(self._descriptor_index, [ConstantType.UTF8])
        Method.__init__(self, name, descriptor, access_flags)
