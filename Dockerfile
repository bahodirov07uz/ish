# Python bazaviy image
FROM python:3.11-slim

# UV o'rnatish
RUN pip install uv

# Ishchi papka
WORKDIR /app

# Faqat kerakli tizim kutubxonalari (agar kerak bo'lsa)
RUN apt-get update && apt-get install -y \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Loyihani nusxalash
COPY . .

# UV orqali kutubxonalarni o'rnatish
RUN uv sync --frozen

# Port ochish
EXPOSE 8000

# Django serverni ishga tushirish
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]