from collections import namedtuple

from .attrib_base import AttributeBase, AttributeLengthError


__all__ = ['AttributeLineNumberTable']


class AttributeLineNumberTable(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        table_length, = self.read_data('>H')

        expected_length = (2 + table_length * 2 * 2)
        if self.length != expected_length:
            raise AttributeLengthError

        self.line_number_table = []
        for _ in range(table_length):
            self.line_number_table.append(_LINE_NUMBER_ENTRY(*self.read_data('>2H')))

    def __str__(self):
        return '%s(%d)' % (self.type, len(self.line_number_table))


_LINE_NUMBER_ENTRY = namedtuple('LineNumberEntry', ['start_pc', 'line_number'])
