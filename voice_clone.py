import os
from dotenv import load_dotenv
load_dotenv()
import requests

fish_audio_api_key = os.getenv("FISH_AUDIO_API_KEY")


def audio_model_create(mp3_file_path, voice_title, voice_text, api_key=fish_audio_api_key):
    response = requests.post(
        "https://api.fish.audio/model",
        files=[
            ("voices", open(mp3_file_path, "rb"))
        ],
        data=[
            ("visibility", "private"),
            ("type", "tts"),
            ("title", voice_title),
            ("train_mode", "fast"),
            # Enhance audio quality will remove background noise
            ("enhance_audio_quality", "true"),
            # Texts are optional, but if you provide them, they must match the number of audio samples
            ("texts", voice_text),
        ],
        headers={
            "Authorization": f"Bearer {api_key}",
        },
    )
    print(response.json())

    '''{'_id': '2b989360f39949d49c49ec4cd3e5d74c', 'type': 'tts', 'title': 'leowang_voice_clone', 'description': '', 'cover_image': 'coverimage/2b989360f39949d49c49ec4cd3e5d74c', 'train_mode': 'fast', 'state': 'trained', 'tags': [], 'samples': [], 'created_at': '2024-09-13T03:01:57.793775Z', 'updated_at': '2024-09-13T03:01:57.793369Z', 'languages': ['zh'], 'visibility': 'private', 'lock_visibility': False, 'like_count': 0, 'mark_count': 0, 'shared_count': 0, 'task_count': 0, 'liked': False, 'marked': False, 'author': {'_id': '29799cfe715540fc907f2bb6f0be72ad', 'nickname': 'Leo Wang', 'avatar': 'avatars/29799cfe715540fc907f2bb6f0be72ad.jpg'}}'''

    '''{'_id': 'a757154213a9446dac775634052c978b', 'type': 'tts', 'title': 'leowang_voice_english', 'description': '', 'cover_image': 'coverimage/a757154213a9446dac775634052c978b', 'train_mode': 'fast', 'state': 'trained', 'tags': [], 'samples': [], 'created_at': '2024-09-13T15:00:59.928006Z', 'updated_at': '2024-09-13T15:00:59.927369Z', 'languages': ['en'], 'visibility': 'private', 'lock_visibility': False, 'like_count': 0, 'mark_count': 0, 'shared_count': 0, 'task_count': 0, 'liked': False, 'marked': False, 'author': {'_id': '29799cfe715540fc907f2bb6f0be72ad', 'nickname': 'Leo Wang', 'avatar': 'avatars/29799cfe715540fc907f2bb6f0be72ad.jpg'}}'''

    '''{'_id': '5567c86e711447848ac70a8d57285deb', 'type': 'tts', 'title': 'danliyu_voice_chinese', 'description': '', 'cover_image': 'coverimage/5567c86e711447848ac70a8d57285deb', 'train_mode': 'fast', 'state': 'trained', 'tags': [], 'samples': [], 'created_at': '2024-09-13T19:01:56.905320Z', 'updated_at': '2024-09-13T19:01:56.904834Z', 'languages': ['zh'], 'visibility': 'private', 'lock_visibility': False, 'like_count': 0, 'mark_count': 0, 'shared_count': 0, 'task_count': 0, 'liked': False, 'marked': False, 'author': {'_id': '29799cfe715540fc907f2bb6f0be72ad', 'nickname': 'Leo Wang', 'avatar': 'avatars/29799cfe715540fc907f2bb6f0be72ad.jpg'}}'''


if __name__ == "__main__":
    mp3_file_path = "Audio_files/Danli_chinese.mp3"
    voice_title = "danliyu_voice_chinese"
    voice_text = "在清晨的阳光中，城市的每个角落都开始苏醒。马路上的车辆渐渐增多，人们匆匆地走向各自的目的地。街道旁的咖啡店，弥漫着浓郁的香气，吸引了路过的行人。每一口热咖啡都仿佛是一种安慰，带来短暂的平静。在这个充满节奏的世界中，我们每个人都在追寻属于自己的节奏。有人喜欢在安静的书房里工作，而有人更习惯于在繁忙的咖啡馆中思考。无论选择哪种方式，重要的是，我们要找到让自己舒适并高效的方法。"
    audio_model_create(mp3_file_path, voice_title, voice_text)
