import subprocess
import re
import undetected_chromedriver as uc

ver = int(re.search(r'(\d+)\.', subprocess.check_output(['google-chrome', '--version']).decode()).group(1))
print(f'Chrome major version: {ver}')

options = uc.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')

driver = uc.Chrome(options=options, version_main=ver, use_subprocess=False)
driver.quit()
print('Chromedriver pre-downloaded OK')
