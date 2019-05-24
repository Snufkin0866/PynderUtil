from datetime import datetime, timedelta
import random
from util import PynderUtil, TinderDBManager
import place
from time import sleep

def regular_task():
    print('start regular task')
    pynder_util = PynderUtil()
    db_manager = TinderDBManager()
    first_messages = db_manager.get_first_contact_messages()
    target_place = place.AOGAKU
    lat = target_place[0]
    lon = target_place[1]
    pynder_util.like_nearby_user(lat, lon)
    since = datetime.today() - timedelta(days=900)
    new_users = pynder_util.get_new_users(since=since)
    for u in new_users: # 新しいマッチがある場合，その人たちにメッセージを送る．
        first_message_index = random.choice(first_messages.index.values.tolist())
        first_message_list = first_messages.loc[first_message_index].dropna().values.tolist()
        print(f'Sending message to {u.user.name}')
        for m in first_message_list:
            u.message(m)
            sleep(1)
    matches = pynder_util.session.matches()
    db_manager.save_all_messages(matches)


if __name__ == '__main__':
    while True:
        regular_task()
        sleep(43201)