import re
import math
import subprocess
from gpt_function import system_prompt_check_sentence, gaia_gpt_chat
from datetime import datetime, timedelta
from send_error import *

def format_subtitles_with_timestamps(transcript, mp3_path, youtube_link, email_link):
    paragraphs = transcript.split("\n")
    final_transcript = []
    last_end = ""
    total = ""
    temp_sentence = ""
    s_pattern = r'\s{2,}'
    for i, paragraph in enumerate(paragraphs):
        try:
            pattern = r'\[(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)'
            time_format = "%H:%M:%S.%f"
            match = re.match(pattern, paragraph)
            # 如果这一句话没有内容，或者以[ or { or (开头，多半代表着这段话里有不正确的内容，就刨除掉这段话
            if match and match.group(3) and not match.group(3).startswith(("[", "{", "(")):
                start_time = match.group(1)
                end_time = match.group(2)
                sentence = match.group(3).strip()
                sentence = re.sub(r'[^，。！？!?,.%\'a-zA-Z0-9\u4e00-\u9fa5\uAC00-\uD7AF\u3040-\u30FF]', ' ', sentence)
                if start_time == "00:00:00.000" and mp3_path:
                    hours, minutes, seconds_milliseconds = end_time.split(":")
                    seconds, milliseconds = seconds_milliseconds.split(".")
                    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
                    ffmpeg_cmd = [
                        'ffmpeg', '-t', str(total_seconds), '-i', mp3_path,
                        '-af', 'silencedetect=noise=-30dB:d=1', '-f', 'null', '-'
                    ]
                    output = subprocess.run(ffmpeg_cmd, capture_output=True, text=True).stderr
                    match_time = re.search(r'silence_end: ([\d\.]+)', output)
                    if match_time:
                        silence_end = match_time[0].split(": ")[1]
                        silence_end = float(silence_end)
                        if (total_seconds - silence_end) / len(sentence) > 0.05:
                            hours = math.floor(silence_end // 3600)
                            minutes = math.floor((silence_end % 3600) // 60)
                            seconds = math.floor(silence_end % 60)
                            milliseconds = math.floor((silence_end - math.floor(silence_end)) * 1000)
                            start_time = f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"
                # 合并一个总和的，给ai用
                total = total + " " + sentence
                # 如果有没完成的数据，和这一句拼起来
                if temp_sentence:
                    if sentence and sentence[0].isupper() and not temp_sentence.endswith(','):
                        check_sentence = gaia_gpt_chat(system_prompt_check_sentence, temp_sentence, youtube_link, email_link, 1)
                        if check_sentence == "yes":
                            final_transcript.append(f"[{last_end} --> {start_time}]  {re.sub(s_pattern, ' ', temp_sentence)}")
                    else:
                        if last_end:
                            start_time = last_end
                        sentence = temp_sentence + " " + sentence
                        sentence = sentence.strip()
                    temp_sentence = ""
                    last_end = ""
                if sentence.endswith(".") or sentence.endswith("!") or sentence.endswith("?"):
                    last_end = end_time
                    final_transcript.append(f"[{start_time} --> {end_time}]  {re.sub(s_pattern, ' ', sentence)}")
                elif '. ' in sentence:
                    # 计算时间差
                    start_timestamps = datetime.strptime(start_time, time_format)
                    end_timestamps = datetime.strptime(end_time, time_format)
                    time_difference = end_timestamps - start_timestamps
                    # 计算语速
                    total_text_length = len(sentence)
                    split_text_list = sentence.split('. ')
                    for idx, item in enumerate(split_text_list):
                        item = item.strip()
                        if idx + 1 != len(split_text_list):
                            this_text_length = len(item)
                            value_to_add = time_difference.total_seconds() * this_text_length / total_text_length
                            new_timestamps = start_timestamps + timedelta(seconds=value_to_add)
                            new_end_time = new_timestamps.strftime(time_format)[:-3]
                            final_transcript.append(f"[{start_time} --> {new_end_time}]  {re.sub(s_pattern, ' ', item)}")
                            last_end = new_end_time
                        elif i + 1 == len(paragraphs):
                            final_transcript.append(f"[{start_time} --> {end_time}]  {re.sub(s_pattern, ' ', item)}")
                        else:
                            temp_sentence = item
                elif i + 1 == len(paragraphs):
                    final_transcript.append(f"[{start_time} --> {end_time}]  {re.sub(s_pattern, ' ', sentence)}")
                else:
                    temp_sentence = sentence
                    last_end = start_time
        except Exception as e:
            send_error_email(f"step 5: 合并timestamps——{paragraphs[i]}失败：{i}: {e}", youtube_link, email_link)
            print("合并timestamps失败")
            return
    transcript = "\n".join(final_transcript)
    return {
        "total": total,
        "transcript": transcript,
        "final_transcript": final_transcript
    }

def convert_milliseconds_to_time_format(milliseconds):
    # 计算小时
    hours = milliseconds // (60 * 60 * 1000)
    milliseconds %= (60 * 60 * 1000)

    # 计算分钟
    minutes = milliseconds // (60 * 1000)
    milliseconds %= (60 * 1000)

    # 计算秒
    seconds = milliseconds // 1000
    # 剩下的是毫秒
    milliseconds %= 1000

    # 格式化成 HH:MM:SS,xxx
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{int(milliseconds):03}"

def convert_to_srt(input_text, output_file, video_file):
    pattern = r"\[(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\]  (.+)"

    max_length = 35
    add_length = 30

    ffprobe_command = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_file
    ]

    # Run the command using subprocess and capture the output
    result = subprocess.run(ffprobe_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        # Successfully executed the command, parse the output
        resolution = result.stdout.strip()
        width, height = map(int, resolution.split('x'))
        max_length = int(35 * 9 / 16 * height // width)
        add_length = int(max_length * 6 // 7)
    else:
        # There was an error executing the command
        print(f"Error: {result.stderr}")

    with open(output_file, "w", encoding="utf-8") as f:
        matches = re.findall(pattern, input_text)
        for idx, (start_time, end_time, text) in enumerate(matches, 1):
            start_time = start_time.replace('.', ',')
            end_time = end_time.replace('.', ',')

            # 分离毫秒部分
            start_time_parts = start_time.split(',')
            end_time_parts = end_time.split(',')
            start_time_clean = start_time_parts[0]
            start_milliseconds = int(start_time_parts[1])
            end_time_clean = end_time_parts[0]
            end_milliseconds  = int(end_time_parts[1])
            # 计算时间差（以秒为单位）
            start_time_milliseconds = (sum(int(x) * 60 ** i for i, x in enumerate(reversed(start_time_clean.split(':')))) * 1000 + start_milliseconds)
            end_time_milliseconds = (sum(int(x) * 60 ** i for i, x in enumerate(reversed(end_time_clean.split(':')))) * 1000 + end_milliseconds)

            duration_milliseconds = end_time_milliseconds - start_time_milliseconds

            if len(text) > max_length:
                segments = []
                start_index = 0
                segment_duration = duration_milliseconds / len(text)

                while start_index < len(text):
                    segment = text[start_index:start_index + add_length]

                    last_comma = segment.rfind('，')
                    last_period = segment.rfind('。')

                    if last_comma != -1:
                        segment = segment[:last_comma + 1]
                    elif last_period != -1:
                        segment = segment[:last_period + 1]

                    segments.append(segment.strip())
                    start_index += len(segment)
                # 计算新的时间段并写入
                last_end = ""
                for i, segment in enumerate(segments):
                    if last_end:
                        new_start_time_seconds = last_end
                    else:
                        new_start_time_seconds = start_time_milliseconds
                    new_end_time_seconds = new_start_time_seconds + len(segment) * segment_duration
                    last_end = new_end_time_seconds

                    new_start_time = convert_milliseconds_to_time_format(new_start_time_seconds)
                    new_end_time = convert_milliseconds_to_time_format(new_end_time_seconds)

                    f.write(f"{idx}\n")
                    f.write(f"{new_start_time} --> {new_end_time}\n")
                    f.write(f"{segment}\n\n")
                    idx += 1
            else:
                f.write(f"{idx}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
