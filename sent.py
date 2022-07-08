from datetime import datetime
import json
import os
import re

from lxml import etree
import requests

import utils

import schedule
import time

# 定义你要周期运行的函数
def job():
    print("I'm working...")

# schedule.every().hour.do(job)                    # 每隔 1 小时运行一次 job 函数
# schedule.every().day.at("10:30").do(job)         # 每天在 10:30 时间点运行 job 函数
# schedule.every().monday.do(job)                  # 每周一 运行一次 job 函数
# schedule.every().wednesday.at("13:15").do(job)   # 每周三 13：15 时间点运行 job 函数
# schedule.every().minute.at(":17").do(job)        # 每分钟的 17 秒时间点运行 job 函数



BASE_URL = 'https://s.weibo.com'
JSON_DIR = './raw'
ARCHIVE_DIR = './archives'
THREAD_HOLD = 1000*10000


def getHTML(url):
    ''' 获取网页 HTML 返回字符串

    Args:
        url: str, 网页网址
    Returns:
        HTML 字符串
    '''
    # Cookie 有效期至2023-02-10
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36',
        'Cookie': 'SUB=_2AkMVWDYUf8NxqwJRmP0Sz2_hZYt2zw_EieKjBMfPJRMxHRl-yj9jqkBStRB6PtgY-38i0AF7nDAv8HdY1ZwT3Rv8B5e5; SUBP=0033WrSXqPxfM72-Ws9jqgMF55529P9D9WFencmWZyNhNlrzI6f0SiqP'
    }
    response = requests.get(url, headers=headers)
    if response.encoding == 'ISO-8859-1':
        response.encoding = response.apparent_encoding if response.apparent_encoding != 'ISO-8859-1' else 'utf-8'
    return response.text


# 使用 xpath 解析 HTML
def parseHTMLByXPath(content):
    ''' 使用 xpath 解析 HTML, 提取榜单信息

    Args:
        content: str, 待解析的 HTML 字符串
    Returns:
        榜单信息的字典 字典
    '''
    html = etree.HTML(content)

    titles = html.xpath(
        '//tr[position()>1]/td[@class="td-02"]/a[not(contains(@href, "javascript:void(0);"))]/text()')
    hrefs = html.xpath(
        '//tr[position()>1]/td[@class="td-02"]/a[not(contains(@href, "javascript:void(0);"))]/@href')
    hots = html.xpath(
        '//tr[position()>1]/td[@class="td-02"]/a[not(contains(@href, "javascript:void(0);"))]/../span/text()')
    titles = [title.strip() for title in titles]
    hrefs = [BASE_URL + href.strip() for href in hrefs]
    hots = [int(hot.strip().split(' ')[-1])
            for hot in hots]  # 该处除了热度还会返回大致分类，形如 `剧集 53412536`，前为分类，后为热度

    correntRank = {}
    for i, title in enumerate(titles):
        correntRank[title] = {'href': hrefs[i], 'hot': hots[i]}

    return correntRank


# 更新本日榜单
def updateJSON(correntRank):
    ''' 更新当天的 JSON 文件

    Args:
        correntRank: dict, 最新的榜单信息
    Returns:
        与当天历史榜单对比去重, 排序后的榜单信息字典
    '''
    filename = datetime.today().strftime('%Y%m%d') + '.json'
    filename = os.path.join(JSON_DIR, filename)

    # 文件不存在则创建
    if not os.path.exists(filename):
        utils.save(filename, {})

    historyRank = json.loads(utils.load(filename))
    for k, v in correntRank.items():
        # 若当前榜单和历史榜单有重复的，取热度数值(名称后面的数值)更大的一个
        if k in historyRank:
            historyRank[k]['hot'] = max(
                historyRank[k]['hot'], correntRank[k]['hot'])
        # 若没有，则添加
        else:
            historyRank[k] = v

    # 将榜单按 hot 值排序
    rank = {k: v for k, v in sorted(
        historyRank.items(), key=lambda item: item[1]['hot'], reverse=True)}

    # 更新当天榜单 json 文件
    utils.save(filename, rank)
    return rank


