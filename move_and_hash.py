import os, shutil, hashlib
from optparse import OptionParser
from MavenHandler import MavenHandler


def processdir(srcpath, tgtpath, ext, move):
    print 'Processing %s files in %s' % (ext, srcpath)

    for filename in [filename for filename in os.listdir(srcpath) if os.path.isfile(os.path.join(srcpath, filename)) and os.path.splitext(filename)[-1].lower() == ext]:
        moveandhashfile(srcpath, filename, tgtpath, move)


def moveandhashfile(srcpath, filename, tgtpath, move):
    artifact, _, version = os.path.splitext(filename)[0].partition('-')
    newpath = os.path.join(tgtpath, artifact, version)
    if not os.path.exists(newpath):
        os.makedirs(newpath)

    newfile = os.path.join(newpath, filename)

    if move:
        print 'Moving %s to %s' % (filename, newpath)
        shutil.move(os.path.join(srcpath, filename), newfile)
    else:
        print 'Copying %s to %s' % (filename, newpath)
        shutil.copy(os.path.join(srcpath, filename), newfile)

    with open(newfile, 'rb') as data:
        filehash = MavenHandler.hashfile(data, hashlib.md5())
        with open(os.path.normpath(newfile + '.md5'), 'w') as hashfile:
            hashfile.write(filehash)
        filehash = MavenHandler.hashfile(data, hashlib.sha1())
        with open(os.path.normpath(newfile + '.sha1'), 'w') as hashfile:
            hashfile.write(filehash)


def main():
    parser = OptionParser(usage="%prog [options]")
    parser.add_option('-m', '--move', action='store_true', default=False, help='Move files instead of copy? [default: %default]')
    parser.add_option('-e', '--ext', default='zip', help='The extension of files to process [default: %default]')
    parser.add_option('-s', '--src-dir', default='.', help='The source directory [default: %default]')
    parser.add_option('-t', '--tgt-dir', default='.', help='The base target directory [default: %default]')

    options, args = parser.parse_args()
    processdir(options.src_dir, options.tgt_dir, options.ext if options.ext.startswith('.') else '.' + options.ext, options.move)

    print('Fin')


if __name__ == "__main__":
    main()