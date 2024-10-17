import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
import httpx
import ormsgpack
import time
from gpt_function import *
from media_process import *
from send_error import *

fish_audio_api_key = os.getenv("FISH_AUDIO_API_KEY")

audio_id_leowang_chinese = os.getenv("FISH_AUDIO_ID_LEOWANG_CHINESE")
audio_id_danli_chinese = os.getenv("FISH_AUDIO_ID_DANLI_CHINESE")


def chinese_audio_generation(input_text, output_file, model_id=audio_id_leowang_chinese, api_key=fish_audio_api_key):
    url = "https://api.fish.audio/v1/tts"
    max_retries = 4
    request = {
        "text": input_text,
        "reference_id": model_id,
        "chunk_length": 200,
        "normalize": False,
        "format": "mp3",
        "mp3_bitrate": 64,
        "opus_bitrate": -1000,
        "latency": "normal"
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/msgpack"
    }

    retries = 0
    success = False

    while retries < max_retries and not success:
        try:
            with (
                httpx.Client() as client,
                open(output_file, "wb") as f,
            ):
                with client.stream(
                        "POST",
                        url,
                        content=ormsgpack.packb(request, option=ormsgpack.OPT_SERIALIZE_PYDANTIC),
                        headers=headers,
                        timeout=None,
                ) as response:
                    if response.status_code == 200:
                        for chunk in response.iter_bytes():
                            f.write(chunk)
                        success = True
                    else:
                        print(f"Request failed with status code {response.status_code}. Retrying...")
        except Exception as e:
            print(f"An error occurred: {e}. Retrying...")

        retries += 1
        if not success:
            time.sleep(2)  # 等待 2 秒再进行下一次重试

    if not success:
        print("Request failed after 5 retries.")
    else:
        print("Request succeeded!")
    return output_file

# def test_audio_generation(model_id, api_key=fish_audio_api_key):
#     print(f"Generating audio...")
#     url = "https://api.fish.audio/v1/tts"
#     request = {
#         "text": "hi",
#         "reference_id": model_id,
#         "chunk_length": 200,
#         "normalize": False,
#         "format": "mp3",
#         "mp3_bitrate": 64,
#         "opus_bitrate": -1000,
#         "latency": "normal"
#     }
#     headers = {
#         "Authorization": f"Bearer {api_key}",
#         "Content-Type": "application/msgpack"
#     }
#
#     with (
#         httpx.Client() as client,
#         open(output_file, "wb") as f,
#     ):
#         with client.stream(
#                 "POST",
#                 url,
#                 content=ormsgpack.packb(request, option=ormsgpack.OPT_SERIALIZE_PYDANTIC),
#                 headers=headers,
#                 timeout=None,
#         ) as response:
#             for chunk in response.iter_bytes():
#                 f.write(chunk)
#     return output_file


