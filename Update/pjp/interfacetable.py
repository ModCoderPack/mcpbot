from .class_ import Class
from .constantpool import ConstantType


__all__ = ['InterfaceTable']


class InterfaceTable(list):
    def __init__(self, parent):
        list.__init__(self)
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        interface_count, = parent.read_data('>H')
        for _ in range(interface_count):
            self.append(InterfaceEntry(self))


class InterfaceEntry(Class):
    def __init__(self, parent):
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        self._name_index, = self.read_data('>H')
        name = self.constant_pool.ref(self._name_index, [ConstantType.CLASS])
        Class.__init__(self, name)
