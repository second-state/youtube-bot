import os
import random
import string
import subprocess
from datetime import datetime
from send_error import *

def split_audio_from_mp4(input_source_mp4, email_link, output_audio_format='mp3'):
    """
    从 mp4 文件中提取音频，并保存为指定格式的音频文件。

    参数：
    - input_source_mp4: 输入的 mp4 视频文件路径。
    - output_audio_format: 输出的音频格式，默认为 'mp3'。可以是 'mp3' 或 'wav'。
    """
    # 检查输入文件是否存在
    if not os.path.isfile(input_source_mp4):
        print(f"文件 {input_source_mp4} 不存在。")
        return None

    # 构建输出音频文件路径
    base_name = os.path.splitext(input_source_mp4)[0]
    output_audio_file = f"{base_name}.{output_audio_format}"

    # 构建 ffmpeg 命令
    if output_audio_format.lower() == 'mp3':
        ffmpeg_command = [
            'ffmpeg',
            '-i', input_source_mp4,
            '-vn',  # 不要视频流
            '-acodec', 'libmp3lame',  # 使用 MP3 编码器
            '-q:a', '2',  # 设置音频质量，0-9，数值越低质量越好
            '-ar', '16000',  # 设置采样率
            '-af', 'aresample=16000',
            '-ac', '1',  # 设置声道数
            output_audio_file
        ]
    elif output_audio_format.lower() == 'wav':
        ffmpeg_command = [
            'ffmpeg',
            '-i', input_source_mp4,
            '-vn',
            '-acodec', 'pcm_s16le',  # 使用 PCM 编码器
            '-ar', '16000',  # 设置采样率
            '-af', 'aresample=16000',
            '-ac', '1',  # 设置声道数
            output_audio_file
        ]
    else:
        print(f"不支持的音频格式：{output_audio_format}")
        return None

    # 运行 ffmpeg 命令
    try:
        subprocess.run(ffmpeg_command, check=True)
        print(f"音频已成功提取并保存为 {output_audio_file}")
        return output_audio_file
    except subprocess.CalledProcessError as e:
        send_error_email(f"step 3: 提取音频时出错：{e}", input_source_mp4, email_link)
        print(f"提取音频时出错：{e}")
        return None


