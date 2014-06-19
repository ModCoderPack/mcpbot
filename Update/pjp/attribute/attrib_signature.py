from .attrib_base import AttributeBase, AttributeLengthError
from ..constantpool import ConstantType


__all__ = ['AttributeSignature']


class AttributeSignature(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        if self.length != 2:
            raise AttributeLengthError

        # TODO: Parse Signature string
        self._signature_index, = self.read_data('>H')
        self.signature = self.constant_pool.ref(self._signature_index, [ConstantType.UTF8])

    def __str__(self):
        return '%s(%s)' % (self.type, self.signature)
