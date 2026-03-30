import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
import motor_logico
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="API Asistente SRI")

# Carga las credenciales desde .env
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

class Consulta(BaseModel):
    pregunta: str
    user_id: str

@app.get("/")
def inicio():
    return {"mensaje": "Servidor IA Idrix Operativo"}

@app.post("/preguntar")
def preguntar(datos: Consulta):
    """Cualquier usuario puede preguntar (usando su user_id)"""
    try:
        respuesta = motor_logico.obtener_respuesta_ia(datos.pregunta, datos.user_id)
        return {"respuesta": respuesta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/subir-pdf")
async def subir_pdf(
    archivo: UploadFile = File(...),
    usuario: str = Form(...),
    password: str = Form(...)
):
    """SOLO EL ADMIN: Sube un PDF a la base de conocimientos"""
    # Validación de seguridad con las variables del .env
    if usuario != ADMIN_USER or password != ADMIN_PASS:
        raise HTTPException(status_code=401, detail="Credenciales de administrador incorrectas")
        
    if not archivo.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Debe ser PDF")
    
    try:
        ruta_temporal = f"temp_{archivo.filename}"
        with open(ruta_temporal, "wb") as buffer:
            shutil.copyfileobj(archivo.file, buffer)
        
        # Llama al motor lógico
        motor_logico.procesar_pdf_a_supabase(ruta_temporal)
        
        # Limpia el archivo físico
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
            
        return {"mensaje": f"Documento '{archivo.filename}' subido por el Admin correctamente."}
    except Exception as e:
        if os.path.exists(f"temp_{archivo.filename}"):
            os.remove(f"temp_{archivo.filename}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/eliminar-pdf")
def eliminar_pdf(
    nombre_archivo: str = Form(...),
    usuario: str = Form(...),
    password: str = Form(...)
):
    """SOLO EL ADMIN: Elimina un PDF de la base de conocimientos"""
    # Validación de seguridad
    if usuario != ADMIN_USER or password != ADMIN_PASS:
        raise HTTPException(status_code=401, detail="Credenciales de administrador incorrectas")
        
    try:
        # Llama al motor lógico
        motor_logico.eliminar_pdf_de_supabase(nombre_archivo)
        return {"mensaje": f"Documento '{nombre_archivo}' eliminado correctamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))