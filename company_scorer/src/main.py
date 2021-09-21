#!/usr/bin/env python3

import undetected_chromedriver.v2 as uc
import sys
import os
import re
import pandas as pd
import requests
import backoff
from time import sleep
from pathlib import Path
from joblib import Parallel,delayed
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException,WebDriverException

def backoff_hdlr(details):
    print ("Backing off {wait:0.1f} seconds after {tries} tries".format(**details))

class score():

    def __init__(self,company=None):
        self.period = sys.argv[1]
        self.company = company
        self.src_dir = os.path.dirname(os.path.realpath(__file__))
        self.asset_dir = f"{os.path.join(os.path.realpath(self.src_dir + '/../'),'assets')}"
        self.variable_path = f"{(os.path.join(os.path.realpath(self.src_dir + '/../'), 'assets'))}/variables.txt"
        self.variables = {}
        self.score = 0
        self.terminate = False
        if Path(f'{self.asset_dir}/scores.txt'):
            pass
        else:
            with open(f'{self.asset_dir}/scores.txt','w') as f:
                pass

    def get(self,company):
        # Initalizing driver
        self.company = company
        driver = self.setup(first=True)

        # Getting symbol and exchange of company
        _ = self.initalize_company(driver)

        if self.terminate:
            return

        # Setting up variables for links
        with open(self.variable_path) as f:
            for line in f:
                (key,val1,val2) = line.split()
                key = key.replace("{period}",self.period)
                val1 = val1.replace("{symbol}",self.symbol)
                val1 = val1.replace("{company}",self.company)
                val1 = val1.replace("{exchange}",self.exchange)
                val1 = val1.replace("{period}",self.period)
                self.variables[key] = (val1,val2)

        # Getting sharpe ratio
        sharpe_key = list(self.variables.keys())[0]
        main = self.get_sharpe(sharpe_key,self.variables[sharpe_key][0],float(self.variables[sharpe_key][1]),driver)

        # Getting ESG scores
        esg_key = list(self.variables.keys())[1]
        main = pd.concat([main,self.get_esg(esg_key,self.variables[esg_key][0],float(self.variables[esg_key][1]),driver)],axis=1)

        # Getting sentiment scores
        sentiment = self.get_sentiment(0.01)
        main = pd.concat([main,sentiment],axis=1)
        driver.quit()

        variables = dict(list(self.variables.items())[2:])
        for key,[val1,val2] in variables.items():
            main = pd.concat([main,self.get_data(key,val1,val2)],axis=1)
            with open(f"{self.asset_dir}/{self.company}.html",'w') as f:
                f.write(main.to_html())

        with open(f"{self.asset_dir}/scores.txt",'a') as f:
            f.write(f'{self.company} Score : {self.score}')
            f.write("\n")

        main = pd.concat([main,pd.DataFrame(self.score,columns=main.columns,index=["Score"])])

    def setup(self,first=False):
        if first:
            options = Options()
            options.add_argument('--incognito')
            options.add_argument('--headless')
            options.add_argument('--disable-extensions')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36')
            options.add_argument('--no-first-run --no-service-autorun --password-store=basic')
            options.page_load_strategy = 'eager'
            driver = webdriver.Chrome(options=options)
            driver.delete_all_cookies
            return driver
        else:
            options = uc.ChromeOptions()
            options.add_argument('--incognito')
            options.add_argument('--disable-extensions')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36')
            options.add_argument('--no-first-run --no-service-autorun --password-store=basic')
            options.page_load_strategy = 'eager'
            driver = uc.Chrome(options=options,headless=True)
            #  driver = uc.Chrome(options=options,headless=False)
            driver.delete_all_cookies
            return driver

    def initalize_company(self,driver):
        wait = WebDriverWait(driver, 10)
        link = "https://finance.yahoo.com"
        driver.get(link)
        search_input = wait.until(EC.element_to_be_clickable((By.XPATH,'//input[@id="yfin-usr-qry"]')))
        ActionChains(driver).send_keys_to_element(search_input,self.company).perform()
        sleep(2)
        ActionChains(driver).send_keys_to_element(search_input,Keys.ENTER).perform()
        try:
            symbol_element = wait.until(lambda d: d.find_element(By.XPATH,'//div[@class="D(ib) "]/h1'))
            self.symbol = re.search(r'\((.*)\)',symbol_element.text).group(1)
            exchange_element = wait.until(lambda d:d.find_element(By.XPATH,'//div[@class="C($tertiaryColor) Fz(12px)"]/span'))
            self.exchange = re.search(r'(^.*?)\s',exchange_element.text).group(1)
        except TimeoutException:
            self.terminate = True

    def get_sharpe(self,v,link,weight,driver):
        driver.get(link)
        try:
            elements = WebDriverWait(driver,10).until(EC.presence_of_all_elements_located((By.XPATH,'//p[@class="MuiTypography-root MuiTypography-body1 MuiTypography-paragraph"]/b')))
            sharpe = float( elements[1].text )
            if ( sharpe > 3.5 ):
                sharpe = 3.5
            normalized_sharpe = sharpe/3.5 * 100
        except TimeoutException:
            sharpe = "N/A"
            normalized_sharpe = 0

        self.score+=normalized_sharpe*weight
        df = pd.DataFrame({f'{v}{period}' : [sharpe,"N/A",normalized_sharpe*weight,normalized_sharpe,"N/A"]},index=["Raw","Percentile","Weighted Sub-Score","Normalized","Troubleshoot"])
        return df

    def get_esg(self,v,link,weight,driver):
        driver.get(link)
        wait = WebDriverWait(driver,10)
        search_input = wait.until(EC.element_to_be_clickable((By.ID,'searchInput')))
        ActionChains(driver).send_keys_to_element(search_input,self.company).send_keys_to_element(search_input,Keys.ENTER).perform()
        try:
            href = wait.until(EC.element_to_be_clickable((By.CLASS_NAME,'search-link'))).get_attribute('href')
            driver.get(href)
            position = wait.until(EC.presence_of_element_located((By.CLASS_NAME,'industry-group-position'))).text
            total = wait.until(EC.presence_of_element_located((By.CLASS_NAME,'industry-group-positions-total'))).text
            esg_percentile = 100-( ( int( position )/int( total ) )*100 )
            esg_raw = f'{position}/{total}'
            driver.quit()

        except TimeoutException:
            esg_percentile = 0
            esg_raw = "No data"

        self.score+=esg_percentile*weight
        df = pd.DataFrame({v : [esg_raw,esg_percentile,esg_percentile*weight,"N/A","N/A"]},index=["Raw","Percentile","Weighted Sub-Score","Normalized","Troubleshoot"])
        return df

    def get_sentiment(self,weight):
        token = ''
        key = ''
        check_link = f'https://api.sentimentinvestor.com/v4/supported?symbol={self.symbol}&token={token}&key={key}'
        response = requests.get(check_link)
        if ( response.json()['result'] ):
            api_link = f'https://api.sentimentinvestor.com/v4/parsed?symbol={self.symbol}&token={token}&key={key}'
            data = requests.get(api_link).json() 
            if data['success']:
                AHI = data['results']['AHI']
                RHI = data['results']['RHI']
                sentiment = data['results']['sentiment']
                sentiment = 63.52
                SGP = data['results']['SGP']
                sub_df = pd.DataFrame({'Sentiment Subscores' : [AHI,RHI,sentiment,SGP]},index=["AHI","RHI","sentiment","SGP"])
                with open(f"{self.asset_dir}/{self.company}_SENT.html",'w') as f:
                    f.write(sub_df.to_html())
                self.score+=float(sentiment)*weight
                df = pd.DataFrame({f'Sentiment' : [sentiment,"N/A",float( sentiment )*weight,sentiment,"N/A"]},index=["Raw","Percentile","Weighted Sub-Score","Normalized","Troubleshoot"])
                return df

    @backoff.on_exception(backoff.expo,TimeoutException,on_backoff=backoff_hdlr)
    @backoff.on_exception(backoff.expo,WebDriverException,on_backoff=backoff_hdlr)
    def get_data(self,v,link,weight):
        driver = self.setup()
        with driver:
            driver.get(link)
            wait = WebDriverWait(driver,6)
            action = ActionChains(driver)
            button = wait.until(EC.element_to_be_clickable((By.XPATH,'//button[@class="_2R9Lw _1nM4t"]')))
            action.click(button).perform()
            industry = (lambda e:e[2])( wait.until(lambda d: d.find_elements(By.XPATH,'//div[@class="bp3-text-overflow-ellipsis bp3-fill"]')) )
            action.move_to_element(industry).click().perform()
            try:
                percentile_element = (lambda e:e[1])( wait.until(lambda d:d.find_elements(By.XPATH,'//div[@class="_3MBK8"]/p')) )
                percentile_text = percentile_element.text
                try:
                    raw = re.search(r'(\d.*\.\d).*?(is|ranks)',percentile_text).group(1)
                except AttributeError:
                    try:
                        raw = re.search(r'(\d.*\d).*?(is|ranks)',percentile_text).group(2)
                    except AttributeError:
                        raw = "N/A"

                if ( percentile_text.find('excluded') + 1 ):
                    percentile = 100
                else:
                    try:
                        percentile = re.search(r'(1\d.\.\d*)% percentile',percentile_text).group(1)
                        self.NA=False
                    except AttributeError:
                        try:
                            percentile = re.search(r'(\d.\.\d*)% percentile',percentile_text).group(1)
                            self.NA=False
                        except AttributeError:
                            try:
                                percentile = re.search(r'(\d\.\d)% percentile',percentile_text).group(1)
                                self.NA=False
                            except AttributeError:
                                percentile = 0
                                self.NA=True

                if ( v[-3:] == "[R]" and not( self.NA ) ):
                    percentile = 100.0 - float( percentile )
                else:
                percentile_text = percentile_text.replace(percentile_text[-55:],'')

            except TimeoutException:
                na_element = wait.until(lambda d: d.find_element(By.XPATH,'//p[@class="_2pFoe"]'))
                percentile_text = na_element.text
                raw = "N/A"
                percentile = 0

            self.score+=float(percentile)*float(weight)
            df = pd.DataFrame({f'{v}{self.period}' : [raw,percentile,float(percentile)*float(weight),"N/A",percentile_text]},index=["Raw","Percentile","Weighted Sub-Score","Normalized","Troubleshoot"])

        return df

if __name__ == '__main__':
    src_dir = os.path.dirname(os.path.realpath(__file__))
    asset_dir = f"{os.path.join(os.path.realpath(src_dir + '/../'),'assets')}"
    period = sys.argv[1]
    filepath = f'{asset_dir}/companies.txt'
    with open(filepath,'r') as f:
        companies = f.readlines()
        for company in companies:
            score().get(company.rstrip())
