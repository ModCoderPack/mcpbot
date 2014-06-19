from .attrib_base import AttributeBase, AttributeLengthError
from ..class_ import Class
from ..method import Method
from ..constantpool import ConstantType


__all__ = ['AttributeEnclosingMethod']


class AttributeEnclosingMethod(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        if self.length != (2 * 2):
            raise AttributeLengthError

        self._class_index, = self.read_data('>H')
        self._method_index, = self.read_data('>H')
        self.class_ = Class(self.constant_pool.ref(self._class_index, [ConstantType.CLASS]))
        if self._method_index:
            method = self.constant_pool.ref(self._method_index, [ConstantType.NAME_AND_TYPE])
            self.method = Method(method.name, method.descriptor)
        else:
            self.method = None
