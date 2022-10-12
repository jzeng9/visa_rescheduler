# -*- coding: utf8 -*-

import time
import json
import random
import platform
import configparser
from datetime import datetime

import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait as Wait
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


config = configparser.ConfigParser()
config.read('config.ini')

USERNAME = config['USVISA']['USERNAME']
PASSWORD = config['USVISA']['PASSWORD']
SCHEDULE_ID = config['USVISA']['SCHEDULE_ID']
MY_SCHEDULE_DATE = config['USVISA']['MY_SCHEDULE_DATE']
COUNTRY_CODE = config['USVISA']['COUNTRY_CODE'] 
FACILITY_ID = config['USVISA']['FACILITY_ID']

SENDGRID_API_KEY = config['SENDGRID']['SENDGRID_API_KEY']
PUSH_TOKEN = config['PUSHOVER']['PUSH_TOKEN']
PUSH_USER = config['PUSHOVER']['PUSH_USER']

LOCAL_USE = config['CHROMEDRIVER'].getboolean('LOCAL_USE')
HUB_ADDRESS = config['CHROMEDRIVER']['HUB_ADDRESS']

REGEX_CONTINUE = "//*[contains(text(),'Groups')]"


# def MY_CONDITION(month, day): return int(month) == 11 and int(day) >= 5
# def MY_CONDITION(month, day): return int(month) >= 10

def MY_CONDITION(appointmentTime):
    return appointmentTime > datetime.strptime("2022-10-01", "%Y-%m-%d")

STEP_TIME = 0.5  # time between steps (interactions with forms): 0.5 seconds
RETRY_TIME = 60*10  # wait time between retries/checks for available dates: 10 minutes
EXCEPTION_TIME = 60*30  # wait time when an exception occurs: 30 minutes
COOLDOWN_TIME = 60*60  # wait time when temporary banned (empty list): 60 minutes

PAY_URL = f"https://ais.usvisa-info.com/{COUNTRY_CODE}/niv/"
DATE_URL = f"https://ais.usvisa-info.com/{COUNTRY_CODE}/niv/schedule/{SCHEDULE_ID}/appointment/days/{FACILITY_ID}.json?appointments[expedite]=false"
TIME_URL = f"https://ais.usvisa-info.com/{COUNTRY_CODE}/niv/schedule/{SCHEDULE_ID}/appointment/times/{FACILITY_ID}.json?date=%s&appointments[expedite]=false"
APPOINTMENT_URL = f"https://ais.usvisa-info.com/{COUNTRY_CODE}/niv/schedule/{SCHEDULE_ID}/appointment"
EXIT = False

def  snap(): time.sleep(random.randint(1, 3))


def send_notification(msg):
    print(f"Sending notification: {msg}")

    if SENDGRID_API_KEY:
        message = Mail(
            from_email=USERNAME,
            to_emails=USERNAME,
            subject=msg,
            html_content=msg)
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e.message)

    if PUSH_TOKEN:
        url = "https://api.pushover.net/1/messages.json"
        data = {
            "token": PUSH_TOKEN,
            "user": PUSH_USER,
            "message": msg
        }
        requests.post(url, data)


def get_driver():
    if LOCAL_USE:
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    else:
        PROXY = "<HOST:PORT>"
        from selenium.webdriver.common.proxy import Proxy, ProxyType
        prox = Proxy()
        prox.proxy_type = ProxyType.MANUAL
        prox.http_proxy = HUB_ADDRESS
        prox.https_proxy = HUB_ADDRESS
        prox.ftp_proxy = HUB_ADDRESS
        prox.ssl_proxy = HUB_ADDRESS
        prox.auto_detect = False

        capabilities = webdriver.DesiredCapabilities.CHROME
        prox.add_to_capabilities(capabilities)
        # webdriver.DesiredCapabilities.CHROME['proxy'] = {
        #     "httpProxy": HUB_ADDRESS,
        #     "ftpProxy": HUB_ADDRESS,
        #     "sslProxy": HUB_ADDRESS,
        #     "proxyType": "MANUAL",
        # }
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), desired_capabilities=capabilities)

driver = get_driver()


def login():
    # Bypass reCAPTCHA
    driver.get(f"https://ais.usvisa-info.com/{COUNTRY_CODE}/niv")
    time.sleep(STEP_TIME)
    a = driver.find_element(By.XPATH, '//a[@class="down-arrow bounce"]')
    a.click()
    time.sleep(STEP_TIME)

    print("Login start...")
    href = driver.find_element(By.XPATH, '//*[@id="header"]/nav/div[2]/div[1]/ul/li[3]/a')
    href.click()
    time.sleep(STEP_TIME)
    Wait(driver, 60).until(EC.presence_of_element_located((By.NAME, "commit")))

    print("\tclick bounce")
    a = driver.find_element(By.XPATH, '//a[@class="down-arrow bounce"]')
    a.click()
    time.sleep(STEP_TIME)

    do_login_action()

