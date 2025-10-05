import threading
import time
import queue
import config
from openai import OpenAI
import sys
import traceback
from io import StringIO
from ncatbot.core import BotClient, GroupMessage, MessageSegment, At, Text, MessageArray
from ncatbot.utils import get_log
from tools import BroadcastSystem, extract_xml_content, extract_message_info
from vlm import analyze_image
import random

input_lock = threading.Lock() # 多线程锁
client = OpenAI(api_key=config.llm["key"], base_url=config.llm["url"]) # llm参数
conversation_history = [] # 初始化聊天记录
bot = BotClient() # qq机器人初始化
_log = get_log()
user = {}
member_info_got = False
chat_history = {}


def member_info_update():
    global user
    members_information = bot.api.get_group_member_list_sync(group_id=int(config.qq["group_id"]))
    # _log.info(members_information)
    new_members = {}
    for j in members_information.members:
        if j.card == '':
            new_members[j.user_id] = j.nickname
            new_members[j.nickname] = j.user_id
        else:
            new_members[j.user_id] = j.card
            new_members[j.card] = j.user_id
    user = new_members
    _log.info(f"已刷新群成员信息: {len(new_members) // 2} 名成员")


def send_to_group():
    '''向群聊发送消息'''
    global conversation_history
    print("发送消息线程已启动")
    q = broadcast_system.register(tag="send_to_group")
    while True:
        time.sleep(0.1)
        try:
            information = q.get()
            message = MessageArray([
                At(int(user[information["user_id"]])),
                Text(information["content"])
            ])
            time.sleep(random.randint(1,3))
            try:
                message_id = bot.api.post_group_msg_sync(group_id=config.qq["group_id"], rtf=message)
                extracted_text, extracted_image = extract_message_info(message, user)
                chat_history[message_id] = {"sender":"Funggy", "text": extracted_text,"image": extracted_image}
            except Exception as e:
                _log.error(e)
        except queue.Empty:
            pass


@bot.group_event()
def get_from_group(message: GroupMessage):
    '''从群聊获取消息'''
    global heartbeat_queue, user, member_info_got, chat_history
    if not member_info_got:
        member_info_update()
        member_info_got = True

    if message.group_id == config.qq["group_id"]:

        _log.info(message)
        _log.info(message.message.to_list())

        message_iter = iter(message.message)

        # 处理历史消息，放入历史消息字典
        with input_lock:
            is_forward = False
            for i in message.message:
                if i.__class__.__name__ == "Forward":
                    is_forward = True

            if is_forward:
                # 处理合并消息
                chat_forward = []
                for i in next(message_iter).content:
                    extracted_text, extracted_image = extract_message_info(i.content, user)
                    chat_forward.append({"sender":i.nickname, "text":extracted_text, "image":extracted_image})
                chat_history[message.message_id] = chat_forward
            else:
                # 处理正常消息
                extracted_text, extracted_image = extract_message_info(message.message, user)
                chat_history[message.message_id] = {"sender":user[int(message.sender.user_id)], "text":extracted_text, "image":extracted_image}

        if {'type':"at", "data":{'qq':config.qq["bot_id"]}} in message.message.to_list():

            user_information = message.sender
            if user_information.card == '':
                user_name = user_information.nickname
            else:
                user_name = user_information.card
            if message.user_id not in user:
                user[message.user_id] = user_name
                user[user_name] = message.user_id

            send_text = ""
            send_image = ""
            reply = ""

            is_reply = False
            for i in message.message:
                if i.to_dict()["type"] == "reply":
                    is_reply = True


            if is_reply:
                reply_msg_id = next(message_iter).id
                print(reply_msg_id)
                # 检查回复的消息是否在历史记录中
                if reply_msg_id in chat_history:
                    if type(chat_history[reply_msg_id]) == list:
                        # 如果回复的是聊天记录
                        send_text2 = "<chat_history>\n"
                        for i in chat_history[reply_msg_id]:
                            send_text2 += f"{i['sender']}: {i['text']}\n"
                        send_text2 += "</chat_history>\n"
                        reply = f"<quote>{send_text2}</quote>"
                    else:
                        # 如果回复的是普通消息
                        send_text2 = chat_history[reply_msg_id]["text"]
                        send_image2 = chat_history[reply_msg_id]["image"]
                        if send_image2 != "":
                            img_information = analyze_image(send_image2)["choices"][0]["message"]["content"]
                            reply = f"<quote>{chat_history[reply_msg_id]['sender']}:<image>{img_information}</image>{send_text2}</quote>"
                        else:
                            reply = f"<quote>{chat_history[reply_msg_id]['sender']}:{send_text2}</quote>"

            send_text, send_image = extract_message_info(message.message, user)

            if send_image != "":
                img_information = analyze_image(send_image)["choices"][0]["message"]["content"]
                send = {"role":"user", "content":f"<name>{user[message.user_id]}</name>{reply}<image>{img_information}</image>{send_text}"}
            else:
                send = {"role":"user", "content":f"<name>{user[message.user_id]}</name>{reply}{send_text}"}

            print("文本：", send_text)
            print("图片：", send_image)
            print(send)
            broadcast_system.broadcast([send],tag="send_to_llm")


