import os
import zipfile
from MavenHandler import MavenHandler
from datetime import timedelta, datetime, time
import Logger


with zipfile.ZipFile('test.zip', 'w', compression=zipfile.ZIP_DEFLATED) as zfile:
    files = os.listdir('testcsv')
    for item in [item for item in files if os.path.isfile('testcsv' + '/' + item) and item.endswith('.csv')]:
        zfile.write('testcsv' + '/' + item, arcname=item)

print('Zip file test.zip created.')

print('Opening test.zip.')

# upload_hour, _, upload_minute = '13:03'.partition(':')
# maven_upload_time = time(int(upload_hour), int(upload_minute), 0)
# min_upload_time = datetime.combine(datetime.now().date(), maven_upload_time) - timedelta(minutes=15) + timedelta(seconds=1)
# max_upload_time = datetime.combine(datetime.now().date(), maven_upload_time) + timedelta(minutes=15)
# if min_upload_time <= datetime.now() <= max_upload_time:
with open('test.zip', 'rb') as data:
    if MavenHandler.upload('http://files.minecraftforge.net/maven/manage/upload/de/oceanlabs/mcp/', 'mcp', '',
                           'test.zip', remote_path='moar_tests', logger=Logger.getLogger('test', 'test.log', 'testerr.log')):
        print 'SUCCESS!'
    else:
        print 'FAILURE!'
# else:
#     print("IT'S NOT TIME!")