def process_video(mp4_path, original_mp4_path, mp3_path, offset_seconds=5, language='zh', srt_file="", with_srt=0):
    import os
    import subprocess
    import sys

    # Step 1: Verify that mp4 and mp3 files exist
    if not os.path.isfile(mp4_path):
        print(f"Error: mp4 file '{mp4_path}' does not exist.")
        sys.exit(1)
    if not os.path.isfile(mp3_path):
        print(f"Error: mp3 file '{mp3_path}' does not exist.")
        sys.exit(1)

    if os.path.splitext(mp4_path)[0].rsplit('_', 1)[0] + f"_{language}" != os.path.splitext(mp3_path)[0]:
        print(f"Error: mp4 file '{mp4_path}' and mp3 file '{mp3_path}' are not matched.")
        sys.exit(1)

    # Step 2: Check if offset_seconds is valid
    if offset_seconds < 0:
        print("Error: offset_seconds must be non-negative.")
        sys.exit(1)

    # Step 3: Get durations
    try:
        mp4_duration = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", mp4_path],
            stderr=subprocess.STDOUT).decode('utf-8').strip())
    except subprocess.CalledProcessError as e:
        print(f"Error getting duration of mp4 file: {e}")
        sys.exit(1)
    try:
        mp3_duration = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", mp3_path],
            stderr=subprocess.STDOUT).decode('utf-8').strip())
    except subprocess.CalledProcessError as e:
        print(f"Error getting duration of mp3 file: {e}")
        sys.exit(1)

    # Step 4: Compute speed_factor
    desired_duration = offset_seconds + mp3_duration
    if mp4_duration <= 10:
        print("Error: Duration of mp4 file is less than 10 seconds.")
        sys.exit(1)
    speed_factor = mp4_duration / desired_duration
    print(f"mp4 duration: {mp4_duration}, mp3 duration: {mp3_duration}")
    print(f"Desired duration (mp3_duration + offset_seconds): {desired_duration}")
    print(f"Speed factor: {speed_factor}")
    if speed_factor <= 0:
        print("Error: Invalid speed factor computed.")
        sys.exit(1)

    # Step 5: Build atempo filters
    atempo_filters = get_atempo_filters(speed_factor)
    print(f"Atempo filters: {atempo_filters}")

    # Step 6: Build ffmpeg command
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    letters = string.ascii_letters + string.digits
    random_value = ''.join(random.choice(letters) for _ in range(6)) + timestamp
    output_video_filename = "Video_downloaded/" + random_value + f"_{language}.mp4"
    output_srt_filename = "Video_downloaded/" + random_value + f"_{language}_dub.mp4"
    delay_in_ms = int(offset_seconds * 1000)
    filter_complex = (
        f"[0:v]setpts=PTS/{speed_factor}[v];"
        f"[0:a]{atempo_filters},volume=0.05[a1];"
        f"[1:a]adelay={delay_in_ms}|{delay_in_ms},volume=1.2[a2];"
        f"[a1][a2]amix=inputs=2:duration=longest[a]"
    )
    command = [
        "ffmpeg", "-y", "-i", mp4_path, "-i", mp3_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]", output_video_filename
    ]

    if language== 'zh':
        font_name = "汉呈正文宋体"
    else:
        font_name = "PopRumKiwi Telop"

    add_srt_command = [
        "ffmpeg", "-y", "-i", original_mp4_path,
        "-vf", f"subtitles={srt_file}:force_style='FontName={font_name},Alignment=2,MaxLineLength=30'", output_srt_filename
    ]

    # Step 7: Execute ffmpeg command
    try:
        subprocess.run(command, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        subprocess.run(add_srt_command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error during ffmpeg processing: {e.stderr.decode('utf-8')}")
        sys.exit(1)

    # Step 8: Output file saved, print filename
    print(f"Output file: {output_video_filename}, {output_srt_filename}")
    return {
        "output_video_filename": output_video_filename,
        "output_srt_filename": output_srt_filename
    }


def get_atempo_filters(speed_factor):
    factors = []
    temp_factor = speed_factor
    while temp_factor > 2.0:
        factors.append(2.0)
        temp_factor /= 2.0
    while temp_factor < 0.5:
        factors.append(0.5)
        temp_factor /= 0.5
    factors.append(temp_factor)
    return ','.join(['atempo={0}'.format(f) for f in factors])


def mp3_to_video_with_image(mp3_file, image_file):
    # 获取文件路径、名称及扩展名
    file_path, file_name = os.path.split(mp3_file)
    file_name_without_ext = os.path.splitext(file_name)[0]

    # 输出文件名（mp4格式，和mp3同名）
    output_video = os.path.join(file_path, f"{file_name_without_ext}.mp4")

    # 构造 ffmpeg 命令
    command = [
        'ffmpeg',
        '-loop', '1',  # 循环静态图片
        '-i', image_file,  # 输入图片
        '-i', mp3_file,  # 输入音频
        '-c:v', 'libx264',  # 使用H.264视频编码
        '-c:a', 'aac',  # 使用AAC音频编码
        '-b:a', '192k',  # 设置音频比特率
        '-shortest',  # 根据音频长度自动停止
        '-pix_fmt', 'yuv420p',  # 兼容大多数播放器的像素格式
        output_video  # 输出视频文件
    ]

    # 执行命令
    try:
        subprocess.run(command, check=True)
        print(f"视频已成功生成: {output_video}")
    except subprocess.CalledProcessError as e:
        print(f"生成视频时出错: {e}")


if __name__ == "__main__":
    print("Processing video...")
    mp4_path = 'Video_downloaded/WeChat_20240923082739.mp4'
    mp3_path = 'Video_downloaded/WeChat_20240923082739_zh.mp3'
    srt_file = 'Video_downloaded/WeChat_20240923082739_srt.srt'
    process_video(mp4_path, mp3_path, 0, 'zh', srt_file, 2)
