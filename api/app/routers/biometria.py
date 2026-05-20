"""
Router: Biometría + Recursos REST
==================================
Endpoints principales:
  GET  /biometria/estudiantes_sin_rostro → Estudiantes sin enrolamiento facial
  POST /biometria/registrar_rostro       → Enrolar rostro en AWS Rekognition
  POST /biometria/marcar_ingreso         → Identificar alumno y registrar ingreso

Endpoints REST heredados:
  GET  /alumnos    → Listar alumnos
  GET  /cursos     → Listar cursos
  GET  /profesores → Listar profesores
"""

import logging
import os
from datetime import datetime, time

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.db import db_cursor

load_dotenv()

logger = logging.getLogger(__name__)


class EstudianteSinRostro(BaseModel):
    uid: str
    nombres: str
    apellidos: str

class RegistroRostroResponse(BaseModel):
    success: bool
    estudiante_id: str
    face_id: str
    estudiante_uid: str

class IngresoResponse(BaseModel):
    success: bool
    mensaje: str
    estudiante_uid: str
    nombres: str
    apellidos: str
    estado_ingreso: str
    hora_llegada: str

# ─── Cliente AWS Rekognition ──────────────────────────────────────────────────
rekognition = boto3.client(
    "rekognition",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)

COLLECTION_ID = os.getenv("REKOGNITION_COLLECTION_ID", "colegio_faces")


def _ensure_collection_exists(collection_id: str) -> None:
    try:
        rekognition.describe_collection(CollectionId=collection_id)
    except rekognition.exceptions.ResourceNotFoundException:
        try:
            rekognition.create_collection(CollectionId=collection_id)
            logger.info("Rekognition collection creada: %s", collection_id)
        except ClientError as e:
            logger.error("No se pudo crear la coleccion Rekognition: %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudo crear la coleccion de Rekognition. Verifique credenciales y permisos.",
            )
    except ClientError as e:
        logger.error("Error al verificar coleccion Rekognition: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo verificar la coleccion de Rekognition. Intente nuevamente.",
        )
SIMILARITY_THRESHOLD = float(os.getenv("REKOGNITION_SIMILARITY_THRESHOLD", "90.0"))
HORA_LIMITE = time(8, 0, 0)  # 08:00 AM — umbral puntualidad


# ─── Schemas Pydantic ─────────────────────────────────────────────────────────

class RegistrarBiometriaRequest(BaseModel):
    estudiante_id: str
    imagen_base64: str  # Foto frontal del estudiante, sin prefijo "data:image/..."

class ReconocerRostroRequest(BaseModel):
    imagen_base64: str

# ─────────────────────────────────────────────────────────────────────────────
# ROUTER PRINCIPAL — Biometría
# ─────────────────────────────────────────────────────────────────────────────

router_biometria = APIRouter(prefix="/biometria", tags=["Biometría"])


# ── GET /biometria/estudiantes_sin_rostro ────────────────────────────────────

@router_biometria.get(
    "/estudiantes_sin_rostro",
    response_model=list[EstudianteSinRostro],
    summary="Listar estudiantes sin rostro registrado",
)
def estudiantes_sin_rostro():
    """
    Devuelve todos los estudiantes cuyo campo `rekognition_face_id` es NULL,
    es decir, que aún no han sido enrolados en AWS Rekognition.
    """
    with db_cursor() as cur:
        cur.execute(
            "SELECT uid, nombres, apellidos "
            "FROM estudiante "
            "WHERE rekognition_face_id IS NULL;"
        )
        filas = cur.fetchall()

    # RealDictCursor devuelve dicts; convertimos uid a str por si es UUID nativo
    return [
        {
            "uid": str(f["uid"]),
            "nombres": f["nombres"],
            "apellidos": f["apellidos"],
        }
        for f in filas
    ]


# ── POST /biometria/registrar_rostro ─────────────────────────────────────────

@router_biometria.post(
    "/registrar_rostro",
    response_model=RegistroRostroResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enrolar biometría facial de un estudiante (IndexFaces)",
)
async def registrar_rostro(
    archivo: UploadFile = File(..., description="Foto frontal del estudiante"),
    estudiante_uid: str = Form(..., description="UID (UUID) del estudiante"),
):
    """
    Recibe la foto del estudiante en Base64 y la indexa en la colección de
    AWS Rekognition usando IndexFaces.
    Guarda el face_id devuelto para usarlo luego en el reconocimiento.
    """
    imagen_bytes = await archivo.read()

    if not imagen_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de imagen está vacío.",
        )

    # ── Indexar rostro en AWS Rekognition ─────────────────────────────────
    _ensure_collection_exists(COLLECTION_ID)
    try:
        response = rekognition.index_faces(
            CollectionId=COLLECTION_ID,
            Image={"Bytes": imagen_bytes},
            ExternalImageId=str(estudiante_uid),
            MaxFaces=1,
            QualityFilter="AUTO",
            DetectionAttributes=["DEFAULT"],
        )
    except ClientError as e:
        logger.error("Error AWS Rekognition IndexFaces: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al comunicarse con AWS Rekognition: {e.response['Error']['Message']}",
        )

    face_records = response.get("FaceRecords", [])
    if not face_records:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se detectó ningún rostro en la imagen. "
                   "Use una foto frontal con buena iluminación.",
        )

    face_id = face_records[0]["Face"]["FaceId"]
    logger.info(f"Biometría enrolada: estudiante_uid={estudiante_uid}, face_id={face_id}")

    # Nodo "Confirmar enrolamiento"
    return {
        "success": True,
        "estudiante_id": str(estudiante_uid),
        "face_id": face_id,
        "estudiante_uid": estudiante_uid,
    }


