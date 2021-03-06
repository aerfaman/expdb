import io
import re
import time
import zipfile
import os
import requests_html
from config.setting import START_EXPLOIT_DB_ID, END_EXPLOIT_DB_ID, get_random_user_agent, PATH_SPLIT
from dao.src_db_dao import EDBDao, DBInit
from model.src_db_model import EdbRecord


# exploitdb代码收集类
class EdbOnlineCollector:
    def __init__(self):
        self.db_init = DBInit()
        self.edb_dao = EDBDao(self.db_init.session)

        self.session = requests_html.HTMLSession()
        self.session.keep_alive = False
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.170 Safari/537.36',
        }

    # 遍历id从start_exploit_db_id到end_exploit_db_id的所有exp
    def traversal_exploit(self,start_exploit_db_id, end_exploit_db_id):
        #session = requests_html.HTMLSession()
        #session.keep_alive = False
        for exploit_db_id in range(start_exploit_db_id,end_exploit_db_id):
            exploit_record = self.parse_exploit(exploit_db_id)
            result = self.edb_dao.add(exploit_record)
            if result == 1000:
                print(f"insert error: record {exploit_record.edb_id} existed ")
            elif result == 5000:
                print(f"{exploit_record.edb_id} commit exception, process force to exit since the db session have been disconnect")
            time.sleep(1)

    # 检测exploitdb更新使用此函数
    def trace_edb_exploit(self):
        # 追踪四大分类更新页面
        url_xpath = {
            "https://www.exploit-db.com/remote/":"/html/body/div[1]/div/div/main/section/div/table/tbody/tr/td[5]/a/@href",
            "https://www.exploit-db.com/webapps/":"/html/body/div[1]/div/div/main/section/div/table/tbody/tr/td[5]/a/@href",
            "https://www.exploit-db.com/local/":"/html/body/div[1]/div/div/main/section/div/table/tbody/tr/td[5]/a/@href",
            "https://www.exploit-db.com/dos/":"/html/body/div[1]/div/div/main/section/div/table/tbody/tr/td[5]/a/@href"
        }
        for k,v in url_xpath.items():
            self.trace_edb_exploit_sub(k,v)

    # 供trace_edb_exploit调用
    def trace_edb_exploit_sub(self,url,xpath):
        exploit_page = self.request_deal_timeout(url)
        exploit_urls = exploit_page.html.xpath(xpath)
        edb_id_pattern = "\d+"
        for exploit_url in exploit_urls:
            edb_id = re.findall(edb_id_pattern, exploit_url)[0]
            exploit_record = self.parse_exploit(edb_id)
            result = self.edb_dao.add(exploit_record)
            if result == 1000:
                print(f"insert error: record {exploit_record.edb_id} existed ")
                break
            elif result == 5000:
                print(f"{exploit_record.edb_id} commit exception")
                # self.db_init = DBInit()
                # # self.db_init.recreate_session()
                # self.edb_dao = EDBDao(self.db_init.session)
            time.sleep(1)

    # 处理超时报错
    def request_deal_timeout(self,url):
        try:
            headers = {
                'user-agent':get_random_user_agent(),
            }
            proxy = {
                'http':'127.0.0.1:8080',
                'https':'127.0.0.1:8080'
            }
            # page = self.session.get(url,proxies=proxy,headers=headers)
            page = self.session.get(url, headers=headers,verify=False)
            return page
        except:
            page = self.request_deal_timeout(url)
            return page

    # 获取xpath结果第一个节点的值
    def get_first_value(self,elements):
        try:
            value = elements[0].strip()
        except:
            value = ""
        return value

    # 解析exp页面获取exp记录
    def parse_exploit(self,exploit_db_id):
        edb_url = f"https://www.exploit-db.com/exploits/{exploit_db_id}/"
        print(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())} start to parse {edb_url}')
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.170 Safari/537.36',
        }
        element_xpath = {
            'edb_id': '/html/body//table[@class="exploit_list"]/tr[1]/td[1]/text()',
            'edb_author': '/html/body//table[@class="exploit_list"]/tr[1]/td[2]/a/text()',
            'edb_published': '/html/body//table[@class="exploit_list"]/tr[1]/td[3]/text()',
            'edb_cve': '/html/body//table[@class="exploit_list"]/tr[2]/td[1]/a/text()',
            'cve_mitre_url': '/html/body//table[@class="exploit_list"]/tr[2]/td[1]/a/@href',
            'edb_type': '/html/body//table[@class="exploit_list"]/tr[2]/td[2]/a/text()',
            'edb_platform': '/html/body//table[@class="exploit_list"]/tr[2]/td[3]/a/text()',
            'edb_aliases': '/html/body//table[@class="exploit_list"]/tr[3]/td[1]/text()',
            'advisory_or_source': '/html/body//table[@class="exploit_list"]/tr[3]/td[2]/a/@href',
            'edb_tags': '/html/body//table[@class="exploit_list"]/tr[3]/td[3]/text()',
            'edb_verified3': '/html/body//table[@class="exploit_list"]/tr[3]/td[1]/a/img/@alt',
            'edb_verified4': '/html/body//table[@class="exploit_list"]/tr[4]/td[1]/a/img/@alt',
            'edb_exploit_raw_url3': '/html/body//table[@class="exploit_list"]/tr[3]/td[2]/a[2]/@href',
            'edb_exploit_raw_url4': '/html/body//table[@class="exploit_list"]/tr[4]/td[2]/a[2]/@href',
            'edb_vulnerable_app_url3': '/html/body//table[@class="exploit_list"]/tr[3]/td[3]/a/@href',
            'edb_vulnerable_app_url4': '/html/body//table[@class="exploit_list"]/tr[4]/td[3]/a/@href',
            'table_tr':'/html/body//table[@class="exploit_list"]/tr'
        }
        # session = requests_html.HTMLSession()
        # session.keep_alive = False

        exploit_page = self.request_deal_timeout(edb_url)
        content_type = exploit_page.headers["content-type"]
        # 处理非html页面。形如https://www.exploit-db.com/exploits/45608/
        if "html" not in content_type:
            download_dir = "download_files"
            if not os.path.exists(download_dir):
                os.mkdir(download_dir)
            file_name = exploit_page.url.rsplit('/', 1)[1]
            if not os.path.exists(f'{download_dir}{PATH_SPLIT}{file_name}'):
                # 下载zip文件
                if "zip" in file_name:
                    zip_file = zipfile.ZipFile(io.BytesIO(content_type.content))
                    zip_file.extractall(download_dir)
                    os.rename("master",file_name)
                else:
                    open(f'{download_dir}{PATH_SPLIT}{file_name}', 'wb').write(exploit_page.content)
            exploit_record = EdbRecord(edb_id=exploit_db_id)
            return exploit_record
        if exploit_page.status_code != 200:
            print(f"request error {exploit_page.status_code}")
            exploit_record = EdbRecord(edb_id=exploit_db_id)
            return exploit_record

        # 处理不存在但status_code仍为200的页面。形如https://www.exploit-db.com/exploits/45634/
        try:
            edb_id = exploit_page.html.xpath(element_xpath['edb_id'])[0].strip(':').strip()
        except:
            print("request error，maybe this page have been remove")
            exploit_record = EdbRecord(edb_id=exploit_db_id)
            return exploit_record
        edb_author = self.get_first_value(exploit_page.html.xpath(element_xpath['edb_author']))
        edb_published = exploit_page.html.xpath(element_xpath['edb_published'])[0].strip(':').strip()
        try:
            edb_cve = self.get_first_value(exploit_page.html.xpath(element_xpath['edb_cve']))
            cve_mitre_url = self.get_first_value(exploit_page.html.xpath(element_xpath['cve_mitre_url']))
            cve_cvedetails_url = f"https://www.cvedetails.com/edb_cve/{edb_cve}"
        except:
            edb_cve = 'N/A'
            cve_mitre_url = 'N/A'
            cve_cvedetails_url = 'N/A'
        edb_type = self.get_first_value(exploit_page.html.xpath(element_xpath['edb_type']))
        edb_platform = self.get_first_value(exploit_page.html.xpath(element_xpath['edb_platform']))
        table_tr_count = len(exploit_page.html.xpath(element_xpath['table_tr']))
        if table_tr_count == 3:
            edb_aliases = 'N/A'
            edb_advisory_or_source_url= 'N/A'
            edb_tags = 'N/A'
        else:
            edb_aliases = self.get_first_value(exploit_page.html.xpath(element_xpath['edb_aliases']))
            edb_advisory_or_source_url = self.get_first_value(exploit_page.html.xpath(element_xpath['advisory_or_source']))
            edb_tags = self.get_first_value(exploit_page.html.xpath(element_xpath['edb_tags']))
        edb_verified = self.get_first_value(exploit_page.html.xpath(element_xpath[f'edb_verified{table_tr_count}']))
        edb_exploit_raw_url = self.get_first_value(exploit_page.html.xpath(element_xpath[f'edb_exploit_raw_url{table_tr_count}']))
        edb_vulnerable_app_url = self.get_first_value(exploit_page.html.xpath(element_xpath[f'edb_vulnerable_app_url{table_tr_count}']))



        exploit_raw_tmp = self.request_deal_timeout(edb_exploit_raw_url)
        edb_exploit_raw = exploit_raw_tmp.text
        # logging.warning(f"edb_exploit_raw length:{len(edb_exploit_raw)}")
        if len(edb_exploit_raw) < 65535:
            edb_exploit_raw = exploit_raw_tmp.text
        else:
            # edb_exploit_raw = "this exp is out off limit length 16777215 bytes"
            edb_exploit_raw = edb_exploit_raw[0:66635]

        edb_collect_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        exploit_record = EdbRecord(edb_id=edb_id, edb_url=edb_url, edb_author=edb_author, edb_published=edb_published, edb_cve=edb_cve,
                                   edb_type=edb_type, edb_platform=edb_platform, edb_aliases=edb_aliases,
                                   edb_advisory_or_source_url=edb_advisory_or_source_url, edb_tags=edb_tags, edb_verified=edb_verified,
                                   edb_vulnerable_app_url=edb_vulnerable_app_url,edb_exploit_raw_url=edb_exploit_raw_url,
                                   edb_exploit_raw=edb_exploit_raw,edb_collect_date=edb_collect_date)
        # session.close()
        return exploit_record

    def __del__(self):
        pass

# 运行此文件即会自动收集exploit的exp
if __name__ == "__main__":
    edb_collect = EdbOnlineCollector()
    # 起始exp由setting的START_EXPLOIT_DB_ID决定
    start_exploit_db_id = START_EXPLOIT_DB_ID
    # 终止exp由setting的END_EXPLOIT_DB_ID决定
    end_exploit_db_id = END_EXPLOIT_DB_ID
    edb_collect.traversal_exploit(start_exploit_db_id,end_exploit_db_id)
    # url = "https://www.exploit-db.com/exploits/45638/"
    # exploit_record = edb_collect.parse_exploit(url)
    # print(f"exploit_record ={exploit_record}")
