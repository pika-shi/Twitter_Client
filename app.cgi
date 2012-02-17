#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import os
import oauth2 as oauth
import sqlite3
import twitter
import re
from system import System
import Cookie
import cgi
import cgitb
import time
cgitb.enable()

request_token_url = 'http://twitter.com/oauth/request_token'
access_token_url = 'http://twitter.com/oauth/access_token'

consumer_key = 't8OrZ1q3NSkAZVeG2g4Ew'
consumer_secret = 'cwJwSo6Qfhrf8w45XbFmDcts0dMIdQnNfQdsKdGzjr4'

sc=Cookie.SimpleCookie(os.environ.get('HTTP_COOKIE',''))

# reply, url の正規表現
regex1 = re.compile('@\w+')
regex2 = re.compile('http[A-Za-z0-9\'~+\-=_.,/%\?!;:@#\*&\(\)]+')

def callback():
    # Cookieがあれば取得
    if sc.has_key('access_token') and sc.has_key('access_token_secret'):
        return sc.get('access_token').value, sc.get('access_token_secret').value

    # oauth_token と oauth_verifier を取得
    if 'QUERY_STRING' in os.environ:
        query = cgi.parse_qs(os.environ['QUERY_STRING'])
    else:
        query = {}

    # oauth_token_secret を取得
    con = sqlite3.connect('oauth.db')
    oauth_token_secret = con.execute(
        u'select oauth_token_secret from oauth where oauth_token = ?'
        , [query['oauth_token'][0]]).fetchone()[0]
    con.close()

    # access_token と access_token_secret を取得
    consumer = oauth.Consumer(key=consumer_key, secret=consumer_secret)
    token = oauth.Token(query['oauth_token'][0], query['oauth_verifier'][0])
    client = oauth.Client(consumer, token)
    resp, content = client.request(access_token_url, "POST", body="oauth_verifier=%s" % query['oauth_verifier'][0])
    access_token = dict(parse_qsl(content))
    sc['access_token'], sc['access_token_secret'] = access_token['oauth_token'], access_token['oauth_token_secret']

    return access_token['oauth_token'], access_token['oauth_token_secret']

def get_timeline(access_token_key, access_token_secret):
    'TLを取得しhtmlに埋め込む'
    api = twitter.Api(consumer_key=consumer_key,
                      consumer_secret=consumer_secret,
                      access_token_key=access_token_key,
                      access_token_secret=access_token_secret,
                      cache=None)
    system = System(api)
    print '<!--'
    # TLとそのvalueを習得
    # 0 今見るべき 1 後で見てもよい 2 もう見なくてよい
    TL, valist = system.classify()
    print '-->'
    timeline = ["" for i in range(3)]
    for c, tweet in enumerate(TL):
        tweet_text = tweet.text.encode('utf-8')
        # リンク情報を付加
        tweet_text = add_link(tweet_text)
        # 投稿日時を取得
        tweet_time = time.ctime(tweet.created_at_in_seconds)
        timeline[valist[c]] += '''<div class="tweet">
                                      <img width="60" height="60" src="{0}">
                                      <div class="screen_name">
                                          <a target="_blank" style="text-decoration: none;" href="http://twitter.com/\x23!/{1}"><b>{1}</b></a>
                                          <font size="2">　{2}</font><br>
                                      </div>
                                      {3}<br>
                                      <br clear="all">
                                  </div>'''.format(tweet.user.profile_image_url,
                                                   tweet.user.screen_name, tweet_time, tweet_text)
    return timeline

def add_link(tweet_text):
    'リンク情報を付加'
    scanner1 = regex1.scanner(tweet_text)
    scanner2 = regex2.scanner(tweet_text)
    # reply
    match = scanner1.search()
    while match:
        tweet_text = tweet_text.replace(match.group(0),
            '<a target="_blank" style="text-decoration: none;" href="http://twitter.com/\x23!/{0}">@{0}</a>'.format(match.group(0)[1:]))
        match = scanner1.search()
    # url
    match = scanner2.search()
    while match:
        tweet_text = tweet_text.replace(match.group(0),
            '<a target="_blank" style="text-decoration: none;" href="{0}">{0}</a>'.format(match.group(0)))
        match = scanner2.search()
    return tweet_text

def parse_qsl(url):
    param = {}
    for i in url.split('&'):
        _p = i.split('=')
        param.update({_p[0]: _p[1]})
    return param

def print_header():
    'ヘッダを出力'
    print 'Content-type: text/html; charset: utf-8'
    print sc.output()
    print

# html source
html = '''<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8"/>
        <title>Client</title>
        <link rel="stylesheet" href="./style.css" type="text/css">
        <link rel="shortcut icon" href="pika_shi.ico">
        <script type="text/javascript"><!--
        function ChangeTab(tab) {
            // 全部消す
            document.getElementById("tab1").style.display = "none";
            document.getElementById("tab2").style.display = "none";
            document.getElementById("tab3").style.display = "none";
            // 指定箇所のみ表示
            document.getElementById(tab).style.display = "block";
        }
        // --></script>
    </head>
    <body link="deepskyblue" vlink="deepskyblue">
        <div class="tabbox">
            <p class="tabs">
                <b>
                    <a href="\x23tab1" onclick="ChangeTab('tab1'); return false;">今見るべき</a>
                    <a href="\x23tab2" onclick="ChangeTab('tab2'); return false;">後で見てもよい</a>
                    <a href="\x23tab3" onclick="ChangeTab('tab3'); return false;">もう見なくてよい</a>
                </b>
            </p>
            <div id="tab1" class="tab">
                %s
            </div>
            <div id="tab2" class="tab">
                %s
            </div>
            <div id="tab3" class="tab">
                %s
            </div>
        </div>

        <script type="text/javascript"><!--
            // デフォルトのタブを選択
            ChangeTab("tab1");
        // --></script>
    </body>
</html>
'''

if __name__ == '__main__':
    # コールバック
    access_token_key, access_token_secret = callback()
    # ヘッダを出力
    print_header()
    # TLを取得
    timeline = get_timeline(access_token_key, access_token_secret)
    # htmlを出力
    print html % (timeline[0], timeline[1], timeline[2])

