from .attrib_base import AttributeBase, AttributeLengthError
from ..constantpool import ConstantType


__all__ = ['AttributeBootstrapMethods']


class AttributeBootstrapMethods(AttributeBase):
    def __init__(self, type_index, parent):
        AttributeBase.__init__(self, type_index, parent)

        num_bootstrap_methods, = self.read_data('>H')
        expected_length = 4
        self.bootstrap_methods = []
        for _ in range(num_bootstrap_methods):
            bootstrap_method = _BootstrapMethod(self)
            expected_length += bootstrap_method.length
            self.bootstrap_methods.append(bootstrap_method)

        if expected_length != self.length:
            raise AttributeLengthError

    def __str__(self):
        return '%s(%s)' % (self.type, len(self.bootstrap_methods))


class _BootstrapMethod(object):
    def __init__(self, parent):
        self._parent = parent
        self.read_data = parent.read_data
        self.constant_pool = parent.constant_pool

        self._bootstrap_method_index, = self.read_data('>H')
        self.length = 2
        self.bootstrap_method = self.constant_pool.ref(self._bootstrap_method_index, [ConstantType.METHOD_HANDLE])

        num_bootstrap_args, = self.read_data('>H')
        self.length += 2 + num_bootstrap_args * 2
        self.bootstrap_arguments = []
        for _ in range(num_bootstrap_args):
            bootstrap_arg_index, = self.read_data('>H')
            bootstrap_arg = self.constant_pool.ref(bootstrap_arg_index)
            self.bootstrap_arguments.append(bootstrap_arg)
