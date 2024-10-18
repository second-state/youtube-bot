import os
import re
import requests
import subprocess
import time
from datetime import datetime, timedelta
from moviepy.editor import AudioFileClip
from celery_local import celery
from format_timestamps import *
from voice_generate import *

load_dotenv()

DOMAIN = os.getenv("DOMAIN")


@celery.task
def main(second=0, youtube_link="https://www.youtube.com/watch?v=Hf9zfjflP_0", email_link="juyichen0413@gmail.com",
         sound_id="59cb5986671546eaa6ca8ae6f29f6d22", language="zh", with_srt=0):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    video_temp_dir = 'Video_temp' + timestamp
    video_downloaded_dir = 'Video_downloaded'
    video_generated = 'Video_generated'

    # 确保目录存在
    os.makedirs(video_generated, exist_ok=True)
    # 检查 video_temp_dir 是否存在，如果存在则清空目录，如果不存在则创建目录
    if not os.path.exists(video_temp_dir):
        os.makedirs(video_temp_dir, exist_ok=True)

    # 检查 video_downloaded_dir 是否存在，如果存在则清空目录，如果不存在则创建目录
    if not os.path.exists(video_downloaded_dir):
        os.makedirs(video_downloaded_dir, exist_ok=True)

    model_id = sound_id

    # 提示用户输入视频开头的偏移时间（秒），并解释一下这个参数的作用
    offset_seconds = second

    # 检查用户输入的是否为数字，如果不是则设置为默认值 3 秒
    try:
        offset_seconds = float(offset_seconds)
    except ValueError:
        offset_seconds = 3
    offset_seconds = int(offset_seconds)

    # 判断用户输入的是一个 Https 链接还是一个绝对文件名路径，如果是文件名路径，则将文件直接移动到 video_temp_dir 目录下，如果是 Https 链接，则使用 yt-dlp 下载视频
    if youtube_link.lower().startswith('http'):
        # yt-dlp 下载命令
        command = [
            'yt-dlp',
            '--cookies',
            'cookies-all.txt',
            '--rm-cache-dir',  # 清除缓存
            '--restrict-filenames',  # 限制文件名字符，避免特殊字符
            '-f',
            'bestvideo+bestaudio/best',
            '--merge-output-format', 'mp4',
            '-o',
            os.path.join(video_temp_dir, '%(title)s.%(ext)s'),
            youtube_link
        ]
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            send_error_email("step 1: 下载youtube视频失败", youtube_link, email_link)
            print(f"下载失败：{e}")
            return
    else:
        # 如果是文件路径，则直接移动到 video_temp_dir 目录下
        if os.path.isfile(youtube_link):
            new_input_file = os.path.join(video_temp_dir, os.path.basename(youtube_link))
            shutil.copy(youtube_link, new_input_file)
        else:
            send_error_email("step 1: 复制文件失败", youtube_link, email_link)
            print("输入的不是有效的链接或文件路径。")
            return

    try:
        files = os.listdir(video_temp_dir)
        if not files: return print("Video_temp 目录中未找到文件。")
        for f in files:
            src = os.path.join(video_temp_dir, f)
            # 检查文件是否为 mp4 格式
            if not f.lower().endswith('.mp4'):
                # 使用 ffmpeg 转换为 mp4 格式
                base_name = os.path.splitext(f)[0]
                mp4_file = base_name + '.mp4'
                mp4_path = os.path.join(video_temp_dir, mp4_file)
                ffmpeg_command = [
                    'ffmpeg',
                    '-i', src,
                    '-c:v', 'copy',
                    '-c:a', 'copy',
                    mp4_path
                ]
                try:
                    subprocess.run(ffmpeg_command, check=True)
                    os.remove(src)  # 删除原始文件
                    src = mp4_path  # 更新源文件路径为转换后的 mp4 文件
                except subprocess.CalledProcessError as e:
                    send_error_email(f"step 2: 转换 {f} 为 mp4 时出错：{e}", youtube_link, email_link)
                    print(f"转换 {f} 为 mp4 时出错：{e}")
                    continue  # 跳过此文件，继续下一个

            # 在此处调用提取音频的功能
            audio_files = split_audio_from_mp4(src, email_link, output_audio_format='wav')

            # 移动 mp4 文件到目标目录
            dst_video = os.path.join(video_downloaded_dir, os.path.basename(src))
            shutil.move(src, dst_video)

            transcript = ""
            # 如果音频提取成功，移动音频文件到目标目录，并删除源文件；如果音频文件不存在，则退出程序并告知用户
            if audio_files:
                last_time = 0
                for index, audio_file in enumerate(audio_files):
                    dst_audio = os.path.join(video_downloaded_dir, os.path.basename(audio_file))
                    if index == 0:
                        first_audio = dst_audio
                    shutil.move(audio_file, dst_audio)
                    # 通过 get_transcript 函数获取音频文件的转录文本
                    try:
                        result = get_transcript_with_timestamps(dst_audio)
                        this_text = result["text"]
                        final_text_list = []
                        paragraphs = this_text.split("\n")
                        for i, paragraph in enumerate(paragraphs):
                            pattern = r'\[(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)'
                            time_format = "%H:%M:%S.%f"
                            match = re.match(pattern, paragraph)
                            if match and match.group(3):
                                start_time = match.group(1)
                                end_time = match.group(2)
                                sentence = match.group(3).strip()
                                start_time = datetime.strptime(start_time, time_format)
                                end_time = datetime.strptime(end_time, time_format)
                                audio_duration_delta = timedelta(seconds=last_time)
                                start_time += audio_duration_delta
                                end_time += audio_duration_delta
                                start_time = start_time.strftime(time_format)[:-3]  # 去掉微秒部分后面的3位
                                end_time = end_time.strftime(time_format)[:-3]
                                final_text_list.append(f"[{start_time} --> {end_time}]  {sentence}")
                        this_text = "\n".join(final_text_list)
                        with AudioFileClip(dst_audio) as audio:
                            last_time += audio.duration
                        if transcript:
                            transcript += "\n"
                        transcript += this_text
                    except Exception as e:
                        send_error_email(f"step 4: whisper请求报错：{e}", youtube_link, email_link)
                        print("whisper报错")
                        return
                print(f"音频已提取并保存")
            else:
                send_error_email(f"step 3: 音频提取失败，split_audio_from_mp4返回空", youtube_link, email_link)
                print("音频提取失败，已退出程序。")
                return
            print("下载成功，视频已转换为 mp4，音频已提取，并移动到 Video_downloaded 目录。")
            print("音频转录文本：")
            print(transcript)
            print("合并成完整句子：")
            format_data = format_subtitles_with_timestamps(transcript, first_audio, youtube_link, email_link)
            transcript = format_data["transcript"]
            final_transcript = format_data["final_transcript"]
            # 将 transcript 保存为 txt 文件，文件名为音频文件名 + _en.txt 后缀
            transcript_file = os.path.splitext(dst_video)[0] + "_en.txt"
            with open(transcript_file, "w") as f:
                f.write(transcript)
            # 通过 openai_gpt_chat 函数获取中文翻译
            print("正在将英文脚本翻译为中文...")
            translated_text_list = []
            for i, line in enumerate(final_transcript):
                pattern = r'\[(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)'
                try:
                    match = re.match(pattern, line)
                    if match:
                        start_time = match.group(1)
                        end_time = match.group(2)
                        sentence = match.group(3).strip()
                        if language == 'ja':
                            system_prompt_script_translator = system_prompt_script_translator_japanese
                            transcript_pattern = r'^[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+$'
                        else:
                            system_prompt_script_translator = system_prompt_script_translator_chinese
                            transcript_pattern = r'[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffef0-9\.\+\-\*/=%\u00B1\u2212\u221A\s]+'
                        sentence_translation = gaia_gpt_chat(system_prompt_script_translator, sentence, youtube_link,
                                                             email_link)
                        if sentence_translation:
                            sentence_translation = sentence_translation.replace('\n', '')
                        else:
                            sentence_translation = sentence
                        print(f"qwen result: {sentence_translation}")
                        max_attempts = 4  # 最大尝试次数
                        attempts = 0  # 当前尝试次数
                        with open('trans_white_list.txt', 'r') as file:
                            words = file.read().splitlines()
                        # 处理每一行，拆分成独立的单词
                        all_words = []
                        for word_line in words:
                            all_words.append(word_line.lower())
                        while attempts < max_attempts:
                            if language == 'ja':
                                system_prompt_script_translator_again = f"I tried to translate this content into Japanese: {sentence}.\n\nBut I found that there is also an English part in it. Can you help me translate it again and make sure it is all translated into Japanese. Aiming for naturalness, and try to make it sound like a native Japanese speaker. In any case, strictly only provide the Chinese part of the translation. No brackets. Keep all proper nouns (like programming languages, brand names, etc.) unchanged. For example, 'I write this code with Rust.' should be translated as 'このコードはRustで書きました。'"
                            else:
                                system_prompt_script_translator_again = f"I tried to translate this content into Chinese: {sentence}.\n\nBut I found that there is also an English part in it. Can you help me translate it again and make sure it is all translated into Chinese. Aiming for naturalness, and try to make it sound like a native Chinese speaker. In any case, strictly only provide the Chinese part of the translation. Delete spaces in sentences appropriately and no brackets. Keep all proper nouns (like programming languages, brand names, etc.) unchanged. For example, 'I write this code with Rust.' should be translated as '我用 Rust 编写这段代码。'"
                            if attempts == 0:
                                this_sentence = sentence
                                this_system_prompt_script_translator = system_prompt_script_translator
                            else:
                                this_sentence = sentence_translation
                                this_system_prompt_script_translator = system_prompt_script_translator_again
                            attempts += 1
                            non_trans_words = re.findall(transcript_pattern, sentence_translation)
                            non_trans_words = [word.lower() for word in non_trans_words if word.strip()]
                            invalid_words = [item for item in non_trans_words if item not in all_words]
                            if invalid_words:
                                unique_invalid_words = set(invalid_words)
                                existing_words = set()
                                try:
                                    with open('invalid_characters.txt', 'r', encoding='utf-8') as file:
                                        existing_words = set(file.read().splitlines())
                                except FileNotFoundError:
                                    pass
                                new_invalid_words = unique_invalid_words - existing_words
                                if new_invalid_words:
                                    with open('invalid_characters.txt', 'a', encoding='utf-8') as file:
                                        for word in new_invalid_words:
                                            file.write(f"{word}\n")  # 每个非法字符一行
                                print(f"发现了非法字符：{invalid_words}")
                            if (len(invalid_words) > 0 and len(non_trans_words) >= 4) or bool(re.search(r'（.*?）', sentence_translation)) or sentence_translation.startswith("'") or sentence_translation.startswith('"'):
                                time.sleep(3)
                                new_translation = openai_gpt_chat(
                                    this_system_prompt_script_translator,
                                    this_sentence, youtube_link, email_link)
                                new_translation = new_translation.replace('\n', '')
                                if new_translation == sentence_translation:
                                    break
                                sentence_translation = new_translation
                            else:
                                break
                        print(sentence_translation)
                        translated_text_list.append(f"[{start_time} --> {end_time}]  {sentence_translation}")
                except Exception as e:
                    send_error_email(f"step 6: 翻译失败{final_transcript[i]}失败：{e}", youtube_link, email_link)
                    print("翻译失败")
                    return
            translated_text = "\n".join(translated_text_list)
            print("中文翻译文本：")
            print(translated_text)
            # 将 translated_script 保存为 txt 文件，文件名为音频文件名 + _cn.txt 后缀
            translated_script_file = os.path.splitext(dst_video)[0] + f"_{language}.txt"
            with open(translated_script_file, "w") as f:
                f.write(translated_text)
            # 通过 chinese_audio_generation 函数生成中文音频并保存在 Video_downloaded 目录下，dst_audio 的文件名后增加 _cn + .mp3 后缀
            output_file = os.path.splitext(dst_video)[0] + f"_{language}.mp3"
            fix_video = chinese_audio_batch_generation_and_merge(translated_text, output_file, offset_seconds,
                                                                 dst_video, youtube_link, email_link,
                                                                 model_id, api_key=fish_audio_api_key)
            # 判断 output_file 是否存在，如果存在则打印成功信息
            if os.path.isfile(output_file):
                print(f"中文音频已生成并保存为 {output_file}")
                try:
                    srt_file = ""
                    if with_srt != 0:
                        srt_file = f"{os.path.splitext(dst_video)[0]}_srt.srt"
                        convert_to_srt(translated_text, srt_file)
                    output_filename_list = process_video(fix_video, dst_video, output_file, offset_seconds, language,
                                                         srt_file, with_srt)
                    output_video_filename = output_filename_list['output_video_filename']
                    output_srt_filename = output_filename_list['output_srt_filename']
                    # 将 output_filename 移到 video_generated 文件夹下，并打印最新的文件 path，另外将video_downloaded_dir文件夹中剩余的其他文件移到 video_temp_dir
                    final_video = os.path.basename(output_video_filename)
                    final_srt = os.path.basename(output_srt_filename)
                    final_en = os.path.basename(transcript_file)
                    final_transcript = os.path.basename(translated_script_file)
                    new_video_file = os.path.join(video_generated, final_video)
                    shutil.move(output_video_filename, new_video_file)
                    new_srt_file = os.path.join(video_generated, final_srt)
                    shutil.move(output_srt_filename, new_srt_file)
                    new_transcript_file = os.path.join(video_generated, final_en)
                    shutil.move(transcript_file, new_transcript_file)
                    new_translated_script_file = os.path.join(video_generated, final_transcript)
                    shutil.move(translated_script_file, new_translated_script_file)
                    # for f in os.listdir(video_downloaded_dir):
                    #     file_path = os.path.join(video_downloaded_dir, f)
                    #     if os.path.isfile(file_path):
                    #         target_file = os.path.join(video_temp_dir, f)
                    #         shutil.move(file_path, target_file)

                except Exception as e:
                    send_error_email(f"step 10: 合并视频、字幕文件失败：{e}", youtube_link, email_link)
                    print(f"视频处理失败。{e}")
                url = "https://code.flows.network/webhook/ruvTvWEtUoK0WyZq3w5y/send_email"

                if language == "ja":
                    trans_message = f"親愛なるユーザーの皆様，\n\n弊社の動画翻訳サービスをご利用いただき誠にありがとうございます。ビデオの翻訳が完了しました。翻訳されたビデオは以下のリンクからご覧いただけます：\n{DOMAIN}/videos/{final_video}\n\n字幕付きのオリジナル動画：\n{DOMAIN}/videos/{final_srt}\n\nオリジナル動画から認識されたテキスト：\n{DOMAIN}/videos/{final_en}\n\n翻訳されたテキスト：\n{DOMAIN}/videos/{final_transcript}\n\nご質問がある場合、またはさらにサポートが必要な場合は、お気軽にお問い合わせください。\n\nご支援に改めて感謝し、より質の高いサービスを提供できることを楽しみにしています！\n\n幸運を祈ります，\n\nSecond State チーム"
                else:
                    trans_message = f"尊敬的用户，\n\n感谢您使用我们的视频翻译服务。我们已经完成了您的视频翻译工作，您可以通过以下链接查看翻译后的视频：\n{DOMAIN}/videos/{final_video}\n\n原声加字幕的视频：\n{DOMAIN}/videos/{final_srt}\n\n原视频识别到的文字：\n{DOMAIN}/videos/{final_en}\n\n翻译后的文字：\n{DOMAIN}/videos/{final_transcript}\n\n如果您有任何疑问或需要进一步的帮助，请随时与我们联系。\n\n再次感谢您的支持，期待为您提供更多优质的服务！\n\n祝好，\n\nSecond State 团队"
                data = {
                    "code": "1234",
                    "mime": "text/plain",
                    "to": email_link,
                    "subject": "您的视频翻译已完成 | Your Video Translation is Complete",
                    "body": f"{trans_message}\n\n\nDear User,\n\nThank you for using our video translation service. We have completed the translation of your video, and you can view the translated video via the link below:\n{DOMAIN}/videos/{final_video}\n\nOriginal video with subtitles:\n{DOMAIN}/videos/{final_srt}\n\nText recognized from the original video:\n{DOMAIN}/videos/{final_en}\n\nTranslated text:\n{DOMAIN}/videos/{final_transcript}\n\nIf you have any questions or need further assistance, feel free to contact us.\n\nOnce again, thank you for your support. We look forward to serving you in the future!\n\nBest regards,\n\nSecond State Team"
                }

                # 发送 POST 请求，使用 json 参数将字典自动转换为 JSON 格式
                response = requests.post(url, json=data)

                # 打印响应结果
                print(response.status_code)
                print(response.text)
            else:
                send_error_email(f"step 7/8/9: 调整视频速度、音频生成失败：", youtube_link, email_link)
                print("中文音频生成失败。")

    except Exception as e:
        send_error_email(f"step *: 未知的错误类型：{e}", youtube_link, email_link)
        print("Error，正在清空 Video_temp 目录。")
        print(f"错误信息：{e}")
        # # 清空 Video_temp 目录
        # for f in os.listdir(video_temp_dir):
        #     file_path = os.path.join(video_temp_dir, f)
        #     if os.path.isfile(file_path):
        #         os.unlink(file_path)
        #     elif os.path.isdir(file_path):
        #         shutil.rmtree(file_path)


if __name__ == '__main__':
    print("欢迎使用视频一键翻译神器！")
    main()
