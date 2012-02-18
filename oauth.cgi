#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import urllib
import oauth2 as oauth
import sqlite3

request_token_url = 'http://twitter.com/oauth/request_token'
access_token_url = 'http://twitter.com/oauth/access_token'
authenticate_url = 'http://twitter.com/oauth/authenticate'

consumer_key = '**********'
consumer_secret = '**********'


def getOAuth():
    consumer = oauth.Consumer(key=consumer_key, secret=consumer_secret)
    client = oauth.Client(consumer)
    # reqest_token を取得
    resp, content = client.request(request_token_url, 'GET')
    request_token = dict(parse_qsl(content))

    # 認証ページに遷移
    url = '%s?oauth_token=%s' % (authenticate_url, request_token['oauth_token'])
    print '<meta http-equiv="refresh"content="1; url=%s">' % url

    # request_token と request_token_secret を保存
    con = sqlite3.connect('oauth.db')
    con.execute(u'insert into oauth values (?, ?)', (request_token['oauth_token'], request_token['oauth_token_secret']))
    con.commit()
    con.close()

def parse_qsl(url):
    param = {}
    for i in url.split('&'):
        _p = i.split('=')
        param.update({_p[0]: _p[1]})
    return param

if __name__ == '__main__':
    print 'Content-type: text/html; charset: utf-8'
    print
    print '<link rel="shortcut icon" href="pika_shi.ico">'
    getOAuth()
