import os
import requests
import json

from dotenv import load_dotenv

load_dotenv()

system_prompt_script_translator_chinese = os.getenv("SYSTEM_PROMPT_SCRIPT_TRANSLATOR_CHINESE")
system_prompt_script_translator_japanese = os.getenv("SYSTEM_PROMPT_SCRIPT_TRANSLATOR_JAPANESE")
system_prompt_summarizer = os.getenv("SYSTEM_PROMPT_SUMMARIZER")


def openai_gpt_chat(system_prompt, prompt):
    url = "https://qwen72b.us.gaianet.network/v1/chat/completions"

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

    response = requests.request("POST", url, headers=headers, data=payload)

    try:
        response_data = response.json()
        return response_data['choices'][0]['message']['content']
    except:
        print("Error in getting the response.")
        return


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