def updateReadme(rank):
    ''' 更新 README.md

    Args:
        rank: dict, 榜单信息
    Returns:
        None
    '''
    filename = './README.md'

    line = '1. [{title}]({href}) {hot}'
    lines = [line.format(title=k, hot=v['hot'], href=v['href'])
             for k, v in rank.items()]
    rank = '\n'.join(lines)

    rank = '最后更新时间 {}\n\n'.format(
        datetime.now().strftime('%Y-%m-%d %X')) + rank
    rank = '<!-- Rank Begin -->\n\n' + rank + '\n<!-- Rank End -->'

    content = re.sub(
        r'<!-- Rank Begin -->[\s\S]*<!-- Rank End -->', rank, utils.load(filename))
    utils.save(filename, content)

def sentWX(title,link,hotvalue):
    print("调用微信发送消息")
    url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=01e2cfba-e610-47e6-a5c9-e936256ad968"
    headers = {'Content-Type': 'application/json;charset=utf-8'}
    date_news = {
    "msgtype": "news",
    "news": {
       "articles" : [
           {
               "title" : title,
               "description" : "当前微博热度为: "+str(hotvalue),
               "url" : link,
               "picurl": "http://resou.today/zb_users/upload/2022/06/202206061654521216577463.jpg",
           }
        ]
    }
}
    # data_text = {
    #     "msgtype": "text",
    #     "text": {
    #         "content": content, #文本内容，最长不超过2048个字节，必须是utf8编码
    #         # "mentioned_list":["wangqing","@all"],               #userid的列表,@指定人员，@all表示提醒所有人
    #         "mentioned_mobile_list":["@all"]      #手机号列表,@指定人员，@all表示提醒所有人
    #     }
    # }
    r = requests.post(url,data=json.dumps(date_news),headers=headers)
    print(r.text)
    return r.text


def updateTodayJSON(correntRank):
    ''' 更新当天的 JSON 文件

        Args:
            correntRank: dict, 最新的榜单信息
        Returns:
            与当天历史榜单对比去重, 排序后的榜单信息字典
        '''
    print("执行更新逻辑")
    filename = datetime.today().strftime('%Y%m%d') + '.json'
    filename = os.path.join(JSON_DIR, filename)

    # 文件不存在则创建
    if not os.path.exists(filename):
        utils.save(filename, {})

    historyRank = json.loads(utils.load(filename))
    for k, v in correntRank.items():
        # 若当前榜单和历史榜单有重复的，取热度数值(名称后面的数值)更大的一个
        if k in historyRank:
            historyRank[k]['hot'] = max(
                historyRank[k]['hot'], correntRank[k]['hot'])
        # 若没有，则添加
        else:
            # 不存在于历史且大于两千万 则发送报警
            if correntRank[k]['hot'] > THREAD_HOLD: sentWX(k,correntRank[k]['href'],correntRank[k]['hot'])
            historyRank[k] = v

    # 将榜单按 hot 值排序
    rank = {k: v for k, v in sorted(
        historyRank.items(), key=lambda item: item[1]['hot'], reverse=True)}

    # 更新当天榜单 json 文件
    utils.save(filename, rank)
    return rank


def update():
    url = '/top/summary'
    content = getHTML(BASE_URL + url)
    contentRank = parseHTMLByXPath(content)
    updateTodayJSON(contentRank)

schedule.every(60*1).seconds.do(update)

def deleteJson():
    print("执行删除逻辑")
    filename = int(datetime.today().strftime('%Y%m%d'))-1
    filename =  str(filename)+ '.json'

    dir = os.path.join(JSON_DIR, filename)

    # 文件存在则创建
    if os.path.exists(dir):
        os.remove(dir)
        print(filename+"----->已被删除")
    else:print("文件不存在")

schedule.every().day.at("10:00").do(deleteJson)

def main():
    while True:
        schedule.run_pending()  # 运行所有可以运行的任务
        time.sleep(10)


if __name__ == '__main__':
    main()