# 基于 chinese_audio_generation 函数，实现一个功能，将 input_text 输入的中文根据句号 。 进行切割，每十个句号为一个段落，然后生成临时的音频文件，生成一个临时文件夹 temp 子目录，放在子目录中，最后用 ffmpeg 将所有文件按顺序合并为一个大文件：output_file，合并成功后删除 temp 临时文件夹及包含的所有临时文件，并 return output_file
def chinese_audio_batch_generation_and_merge(input_text, output_file, offset_seconds, dst_video, youtube_link, email_link, model_id=audio_id_leowang_chinese,
                                             api_key=fish_audio_api_key):
    paragraphs = input_text.split("\n")
    # 在工作目录下创建临时文件夹
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    temp_dir = "temp_" + timestamp
    os.makedirs(temp_dir, exist_ok=True)
    fix_video = os.path.splitext(dst_video)[0] + "_fix.mp4"
    # 生成临时音频文件
    temp_files = []
    split_list = []
    try:
        for i, paragraph in enumerate(paragraphs):
            temp_file = os.path.join(temp_dir, f"temp_{i}.mp3")
            pattern = r'\[(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)'
            # 查找匹配的部分
            match = re.match(pattern, paragraph)
            print(match.group(3))
            if match and match.group(3) and not match.group(3).startswith(("[", "{")):
                start_time = match.group(1)
                end_time = match.group(2)
                time_format = "%H:%M:%S.%f"
                base_datetime = datetime(1900, 1, 1)
                start_dt = datetime.strptime(start_time, time_format)
                if i == 0 and (start_dt.hour != 0 or start_dt.minute != 0 or start_dt.second != 0 or start_dt.microsecond != 0):
                    silence_time = (start_dt - base_datetime).total_seconds()
                    print(f'[INFO-{i}] create silence file: {silence_time}')
                    silence_file = f"{temp_dir}/silence_{i}.mp3"
                    subprocess.run([
                        'ffmpeg', '-f', 'lavfi', '-t', str(silence_time),
                        '-i', 'anullsrc=r=44100:cl=mono',  # 设置采样率为 44.100kHz，声道为单声道
                        '-b:a', '64k',  # 设置比特率为 64kbps
                        silence_file
                    ], check=True)
                    temp_files.append(silence_file)
                if i < len(paragraphs) - 1:
                    end_dt = datetime.strptime(end_time, time_format)
                else:
                    mp4_duration = float(subprocess.check_output(
                        ["ffprobe", "-v", "error", "-show_entries",
                         "format=duration", "-of",
                         "default=noprint_wrappers=1:nokey=1", dst_video],
                        stderr=subprocess.STDOUT).decode('utf-8').strip())
                    duration = mp4_duration - offset_seconds
                    duration_dt = timedelta(seconds=duration)
                    end_dt = base_datetime + duration_dt
                text = match.group(3)
                temp_audio_file = chinese_audio_generation(text, temp_file, model_id, api_key)
                target_duration = (end_dt - start_dt).total_seconds()
                ffprobe_result = subprocess.run(
                    ["ffprobe", "-i", temp_audio_file, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"],
                    stdout=subprocess.PIPE
                )
                original_duration = float(ffprobe_result.stdout.decode('utf-8').strip())
                if original_duration > target_duration:
                    speed_factor = original_duration / target_duration
                    split_list.append({
                        "start_time": start_time,
                        "end_time": end_time,
                        "speed_factor": speed_factor
                    })
                    temp_files.append(temp_audio_file)
                else:
                    temp_files.append(temp_audio_file)
                    silence_time = target_duration - original_duration
                    if original_duration < target_duration:
                        print(f'[INFO-{i}] create silence file: {silence_time}')
                        silence_file = f"{temp_dir}/silence_{i}.mp3"
                        subprocess.run([
                            'ffmpeg', '-f', 'lavfi', '-t', str(silence_time),
                            '-i', 'anullsrc=r=44100:cl=mono',  # 设置采样率为 44.100kHz，声道为单声道
                            '-b:a', '64k',  # 设置比特率为 64kbps
                            silence_file
                        ], check=True)
                        temp_files.append(silence_file)
    except Exception as e:
        send_error_email(f"step 7: 生成音频{paragraphs[i]}失败：{i}: {str(e)}", youtube_link, email_link)
        print("生成音频失败")
        return

    temp_videos = []
    last_end_time = "00:00:00.000"  # 初始时间，从视频开始

    try:
        # 遍历所有的片段
        for i, segment in enumerate(split_list):
            start_time = segment['start_time']
            end_time = segment['end_time']
            speed_factor = segment['speed_factor']

            if last_end_time < start_time:
                # 提取中间不需要调整速度的片段
                temp_filename = f"{temp_dir}/part_no_change_{i}.mp4"
                temp_videos.append(temp_filename)
                subprocess.run([
                    "ffmpeg", "-i", dst_video, "-ss", last_end_time, "-to", start_time,
                    "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-reset_timestamps", "1", temp_filename
                ])

                # 提取需要调整速度的片段
            temp_filename = f"{temp_dir}/part_slow_{i}.mp4"
            temp_videos.append(temp_filename)
            atempo_filters = get_atempo_filters(1/speed_factor)
            subprocess.run([
                "ffmpeg", "-ss", start_time, "-to", end_time, "-i", dst_video,  # 移动 -ss 和 -to 到 -i 之前
                "-filter:v", f"setpts={speed_factor}*PTS",  # 调整视频速度滤镜
                "-filter:a", atempo_filters,  # 调整音频速度滤镜
                "-r", "30",  # 设置帧率在滤镜之后
                "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-reset_timestamps", "1",
                temp_filename
            ])

            # 更新 last_end_time 为当前片段的结束时间
            last_end_time = end_time

            # 处理最后一个片段之后剩余的视频部分
        final_filename = f"{temp_dir}/final_part.mp4"
        temp_videos.append(final_filename)
        subprocess.run([
            "ffmpeg", "-i", dst_video, "-ss", last_end_time,
            "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-reset_timestamps", "1", final_filename
        ])
        # 创建文件列表以合并视频
        with open(f"{temp_dir}/filelist.txt", "w") as f:
            for video in temp_videos:
                f.write(f"file '{os.path.abspath(video)}'\n")
    except Exception as e:
        send_error_email(f"step 8: 调整视频速度失败: {e}", youtube_link, email_link)
        print("调整视频速度失败")
        return

    try:
        # 合并所有片段
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{temp_dir}/filelist.txt",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-strict", "experimental", fix_video
        ])
    except Exception as e:
        send_error_email(f"step 8: 合并调速视频失败: {e}", youtube_link, email_link)
        print("合并调速视频失败")
        return

    # 合并临时文件
    ffmpeg_command = [
        "ffmpeg",
        "-y",
        "-i", "concat:" + "|".join(temp_files),
        "-c", "copy",
        output_file
    ]
    try:
        subprocess.run(ffmpeg_command, check=True)
        print(f"Output file: {fix_video}")
        # shutil.rmtree(temp_dir)
        return fix_video
    except subprocess.CalledProcessError as e:
        send_error_email(f"step 9: 合并音频失败：{e}", youtube_link, email_link)
        print(f"Error during ffmpeg processing: {e}")


