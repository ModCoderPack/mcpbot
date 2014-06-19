from .constantpool import ConstantType
from .attribute.attrib_base import AttributeGeneric
from .attribute.attrib_constantvalue import AttributeConstantValue
from .attribute.attrib_exceptions import AttributeExceptions
from .attribute.attrib_innerclasses import AttributeInnerClasses
from .attribute.attrib_synthetic import AttributeSynthetic
from .attribute.attrib_sourcefile import AttributeSourceFile
from .attribute.attrib_linenumbertable import AttributeLineNumberTable
from .attribute.attrib_deprecated import AttributeDeprecated
from .attribute.attrib_enclosingmethod import AttributeEnclosingMethod
from .attribute.attrib_signature import AttributeSignature
from .attribute.attrib_localvariabletypetable import AttributeLocalVariableTypeTable
from .attribute.attrib_localvariabletable import AttributeLocalVariableTable
from .attribute.attrib_sourcedebugextension import AttributeSourceDebugExtension
from .attribute.attrib_stackmaptable import AttributeStackMapTable
from .attribute.attrib_annotations import AttributeRuntimeVisibleAnnotations
from .attribute.attrib_annotations import AttributeRuntimeInvisibleAnnotations
from .attribute.attrib_annotations import AttributeRuntimeVisibleParameterAnnotations
from .attribute.attrib_annotations import AttributeRuntimeInvisibleParameterAnnotations
from .attribute.attrib_annotations import AttributeAnnotationDefault
from .attribute.attrib_bootstrapmethods import AttributeBootstrapMethods


__all__ = ['AttributeTable']


class AttributeTable(list):
    def __init__(self, parent):
        list.__init__(self)
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        attribute_count, = self.read_data('>H')
        self.length = 2
        for _ in range(attribute_count):
            attribute_type_index, = self.read_data('>H')
            self.length += 2
            attribute_type = self.constant_pool.ref(attribute_type_index, [ConstantType.UTF8])
            attribute = _ATTRIBUTE_MAP.get(attribute_type, AttributeGeneric)(attribute_type_index, self)
            self.length += 4 + attribute.length
            self.append(attribute)


# code attribute contains a attribute table, so import here to avoid circular import
from .attribute.attrib_code import AttributeCode


_ATTRIBUTE_MAP = {
    'Code': AttributeCode,
    'ConstantValue': AttributeConstantValue,
    'Exceptions': AttributeExceptions,
    'InnerClasses': AttributeInnerClasses,
    'Synthetic': AttributeSynthetic,
    'SourceFile': AttributeSourceFile,
    'LineNumberTable': AttributeLineNumberTable,
    'Deprecated': AttributeDeprecated,
    'EnclosingMethod': AttributeEnclosingMethod,
    'Signature': AttributeSignature,
    'LocalVariableTypeTable': AttributeLocalVariableTypeTable,
    'LocalVariableTable': AttributeLocalVariableTable,
    'SourceDebugExtension': AttributeSourceDebugExtension,
    'StackMapTable': AttributeStackMapTable,
    'RuntimeVisibleAnnotations': AttributeRuntimeVisibleAnnotations,
    'RuntimeInvisibleAnnotations': AttributeRuntimeInvisibleAnnotations,
    'RuntimeVisibleParameterAnnotations': AttributeRuntimeVisibleParameterAnnotations,
    'RuntimeInvisibleParameterAnnotations': AttributeRuntimeInvisibleParameterAnnotations,
    'AnnotationDefault': AttributeAnnotationDefault,
    'BootstrapMethods': AttributeBootstrapMethods
}
