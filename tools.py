import queue
import re
import threading
from typing import Dict, Tuple, List, Union
from ncatbot.core import GroupMessage, MessageArray


def extract_xml_content(text: str) -> Tuple[List[str], List[Dict[str, str]], str]:
    """
    提取文本中的XML标记内容

    参数:
        text: 包含XML标记的文本

    返回:
        包含三个元素的元组:
        1. 提取的Python代码段列表
        2. 包含send标记信息的字典列表(每个字典包含user_id和content)
        3. 去除所有标记后的纯文本(保留原始换行和格式)
    """
    # 提取<python>标签内容(保持不变)
    python_code_blocks = re.findall(r'<python>(.*?)</python>', text, re.DOTALL)

    # 提取所有<send>标签内容及其属性(改进多标签处理)
    send_blocks = []
    send_pattern = re.compile(r'<send\s+user_id="([^"]*)">(.*?)</send>', re.DOTALL)
    for match in send_pattern.finditer(text):
        user_id, content = match.groups()
        send_blocks.append({
            'user_id': user_id,
            'content': content.strip()
        })

    # 提取无标记的文本(改进处理方式，保留原始格式)
    # 创建一个临时文本副本用于处理
    temp_text = text
    # 先移除所有python标签内容
    temp_text = re.sub(r'<python>.*?</python>', '', temp_text, flags=re.DOTALL)
    # 再移除所有send标签内容
    temp_text = re.sub(r'<send\s+user_id="[^"]*">.*?</send>', '', temp_text, flags=re.DOTALL)
    # 保留原始换行和格式，只去除空标签
    plain_text = temp_text.strip()

    return python_code_blocks, send_blocks, plain_text


def extract_message_info(message:MessageArray, user):
    extracted_text = ""
    extracted_image = ""

    try:
        for i in message:
            if i.__class__.__name__ == "PlainText":
                extracted_text += i.text
            if i.__class__.__name__ == "Text":
                extracted_text += i.text
            elif i.__class__.__name__ == "Image":
                extracted_image = i.url
            elif i.__class__.__name__ == "At":
                extracted_text += f"@{user[int(i.qq)]}"
    except:
        for i in message:
            if i["type"] == "PlainText":
                extracted_text += i.text
            elif i["type"] == "Text":
                extracted_text += i.text
            elif i["type"] == "Image":
                extracted_image += i.url
            elif i["type"] == "At":
                extracted_text += f"@{user[int(i.qq)]}"

    return extracted_text, extracted_image


class BroadcastSystem:
    '''广播系统'''
    def __init__(self):
        self.queues = []
        self.lock = threading.Lock()

    def register(self, tag):
        q = queue.Queue()
        with self.lock:
            self.queues.append({"tag": tag, "queue": q})
        return q

    def unregister(self, q):
        with self.lock:
            for i in self.queues:
                if i["queue"] == q:
                    self.queues.remove(i)

    def broadcast(self, message, tag):
        with self.lock:
            for j in self.queues:
                if j["tag"] == tag:
                    j["queue"].put(message)


# 测试多send标签的示例
if __name__ == "__main__":
    sample_text = """
    这是一段无标记的文本。

    <python>
    def hello():
        print("Hello, World!")
    </python>

    这是中间的无标记文本。

    <send user_id="123">
    这是第一条要发送的消息。
    包含多行内容。
    </send>

    更多无标记文本。

    <send user_id="456">
    这是第二条消息，发给不同用户。
    </send>

    最后一段无标记文本。
    """

    python_blocks, send_blocks, plain_text = extract_xml_content(sample_text)

    print("Python代码段:")
    for i, code in enumerate(python_blocks, 1):
        print(f"代码段 {i}:\n{code}\n")

    print("\nSend标记内容:")
    for i, send in enumerate(send_blocks, 1):
        print(f"Send {i}: \n{send}\n")

    print("\n无标记文本:")
    print(plain_text)