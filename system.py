# -*- coding:utf-8 -*-

from datetime import datetime, date
import time
import socket
import re
import collections
import math
import urllib2
import MeCab
from svm import *
from svmutil import *
import twitter

# タイムアウトを設定
socket.setdefaulttimeout(30)

# ストップワードリスト
f = open('stopwords.txt', 'r')
stopword_list = [stopword.strip() for stopword in f]
f.close()

# 写真投稿サービスのURL
photo_url_list = ['http://twitpic.com/', 'http://movapic.com/',
              'http://f.hatena.ne.jp/', 'http://www.mobypicture.com/'
              'http://yfrog.com/', 'http://www.bcphotoshare.com/',
              'http://img.ly/', 'http://twitgoo.com/',
              'http://imgur.com/', 'http://lockerz.com/',
              'http://pic.twitter.com']

class System(object):
    def __init__(self, api):
        'コンストラクタ'
        self.api = api
        # TLを取得(100件)
        self.TL = api.GetFriendsTimeline(count=100, retweets=True)
        # ログイン時間を取得
        self.login_time = int(time.time())

    def classify(self):
        # 特徴ベクトルを取得
        data_list = self._GetFeatureVector()
        # 訓練データを取得
        m_list = self._SVMLearn()
        data_class = [1] * len(self.TL)
        result_list = []
        value_span = [2419200] * len(self.TL)
        for m in m_list:
            result_list.append(svm_predict(data_class, data_list, m)[0])
        # 10分, 1時間, 6時間, 1日, 1週間, それ以降 (秒)
        span_list = [600, 3600, 21600, 86400, 604800]
        # どの程度のスパンで時間依存性を考えるか
        user_span = 1800
        for i, tweet in enumerate(self.TL):
            for j in range(5):
                if result_list[j][i] == -1:
                    value_span = span_list[j]
                    break
        valist = []
        for tweet in self.TL:
            time_span = self.login_time - tweet.created_at_in_seconds
            if time_span > value_span:
                # もう見なくてよい
                valist.append(2)
            elif time_span + user_span > value_span:
                # 今見るべき
                valist.append(0)
            else:
                # 後で見てもよい
                valist.append(1)
        return self.TL, valist

    def _GetFeatureVector(self):
        '特徴ベクトルを生成'
        # SVMの特徴ベクトルを格納
        data_list = []
        # タームの上昇度を格納
        hotscore_dict = self._CalcHotScore()
        # ツイートの投稿時間を格納 {id:posttime,..}
        id_dict = self._GetPostTime()
        for tweet in self.TL:
            # 各特徴量を格納
            valist = [0] * 5
            # 文字数
            valist[0] = math.log(len(tweet.text), 140)
            # タームの上昇度
            valist[1] = self._GetHotScore(tweet, hotscore_dict)
            # 会話の時間間隔
            valist[2] = self._GetIntervalTime(tweet, id_dict)
            # 写真,urlを含むかどうか
            valist[3], valist[4] = self._GetURL(tweet)
            # 特徴量をリストに加える
            data_list.append(valist)
        return data_list

    def _SVMLearn(self):
        train_list, class_list = self._SVMTrain()
        m_list = []
        parameter = svm_parameter('-h 0')
        for i in range(5):
            problem = svm_problem(class_list[i], train_list)
            m_list.append(svm_train(problem, parameter))
        return m_list

    def _SVMTrain(self):
        '訓練データを生成'
        f = open('svm_train.txt', 'r')
        class_list = [[] for i in range(5)]
        train_list = []
        for i in f:
            train_list.append([float(i[23:31]), float(i[71:79]), float(i[97:105]), float(i[145]), float(i[150])])
            val = int(i[19])
            for c, j in enumerate(class_list):
                if val >= c+2:
                    j.append(1)
                else:
                    j.append(-1)
        return train_list, class_list

    def _CalcHotScore(self):
        'タームの上昇度を計算'
        hotscore_dict = collections.defaultdict(int)
        mecab = MeCab.Tagger()
        for tweet in self.TL:
            node = mecab.parseToNode(tweet.text.encode('utf-8'))
            node = node.next
            while node:
                # 名詞, 動詞, 形容詞を抽出, ストップワードは除去
                if (node.feature.split(',')[0] == ('名詞' or '動詞' or '形容詞') and
                    node.surface not in stopword_list):
                    # スコアを加算
                    hotscore_dict[node.surface] += 1.0 / ((self.login_time - tweet.created_at_in_seconds) / 60 + 1)
                node = node.next
        return hotscore_dict

    def _GetPostTime(self):
        'ツイートの投稿日時を格納'
        posttime_dict = {}
        for tweet in self.TL:
            posttime_dict[tweet.id] = tweet.created_at_in_seconds
        return posttime_dict

    def _GetHotScore(self, tweet, hotscore_dict):
        'タームの上昇度を取得'
        hotscore = 0
        mecab = MeCab.Tagger()
        node = mecab.parseToNode(tweet.text.encode('utf-8'))
        node = node.next
        # ターム上昇度の最大値をそのツイートの最大値とする
        while node:
            if hotscore_dict[node.surface] > hotscore:
                hotscore = hotscore_dict[node.surface]
            node = node.next
        return hotscore

    def _GetIntervalTime(self, tweet, id_dict):
        'リプライの場合,リプライ元との時間間隔を取得'
        if tweet.in_reply_to_status_id in id_dict:
            # 1時間で正規化
            val = (tweet.created_at_in_seconds - id_dict[tweet.in_reply_to_status_id]) / 3600.0
            return min(1.0, val)
        else:
            # リプライでない場合,値を1に設定
            return 1.0

    def _GetURL(self, tweet):
        'ツイートに含まれる写真,urlを取得'
        photo_val, url_val = 0, 0
        if 'http://' in tweet.text:
            url_val = 1.0
            # urlの開始位置
            st = tweet.text.find('http://')
            # urlの終了位置
            en = len(tweet.text)
            if ' ' in tweet.text[st:]:
                en = st + tweet.text[st:].find(' ') + 1
            if u'　' in tweet.text[st:]:
                en = min(en, st + tweet.text.find(u'　') + 1)
            try:
                # urlを取得
                url = urllib2.urlopen(tweet.text[st:en]).geturl()
                # urlが写真かどうか判定
                for photo_url in photo_url_list:
                    if photo_url in url:
                        photo_val = 1.0
                        url_val = 0.0
            except:
                pass
        return photo_val, url_val

if __name__ == '__main__':
    CONSUMER_KEY="gtCXsTWe36CVbW5XzatYSg"
    CONSUMER_SECRET="igYhRFLGC3aeGnNst8VbWOVbbrK854NRtlJvravO8U"
    ACCESS_TOKEN="141077154-YAcEuL6qZIifys2jN4vLqrtTsWrgQHQiM8qbXrch"
    ACCESS_TOKEN_SECRET="Ry09sYcYuh9cWEldXsmQn9ooJVlkIspxbQUHyX0Ls"
    api = twitter.Api(consumer_key=CONSUMER_KEY,
                      consumer_secret=CONSUMER_SECRET,
                      access_token_key=ACCESS_TOKEN,
                      access_token_secret=ACCESS_TOKEN_SECRET,
                      cache=None)
    system = System(api)
    system.classify()
