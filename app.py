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
    PostbackTemplateAction, ImageSendMessage
)

from config import *

app = Flask(__name__)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

weather_station_dict = {
    'CWB': '中央氣象局',
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

    if text == 'profile':
        if isinstance(event.source, SourceUser):
            profile = line_bot_api.get_profile(event.source.user_id)
            line_bot_api.reply_message(
                event.reply_token, [
                    TextSendMessage(text='Display name: ' + profile.display_name),
                    TextSendMessage(text='Status message: ' + profile.status_message)
                ]
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="Bot can't use profile API without user ID"))
    elif text == 'bye':
        if isinstance(event.source, SourceGroup):
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text='Leaving group'))
            line_bot_api.leave_group(event.source.group_id)
        elif isinstance(event.source, SourceRoom):
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text='Leaving group'))
            line_bot_api.leave_room(event.source.room_id)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="Bot can't leave from 1:1 chat"))
    elif text == 'confirm':
        confirm_template = ConfirmTemplate(text='Do it?', actions=[
            MessageAction(label='Yes', text='Yes!'),
            MessageAction(label='No', text='No!'),
        ])
        template_message = TemplateSendMessage(
            alt_text='Confirm alt text', template=confirm_template)
        line_bot_api.reply_message(event.reply_token, template_message)
    elif text == 'buttons':
        buttons_template = ButtonsTemplate(
            title='My buttons sample', text='Hello, my buttons', actions=[
                URIAction(label='Go to line.me', uri='https://line.me'),
                PostbackAction(label='ping', data='ping'),
                PostbackAction(label='ping with text', data='ping', text='ping'),
                MessageAction(label='Translate Rice', text='米')
            ])
        template_message = TemplateSendMessage(
            alt_text='Buttons alt text', template=buttons_template)
        line_bot_api.reply_message(event.reply_token, template_message)
    elif text == 'carousel':
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(text='hoge1', title='fuga1', actions=[
                URIAction(label='Go to line.me', uri='https://line.me'),
                PostbackAction(label='ping', data='ping')
            ]),
            CarouselColumn(text='hoge2', title='fuga2', actions=[
                PostbackAction(label='ping with text', data='ping', text='ping'),
                MessageAction(label='Translate Rice', text='米')
            ]),
        ])
        template_message = TemplateSendMessage(
            alt_text='Carousel alt text', template=carousel_template)
        line_bot_api.reply_message(event.reply_token, template_message)
    elif text == 'image_carousel':
        image_carousel_template = ImageCarouselTemplate(columns=[
            ImageCarouselColumn(image_url='https://via.placeholder.com/1024x1024',
                                action=DatetimePickerAction(label='datetime',
                                                            data='datetime_postback',
                                                            mode='datetime')),
            ImageCarouselColumn(image_url='https://via.placeholder.com/1024x1024',
                                action=DatetimePickerAction(label='date',
                                                            data='date_postback',
                                                            mode='date'))
        ])
        template_message = TemplateSendMessage(
            alt_text='ImageCarousel alt text', template=image_carousel_template)
        line_bot_api.reply_message(event.reply_token, template_message)
    elif text == 'imagemap':
        pass
    elif text == 'flex':
        bubble = BubbleContainer(
            direction='ltr',
            hero=ImageComponent(
                url='https://example.com/cafe.jpg',
                size='full',
                aspect_ratio='20:13',
                aspect_mode='cover',
                action=URIAction(uri='http://example.com', label='label')
            ),
            body=BoxComponent(
                layout='vertical',
                contents=[
                    # title
                    TextComponent(text='Brown Cafe', weight='bold', size='xl'),
                    # review
                    BoxComponent(
                        layout='baseline',
                        margin='md',
                        contents=[
                            IconComponent(size='sm', url='https://example.com/gold_star.png'),
                            IconComponent(size='sm', url='https://example.com/grey_star.png'),
                            IconComponent(size='sm', url='https://example.com/gold_star.png'),
                            IconComponent(size='sm', url='https://example.com/gold_star.png'),
                            IconComponent(size='sm', url='https://example.com/grey_star.png'),
                            TextComponent(text='4.0', size='sm', color='#999999', margin='md',
                                          flex=0)
                        ]
                    ),
                    # info
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        spacing='sm',
                        contents=[
                            BoxComponent(
                                layout='baseline',
                                spacing='sm',
                                contents=[
                                    TextComponent(
                                        text='Place',
                                        color='#aaaaaa',
                                        size='sm',
                                        flex=1
                                    ),
                                    TextComponent(
                                        text='Shinjuku, Tokyo',
                                        wrap=True,
                                        color='#666666',
                                        size='sm',
                                        flex=5
                                    )
                                ],
                            ),
                            BoxComponent(
                                layout='baseline',
                                spacing='sm',
                                contents=[
                                    TextComponent(
                                        text='Time',
                                        color='#aaaaaa',
                                        size='sm',
                                        flex=1
                                    ),
                                    TextComponent(
                                        text="10:00 - 23:00",
                                        wrap=True,
                                        color='#666666',
                                        size='sm',
                                        flex=5,
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
            ),
            footer=BoxComponent(
                layout='vertical',
                spacing='sm',
                contents=[
                    # callAction, separator, websiteAction
                    SpacerComponent(size='sm'),
                    # callAction
                    ButtonComponent(
                        style='link',
                        height='sm',
                        action=URIAction(label='CALL', uri='tel:000000'),
                    ),
                    # separator
                    SeparatorComponent(),
                    # websiteAction
                    ButtonComponent(
                        style='link',
                        height='sm',
                        action=URIAction(label='WEBSITE', uri="https://example.com")
                    )
                ]
            ),
        )
        message = FlexSendMessage(alt_text="hello", contents=bubble)
        line_bot_api.reply_message(
            event.reply_token,
            message
        )
    elif text == 'quick_reply':
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='Quick reply',
                quick_reply=QuickReply(
                    items=[
                        QuickReplyButton(
                            action=PostbackAction(label="label1", data="data1")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="label2", text="text2")
                        ),
                        QuickReplyButton(
                            action=DatetimePickerAction(label="label3",
                                                        data="data3",
                                                        mode="date")
                        ),
                        QuickReplyButton(
                            action=CameraAction(label="label4")
                        ),
                        QuickReplyButton(
                            action=CameraRollAction(label="label5")
                        ),
                        QuickReplyButton(
                            action=LocationAction(label="label6")
                        ),
                    ])))
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

    if event.postback.data == 'ping':
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text='pong'))
    elif event.postback.data == 'datetime_postback':
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=event.postback.params['datetime']))
    elif event.postback.data == 'date_postback':
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=event.postback.params['date']))
    elif data['action'][0] == 'search_weather_stations':
        url = 'http://52.183.94.1:8001/?backend=CWB&get=stations&q={"lat":%s,"lng":%s,"max_distance":7}' % (data['lat'][0], data['lng'][0])
        r = requests.get(url)
        stations = r.json()

        columns = []

        for station in stations:
            text = """地址：%s
距離：%s km""" % (station['address'], station['distance_km'])

            actions = [ PostbackTemplateAction(label='即時天氣', data='action=get_weather_current&station_source=%s&station_id=%s&station_name=%s&user_lat=%s&user_lng=%s' % (station['source'], station['station_id'], station['station_name'], data['lat'][0], data['lng'][0])),
                        PostbackTemplateAction(label='訂閱', data='action=subscribe_weather_station&station_source=%s&station_id=%s&station_name=%s&user_lat=%s&user_lng=%s' % (station['source'], station['station_id'], station['station_name'], data['lat'][0], data['lng'][0]))
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
