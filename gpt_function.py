import re
import os
import requests
import json
import time
from openai import OpenAI
from dotenv import load_dotenv
from send_error import send_error_email

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
system_prompt_script_translator_chinese = os.getenv("SYSTEM_PROMPT_SCRIPT_TRANSLATOR_CHINESE")
system_prompt_script_translator_japanese = os.getenv("SYSTEM_PROMPT_SCRIPT_TRANSLATOR_JAPANESE")
system_prompt_summarizer = os.getenv("SYSTEM_PROMPT_SUMMARIZER")


def openai_gpt_chat(system_prompt, prompt, youtube_link, email_link):
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    )
    try:
        return completion.choices[0].message.content
    except:
        send_error_email(f"step 6: openai获取翻译失败——{prompt}:", youtube_link, email_link)
        print("Error in getting the response.")
        return gaia_gpt_chat(system_prompt, prompt, youtube_link, email_link)

def gaia_gpt_chat(system_prompt, prompt, youtube_link, email_link):
    node_list = ['qwen72b', 'llama', 'phi', 'gemma']

    payload = json.dumps({
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    })
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    max_retries = 8
    attempt = 0

    while attempt < max_retries:
        num = attempt // 2
        path = attempt % 2
        attempt += 1
        try:
            url = f"https://{node_list[num]}.us.gaianet.network/v1/chat/completions"
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()  # 检查HTTP错误
            response_data = response.json()
            translation_data = response_data['choices'][0]['message']['content']
            return re.sub(r'^\.[a-zA-Z]+', '', translation_data).strip()
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt} failed for {node_list[num]}. Error: {e}")
            if path == 0:
                retry_delay = 3
            else:
                retry_delay = 0
            time.sleep(retry_delay)  # 等待一段时间后重试

    send_error_email(f"step 6: 多node获取翻译失败——{prompt}:", youtube_link, email_link)
    return
    # completion = client.chat.completions.create(
    #     model="gpt-4o",
    #     messages=[
    #         {"role": "system", "content": system_prompt},
    #         {"role": "user", "content": prompt}
    #     ]
    # )
    # try: return completion.choices[0].message.content
    # except:
    #     print("Error in getting the response.")
    #     return

def get_transcript(audio_file_path):
    print(f"正在通过音频文件转录英文脚本")
    # check if the file exists
    if not os.path.isfile(audio_file_path):
        print(f"File {audio_file_path} does not exist.")
        return
    audio_file = open(audio_file_path, "rb")
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="srt"
    )
    try:
        return transcript.text
    except:
        print("Error in getting the transcript.")
        return


def get_transcript_with_timestamps(audio_file_path):
    url = 'http://localhost:8080/v1/audio/transcriptions'

    # 打开文件并准备发送请求
    with open(audio_file_path, 'rb') as f:
        file_name_only = os.path.basename(f.name)
        files = [
            ('file', (file_name_only, f, 'audio/wav'))
        ]

        response = requests.post(url, files=files, proxies={"http": None, "https": None})

        response_data = response.json()  # 解析 JSON 数据
        return response_data


def load_transcript(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        transcript = json.load(f)
    return transcript


def group_words_into_sentences(transcript, max_words=10, max_silence=1.0):
    sentences = []
    current_sentence = []
    for i, word_info in enumerate(transcript):
        print(i, word_info)
        current_sentence.append(word_info)
        if i + 1 < len(transcript):
            silence = transcript[i + 1]['start'] - word_info['end']
            if len(current_sentence) >= max_words or silence > max_silence:
                sentences.append(current_sentence)
                current_sentence = []
        else:
            sentences.append(current_sentence)
    return sentences


# if __name__ == "__main__":
    # 测试 openai_gpt_chat
    # transcript_file_path = 'transcript_sample.json'
    # transcript = load_transcript(transcript_file_path)
    # sentences = group_words_into_sentences(transcript)
    # # save sentences as json file
    # with open('sentences_sample.json', 'w') as f:
    #     json.dump(sentences, f)