def generate_audio_from_text_file(input_file):
    with open(input_file, "r") as f:
        input_text = f.read()
    summary = openai_gpt_chat(system_prompt_summarizer, input_text)
    summary_file = os.path.splitext(input_file)[0] + "_summary.txt"
    with open(summary_file, "w") as f:
        f.write(summary)
    output_audio_file = os.path.splitext(input_file)[0] + f".mp3"
    chinese_audio_batch_generation_and_merge(summary, output_audio_file)
    return output_audio_file


def generate_audio_from_text_file_with_edit(input_file):
    with open(input_file, "r") as f:
        input_text = f.read()
    summary = openai_gpt_chat(system_prompt_summarizer, input_text)
    print(f"Summary\n: {summary}")
    summary_file = os.path.splitext(input_file)[0] + "_summary.txt"
    with open(summary_file, "w") as f:
        f.write(summary)
    # 使用 While 循环等待用户修改并确认 summary 文件，然后再继续
    while True:
        # 使用 VC Code 打开 summary 文件
        subprocess.run(["code", summary_file])
        confirm_go = input(f"请查看 {summary_file} 内容、修改并保存，，然后按 Y 继续，按 X 退出：")
        if confirm_go in ["Y", "y"]:
            break
        elif confirm_go in ["X", "x"]:
            return

    # 使用 While 循环请用户选择配音模型，1) Male; 2) Female 3) Exit;
    while True:
        voice_model_id = input("请选择配音模型性别：1) 男声; 2) 女声; 3) 退出; ")
        if voice_model_id == "1":
            voice_model_id = audio_id_leowang_chinese
            break
        elif voice_model_id == "2":
            voice_model_id = audio_id_danli_chinese
            break
        elif voice_model_id == "3":
            return
        else:
            print("请选择 1, 2 或 3")

    with open(summary_file, "r") as f:
        summary = f.read()
    output_audio_file = os.path.splitext(input_file)[0] + f".mp3"
    chinese_audio_batch_generation_and_merge(summary, output_audio_file, voice_model_id)
    return output_audio_file


def generate_video_from_text_file(input_file, image_file='Audio_generated/news_today.png'):
    input_audio_file = generate_audio_from_text_file_with_edit(input_file)
    return mp3_to_video_with_image(input_audio_file, image_file)


if __name__ == "__main__":
    print(system_prompt_summarizer)
    input_file = 'Audio_generated/news_today.txt'
    generate_video_from_text_file(input_file)
