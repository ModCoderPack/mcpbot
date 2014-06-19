from .attrib_base import AttributeBase, AttributeLengthError
from ..constantpool import ConstantType


__all__ = ['AttributeRuntimeVisibleAnnotations', 'AttributeRuntimeInvisibleAnnotations',
           'AttributeRuntimeVisibleParameterAnnotations', 'AttributeRuntimeInvisibleParameterAnnotations',
           'AttributeAnnotationDefault']


class Error(Exception):
    pass


class AnnotationError(Error):
    pass


class AttributeRuntimeVisibleAnnotations(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        num_annotations, = self.read_data('>H')
        expected_length = 2
        self.annotations = []
        for _ in range(num_annotations):
            annotation = _Annotation(self)
            expected_length += annotation.length
            self.annotations.append(annotation)

        if expected_length != self.length:
            raise AttributeLengthError

    def __str__(self):
        return '%s(%s)' % (self.type, len(self.annotations))


class AttributeRuntimeInvisibleAnnotations(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        num_annotations, = self.read_data('>H')
        expected_length = 2
        self.annotations = []
        for _ in range(num_annotations):
            annotation = _Annotation(self)
            expected_length += annotation.length
            self.annotations.append(annotation)

        if expected_length != self.length:
            raise AttributeLengthError

    def __str__(self):
        return '%s(%s)' % (self.type, len(self.annotations))


class AttributeRuntimeVisibleParameterAnnotations(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        num_parameters, = self.read_data('>B')
        expected_length = 1
        self.parameters = []
        for _ in range(num_parameters):
            num_annotations, = self.read_data('>H')
            expected_length += 2
            annotations = []
            for _ in range(num_annotations):
                annotation = _Annotation(self)
                expected_length += annotation.length
                annotations.append(annotation)
            self.parameters.append(annotations)

        if expected_length != self.length:
            raise AttributeLengthError

    def __str__(self):
        return '%s(%s)' % (self.type, len(self.parameters))


class AttributeRuntimeInvisibleParameterAnnotations(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        num_parameters, = self.read_data('>B')
        expected_length = 1
        self.parameters = []
        for _ in range(num_parameters):
            num_annotations, = self.read_data('>H')
            expected_length += 2
            annotations = []
            for _ in range(num_annotations):
                annotation = _Annotation(self)
                expected_length += annotation.length
                annotations.append(annotation)
            self.parameters.append(annotations)

        if expected_length != self.length:
            raise AttributeLengthError

    def __str__(self):
        return '%s(%s)' % (self.type, len(self.parameters))


class AttributeAnnotationDefault(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        self.default_value = _ElementValue(self)

        if self.default_value.length != self.length:
            raise AttributeLengthError

    def __str__(self):
        return '%s(%s)' % (self.type, self.default_value)


class _Annotation(object):
    def __init__(self, parent):
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        self._type_index, = self.read_data('>H')
        self.length = 2
        self.type = self.constant_pool.ref(self._type_index, [ConstantType.UTF8])
        num_element_value_pairs, = self.read_data('>H')
        self.length += 2
        self.element_value_pairs = []
        for _ in range(num_element_value_pairs):
            element_name_index, = self.read_data('>H')
            self.length += 2
            element_name = self.constant_pool.ref(element_name_index, [ConstantType.UTF8])
            element_value = _ElementValue(self)
            self.length += element_value.length
            self.element_value_pairs.append((element_name, element_value))

    def __str__(self):
        return '%s(%s)' % (self.type, len(self.element_value_pairs))


class _ElementValue(object):
    def __init__(self, parent):
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        self.tag, = self.read_data('>B')
        self.length = 1
        tag = chr(self.tag)
        if tag == 'B':
            self._value_index, = self.read_data('>H')
            self.length += 2
            self.value = self.constant_pool.ref(self._value_index, [ConstantType.INTEGER])
        elif tag == 'C':
            self._value_index, = self.read_data('>H')
            self.length += 2
            self.value = self.constant_pool.ref(self._value_index, [ConstantType.INTEGER])
        elif tag == 'D':
            self._value_index, = self.read_data('>H')
            self.length += 2
            self.value = self.constant_pool.ref(self._value_index, [ConstantType.DOUBLE])
        elif tag == 'F':
            self._value_index, = self.read_data('>H')
            self.length += 2
            self.value = self.constant_pool.ref(self._value_index, [ConstantType.FLOAT])
        elif tag == 'I':
            self._value_index, = self.read_data('>H')
            self.length += 2
            self.value = self.constant_pool.ref(self._value_index, [ConstantType.INTEGER])
        elif tag == 'J':
            self._value_index, = self.read_data('>H')
            self.length += 2
            self.value = self.constant_pool.ref(self._value_index, [ConstantType.LONG])
        elif tag == 'S':
            self._value_index, = self.read_data('>H')
            self.length += 2
            self.value = self.constant_pool.ref(self._value_index, [ConstantType.INTEGER])
        elif tag == 'Z':
            self._value_index, = self.read_data('>H')
            self.length += 2
            self.value = self.constant_pool.ref(self._value_index, [ConstantType.INTEGER])
        elif tag == 's':
            self._value_index, = self.read_data('>H')
            self.length += 2
            self.value = self.constant_pool.ref(self._value_index, [ConstantType.UTF8])
        elif tag == 'e':
            self._type_name_index, = self.read_data('>H')
            self.length += 2
            self.type_name = self.constant_pool.ref(self._type_name_index, [ConstantType.UTF8])
            self._const_name_index, = self.read_data('>H')
            self.length += 2
            self.const_name = self.constant_pool.ref(self._const_name_index, [ConstantType.UTF8])
            self.value = (self.type_name, self.const_name)
        elif tag == 'c':
            self._value_index, = self.read_data('>H')
            self.length += 2
            self.value = self.constant_pool.ref(self._value_index, [ConstantType.UTF8])
        elif tag == '@':
            annotation = _Annotation(self)
            self.value = annotation
            self.length += annotation.length
        elif tag == '[':
            num_value, = self.read_data('>H')
            self.length += 2
            self.value = []
            for _ in range(num_value):
                element = _ElementValue(self)
                self.length += element.length
                self.value.append(element)
        else:
            raise AnnotationError('Unknown annotation element tag: %c' % tag)

    def __str__(self):
        return '%c(%s)' % (self.tag, self.value)
