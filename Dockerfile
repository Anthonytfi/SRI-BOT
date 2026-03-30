# Usamos una versión de Python oficial y ligera
FROM python:3.11-slim

# Evita que Python escriba archivos .pyc y fuerza a que la salida de consola sea inmediata
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Creamos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos primero el archivo de requerimientos para aprovechar el caché de Docker
COPY requirements.txt /app/

# Instalamos las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de los archivos de tu proyecto (main.py, motor_logico.py, etc.)
COPY . /app/

# Exponemos el puerto 8000 que es el que usa FastAPI
EXPOSE 8000

# Comando para iniciar el servidor cuando el contenedor se levante
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]