FROM python:3.9-slim

WORKDIR /app

# 安装Poetry
RUN pip install poetry==1.6.1

# 复制项目文件
COPY pyproject.toml poetry.lock* ./

# 配置Poetry不创建虚拟环境（因为在容器中没有必要）
RUN poetry config virtualenvs.create false

# 安装依赖
RUN poetry install --no-dev

# 复制项目代码
COPY . .

# 收集静态文件
RUN python manage.py collectstatic --noinput

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "LibraryManagementSystem.wsgi"] 