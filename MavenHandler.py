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
    def upload(cls, maven_url, maven_user, maven_pass, artifact_name, local_path=None, remote_path=None, logger=None, do_hashsums=True):
        if local_path:
            if local_path[-1] != '/': local_path += '/'
        else:
            local_path = ''

        maven_url = MavenHandler.build_url(maven_url, remote_path)

        with open(local_path + artifact_name, 'rb') as data:
            if logger: logger.info('Sending PUT request for artifact %s to %s' % (artifact_name, maven_url))
            status = MavenHandler.do_put(maven_url + artifact_name, (maven_user, maven_pass), data)
            if status != 200:
                if logger: logger.error('Artifact upload for %s failed with HTTP status code %d' % (artifact_name, status))
                return False

            if do_hashsums:
                if logger: logger.info('Sending PUT request for artifact %s to %s' % (artifact_name + '.md5', maven_url))
                status = MavenHandler.do_put(maven_url + artifact_name + '.md5', (maven_user, maven_pass), MavenHandler.hashfile(data, hashlib.md5()))
                if status != 200:
                    if logger: logger.error('Artifact upload for %s failed with HTTP status code %d' % (artifact_name + '.md5', status))
                    return False

                if logger: logger.info('Sending PUT request for artifact %s to %s' % (artifact_name + '.sha1', maven_url))
                status = MavenHandler.do_put(maven_url + artifact_name + '.sha1', (maven_user, maven_pass), MavenHandler.hashfile(data, hashlib.sha1()))
                if status != 200:
                    if logger: logger.error('Artifact upload for %s failed with HTTP status code %d' % (artifact_name + '.md5', status))
                    return False


        return True


    @classmethod
    def do_put(cls, url, auth, data, retry_count=0):
        r = requests.put(url, auth=auth, data=data)
        return r.status_code


    @classmethod
    def build_url(cls, base_url, path, filename=''):
        if base_url[-1] != '/': base_url += '/'
        if path:
            if path[-1] != '/': path += '/'
        else:
            path = ''
        return base_url + path + filename
