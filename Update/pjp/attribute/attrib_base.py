from ..constantpool import ConstantType


__all__ = ['AttributeLengthError', 'AttributeBase', 'AttributeGeneric']


class Error(Exception):
    pass


class AttributeLengthError(Error):
    pass


class AttributeBase(object):
    def __init__(self, type_index, parent):
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        self._type_index = type_index
        self.type = self.constant_pool.ref(type_index, [ConstantType.UTF8])
        self.length, = self.read_data('>I')

    def __str__(self):
        return self.type


class AttributeGeneric(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        self.value, = self.read_data('>%ss' % self.length)

    def __str__(self):
        return '* %s' % self.type
