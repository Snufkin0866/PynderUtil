import re
from time import sleep
import robobrowser
from logging import getLogger, FileHandler, StreamHandler, Formatter, DEBUG
from datetime import datetime, timedelta
import sqlite3
import pynder
import pandas as pd
import sys
sys.path.append('../')

from pynder import Session
from fb_config import FB_ID, FB_MAIL, FB_PASS




class PynderUtil(object):

    def __init__(self, session=None):
        if session is None:
            print(f'FB MAIL: {FB_MAIL}, FB_PASS: {FB_PASS}')
            self.session = Session(self.get_fb_token(FB_MAIL, FB_PASS))
        else:
            self.session = session
        self.logger = self.get_logger()

    def get_logger(self):
        logger = getLogger('util')
        logger.setLevel(DEBUG)
        handler1 = StreamHandler()
        handler1.setFormatter(Formatter("%(asctime)s %(levelname)8s %(message)s"))
        handler2 = FileHandler(filename="pynder_util.log")  # handler2はファイル出力
        handler2.setFormatter(Formatter("%(asctime)s %(levelname)8s %(message)s"))
        logger.addHandler(handler1)
        logger.addHandler(handler2)
        return logger

    def get_fb_token(self, fb_mail, fb_pass):
        MOBILE_USER_AGENT = "Mozilla/5.0 (Linux; U; en-gb; KFTHWI Build/JDQ39) AppleWebKit/535.19 (KHTML, like Gecko) Silk/3.16 Safari/535.19"
        FB_AUTH = "https://www.facebook.com/v2.6/dialog/oauth?redirect_uri=fb464891386855067%3A%2F%2Fauthorize%2F&display=touch&state=%7B%22challenge%22%3A%22IUUkEUqIGud332lfu%252BMJhxL4Wlc%253D%22%2C%220_auth_logger_id%22%3A%2230F06532-A1B9-4B10-BB28-B29956C71AB1%22%2C%22com.facebook.sdk_client_state%22%3Atrue%2C%223_method%22%3A%22sfvc_auth%22%7D&scope=user_birthday%2Cuser_photos%2Cuser_education_history%2Cemail%2Cuser_relationship_details%2Cuser_friends%2Cuser_work_history%2Cuser_likes&response_type=token%2Csigned_request&default_audience=friends&return_scopes=true&auth_type=rerequest&client_id=464891386855067&ret=login&sdk=ios&logger_id=30F06532-A1B9-4B10-BB28-B29956C71AB1&ext=1470840777&hash=AeZqkIcf-NEW6vBd"
        s = robobrowser.RoboBrowser(user_agent=MOBILE_USER_AGENT, parser="lxml")
        s.open(FB_AUTH)
        ##submit login form##
        f = s.get_form()
        f["pass"] = fb_pass
        f["email"] = fb_mail
        s.submit_form(f)
        ##click the 'ok' button on the dialog informing you that you have already authenticated with the Tinder app##
        f = s.get_form()
        s.submit_form(f, submit=f.submit_fields['__CONFIRM__'])
        ##get access token from the html response##
        access_token = re.search(r"access_token=([\w\d]+)", s.response.content.decode()).groups()[0]
        return access_token

    def like_nearby_user(self, lat, lon):
        self.session.update_location(lat, lon)
        users = self.session.nearby_users()
        liked_users = []
        for u in users:
            remaining = self.session.likes_remaining
            if not remaining:
                self.logger.info(f'All of your like is used. Remaining: {remaining}')
                break
            u.like()
            self.logger.info(f'Common connections: {u.common_connections}')
            self.logger.info(f'Sending like to {u.name}. Remaining number of likes: {remaining}')
            sleep(1)
            liked_users.append(u)
        return liked_users

    def get_new_users(self, since:datetime):
        """sinceより後にマッチしたユーザのうち，まだメッセージを送っていないユーザを取得．
        """
        matches = self.session.matches(since=since.isoformat() + 'Z')
        new_users = []
        for m in matches:
            if not len(m.messages):
                self.logger.info(f'Listing new user: {m}')
                new_users.append(m)
        return new_users

    def send_messages_to_users(self, users, messages):
        for u in users:
            for m in messages:
                self.logger.info(f'Sending message "{m}" to {u}')
                u.message(m)
        return users, messages

    def get_reactions(self, matches):
        """指定されたマッチのメッセージに対する反応を返す．最終メッセージが相手からのものから探す．

        Arguments:
            user {models.User} -- ユーザオブジェクト
        """
        for m in matches:
            if len(m.messages): # やり取りをした相手だけ．
                self.logger.info(f'Getting reaction of {m.user.name}')
                reactions = []
                for mess in m.messages[::-1]:
                    if mess.sender.id != self.session.profile.id:
                        reactions.append(mess)
                    else:
                        break
        return reactions

    def get_match_by_id(self, id):
        """idからマッチを取得．該当ユーザがいなかった場合はNoneを返す．

        Arguments:
            id {[type]} -- [description]
        """
        for m in self.session.matches():
            if m.user.id == id:
                return m
        return None

    def get_contacted_matches(self):
        matches = self.session.matches()
        contacted_matches = []
        for m in matches:
            if len(m.messages):
                contacted_matches.append(m)
        return contacted_matches


class TinderDBManager():

    def __init__(self, file_path='./data/tinder_data.db'):
        self.file_path = file_path
        self.con = sqlite3.connect(file_path)
        self.cur = self.con.cursor()
        self.message_table ='messages'
        create_table = f'''create table if not exists {self.message_table} (timestamp real, id text, sender text, receiver text, content text)'''
        self.cur.execute(create_table)

    def __del__(self):
        self.con.close()

    def save_message(self, message: pynder.models.Message):
        """メッセージをdbに保存
        idで識別して，まだないものだけを保存
        Arguments:
            message {pynder.models.Message} -- [description]

        Returns:
            [type] -- [description]
        """
        message_info = (message.sent.timestamp(), message.id, message.sender.id, message.to.id, message.body)
        if not self.is_exist_id(message.id):
            sql = f'insert into {self.message_table} (timestamp, id, sender, receiver, content) values (?,?,?,?,?)'
            self.cur.execute(sql, message_info)
            print(f'Saving info:{message_info}')
        self.con.commit()
        return message_info

    def save_personal_info(self):
        return

    def save_all_messages(self, matches):
        for m in matches:
            for mess in m.messages:
                self.save_message(mess)
        return

    def is_exist_id(self, id):
        sql = f'SELECT id FROM {self.message_table} WHERE id = "{id}"'
        self.cur.execute(sql)
        if len(self.cur.fetchall()):
            return True
        else:
            return False

    def get_first_contact_messages(self, file_name='./data/first_messages.csv'):
        messages_df = pd.read_csv(file_name, encoding="utf-8", index_col='Index')
        return messages_df

if __name__ == '__main__':
    util = PynderUtil()
    print(util.get_fb_token(FB_MAIL, FB_PASS))
    '''
    db_manager = TinderDBManager()
    matches = util.session.matches()
    # db_manager.save_all_messages(matches)
    df = db_manager.get_first_contact_messages()
    print(df["1"])
    print(df["2"])
    '''
