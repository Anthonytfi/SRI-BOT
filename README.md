# 🧠 Backend de IA - Asistente SRI (Idrix)

Este es el servidor Backend que conecta la aplicación móvil con el motor de Inteligencia Artificial (Llama 3.3) utilizando una arquitectura RAG (Retrieval-Augmented Generation) con base de datos vectorial en Supabase.

## Arquitectura
* **Framework:** FastAPI (Python)
* **Base de Datos:** Supabase (PostgreSQL + pgvector)
* **Embeddings:** HuggingFace (`paraphrase-multilingual-MiniLM-L12-v2`)
* **LLM:** Llama 3.3 70B (Vía Groq)
* **Gestión de Tokens:** Carrusel automático de API Keys de Groq para alta disponibilidad.

## Variables de Entorno (.env)
Para que el servidor funcione, se debe crear un archivo `.env` en la raíz del proyecto con las siguientes credenciales:

```env
SUPABASE_URL=tu_url_de_supabase
SUPABASE_KEY=tu_anon_key_de_supabase
# Carrusel de tokens (puedes agregar N tokens siguiendo la secuencia)
GROQ_API_KEY_1=gsk_token_1
GROQ_API_KEY_2=gsk_token_2
```

## Instalación y Despliegue en Servidor (Idrix)

1. **Clonar o descargar el código fuente.**
2. **Crear y activar un entorno virtual (recomendado):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Para Linux/Mac
   # o
   venv\Scripts\activate     # Para Windows
   ```
3. **Instalar las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Ejecutar el servidor (Comando para Producción):**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## Contrato de API para el Desarrollador Móvil (Endpoints)

Una vez que el servidor esté en línea, el desarrollador móvil debe apuntar a estas rutas:

### 1. Hacer una pregunta a la IA
* **Ruta:** `POST /preguntar`
* **Headers:** `Content-Type: application/json`
* **Body (JSON):**
  ```json
  {
    "pregunta": "texto de la pregunta",
    "user_id": "identificador_unico_del_usuario"
  }
  ```
* **Respuesta Exitosa (200 OK):**
  ```json
  {
    "respuesta": "Texto generado por la IA..."
  }

### Subir un Documento (PDF) para un Usuario
* **Ruta:** `POST /subir-pdf`
* **Headers:** `Content-Type: multipart/form-data`
* **Campos del Formulario (Form Data):**
  * `user_id` (texto): Identificador único del usuario.
  * `archivo` (archivo): El archivo PDF físico seleccionado.
  
## Configuración de la Base de Datos (Supabase)

**IMPORTANTE:** El servidor requiere su propia base de datos Supabase con la extensión pgvector activada para buscar similitud de textos.

**Pasos para el equipo de Infraestructura:**
1. **Crear un proyecto nuevo en Supabase.**
2. **Ir a la sección SQL Editor en el menú izquierdo.**
3. **Pegar y ejecutar (Run) el siguiente código SQL para preparar las tablas y funciones de IA:**

```sql
-- 1. Activar la extensión de vectores
create extension if not exists vector;

-- 2. Crear la tabla para almacenar los documentos de los usuarios
create table documentos_ia (
  id bigserial primary key,
  content text,
  metadata jsonb,
  embedding vector(384) -- 384 es el tamaño del modelo multilingual de HuggingFace
);

-- 3. Crear la función de búsqueda de similitud (con filtro por usuario)
create or replace function match_documents (
  query_embedding vector(384),
  match_threshold float,
  match_count int,
  filter jsonb default '{}'
) returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language sql stable
as $$
  select
    documentos_ia.id,
    documentos_ia.content,
    documentos_ia.metadata,
    1 - (documentos_ia.embedding <=> query_embedding) as similarity
  from documentos_ia
  where metadata @> filter
  and 1 - (documentos_ia.embedding <=> query_embedding) > match_threshold
  order by documentos_ia.embedding <=> query_embedding
  limit match_count;
$$;

