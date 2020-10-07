from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.utils.browser import Browser

def atomy_login(username, password):
    browser = Browser()
    browser.get('https://www.atomy.kr/v2/Home/Account/Login')
    user_field = browser.find_element_by_id('userId')
    password_field = browser.find_element_by_id('userPw')
    user_field.send_keys(username)
    password_field.send_keys(password)
    password_field.submit()
    try:
        WebDriverWait(browser, 10).until(
            EC.url_to_be('https://www.atomy.kr/v2/Home')
        )
    except:
        raise AttributeError('Login failed')
    finally:
        browser.close()
