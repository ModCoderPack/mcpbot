import fnmatch
import zipfile


__all__ = ['JarFile']


class JarFile(object):
    _manifest_file = 'META-INF/MANIFEST.MF'

    def __init__(self, jar_file):
        self._jar_file = zipfile.ZipFile(jar_file)
        self.classes = []
        self.other = []
        for file_entry in self._jar_file.infolist():
            if fnmatch.fnmatch(file_entry.filename, '*.class'):
                self.classes.append(file_entry)
            else:
                self.other.append(file_entry)
        self.manifest = None
        try:
            self.manifest = self._jar_file.read(self._jar_file.getinfo(self._manifest_file))
        except KeyError:
            pass

    def __getitem__(self, item):
        return self._jar_file.read(item)

    def __contains__(self, item):
        if isinstance(item, zipfile.ZipInfo):
            if item in self._jar_file.infolist():
                return True
            else:
                return False
        else:
            try:
                self._jar_file.getinfo(item)
            except KeyError:
                return False
            else:
                return True
