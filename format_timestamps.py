import re
from datetime import datetime, timedelta
from send_error import *

def format_subtitles_with_timestamps(transcript, youtube_link, email_link):
    paragraphs = transcript.split("\n")
    final_transcript = []
    last_end = ""
    total = ""
    temp_sentence = ""
    for i, paragraph in enumerate(paragraphs):
        try:
            pattern = r'\[(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)'
            time_format = "%H:%M:%S.%f"
            match = re.match(pattern, paragraph)
            # 如果这一句话没有内容，或者以[ or { or (开头，多半代表着这段话里有不正确的内容，就刨除掉这段话
            if match and match.group(3) and not match.group(3).startswith(("[", "{", "(")):
                start_time = match.group(1)
                if last_end:
                    start_time = last_end
                    last_end = ""
                end_time = match.group(2)
                sentence = match.group(3).strip()
                sentence = re.sub(r'[^，。！？!?,.\'a-zA-Z0-9\u4e00-\u9fa5\uAC00-\uD7AF\u3040-\u30FF]', ' ', sentence)
                # 合并一个总和的，给ai用
                total = total + " " + sentence
                # 如果有没完成的数据，和这一句拼起来
                if temp_sentence:
                    sentence = temp_sentence + " " + sentence
                    sentence = sentence.strip()
                    temp_sentence = ""
                if sentence.endswith(".") or sentence.endswith("!") or sentence.endswith("?") or (i + 1) == len(paragraphs):
                    last_end = end_time
                    final_transcript.append(f"[{start_time} --> {end_time}]  {sentence}")
                elif '.' in sentence:
                    # 计算时间差
                    start_timestamps = datetime.strptime(start_time, time_format)
                    end_timestamps = datetime.strptime(end_time, time_format)
                    time_difference = end_timestamps - start_timestamps
                    # 计算语速
                    total_text_length = len(sentence)
                    split_text_list = sentence.split('.')
                    for idx, item in enumerate(split_text_list):
                        item = item.strip()
                        if idx + 1 != len(split_text_list):
                            this_text_length = len(item)
                            value_to_add = time_difference.total_seconds() * this_text_length / total_text_length
                            new_timestamps = start_timestamps + timedelta(seconds=value_to_add)
                            new_end_time = new_timestamps.strftime(time_format)[:-3]
                            final_transcript.append(f"[{start_time} --> {new_end_time}]  {item}")
                            last_end = new_end_time
                        else:
                            temp_sentence = item
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


def convert_to_srt(input_text, output_file="subtitles.srt"):
    pattern = r"\[(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\]  (.+)"

    with open(output_file, "w", encoding="utf-8") as f:
        matches = re.findall(pattern, input_text)
        for idx, (start_time, end_time, text) in enumerate(matches, 1):
            start_time = start_time.replace('.', ',')
            end_time = end_time.replace('.', ',')

            # 分离毫秒部分
            start_time_parts = start_time.split(',')
            end_time_parts = end_time.split(',')
            start_time_clean = start_time_parts[0]
            end_time_clean = end_time_parts[0]

            # 计算时间差（以秒为单位）
            start_time_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(start_time_clean.split(':'))))
            end_time_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(end_time_clean.split(':'))))
            duration = end_time_seconds - start_time_seconds

            # 如果文本长度大于50，进行分段处理
            if len(text) > 35:
                segments = []
                start_index = 0
                segment_duration = duration / (len(text) // 30 + 1) if len(text) > 30 else duration

                while start_index < len(text):
                    segment = text[start_index:start_index + 30]

                    last_comma = segment.rfind('，')
                    last_period = segment.rfind('。')

                    if last_comma != -1:
                        segment = segment[:last_comma + 1]
                    elif last_period != -1:
                        segment = segment[:last_period + 1]

                    segments.append(segment.strip())
                    start_index += len(segment)

                # 计算新的时间段并写入
                for i, segment in enumerate(segments):
                    new_start_time_seconds = start_time_seconds + i * segment_duration
                    new_end_time_seconds = new_start_time_seconds + (segment_duration * len(segment) / 30)

                    new_start_time = f"{int(new_start_time_seconds // 3600):02}:{int((new_start_time_seconds % 3600) // 60):02}:{int(new_start_time_seconds % 60):02},{int((new_start_time_seconds % 1) * 1000):03}"
                    new_end_time = f"{int(new_end_time_seconds // 3600):02}:{int((new_end_time_seconds % 3600) // 60):02}:{int(new_end_time_seconds % 60):02},{int((new_end_time_seconds % 1) * 1000):03}"

                    f.write(f"{idx}\n")
                    f.write(f"{new_start_time} --> {new_end_time}\n")
                    f.write(f"{segment}\n\n")
                    idx += 1
            else:
                f.write(f"{idx}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
