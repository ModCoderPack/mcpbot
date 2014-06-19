from .attrib_base import AttributeBase, AttributeLengthError
from ..constantpool import ConstantType


__all__ = ['AttributeSourceFile']


class AttributeSourceFile(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        if self.length != 2:
            raise AttributeLengthError

        self._sourcefile_index, = self.read_data('>H')
        self.sourcefile = self.constant_pool.ref(self._sourcefile_index, [ConstantType.UTF8])

    def __str__(self):
        return '%s(%s)' % (self.type, self.sourcefile)
