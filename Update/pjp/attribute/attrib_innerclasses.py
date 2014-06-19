from .attrib_base import AttributeBase, AttributeLengthError
from ..constantpool import ConstantType
from ..class_ import Class, InnerClass


__all__ = ['AttributeInnerClasses']


class AttributeInnerClasses(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        number_of_classes, = self.read_data('>H')

        expected_length = (2 + number_of_classes * 4 * 2)
        if self.length != expected_length:
            raise AttributeLengthError

        self.classes = []
        for _ in range(number_of_classes):
            self.classes.append(_InnerClassesEntry(self, *self.read_data('>4H')))

    def __str__(self):
        return '%s(%d)' % (self.type, len(self.classes))


class _InnerClassesEntry(InnerClass):
    def __init__(self, parent, inner_class_info_index, outer_class_info_index, inner_name_index,
                 inner_class_access_flags):
        self._parent = parent
        self.constant_pool = parent.constant_pool
        self._inner_class_info_index = inner_class_info_index
        self._outer_class_info_index = outer_class_info_index
        self._inner_name_index = inner_name_index
        self.inner_class_access_flags = inner_class_access_flags
        if self._inner_class_info_index:
            inner_class_info = self.constant_pool.ref(self._inner_class_info_index, [ConstantType.CLASS])
            self.inner_class_info = InnerClass(inner_class_info, inner_class_access_flags)
        else:
            self.inner_class_info = None
        if self._outer_class_info_index:
            outer_class_info = self.constant_pool.ref(self._outer_class_info_index, [ConstantType.CLASS])
            self.outer_class_info = Class(outer_class_info)
        else:
            self.outer_class_info = None
        if self._inner_name_index:
            self.inner_name = self.constant_pool.ref(self._inner_name_index, [ConstantType.UTF8])
        else:
            self.inner_name = None
        InnerClass.__init__(self, inner_class_info, inner_class_access_flags)
