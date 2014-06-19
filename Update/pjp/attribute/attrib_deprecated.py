from .attrib_base import AttributeBase, AttributeLengthError


__all__ = ['AttributeDeprecated']


class AttributeDeprecated(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        if self.length:
            raise AttributeLengthError
