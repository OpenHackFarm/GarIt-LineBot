# -*- coding: utf-8 -*-

#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from __future__ import unicode_literals

import errno
import os
import sys
import tempfile
from argparse import ArgumentParser
from urllib.parse import parse_qs
import requests
import pymysql
from dateutil import parser
import datetime

from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    LineBotApiError, InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    SourceUser, SourceGroup, SourceRoom,
    TemplateSendMessage, ConfirmTemplate, MessageAction,
    ButtonsTemplate, ImageCarouselTemplate, ImageCarouselColumn, URIAction,
    PostbackAction, DatetimePickerAction,
    CameraAction, CameraRollAction, LocationAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage, FileMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent,
    FlexSendMessage, BubbleContainer, ImageComponent, BoxComponent,
    TextComponent, SpacerComponent, IconComponent, ButtonComponent,
    SeparatorComponent, QuickReply, QuickReplyButton,
    PostbackTemplateAction, ImageSendMessage, URITemplateAction, MessageTemplateAction
)

from config import *

app = Flask(__name__)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

weather_station_dict = {
    'CWB': '中央氣象局',
}

week_day_dict = {
    0 : '日',
    1 : '一',
    2 : '二',
    3 : '三',
    4 : '四',
    5 : '五',
    6 : '六',
}


# function for create tmp dir for download content
def make_static_tmp_dir():
    try:
        os.makedirs(static_tmp_path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(static_tmp_path):
            pass
        else:
            raise


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except LineBotApiError as e:
        print("Got exception from LINE Messaging API: %s\n" % e.message)
        for m in e.error.details:
            print("  %s: %s" % (m.property, m.message))
        print("\n")
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    text = event.message.text

    if text == 'Weather':
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_DB, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
        c = conn.cursor()
        c.execute("SELECT * FROM user_weather_locations WHERE line_id = '%s'" % event.source.user_id)
        rows = c.fetchall()

        if len(rows) is 0:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='您好，初次使用，請參考如何訂閱氣象站，謝謝。\nhttps://i.imgur.com/gYMVUia.png'))
        else:
            columns = []

            for row in rows:
                if row['station_source'] == 'CWB':
                    url = 'http://52.183.94.1:8001/?backend=%s&get=current&q={"name":"%s"}' % (row['station_source'], row['station_name'])
                else:
                    #TODO: complete weather proxy
                    continue

                r = requests.get(url)
                json_data = r.json()

                text = """溫度：%s ℃
溼度：%s %%
""" % (json_data['temperature_c'], json_data['humidity'])

                if 'rain_24hr_mm' in json_data:
                    text = text + '降雨：%s mm\n' % json_data['rain_24hr_mm']
                elif 'rain' in json_data:
                    text = text + '降雨：%s mm\n' % json_data['rain']

                if 'datetime' in json_data:
                    dt = parser.parse(json_data['datetime'])
                elif 'time' in json_data:
                    dt = parser.parse(json_data['time'])

                columns.append(
                    CarouselColumn(title='%s - %s (時間：%s)' % (row['station_source'], row['station_name'], dt.strftime('%H:%M')),
                                   text=text,
                                   actions=[
                                       PostbackTemplateAction(label='一週預報', data='action=forecast&lat=%s&lng=%s' % (row['user_lat'], row['user_lng'])),
                                       PostbackTemplateAction(label='在地農民曆', data='action=crops_suggestion&station_id=%s&station_name=%s' % (row['station_id'], row['station_name']))
                                   ]
                ))

            carousel_template = CarouselTemplate(columns=columns)
            template_message = TemplateSendMessage(
                alt_text='Weather', template=carousel_template)
            line_bot_api.reply_message(event.reply_token, template_message)
    elif text == 'Farm':
        buttons_template = ButtonsTemplate(
            title='農場管理', text='管理農場與作物生長記錄', actions=[
                URITemplateAction(
                    label='建立農場', uri='https://www.openhackfarm.tw/onsen/field_add.html?token=' + event.source.user_id),
                URITemplateAction(
                    label='種植新作物', uri='https://www.openhackfarm.tw/onsen/planting_add.html?token=' + event.source.user_id),
                MessageTemplateAction(label='我的作物', text='Plantings'),
            ])
        template_message = TemplateSendMessage(
            alt_text='Farm Management', template=buttons_template)
        line_bot_api.reply_message(event.reply_token, template_message)
    elif text == 'Plantings':
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_DB, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
        c = conn.cursor()
        c.execute("SELECT plantings.*, fields.* FROM plantings, fields WHERE plantings.line_id = '%s' AND crop_name IS NOT NULL AND plantings.end_date IS NULL AND plantings.deleted = 0 AND plantings.field_id = fields.uuid" % event.source.user_id)
        rows = c.fetchall()
        print(rows)
        print(len(rows))

        if len(rows) is 0:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='請新增作物'))
        else:
            columns = []

            # TODO : Line 一次最多只能回傳 10 筆資料，需 loop and push
            for row in rows[0:10]:
                # TODO: Calculate GDD with nearby weather station
                url = 'https://api.openhackfarm.tw/testing/demo/gdd?crop=%s&start_date=%s' % (row['crop'] if row['crop'] else '', row['start_date'])
                r = requests.get(url)
                json_data = r.json()

                title = '%s' % row['crop_name']
                if row['crop_variety']:
                    title = title + ' - %s' % row['crop_variety']
                if row['field_name']:
                    title = title + ' (%s' % row['field_name']
                    if row['bed_no']:
                        title = title + ' - %s' % row['bed_no']
                    title = title + ')'

                text = """種植日期：%s
生長天數：%d
累積溫度：%.2f""" % (row['start_date'].strftime('%Y/%m/%d'), json_data['days'], json_data['cumulative'])

                actions = [
			    URITemplateAction(label='新增記錄', uri='http://www.openhackfarm.tw/onsen/activity_add.html?planting_id=%s' % row['uuid']),
                            PostbackTemplateAction(label='查看報表', data='action=planting_detail&uuid=%s' % row['uuid']),
                            PostbackTemplateAction(label='最近影像', data='action=last_planting_image&uuid=%s' % row['uuid'])
#                            PostbackTemplateAction(label='結束種植', data='action=planting_end&uuid=%s' % row['uuid']),
			  ]

                columns.append(
                    CarouselColumn(title=title,
                                   text=text,
                                   actions=actions)
                )

            carousel_template = CarouselTemplate(columns=columns)
            template_message = TemplateSendMessage(
                alt_text='Plantings', template=carousel_template)
            line_bot_api.reply_message(event.reply_token, template_message)
    elif text == 'qrcode':
        image_message = ImageSendMessage(
            original_content_url='https://qr-official.line.me/L/jMcenk9cBa.png',
            preview_image_url='https://qr-official.line.me/L/jMcenk9cBa.png'
        )
        line_bot_api.reply_message(event.reply_token, image_message)
    else:
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=event.message.text))


