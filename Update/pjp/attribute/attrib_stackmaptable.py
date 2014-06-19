from .attrib_base import AttributeBase


__all__ = ['AttributeStackMapTable']


class AttributeStackMapTable(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        # TODO: parse StackMapTable
        self.stack_map_table, = self.read_data('>%ss' % self.length)

    def __str__(self):
        return '%s(%s)' % (self.type, len(self.stack_map_table))
