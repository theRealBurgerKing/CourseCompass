from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time

executable_path = '/opt/homebrew/bin/chromedriver'

chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9229")

service = Service(executable_path=executable_path)
browser = webdriver.Chrome(service=service, options=chrome_options)


# ========= 第一步：获取所有课程代码 =========
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


# ========= 第二步：抓单门课详细信息 =========
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

    def get_texts(xpath):
        try:
            elements = browser.find_elements(By.XPATH, xpath)
            return [e.text.strip() for e in elements if e.text.strip()]
        except:
            return []

    # 展开所有 toggle
    toggles = browser.find_elements(By.XPATH, '//*[contains(@id,"_toggle")]')
    for toggle in toggles:
        browser.execute_script("arguments[0].scrollIntoView();", toggle)
        browser.execute_script("arguments[0].click();", toggle)
        time.sleep(1)

    time.sleep(1)

    # 重新找并提取内容
    delivery = []
    toggles = browser.find_elements(By.XPATH, '//*[contains(@id,"_toggle")]')
    for toggle in toggles:
        try:
            parent = toggle.find_element(By.XPATH, '..')
            siblings = parent.find_elements(By.XPATH, './*')
            if len(siblings) >= 2:
                content = siblings[1].text.strip()
                # 提取标题
                display = toggle.text.replace('keyboard_arrow_down', '').strip()
                # 用正则提取各字段
                import re
                mode = re.search(r'Delivery Mode(.+?)(?:Delivery Format|$)', content, re.DOTALL)
                fmt = re.search(r'Delivery Format(.+?)(?:Indicative Contact Hours|$)', content, re.DOTALL)
                hours = re.search(r'Indicative Contact Hours(.+?)$', content, re.DOTALL)
                delivery.append({
                    'display': display,
                    'delivery_mode': mode.group(1).strip() if mode else '',
                    'delivery_format': fmt.group(1).strip() if fmt else '',
                    'contact_hours': hours.group(1).strip() if hours else ''
                })
        except:
            continue

    # 抓 equivalent courses
    equiv_elements = browser.find_elements(By.XPATH, '//*[@id="EquivalentCourses"]/div[2]/div//a')
    equivalent_courses = []
    for e in equiv_elements:
        try:
            # 只取课程代码，格式类似 ENGG9020
            code_element = e.find_element(By.XPATH, './/div[contains(@class,"code") or contains(text(),"COMP") or contains(text(),"ENGG") or contains(text(),"MATH")]')
            equivalent_courses.append(code_element.text.strip())
        except:
            # 备用：用正则从文字里提取课程代码
            import re
            text = e.text
            codes = re.findall(r'[A-Z]{4}\d{4}', text)
            equivalent_courses.extend(codes)

    data = {
        'course_code': course_code,
        'url': url,
        'course_name': get_text('//*[@id="academic-item-banner"]/div/div/h2'),
        'units_of_credit': get_text('//*[contains(text(),"Units of Credit")]'),
        'overview': get_text('//*[@id="Overview"]/div[2]/div[2]/div/p[1]'),
        'additional_enrolment_constraints': get_text('//*[@id="AdditionalEnrolmentConstraints"]/div[2]/div[2]/div'),
        'equivalent_courses': equivalent_courses,
        'delivery': delivery,
        'offering_terms': get_text('//*[contains(text(),"Offering Terms")]/following-sibling::*[1]'),
        'campus': get_text('//*[contains(text(),"Campus")]/following-sibling::*[1]'),
        'faculty': get_text('//*[@id="flex-around-rhs"]/aside/div[1]/div[1]/div/div[2]/div/a'),
        'notes': get_text('//*[@id="Notes"]/div[2]/div[2]/div'),
    }

    return data


# ========= 主流程 =========
course_codes = get_all_course_codes()

results = []
for code in course_codes:
    try:
        data = scrape_course(code)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        results.append(data)
    except Exception as e:
        print(f'{code} 抓取失败: {e}')
    time.sleep(2)

# 保存为 JSON
with open('unsw_8543_courses.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f'\n完成！共抓取 {len(results)} 门课程')
print('已保存到 unsw_8543_courses.json')