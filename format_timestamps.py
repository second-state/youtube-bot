import re
from datetime import datetime, timedelta

def format_subtitles_with_timestamps(transcript):
    paragraphs = transcript.split("\n")
    final_transcript = []
    last_end = ""
    total = ""
    temp_sentence = ""
    for i, paragraph in enumerate(paragraphs):
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
            sentence = re.sub(r'[^，。！？!?,.a-zA-Z0-9\u4e00-\u9fa5\uAC00-\uD7AF\u3040-\u30FF]', ' ', sentence)
            # 合并一个总和的，给ai用
            total = total + " " + sentence
            # final_transcript.append(f"[{start_time} --> {end_time}]  {sentence}")
            # 如果有没完成的数据，和这一句拼起来
            if temp_sentence:
                sentence = temp_sentence + " " + sentence
            if sentence.endswith("."):
                last_end = end_time
                temp_sentence = ""
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
                    if idx+1 != len(split_text_list):
                        this_text_length = len(item)
                        value_to_add = time_difference.total_seconds() * this_text_length / total_text_length
                        new_timestamps = start_timestamps + timedelta(seconds=value_to_add)
                        new_end_time = new_timestamps.strftime(time_format)
                        final_transcript.append(f"[{start_time} --> {new_end_time}]  {item}")
                        start_time = new_end_time
                        last_end = new_end_time
            else:
                temp_sentence = sentence
                last_end = start_time
    transcript = "\n".join(final_transcript)
    print(final_transcript)
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
            f.write(f"{idx}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")