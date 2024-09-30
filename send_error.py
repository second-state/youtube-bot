import requests
def send_error_email(error_message,fileName, email_link):
    # 构造邮件内容
    url = "https://code.flows.network/webhook/ruvTvWEtUoK0WyZq3w5y/send_email"
    data = {
        "code": "1234",
        "mime": "text/plain",
        "to": "juyichen0413@gmail.com",
        "subject": "youtube_bot 程序错误通知",
        "message": f"程序运行出错，错误信息：{error_message}\n\n文件地址：{fileName}\n\n接收人：{email_link}"
    }
    response = requests.post(url, json=data)
    return response.status_code