def do_login_action():
    print("\tinput email")
    user = driver.find_element(By.ID, 'user_email')
    user.send_keys(USERNAME)
    time.sleep(random.randint(1, 3))

    print("\tinput pwd")
    pw = driver.find_element(By.ID, 'user_password')
    pw.send_keys(PASSWORD)
    time.sleep(random.randint(1, 3))

    print("\tclick privacy")
    box = driver.find_element(By.CLASS_NAME, 'icheckbox')
    box .click()
    time.sleep(random.randint(1, 3))

    print("\tcommit")
    btn = driver.find_element(By.NAME, 'commit')
    btn.click()
    time.sleep(random.randint(1, 3))

    Wait(driver, 60).until(
        EC.presence_of_element_located((By.XPATH, REGEX_CONTINUE)))
    print("\tlogin successful!")

def move_to_date_page():
    print("\t start to move")
    driver.find_element(By.CSS_SELECTOR, '.button.primary.small').click()
    # driver.find_element(By.XPATH, '//a[contains(text(),"Continue")]').click()
    print("\t hit continue")
    snap()
    driver.find_element(By.CLASS_NAME, 'accordion-item').click()
    print("\t expand pay visa fee")
    snap()
    driver.find_element(By.CSS_SELECTOR, '.button.small.primary.small-only-expanded').click() 
    print("\t hit pay visa fee")
    snap()


def get_date():
    snap()
    driver.get("https://www.whatismyipaddress.com")
    while 1:
        pass
    driver.get(PAY_URL)
    if not is_logged_in():
        login()
        return get_date()
    else:
        # move to the pay detailed page
        move_to_date_page()
        print("\t load table")
        rows = driver.find_elements(By.XPATH, '//*[@id="paymentOptions"]/div[2]/table/tbody/tr')
        snap()
        def process(row):
            return (row.find_element(By.XPATH, './td[1]').text, row.find_element(By.XPATH, './td[2]').text)
        return [process(i) for i in rows]

# return filter(lambda x: x[1] == "No Appointments Avaliable", data)


def get_time(date):
    time_url = TIME_URL % date
    driver.get(time_url)
    content = driver.find_element(By.TAG_NAME, 'pre').text
    data = json.loads(content)
    time = data.get("available_times")[-1]
    print(f"Got time successfully! {date} {time}")
    return time

def is_logged_in():
    content = driver.page_source
    if(content.find("Groups") == -1):
        return False
    return True

last_seen = {}

def get_available_date(inputs):
    global last_seen

    def is_earlier_old(date):
        my_date = datetime.strptime(MY_SCHEDULE_DATE, "%Y-%m-%d")
        new_date = datetime.strptime(date, "%d %B, %Y")
        result = my_date > new_date
        print(f'Is {my_date} > {new_date}:\t{result}')
        return result
    
    def is_earlier(a, b):
        my_date = datetime.strptime(b, "%d %B, %Y")
        new_date = datetime.strptime(a, "%d %B, %Y")
        result = my_date > new_date
        print(f'Is {my_date} > {new_date}:\t{result}')
        return result 

    dates = list(filter(lambda x: x[1] != "No Appointments Available", inputs))
    print("Checking for an earlier date:")
    res = []
    for (city, date) in dates:
        if is_earlier_old(date) and (city not in last_seen or date != last_seen[city]):
            datetime_obj = datetime.strptime(date, "%d %B, %Y")
            if MY_CONDITION(datetime_obj):
                last_seen[city] = date
                res.append((city, date))
    return res


def push_notification(dates):
    msg = "new avaliable dates: "
    for k in last_seen:
        msg = msg + k + ' ' + last_seen[k] + '; '
    send_notification(msg)


if __name__ == "__main__":
    login()
    retry_count = 0
    while 1:
        if retry_count > 6:
            break
        try:
            print("------------------")
            print(datetime.today())
            print(f"Retry count: {retry_count}")
            print()

            dates = get_date()
            if not dates:
                print("List is empty")
                msg = "List is empty"
                send_notification(msg)
                EXIT = True
                print("cool down")
                time.sleep(COOLDOWN_TIME)
                break
            results = get_available_date(dates)
            print()
            print(f"Avaliables: {results}")
            if results:
                push_notification(results)
            else:
                print("no avaliable dates, retry")
                time.sleep(RETRY_TIME)

        except:
            retry_count += 1
            time.sleep(EXCEPTION_TIME)

    if(not EXIT):
        send_notification("HELP! Crashed.")
