from pyvirtualdisplay import Display
from random import shuffle
from time import sleep
import os
import pyperclip
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class Proxy:
    def __init__(self,src_dir):
        self.src_dir = src_dir
        self.asset_dir = os.path.join(os.path.realpath(src_dir + '/../'),'assets')
        self.http_proxy_path = f'{self.asset_dir}/HTTP[S]_proxies.txt'
        self.sock_proxy_path = f'{self.asset_dir}/SOCKS5_proxies.txt'
        self.http_temp_path = f'{self.asset_dir}/HTTP[S]_temp.txt'
        self.sock_temp_path = f'{self.asset_dir}/SOCKS5_temp.txt'
        self.tmp_path = f'{self.asset_dir}/tmp.txt'
        self.proxy_paths = [self.http_proxy_path,self.sock_proxy_path]
        self.temp_paths = [self.http_temp_path,self.sock_temp_path]
        self.protcols = {"SOCKS5" : [ self.sock_proxy_path,self.sock_temp_path ],
                "HTTP[S]": [self.http_proxy_path,self.http_temp_path]}

    def setup(self):
        # Initalizing driver with incognito + headless
        print("Initalizing driver for proxies")
        options = Options()
        options.add_argument('--incognito')
        options.add_argument('--disable-extensions')
        options.add_argument('--start-maximized')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36')
        options.add_argument('--no-first-run --no-service-autorun --password-store=basic')
        driver = webdriver.Chrome(options=options)
        driver.delete_all_cookies
        print("Driver ready")
        return driver

    def load_proxies(self):
        with open(f'{self.tmp_path}','w') as f:
            pass

        # Initalizing virtual display
        print("Initalizing virtual display")
        display = Display(visible=False,size=(1920,1080))
        display.start()

        driver = self.setup()
        wait = WebDriverWait(driver,10)
        actions = ActionChains(driver)
        driver.get('https://checkerproxy.net/getAllProxy')
        print(f'Grabbing proxies')
        archive_elements = driver.find_elements(By.XPATH,'//div[@class="block archive full_list"]/ul/li/a')
        for path in self.temp_paths:
            with open(f'{path}','w') as f:
                pass

        hrefs = []
        for element in archive_elements:
            hrefs.append(element.get_attribute('href'))

        for href in hrefs:
            driver.get(href)
            select_elements = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME,'select')))
            timeout = Select( select_elements[2] )
            timeout.select_by_value('20')

            for protcol,[_,temp] in self.protcols.items():
                selection = Select(select_elements[0])
                if ( protcol == "HTTP[S]" ):
                    selection.select_by_visible_text("HTTP/HTTPS")
                    sleep(2.5)
                else:
                    selection.select_by_visible_text(protcol)
                    sleep(5.5)

                proxy_element = driver.find_element(By.CLASS_NAME,'inner')
                actions.click(proxy_element).key_down(Keys.CONTROL).send_keys('c').key_up(Keys.CONTROL).perform()
                with open(f'{temp}','a') as f:
                    f.write(pyperclip.paste())
                    print(f'Writing {protcol} proxies to file')
                    
        self.cleanup()

        display.stop()
        driver.quit()
        print(f'Finished saving proxies, ending session')

    def cleanup(self):
        print(f'Cleaning duplicates')
        for protcol,[pp,tp] in self.protcols.items():
            os.system(f'awk \'!seen[$0]++\' {pp} > {tp}')
            print(f'Finished cleaning duplicates for {protcol}')
            print(f"Unique {protcol} Proxies : {os.popen(f'cat {pp} | wc -l').read().rstrip()}")
            print(f"Total {protcol} Proxies : {os.popen(f'cat {tp} | wc -l').read().rstrip()}")
        self.shuffle_file()

    def get(self):
        # Using socks then http proxies
        if os.stat(self.http_proxy_path).st_size == 0: # Checking HTTP and reading socks
            self.load_proxies()
            with open(self.sock_proxy_path,'r') as f:
                proxy = f.readline().rstrip
                print(f'Removing used SOCKS5 proxy')
                os.system(f'tail -n +2 "{self.sock_proxy_path}" > {self.tmp_path}')
                os.system(f'cat {self.tmp_path} > {self.sock_proxy_path}')
                return proxy
        elif os.stat(self.sock_proxy_path).st_size == 0: # Checking socks and reading http
            with open(self.http_proxy_path,'r') as f:
                proxy = f.readline().rstrip()
                print(f'Removing used HTTP[S] proxy')
                os.system(f'tail -n +2 "{self.http_proxy_path}" > {self.tmp_path}')
                os.system(f'cat {self.tmp_path} > {self.http_proxy_path}')
                return proxy
        else:
            with open(self.sock_proxy_path,'r') as f: # Reading socks
                proxy = f.readline().rstrip()
                print(f'Removing used SOCKS5 proxy')
                os.system(f'tail -n +2 "{self.sock_proxy_path}" > {self.tmp_path}')
                os.system(f'cat {self.tmp_path} > {self.sock_proxy_path}')
                return proxy

    def shuffle_file(self):
        for protcol,[pp,_] in self.protcols.items():
            print(f'Shuffling {protcol} proxies')
            lines = open(pp).readlines()
            shuffle(lines)
            open(pp,'w').writelines(lines)