@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    buttons_template = ButtonsTemplate(
        title='地理位置搜尋', text='請問您要？', actions=[
            PostbackTemplateAction(label='搜尋氣象站', data='action=search_weather_stations&lat=%s&lng=%s' % (event.
message.latitude, event.message.longitude)),
        ])
    template_message = TemplateSendMessage(
        alt_text='Location Menu', template=buttons_template)
    line_bot_api.reply_message(
        event.reply_token,
        template_message
    )


@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(
            package_id=event.message.package_id,
            sticker_id=event.message.sticker_id)
    )


# Other Message Type
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, AudioMessage))
def handle_content_message(event):
    if isinstance(event.message, ImageMessage):
        ext = 'jpg'
    elif isinstance(event.message, VideoMessage):
        ext = 'mp4'
    elif isinstance(event.message, AudioMessage):
        ext = 'm4a'
    else:
        return

    message_content = line_bot_api.get_message_content(event.message.id)
    with tempfile.NamedTemporaryFile(dir=static_tmp_path, prefix=ext + '-', delete=False) as tf:
        for chunk in message_content.iter_content():
            tf.write(chunk)
        tempfile_path = tf.name

    dist_path = tempfile_path + '.' + ext
    dist_name = os.path.basename(dist_path)
    os.rename(tempfile_path, dist_path)

    line_bot_api.reply_message(
        event.reply_token, [
            TextSendMessage(text='Save content.'),
            TextSendMessage(text=request.host_url + os.path.join('static', 'tmp', dist_name))
        ])


@handler.add(MessageEvent, message=FileMessage)
def handle_file_message(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    with tempfile.NamedTemporaryFile(dir=static_tmp_path, prefix='file-', delete=False) as tf:
        for chunk in message_content.iter_content():
            tf.write(chunk)
        tempfile_path = tf.name

    dist_path = tempfile_path + '-' + event.message.file_name
    dist_name = os.path.basename(dist_path)
    os.rename(tempfile_path, dist_path)

    line_bot_api.reply_message(
        event.reply_token, [
            TextSendMessage(text='Save file.'),
            TextSendMessage(text=request.host_url + os.path.join('static', 'tmp', dist_name))
        ])


@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(
        event.reply_token, TextSendMessage(text='Got follow event'))


@handler.add(UnfollowEvent)
def handle_unfollow():
    app.logger.info("Got Unfollow event")


@handler.add(JoinEvent)
def handle_join(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='Joined this ' + event.source.type))


