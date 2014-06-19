from .attrib_base import AttributeBase, AttributeLengthError
from ..class_ import Class
from ..constantpool import ConstantType


__all__ = ['AttributeExceptions']


class AttributeExceptions(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        number_of_exceptions, = self.read_data('>H')

        expected_length = (2 + number_of_exceptions * 2)
        if self.length != expected_length:
            raise AttributeLengthError

        self.exception_table = []
        for _ in range(number_of_exceptions):
            exception_index, = self.read_data('>H')
            self.exception_table.append(Class(self.constant_pool.ref(exception_index, [ConstantType.CLASS])))

    def __str__(self):
        return '%s(%d)' % (self.type, len(self.exception_table))
