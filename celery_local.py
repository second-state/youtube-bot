from Celery import Celery
from flask import Flask

# 初始化 Flask 应用
app = Flask(__name__)

def make_celery(app):
    # 初始化 Celery
    c = Celery(
        app.import_name,
        broker='pyamqp://guest@localhost//',  # RabbitMQ 默认配置
        backend='rpc://'
    )

    celery.conf.update(app.config)
    return c

celery = make_celery(app)
