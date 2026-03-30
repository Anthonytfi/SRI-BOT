import os
import re
import pymupdf4llm
from dotenv import load_dotenv
from supabase import create_client, Client
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq

# --- 1. CARGAR CONFIGURACIÓN Y LLAVES ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Extraer y ORDENAR las llaves de Groq (1, 2, 3...)
nombres_keys = [k for k in os.environ if k.startswith("GROQ_API_KEY_")]
nombres_keys.sort() 
API_KEYS = [os.getenv(k) for k in nombres_keys]

# Conexión a Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Modelo de Embeddings (Ligero y potente)
modelo_embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")

# Puntero global para el carrusel
contador_key = 0

# --- NUEVO: ID MAESTRO PARA LA BIBLIOTECA GLOBAL ---
ID_BIBLIOTECA_GLOBAL = "BIBLIOTECA_ADMIN"

# --- NUEVO: MEMORIA DE CONVERSACIÓN ---
memoria_conversacion = {}


# --- 2. MOTOR DE ROTACIÓN DE LLAVES ---
def obtener_llm_con_rotacion():
    """Selecciona la siguiente llave disponible en el carrusel."""
    global contador_key
    
    if not API_KEYS:
        raise Exception("No se encontraron llaves con el prefijo GROQ_API_KEY_ en el .env")

    # Intentamos usar las llaves disponibles una por una
    for _ in range(len(API_KEYS)):
        llave_actual = API_KEYS[contador_key % len(API_KEYS)]
        contador_key += 1
        
        try:
            # Creamos el objeto LLM con la llave de turno
            return ChatGroq(
                temperature=0, 
                model_name="llama-3.3-70b-versatile", 
                groq_api_key=llave_actual
            )
        except Exception as e:
            print(f"Error con llave {contador_key}: {e}. Saltando a la siguiente...")
            continue 
    
    raise Exception("Todas las API Keys han agotado sus límites o son inválidas.")

# --- 3. FUNCIÓN PARA PROCESAR PDF (BACKEND) ---
def procesar_pdf_a_supabase(ruta_pdf):
    """Extrae, limpia y sube vectores a la nube bajo el ID del Admin y limpia la memoria."""
    global memoria_conversacion
    
    texto_sucio = pymupdf4llm.to_markdown(ruta_pdf)
    
    # Limpieza profunda
    limpio = texto_sucio.replace('"', '').replace('|', ' ').replace('\r', '')
    limpio = re.sub(r'\n+', '\n', limpio)
    limpio = re.sub(r' +', ' ', limpio)

    # Troceado para RAG
    picadora = RecursiveCharacterTextSplitter(
        chunk_size=1200, 
        chunk_overlap=200,
        separators=["\n#", "\nArt.", "\n\n", ". ", "\n"]
    )
    pedazos = picadora.split_text(limpio)

    # Limpiar el nombre del archivo si viene de un archivo temporal
    nombre_archivo = os.path.basename(ruta_pdf)
    if nombre_archivo.startswith("temp_"):
        nombre_archivo = nombre_archivo[5:]

    # Forzamos a que el user_id sea siempre ID_BIBLIOTECA_GLOBAL
    metadatos = [{"user_id": ID_BIBLIOTECA_GLOBAL, "source": nombre_archivo} for _ in pedazos]

    # Inyección directa a Supabase
    SupabaseVectorStore.from_texts(
        texts=pedazos,
        embedding=modelo_embeddings,
        metadatas=metadatos,
        client=supabase,
        table_name="documentos_ia",
        query_name="match_documents"
    )
    
    memoria_conversacion.clear() 
    
    return len(pedazos)

# --- NUEVO: FUNCIÓN PARA ELIMINAR PDF ---
def eliminar_pdf_de_supabase(nombre_archivo: str):
    """Busca y elimina todos los fragmentos de un PDF en Supabase y limpia la memoria."""
    global memoria_conversacion # <--- NUEVO: Traemos la memoria global
    
    # Usamos el filtro de metadata para borrar solo los pedazos de ese archivo
    respuesta = supabase.table("documentos_ia").delete().eq("metadata->>source", nombre_archivo).execute()
    
    # <--- NUEVO: Vaciamos la memoria RAM para que nadie pregunte sobre info vieja
    memoria_conversacion.clear()
    
    return True

# --- 4. FUNCIÓN PARA PREGUNTAR (EL CORAZÓN DE LA API) ---
def obtener_respuesta_ia(pregunta, user_id):
    """Busca contexto en la biblioteca global y responde con la IA manteniendo memoria individual."""
    
    try:
        # 1. Convertimos la pregunta en números (vectores)
        vector_pregunta = modelo_embeddings.embed_query(pregunta)

        # 2. Llamada DIRECTA a nuestra función de Supabase (Esquivamos el bug)
        respuesta_bd = supabase.rpc(
            "match_documents", 
            {
                "query_embedding": vector_pregunta,
                "match_threshold": 0.1, # Nivel de similitud
                "match_count": 5,       # Traer los 5 mejores pedazos
                # CAMBIO: Filtramos siempre por la biblioteca del Admin para buscar respuestas
                "filter": {"user_id": ID_BIBLIOTECA_GLOBAL} 
            }
        ).execute()

        # 3. Extraemos los documentos de la respuesta
        documentos = respuesta_bd.data
        
        if not documentos or len(documentos) == 0:
            return "No encontré información en la base de conocimientos oficial para responder esta pregunta."

        # Unimos los pedazos de texto encontrados
        contexto = "\n\n".join([doc["content"] for doc in documentos])

        # --- NUEVO: GESTIÓN DE MEMORIA POR USUARIO ---
        if user_id not in memoria_conversacion:
            memoria_conversacion[user_id] = []
        
        # Tomamos solo los últimos 4 mensajes para no gastar muchos tokens
        historial_reciente = "\n".join(memoria_conversacion[user_id][-4:])

        # 4. Obtenemos el LLM del carrusel de llaves
        llm = obtener_llm_con_rotacion()

        prompt = f"""
        Eres un asistente experto en leyes y normativa del SRI (Ecuador). 
        Responde de forma profesional y precisa basándote ÚNICAMENTE en el contexto proporcionado.
        Si la respuesta no está en el contexto, di que no lo sabes.
        
        CONTEXTO OFICIAL:
        {contexto}
        
        HISTORIAL DE LA CONVERSACIÓN CON ESTE USUARIO:
        {historial_reciente}
        
        PREGUNTA ACTUAL:
        {pregunta}
        
        RESPUESTA:
        """
        
        respuesta = llm.invoke(prompt)
        
        # Guardamos la interacción actual en la memoria del usuario
        memoria_conversacion[user_id].append(f"Usuario: {pregunta}")
        memoria_conversacion[user_id].append(f"IA: {respuesta.content}")

        return respuesta.content

    except Exception as e:
        # Si algo falla, lo imprimimos en la terminal para saber qué fue
        print(f"Error en obtener_respuesta_ia: {e}")
        raise e