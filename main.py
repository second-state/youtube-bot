import os
import re
import requests
import subprocess

from format_timestamps import *
from voice_generate import *

load_dotenv()

DOMAIN = os.getenv("DOMAIN")


def main(second=0, youtube_link="https://www.youtube.com/watch?v=Hf9zfjflP_0", email_link="juyichen0413@gmail.com",
         sound_id="59cb5986671546eaa6ca8ae6f29f6d22", language="zh", with_srt=0):
    video_temp_dir = 'Video_temp'
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
            print(f"下载失败：{e}")
            return
    else:
        # 如果是文件路径，则直接移动到 video_temp_dir 目录下
        if os.path.isfile(youtube_link):
            new_input_file = os.path.join(video_temp_dir, os.path.basename(youtube_link))
            shutil.move(youtube_link, new_input_file)
        else:
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
                    print(f"转换 {f} 为 mp4 时出错：{e}")
                    continue  # 跳过此文件，继续下一个

            # 在此处调用提取音频的功能
            audio_file = split_audio_from_mp4(src, output_audio_format='wav')

            # 移动 mp4 文件到目标目录
            dst_video = os.path.join(video_downloaded_dir, os.path.basename(src))
            shutil.move(src, dst_video)

            # 如果音频提取成功，移动音频文件到目标目录，并删除源文件；如果音频文件不存在，则退出程序并告知用户
            if audio_file:
                dst_audio = os.path.join(video_downloaded_dir, os.path.basename(audio_file))
                shutil.move(audio_file, dst_audio)
                print(f"音频已提取并保存为 {dst_audio}")

            else:
                print("音频提取失败，已退出程序。")
                return
            print("下载成功，视频已转换为 mp4，音频已提取，并移动到 Video_downloaded 目录。")
            # 通过 get_transcript 函数获取音频文件的转录文本
            result = get_transcript_with_timestamps(dst_audio)
            transcript = result["text"]
            print("音频转录文本：")
            print(transcript)
            print("合并成完整句子：")
            format_data = format_subtitles_with_timestamps(transcript)
            total = format_data["total"]
            transcript = format_data["transcript"]
            final_transcript = format_data["final_transcript"]
            # 将 transcript 保存为 txt 文件，文件名为音频文件名 + _en.txt 后缀
            transcript_file = os.path.splitext(dst_audio)[0] + "_en.txt"
            with open(transcript_file, "w") as f:
                f.write(transcript)
            # 通过 openai_gpt_chat 函数获取中文翻译
            print("正在将英文脚本翻译为中文...")
            translated_text_list = []
            for i, line in enumerate(final_transcript):
                pattern = r'\[(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)'
                match = re.match(pattern, line)
                if match:
                    start_time = match.group(1)
                    end_time = match.group(2)
                    sentence = match.group(3)
                    if language == 'ja':
                        system_prompt_script_translator = system_prompt_script_translator_japanese
                    else:
                        system_prompt_script_translator = system_prompt_script_translator_chinese
                    sentence_translation = openai_gpt_chat(system_prompt_script_translator, sentence)
                    print(sentence_translation)
                    if bool(re.search(r'[a-zA-Z]', sentence_translation)):
                        system_prompt_script_translator_again = f"I tried to translate this content into Chinese: {sentence}, but I found that there is also an English part in it. Can you help me translate it again and make sure it is all translated into Chinese. This is what I translated this time:"
                        sentence_translation = openai_gpt_chat(
                            system_prompt_script_translator + system_prompt_script_translator_again,
                            sentence_translation)
                        print(sentence_translation)
                    translated_text_list.append(f"[{start_time} --> {end_time}]  {sentence_translation}")
            translated_text = "\n".join(translated_text_list)
            print("中文翻译文本：")
            print(translated_text)
            # 将 translated_script 保存为 txt 文件，文件名为音频文件名 + _cn.txt 后缀
            translated_script_file = os.path.splitext(dst_audio)[0] + f"_{language}.txt"
            with open(translated_script_file, "w") as f:
                f.write(translated_text)
            # 通过 chinese_audio_generation 函数生成中文音频并保存在 Video_downloaded 目录下，dst_audio 的文件名后增加 _cn + .mp3 后缀
            output_file = os.path.splitext(dst_audio)[0] + f"_{language}.mp3"
            fix_video = chinese_audio_batch_generation_and_merge(translated_text, output_file, offset_seconds, dst_video,
                                                                model_id, api_key=fish_audio_api_key)
            # 判断 output_file 是否存在，如果存在则打印成功信息
            if os.path.isfile(output_file):
                print(f"中文音频已生成并保存为 {output_file}")
                try:
                    srt_file = ""
                    if with_srt != 0:
                        srt_file = f"{os.path.splitext(dst_audio)[0]}_srt.srt"
                        convert_to_srt(translated_text, srt_file)
                    output_filename_list = process_video(fix_video, dst_video, output_file, offset_seconds, language, srt_file, with_srt)
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
                    # 用 openai_gpt_chat(system_prompt, prompt) 为视频 title 生成中文翻译，prompt 为视频base file name，并用翻译后的中文title 替代原始的 title
                    # # chinese_title = openai_gpt_chat(os.getenv("SYSTEM_PROMPT_TITLE_TRANSLATOR"), english_title)
                    # new_output_file_cn = os.path.join(video_generated, english_title + '_cn.mp4')
                    # os.rename(new_output_file, new_output_file_cn)
                    # print(f"Output file: {final_title}")
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
                    # for f in os.listdir(video_downloaded_dir):
                    #     file_path = os.path.join(video_downloaded_dir, f)
                    #     if os.path.isfile(file_path):
                    #         target_file = os.path.join(video_temp_dir, f)
                    #         shutil.move(file_path, target_file)

                except:
                    print("视频处理失败。")
            else:
                print("中文音频生成失败。")

    except Exception as e:
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
