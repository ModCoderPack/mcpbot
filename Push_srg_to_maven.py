from MavenHandler import MavenHandler
from ConfigHandler import AdvConfigParser
import Logger

logger = Logger.getLogger('test', 'test.log', 'testerr.log')
configfile = 'bot.cfg'

config = AdvConfigParser()
config.read(configfile)
maven_repo_url = config.get('EXPORT', 'MAVEN_REPO_URL', 'http://files.minecraftforge.net/maven/manage/upload/de/oceanlabs/mcp/')
maven_repo_user = config.get('EXPORT', 'MAVEN_REPO_USER', 'mcp')
maven_repo_pass = config.get('EXPORT', 'MAVEN_REPO_PASS', '')

print MavenHandler.upload(maven_repo_url, maven_repo_user, maven_repo_pass, 'mcp-1.8-csrg.zip', remote_path='mcp/1.8', logger=logger)
print MavenHandler.upload(maven_repo_url, maven_repo_user, maven_repo_pass, 'mcp-1.8-srg.zip', remote_path='mcp/1.8', logger=logger)
