import os
import requests
import hashlib

class MavenHandler:
    def __init__(self):
        pass

    @classmethod
    def hashfile(cls, afile, hasher, blocksize=65536):
        afile.seek(0)
        buf = afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(blocksize)
        return hasher.hexdigest()


    @classmethod
    def upload(cls, maven_url, maven_user, maven_pass, artifact_name, local_path='', remote_path='', logger=None, do_hashsums=True):
        maven_url = MavenHandler.build_url(maven_url, remote_path)

        with open(os.path.normpath(os.path.join(local_path, artifact_name)), 'rb') as data:
            if logger: logger.info('Sending PUT request for artifact %s to %s' % (artifact_name, maven_url))
            status = MavenHandler.do_put(maven_url + artifact_name, (maven_user, maven_pass), data)
            if status != 200:
                if logger: logger.error('Artifact upload for %s failed with HTTP status code %d' % (artifact_name, status))
                return None

            if do_hashsums:
                if logger: logger.info('Sending PUT request for artifact %s to %s' % (artifact_name + '.md5', maven_url))
                filehash = MavenHandler.hashfile(data, hashlib.md5())
                with open(os.path.normpath(os.path.join(local_path, artifact_name + '.md5')), 'w') as hashfile:
                    hashfile.write(filehash)
                status = MavenHandler.do_put(maven_url + artifact_name + '.md5', (maven_user, maven_pass), filehash)
                if status != 200:
                    if logger: logger.error('Artifact upload for %s failed with HTTP status code %d' % (artifact_name + '.md5', status))
                    return None

                if logger: logger.info('Sending PUT request for artifact %s to %s' % (artifact_name + '.sha1', maven_url))
                filehash = MavenHandler.hashfile(data, hashlib.sha1())
                with open(os.path.normpath(os.path.join(local_path, artifact_name + '.sha1')), 'w') as hashfile:
                    hashfile.write(filehash)
                status = MavenHandler.do_put(maven_url + artifact_name + '.sha1', (maven_user, maven_pass), filehash)
                if status != 200:
                    if logger: logger.error('Artifact upload for %s failed with HTTP status code %d' % (artifact_name + '.sha1', status))
                    return None


        return maven_url + artifact_name


    @classmethod
    def do_put(cls, url, auth, data, logger=None):
        try:
            r = requests.put(url, auth=auth, data=data)
        except:
            return 1
        return r.status_code


    @classmethod
    def build_url(cls, base_url, path, filename=''):
        if base_url[-1] != '/': base_url += '/'
        if path:
            if path[-1] != '/': path += '/'
        else:
            path = ''
        return base_url + path + filename
