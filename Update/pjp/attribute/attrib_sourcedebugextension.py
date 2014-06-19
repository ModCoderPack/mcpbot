from .attrib_base import AttributeBase


__all__ = ['AttributeSourceDebugExtension']


class AttributeSourceDebugExtension(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        self.debug_extension, = self.read_data('>%ss' % self.length)

    def __str__(self):
        return '%s(%s)' % (self.type, len(self.debug_extension))