# ── POST /biometria/marcar_ingreso ───────────────────────────────────────────

@router_biometria.post(
    "/marcar_ingreso",
    response_model=IngresoResponse,
    summary="Identificar alumno por rostro y registrar ingreso",
)
async def marcar_ingreso(
    archivo: UploadFile = File(..., description="Foto capturada en la puerta del colegio"),
):
    """
    Recibe la imagen capturada en la puerta del colegio, busca coincidencia
    en AWS Rekognition, determina puntualidad y registra el ingreso en la BD.
    """
    imagen_bytes = await archivo.read()

    if not imagen_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de imagen está vacío.",
        )

    # ── Buscar rostro en la colección de Rekognition ─────────────────────
    _ensure_collection_exists(COLLECTION_ID)
    try:
        response = rekognition.search_faces_by_image(
            CollectionId=COLLECTION_ID,
            Image={"Bytes": imagen_bytes},
            MaxFaces=1,
            FaceMatchThreshold=SIMILARITY_THRESHOLD,
        )
    except rekognition.exceptions.InvalidParameterException:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se detectó ningún rostro en la imagen proporcionada.",
        )
    except ClientError as e:
        logger.error("Error AWS Rekognition SearchFacesByImage: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al comunicarse con AWS Rekognition: {e.response['Error']['Message']}",
        )

    face_matches = response.get("FaceMatches", [])
    if not face_matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rostro no reconocido. Verifique que el alumno esté enrolado.",
        )

    face_id_match = face_matches[0]["Face"]["FaceId"]

    # ── Buscar al estudiante en PostgreSQL ───────────────────────────────
    with db_cursor() as cur:
        cur.execute(
            "SELECT uid, nombres, apellidos, matricula_actual_uid "
            "FROM estudiante "
            "WHERE rekognition_face_id = %s;",
            (face_id_match,),
        )
        estudiante = cur.fetchone()

    if not estudiante:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El rostro fue reconocido por AWS pero no se encontró "
                   "un estudiante asociado en la base de datos.",
        )

    estudiante_uid = str(estudiante["uid"])
    nombres = estudiante["nombres"]
    apellidos = estudiante["apellidos"]
    matricula_uid = estudiante["matricula_actual_uid"]

    if not matricula_uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El estudiante {nombres} {apellidos} no tiene una matrícula activa.",
        )

    # ── Calcular estado de ingreso ───────────────────────────────────────
    ahora = datetime.now()
    estado_ingreso = "a_tiempo" if ahora.time() <= HORA_LIMITE else "tardanza"

    # ── Insertar registro de ingreso ─────────────────────────────────────
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO registro_ingreso "
            "(matricula_uid, estudiante_uid, fecha_ingreso, hora_llegada, estado_ingreso) "
            "VALUES (%s, %s, CURRENT_DATE, CURRENT_TIMESTAMP, %s) "
            "ON CONFLICT (matricula_uid, fecha_ingreso) DO NOTHING "
            "RETURNING hora_llegada, estado_ingreso;",
            (str(matricula_uid), estudiante_uid, estado_ingreso),
        )
        inserted = cur.fetchone()

        if inserted:
            hora_llegada = inserted["hora_llegada"]
            estado_final = inserted["estado_ingreso"]
            mensaje = "Registrado"
        else:
            cur.execute(
                "SELECT hora_llegada, estado_ingreso "
                "FROM registro_ingreso "
                "WHERE matricula_uid = %s AND fecha_ingreso = CURRENT_DATE;",
                (str(matricula_uid),),
            )
            previo = cur.fetchone()

            if not previo:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe un registro de ingreso para hoy, pero no se pudo recuperar.",
                )

            hora_llegada = previo["hora_llegada"]
            estado_final = previo["estado_ingreso"]
            mensaje = "Registrado"

    hora_str = hora_llegada.strftime("%H:%M:%S")
    logger.info(
        "Ingreso registrado: %s %s — %s (%s)",
        nombres, apellidos, estado_final, hora_str,
    )

    return {
        "success": True,
        "mensaje": mensaje,
        "estudiante_uid": estudiante_uid,
        "nombres": nombres,
        "apellidos": apellidos,
        "estado_ingreso": estado_final,
        "hora_llegada": hora_str,
    }