def execute_python_code():
    '''代码段执行'''
    print("代码运行线程已启动")
    q = broadcast_system.register(tag="executer")
    while True:
        time.sleep(1)
        try:
            code = q.get()
            # print(code)

            # 如果code是空字符串，直接跳过不处理
            if not code.strip():
                continue

            # 重定向标准输出以捕获执行结果
            old_stdout = sys.stdout
            sys.stdout = output = StringIO()

            try:
                # 将分号替换为换行符以支持单行简写
                # formatted_code = code.replace(';', '\n')
                exec(code)
                result = output.getvalue()
            except Exception as e:
                result = f"执行错误:\n{traceback.format_exc()}"
            finally:
                sys.stdout = old_stdout

            # 只有实际执行了代码才广播结果
            if result.strip():  # 确保结果不是空字符串
                broadcast_system.broadcast(message=[{"role":"system", "content":result}], tag="send_to_llm")
        except queue.Empty:
            pass


def send_to_llm():
    '''llm接口'''
    print("llm接口线程已启动")
    global conversation_history
    q = broadcast_system.register(tag="send_to_llm")
    while True:
        time.sleep(0.1)
        try:
            messages = q.get()

            for message in messages:
                with input_lock:
                    conversation_history.append(message)
                    if len(conversation_history) > 30:
                        conversation_history = conversation_history[-30:]
                    print(conversation_history[-1])

            response = client.chat.completions.create(
                model=config.llm["model"],
                messages=conversation_history + [{"role":"system", "content":config.llm["group_prompt"]}],
                stream=False
            )

            with input_lock:
                conversation_history.append({"role": "assistant", "content":response.choices[0].message.content})
                print(conversation_history[-1])

            code, to_send, text = extract_xml_content(response.choices[0].message.content)

            if code == []:
                code = ['']

            if to_send != []:
                for send in to_send:
                    broadcast_system.broadcast(message=send, tag="send_to_group")

            if text != "":
                broadcast_system.broadcast(message=text, tag="send_to_tts")

            broadcast_system.broadcast(message=code[0], tag="executer")
            print("Funggy:", text)
        except queue.Empty:
            pass


broadcast_system = BroadcastSystem()

if __name__ == "__main__":


    send_to_group_thread = threading.Thread(target=send_to_group, daemon=True)
    llm_thread = threading.Thread(target=send_to_llm, daemon=True)
    code_thread = threading.Thread(target=execute_python_code, daemon=True)


    send_to_group_thread.start()
    code_thread.start()
    llm_thread.start()

    bot.run(bt_uin=config.qq["bot_id"])