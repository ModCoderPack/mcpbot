from .attrib_base import AttributeBase, AttributeLengthError
from ..constantpool import ConstantType


__all__ = ['AttributeConstantValue']


class AttributeConstantValue(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        if self.length != 2:
            raise AttributeLengthError

        self._constantvalue_index, = self.read_data('>H')
        self.constantvalue_tag = self.constant_pool.tag(self._constantvalue_index)
        self.constantvalue = self.constant_pool.ref(self._constantvalue_index, [
            ConstantType.LONG, ConstantType.FLOAT, ConstantType.DOUBLE, ConstantType.INTEGER, ConstantType.STRING])

    def __str__(self):
        return '%s(%s)' % (self.type, self.constantvalue)
