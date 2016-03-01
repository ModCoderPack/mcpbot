from MavenHandler import MavenHandler
from ConfigHandler import AdvConfigParser
import Logger

logger = Logger.getLogger('push_srg_to_maven', 'push_srg_to_maven.log', 'push_srg_to_maven_err.log')
configfile = 'bot.cfg'

config = AdvConfigParser()
config.read(configfile)
maven_repo_url = config.get('EXPORT', 'MAVEN_REPO_URL', 'http://files.minecraftforge.net/maven/manage/upload/de/oceanlabs/mcp/')
maven_repo_user = config.get('EXPORT', 'MAVEN_REPO_USER', 'mcp')
maven_repo_pass = config.get('EXPORT', 'MAVEN_REPO_PASS', '')
mc_version = '1.9'

print MavenHandler.upload(maven_repo_url, maven_repo_user, maven_repo_pass, 'mcp-' + mc_version + '-csrg.zip', remote_path='mcp/' + mc_version, logger=logger)
print MavenHandler.upload(maven_repo_url, maven_repo_user, maven_repo_pass, 'mcp-' + mc_version + '-srg.zip', remote_path='mcp/' + mc_version, logger=logger)
