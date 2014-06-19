import fnmatch
import os


__all__ = ['ClassDir']


class ClassDir(object):
    _manifest_file = 'META-INF/MANIFEST.MF'

    def __init__(self, class_dir):
        self._class_dir = os.path.normpath(class_dir)
        self.classes = []
        self.other = []
        for dirpath, _, filenames in os.walk(self._class_dir):
            sub_dir = os.path.relpath(dirpath, self._class_dir)
            if sub_dir == '.':
                sub_dir = ''

            for filename in filenames:
                if fnmatch.fnmatch(filename, '*.class'):
                    self.classes.append(os.path.join(sub_dir, filename))
                else:
                    self.other.append(os.path.join(sub_dir, filename))
            self.manifest = None
            try:
                self.manifest = open(os.path.join(self._class_dir, os.path.normpath(self._manifest_file))).read()
            except IOError:
                pass

    def __getitem__(self, item):
        return open(os.path.join(self._class_dir, os.path.normpath(item)), 'rb').read()

    def __contains__(self, item):
        try:
            os.path.isfile(os.path.join(self._class_dir, os.path.normpath(item)))
        except KeyError:
            return False
        else:
            return True
