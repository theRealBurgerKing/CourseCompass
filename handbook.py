from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

executable_path = '/opt/homebrew/bin/chromedriver'

chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9229")

service = Service(executable_path=executable_path)
browser = webdriver.Chrome(service=service, options=chrome_options)

# ========= 第一步：从专业页面抓所有课程代码 =========
def get_all_course_codes():
    url = 'https://www.handbook.unsw.edu.au/postgraduate/specialisations/2026/COMPMS'
    print('正在获取课程列表...')
    browser.get(url)
    time.sleep(3)

    # 点击所有 Expand all 按钮
    expand_buttons = browser.find_elements(By.XPATH, '//button[contains(text(),"Expand all")]')
    print(f'找到 {len(expand_buttons)} 个 Expand all 按钮')
    for btn in expand_buttons:
        try:
            browser.execute_script("arguments[0].click();", btn)
            time.sleep(1)
        except:
            pass

    time.sleep(2)

    # 找所有课程链接
    links = browser.find_elements(By.XPATH, '//a[contains(@href, "/postgraduate/courses/")]')
    
    course_codes = []
    for link in links:
        href = link.get_attribute('href')
        if href:
            code = href.split('/')[-1]
            if code not in course_codes:
                course_codes.append(code)

    print(f'找到 {len(course_codes)} 门课程: {course_codes}')
    return course_codes

# ========= 第二步：逐一抓每门课的详细信息 =========
def scrape_course(course_code):
    url = f'https://www.handbook.unsw.edu.au/postgraduate/courses/2026/{course_code}'
    print(f'正在抓取：{course_code}')
    browser.get(url)

    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.ID, 'academic-item-banner'))
    )
    time.sleep(2)

    def get_text(xpath):
        try:
            return browser.find_element(By.XPATH, xpath).text.strip()
        except:
            return ''

    return {
        'course_code': course_code,
        'course_name': get_text('//*[@id="academic-item-banner"]/div/div/h2'),
        'units_of_credit': get_text('//*[contains(text(),"Units of Credit")]'),
        'overview': get_text('//*[@id="Overview"]/div[2]/div[2]/div/p[1]'),
        'offering_terms': get_text('//*[contains(text(),"Offering Terms")]/following-sibling::*[1]'),
        'campus': get_text('//*[contains(text(),"Campus")]/following-sibling::*[1]'),
        'faculty': get_text('//*[@id="flex-around-rhs"]/aside/div[1]/div[1]/div/div[2]/div/a'),
    }

# ========= 主流程 =========
course_codes = get_all_course_codes()

results = []
for code in course_codes:
    try:
        data = scrape_course(code)
        print(data)
        results.append(data)
    except Exception as e:
        print(f'{code} 抓取失败: {e}')
    time.sleep(2)

df = pd.DataFrame(results)
df.to_csv('unsw_8543_courses.csv', index=False, encoding='utf-8-sig')
print(f'\n完成！共抓取 {len(df)} 门课程')
print(df)