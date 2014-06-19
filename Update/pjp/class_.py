from .accessflags import ClassAccessFlags, InnerClassAccessFlags


__all__ = ['Class', 'InnerClass']


class Class(object):
    def __init__(self, name, access_flags=None):
        self.name = name
        self.access_flags = ClassAccessFlags(access_flags)
        self.package_name, _, self.class_name = name.rpartition('/')
        inner_names = name.rpartition('$')
        if inner_names[1]:
            self.inner_name = inner_names[2]
        else:
            self.inner_name = ''
        self.outer_name = name.split('$')[0]

    @property
    def key(self):
        return self.name

    def __str__(self):
        result = ''
        if str(self.access_flags):
            result += str(self.access_flags) + ' '
        result += self.name
        return result


class InnerClass(Class):
    def __init__(self, name, access_flags=None):
        Class.__init__(self, name)
        self.access_flags = InnerClassAccessFlags(access_flags)
