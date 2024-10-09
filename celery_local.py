from celery import Celery

def make_celery(app):
    # 初始化 Celery
    celery = Celery(
        app.import_name,
        broker='pyamqp://guest@localhost//',  # RabbitMQ 默认配置
        backend='rpc://'
    )

    celery.conf.update(app.config)
    return celery
