import requests
import os
import zipfile
import hashlib

class MavenHandler():
    def __init__(self, logger, maven_url, maven_user, maven_pass, stable_path, snapshot_path):
        self.logger = logger
        self.maven_url = maven_url
        self.maven_user = maven_user
        self.maven_pass = maven_pass
        self.stable_path = stable_path
        self.snapshot_path = snapshot_path

        if self.maven_url[-1] != '/': self.maven_url += '/'


    @classmethod
    def hashfile(cls, afile, hasher, blocksize=65536):
        buf = afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(blocksize)
        return hasher.hexdigest()


    def upload(self, csv_path, remote_path):
        if remote_path[-1] != '/': remote_path += '/'

        with zipfile.ZipFile(csv_path + '.zip', 'w', compression=zipfile.ZIP_DEFLATED) as zfile:
            files = os.listdir(csv_path)
            for item in files:
                zfile.write(csv_path + '/' + os.path.basename(item), arcname=os.path.basename(item))

        print('Zip file test.zip created.')

        print('Opening test.zip.')
        with open('test.zip', 'rb') as data:
            print('Reading test.zip.')

            print('Sending zip request.')
            r = requests.put(self.maven_url + remote_path + 'csv.zip', auth=(self.maven_user, self.maven_pass), data=data)
            print r

            data.seek(0)
            print('Sending md5 request.')
            r = requests.put(self.maven_url + remote_path + 'csv.zip.md5', auth=(self.maven_user, self.maven_pass), data=self.hashfile(data, hashlib.md5()))
            print r

            data.seek(0)
            print('Sending sha1 request.')
            r = requests.put(self.maven_url + remote_path + 'csv.zip.sha1', auth=(self.maven_user, self.maven_pass), data=self.hashfile(data, hashlib.sha1()))
            print r