@handler.add(LeaveEvent)
def handle_leave():
    app.logger.info("Got leave event")


@handler.add(PostbackEvent)
def handle_postback(event):
    data = parse_qs(event.postback.data)

    if data['action'][0] == 'search_weather_stations':
        url = 'http://52.183.94.1:8001/?backend=CWB&get=stations&q={"lat":%s,"lng":%s,"max_distance":7}' % (data['lat'][0], data['lng'][0])
        r = requests.get(url)
        stations = r.json()

        columns = []

        for station in stations:
            text = """地址：%s
距離：%s km""" % (station['address'], station['distance_km'])

            actions = [ PostbackTemplateAction(label='即時天氣', data='action=get_weather_current&station_source=%s&station_id=%s&station_name=%s&user_lat=%s&user_lng=%s' % (station['source'], station['station_id'], station['station_name'], data['lat'][0], data['lng'][0])),
                        PostbackTemplateAction(label='一週預報', data='action=forecast&lat=%s&lng=%s' % (data['lat'][0], data['lng'][0])),
                        PostbackTemplateAction(label='訂閱', data='action=subscribe_weather_station&station_source=%s&station_id=%s&station_name=%s&station_city=%s&user_lat=%s&user_lng=%s' % (station['source'], station['station_id'], station['station_name'], station['city'], data['lat'][0], data['lng'][0]))
    		  ]

            columns.append(
                CarouselColumn(title='%s - %s' % (weather_station_dict[station['source']], station['station_name']),
                               text=text,
                               actions=actions)
            )

        template_message = TemplateSendMessage(
            alt_text='Station List', template=CarouselTemplate(columns=columns))
        line_bot_api.reply_message(event.reply_token, template_message)
    elif data['action'][0] == 'get_weather_current':
        print(data)

        station_source = data['station_source'][0]

        if station_source == 'CWB':
            url = 'http://52.183.94.1:8001/?backend=%s&get=current&q={"name":"%s"}' % (station_source, data['station_name'][0])
        elif station_source == 'CWB_OA':
            url = 'http://52.183.94.1:8001/?backend=%s&get=current&q={"id":"%s"}' % (row['station_source'], row['station_id'])
        elif station_source == 'WU':
            url = 'http://52.183.94.1:8001/?backend=%s&get=current&q={"id":"%s"}' % (row['station_source'], row['station_id'])
        elif station_source == 'OHF':
            url = 'https://api.openhackfarm.tw/testing/demo/davis/latest'

        r = requests.get(url)
        json_data = r.json()
        print(json_data)

        if json_data:
            text = """%s
    ----------------------------------------
    溫度：%s ℃
    溼度：%s %%
    """ % (json_data['station_name'], json_data['temperature_c'], json_data['humidity'])

            if 'rain_24hr_mm' in json_data:
                text = text + '降雨：%s mm\n' % json_data['rain_24hr_mm']
            elif 'rain' in json_data:
                text = text + '降雨：%s mm\n' % json_data['rain']

            text = text + '時間：%s' % json_data['datetime']
        else:
            text = '此氣象站無回應'

        line_bot_api.reply_message(event.reply_token, TextMessage(text=text))
    elif data['action'][0] == 'forecast':
        url = 'http://weather-api.openhackfarm.tw/?backend=ForecastIO&get=forecast&key=3d63fa0b4d55f3be7f594fcfad9a2e06&q={"lat":%s,"lng":%s}' % (data['lat'][0], data['lng'][0])
        r = requests.get(url)
        json_data = r.json()

        text = ''
        columns = []
        for i in range(5):
            dt = parser.parse(json_data[i]['datetime']) + datetime.timedelta(hours=8)

            columns.append(
                CarouselColumn(title='%s (%s)' % (dt.strftime('%-m/%-d'), week_day_dict[int(dt.strftime('%w'))]),
                               text="""天氣狀況：%s
氣溫：%d
降雨機率：%d%%""" % (json_data[i]['condition'], round((json_data[i]['min_temperature_c'] + json_data[i]['max_temperature_c']) / 2), json_data[i]['PoP']),
                               actions=[
                                   URITemplateAction(label='中央氣象局', uri='https://www.cwb.gov.tw/m/f/town368/6300500.php'),
                               ]
            ))

        template_message = TemplateSendMessage(
            alt_text='Forecast', template=CarouselTemplate(columns=columns))
        line_bot_api.reply_message(event.reply_token, template_message)
    elif data['action'][0] == 'subscribe_weather_station':
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_DB, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
        c = conn.cursor()

        c.execute("INSERT INTO user_weather_locations (line_id, station_source, station_id, station_name, station_city, user_lat, user_lng) VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s')" % (event.source.user_id, data['station_source'][0], data['station_id'][0], data['station_name'][0], data['station_city'][0], data['user_lat'][0], data['user_lng'][0]))

        conn.commit()
        conn.close()

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='訂閱成功！可由下方選單內點選觀看即時天氣。'))
    elif data['action'][0] == 'crops_suggestion':
        url = 'https://api.openhackfarm.tw/testing/crops/suggestions/%s_%s' % (data['station_id'][0], data['station_name'][0])
        r = requests.get(url)
        json_data = r.json()

        suggestions_1 = []
        suggestions_2 = []
        suggestions_3 = []
        for c in json_data:
            if c['percent'] >= 90:
                if c['rain_alert'] is True:
                    suggestions_2.append(c['name'].split(',')[0] + '(!)')
                else:
                    suggestions_1.append(c['name'].split(',')[0])
            if 80 <= c['percent'] < 90:
                if c['rain_alert'] is True:
                    suggestions_3.append(c['name'].split(',')[0] + '(!)')
                else:
                    suggestions_3.append(c['name'].split(',')[0])

        text = """適種作物：
    ● %s

    ○ %s""" %  (', '.join(suggestions_1), ', '.join(suggestions_2))

        line_bot_api.reply_message(event.reply_token, TextMessage(text=text))
    elif data['action'][0] == 'planting_detail':
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_DB, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
        c = conn.cursor()
        c.execute("SELECT plantings.*, fields.* FROM plantings, fields WHERE plantings.line_id = '%s' AND plantings.uuid = '%s' AND plantings.field_id = fields.uuid" % (event.source.user_id, data['uuid'][0]))
        planting = c.fetchone()
        print(planting)
        c.execute("SELECT * FROM activities WHERE planting_uuid = '%s' ORDER BY date" % data['uuid'][0])
        activities = c.fetchall()
        print(activities)

        r = requests.get('https://api.openhackfarm.tw/testing/demo/gdd?crop=%s&start_date=%s' % (planting['crop'], planting['start_date']))
        json_data = r.json()

        text = """%s %s
- - - - - - - - - - - - - - - -
田區：%s""" % (planting['crop_name'], '- %s' % planting['crop_variety'] if planting['crop_variety'] else '', planting['field_name'])

        # 植床編號
        if planting['bed_no']:
            text = text + ' - %s' % planting['bed_no']
        text = text + '\n'

        # 種植時間
        text = text + '日期：%s' % planting['start_date'].strftime('%Y/%m/%d')
        if planting['end_date']:
            text = text + ' ~ %s' % planting['end_date']
        text = text + '\n'

        # 累積溫度
        text = text + '生長日數：%d 天 (%.2f ℃ )' % (json_data['days'], json_data['cumulative'])
        text = text + '\n\n'

        # 成長記錄
        outcome = 0
        income = 0
        text = text + '成長記錄：\n'
        for a in activities:
            delta = a['date'] - planting['start_date']
            text = text + '    %s (%s) - ' % (a['date'].strftime('%m/%d'), delta.days)
            if a['action'] and a['comment']:
                text = text + '%s (%s)' % (a['action'], a['comment'])
            elif a['action']:
                text = text + '%s' % (a['action'])
            elif a['comment']:
                text = text + '(%s)' % (a['comment'])
            text = text + '\n'

            if a['outcome']:
                outcome = outcome + a['outcome']
            if a['income']:
                income = income + a['income']

        text = text + '- - - - - - - - - - - - - - - -\n'

        text = text + '支出：\n           $%d\n' % outcome
        text = text + '收入：\n           $%d' % income

        line_bot_api.reply_message(event.reply_token, TextMessage(text=text))
    elif data['action'][0] == 'last_planting_image':
        url = 'https://api.openhackfarm.tw/planting/resume/%s' % data['uuid'][0]
        r = requests.get(url)
        json_data = r.json()

        if json_data['activities']:
            last_image_url = json_data['activities'][-1]['image']
            last_image_url = last_image_url.replace('https', 'http').replace('http', 'https')
            original_image_url = '/'.join(last_image_url.split('/')[0:-1]) + '/500x500/' + last_image_url.split('/')[-1]
            preview_image_url = '/'.join(last_image_url.split('/')[0:-1]) + '/300x300/' + last_image_url.split('/')[-1]

            image_message = ImageSendMessage(
                original_content_url=original_image_url,
                preview_image_url=preview_image_url
            )
            line_bot_api.reply_message(event.reply_token, image_message)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text='無記錄'))


@handler.add(BeaconEvent)
def handle_beacon(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text='Got beacon event. hwid={}, device_message(hex string)={}'.format(
                event.beacon.hwid, event.beacon.dm)))


if __name__ == "__main__":
    # create tmp dir for download content
    make_static_tmp_dir()

    app.run(debug=DEBUG, port=PORT, host=HOST)
