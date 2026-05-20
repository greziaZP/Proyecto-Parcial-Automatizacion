"""
Router: Biometría + Recursos REST
==================================
Flujos n8n implementados:
  POST /biometria/registrar  → Nodo "AWS Rekognition (IndexFaces)"
  GET  /alumnos              → Nodo "GET Alumnos → Obtener Alumnos"
  GET  /cursos               → Nodo "GET Cursos → Obtener Cursos"
  GET  /profesores           → Nodo "GET Profesores → Obtener Profesores"
"""

import base64
import logging
import os
import psycopg2

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Cliente AWS Rekognition ──────────────────────────────────────────────────
rekognition = boto3.client(
    "rekognition",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)

COLLECTION_ID        = os.getenv("REKOGNITION_COLLECTION_ID", "colegio-faces")
SIMILARITY_THRESHOLD = float(os.getenv("REKOGNITION_SIMILARITY_THRESHOLD", "90.0"))

# ─── Schemas ──────────────────────────────────────────────────────────────────

class RegistrarBiometriaRequest(BaseModel):
    alumno_id: int
    imagen_base64: str  # Foto frontal del alumno, sin prefijo "data:image/..."

class ReconocerRostroRequest(BaseModel):
    imagen_base64: str

# ─────────────────────────────────────────────────────────────────────────────
# FLUJO 1: Registro de Biometría
# n8n: Webhook → AWS Rekognition (IndexFaces) → HTTP Request → Code JS → Confirmar
# ─────────────────────────────────────────────────────────────────────────────

router_biometria = APIRouter(prefix="/biometria", tags=["Biometría"])


@router_biometria.post(
    "/registrar",
    status_code=status.HTTP_201_CREATED,
    summary="Enrolar biometría facial de un alumno (IndexFaces)",
)
def registrar_biometria(payload: RegistrarBiometriaRequest):
    """
    Recibe la foto del alumno en Base64 y la indexa en la colección de
    AWS Rekognition usando IndexFaces.
    Guarda el face_id devuelto para usarlo luego en el reconocimiento.
    """
    # Nodo "Decodifica Base64"
    try:
        imagen_bytes = base64.b64decode(payload.imagen_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen no es un Base64 válido.",
        )

    # Nodo "AWS Rekognition (IndexFaces)"
    try:
        response = rekognition.index_faces(
            CollectionId=COLLECTION_ID,
            Image={"Bytes": imagen_bytes},
            ExternalImageId=str(payload.alumno_id),
            MaxFaces=1,
            QualityFilter="AUTO",
            DetectionAttributes=["DEFAULT"],
        )
    except ClientError as e:
        logger.error(f"Error AWS Rekognition IndexFaces: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al comunicarse con AWS Rekognition: {e.response['Error']['Message']}",
        )

    face_records = response.get("FaceRecords", [])

    # Nodo "Code in JavaScript": validar si se detectó cara
    if not face_records:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se detectó ninguna cara en la imagen. Use una foto frontal con buena iluminación.",
        )

    face_id = face_records[0]["Face"]["FaceId"]
    logger.info(f"Biometría enrolada: alumno_id={payload.alumno_id}, face_id={face_id}")

    # Nodo "Confirmar enrolamiento"
    return {
        "success": True,
        "alumno_id": payload.alumno_id,
        "face_id": face_id,
        "mensaje": f"Biometría registrada exitosamente. face_id: {face_id}",
    }


@router_biometria.post(
    "/reconocer_rostro",
    status_code=status.HTTP_200_OK,
    summary="Reconoce un rostro en base64 y registra su ingreso",
)
def reconocer_rostro(payload: ReconocerRostroRequest):
    """
    Decodifica el base64, busca el rostro en Rekognition e inserta el 
    registro_ingreso real en PostgreSQL.
    """
    try:
        imagen_bytes = base64.b64decode(payload.imagen_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen no es un Base64 válido."
        )
        
    try:
        response = rekognition.search_faces_by_image(
            CollectionId=COLLECTION_ID,
            Image={'Bytes': imagen_bytes},
            FaceMatchThreshold=SIMILARITY_THRESHOLD,
            MaxFaces=1
        )
    except ClientError as e:
        logger.error(f"Error AWS Rekognition SearchFacesByImage: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al comunicarse con AWS Rekognition: {e.response['Error']['Message']}"
        )

    face_matches = response.get("FaceMatches", [])
    if not face_matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rostro no reconocido."
        )

    # Obtenemos el ExternalImageId que se guardó al enrolar (uuid del estudiante)
    estudiante_uid = face_matches[0]["Face"].get("ExternalImageId")
    if not estudiante_uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El rostro reconocido no tiene un ExternalImageId válido asociado."
        )

    # Conectar a PostgreSQL para insertar la asistencia
    # Nota: extraemos "matricula_actual_uid" para respetar el NOT NULL de la DB
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "mysecretpassword"),
            dbname=os.getenv("POSTGRES_DB", "defaultdb")
        )
        with conn.cursor() as cur:
            # 1. Obtener la matrícula activa
            cur.execute("""
                SELECT matricula_actual_uid 
                FROM estudiante 
                WHERE uid = %s;
            """, (estudiante_uid,))
            res = cur.fetchone()
            if not res or not res[0]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El estudiante no tiene una matrícula activa."
                )
            matricula_uid = res[0]

            # 2. Insertar el ingreso
            cur.execute("""
                INSERT INTO registro_ingreso (matricula_uid, estudiante_uid)
                VALUES (%s, %s)
                RETURNING uid;
            """, (matricula_uid, estudiante_uid))
            ingreso_uid = cur.fetchone()[0]
        
        conn.commit()
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        logger.error(f"Error DB guardando asistencia biométrica: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno guardando la asistencia: {str(e)}"
        )
    finally:
        if 'conn' in locals():
            conn.close()

    return {
        "success": True,
        "estudiante_uid": estudiante_uid,
        "ingreso_uid": str(ingreso_uid),
        "mensaje": "Ingreso registrado correctamente."
    }

# ─────────────────────────────────────────────────────────────────────────────
# FLUJO 2: Endpoints REST — Alumnos / Cursos / Profesores
# n8n: GET Alumnos → Obtener Alumnos | GET Cursos → Obtener Cursos | etc.
# ─────────────────────────────────────────────────────────────────────────────

router_rest = APIRouter(tags=["REST"])


@router_rest.get("/alumnos", summary="Listar alumnos")
def obtener_alumnos():
    """Equivale al nodo n8n: GET Alumnos → Obtener Alumnos."""
    # TODO: reemplazar con consulta a DB real → db.query(Alumno).all()
    return {"mensaje": "Conectar con la base de datos PostgreSQL"}


@router_rest.get("/cursos", summary="Listar cursos")
def obtener_cursos():
    """Equivale al nodo n8n: GET Cursos → Obtener Cursos."""
    # TODO: reemplazar con consulta a DB real → db.query(Curso).all()
    return {"mensaje": "Conectar con la base de datos PostgreSQL"}


@router_rest.get("/profesores", summary="Listar profesores")
def obtener_profesores():
    """Equivale al nodo n8n: GET Profesores → Obtener Profesores."""
    # TODO: reemplazar con consulta a DB real → db.query(Profesor).all()
    return {"mensaje": "Conectar con la base de datos PostgreSQL"}
