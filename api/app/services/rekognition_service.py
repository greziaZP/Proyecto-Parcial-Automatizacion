import base64
import os
import logging
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()  # Lee el archivo .env automáticamente

logger = logging.getLogger(__name__)

# ─── Credenciales desde .env ──────────────────────────────────────────────────
AWS_ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION            = os.getenv("AWS_REGION", "us-east-1")
COLLECTION_ID         = os.getenv("REKOGNITION_COLLECTION_ID", "colegio-faces")
SIMILARITY_THRESHOLD  = float(os.getenv("REKOGNITION_SIMILARITY_THRESHOLD", "90.0"))

# ─── Cliente Rekognition ──────────────────────────────────────────────────────
_client = boto3.client(
    "rekognition",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)


# ─────────────────────────────────────────────────────────────────────────────
# IndexFaces — enrolar cara de un alumno
# Usado en: POST /biometria/registrar
# ─────────────────────────────────────────────────────────────────────────────

def registrar_cara(imagen_base64: str, alumno_id: int) -> dict:
    """
    Indexa la cara del alumno en la colección de Rekognition.

    Args:
        imagen_base64: Foto frontal del alumno en Base64.
        alumno_id: ID del alumno (se guarda como ExternalImageId en Rekognition).

    Returns:
        {
            "face_id": str,       # ID único asignado por Rekognition
            "alumno_id": int,
            "calidad": float,     # Confidence de la cara detectada
        }

    Raises:
        ValueError: Si la imagen no tiene cara detectable.
        ClientError: Si falla la comunicación con AWS.
    """
    imagen_bytes = base64.b64decode(imagen_base64)

    response = _client.index_faces(
        CollectionId=COLLECTION_ID,
        Image={"Bytes": imagen_bytes},
        ExternalImageId=str(alumno_id),
        MaxFaces=1,
        QualityFilter="AUTO",
        DetectionAttributes=["DEFAULT"],
    )

    face_records = response.get("FaceRecords", [])

    if not face_records:
        raise ValueError("No se detectó ninguna cara en la imagen.")

    cara = face_records[0]["Face"]

    return {
        "face_id": cara["FaceId"],
        "alumno_id": alumno_id,
        "calidad": cara.get("Confidence", 0.0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SearchFacesByImage — identificar quién es el alumno en la foto
# Usado en: POST /asistencia/registrar
# ─────────────────────────────────────────────────────────────────────────────

def identificar_cara(imagen_base64: str) -> dict | None:
    """
    Busca la cara de la imagen dentro de la colección de Rekognition.

    Args:
        imagen_base64: Foto capturada en el momento de marcar asistencia, en Base64.

    Returns:
        Si encuentra coincidencia:
        {
            "face_id": str,       # Face ID de la cara encontrada
            "alumno_id": str,     # ExternalImageId que pusimos al enrolar (= alumno_id)
            "similitud": float,   # Porcentaje de similitud (0-100)
        }
        Si NO encuentra coincidencia por encima del umbral: retorna None.

    Raises:
        ValueError: Si la imagen no tiene cara detectable.
        ClientError: Si falla la comunicación con AWS.
    """
    imagen_bytes = base64.b64decode(imagen_base64)

    try:
        response = _client.search_faces_by_image(
            CollectionId=COLLECTION_ID,
            Image={"Bytes": imagen_bytes},
            MaxFaces=1,
            FaceMatchThreshold=SIMILARITY_THRESHOLD,
        )
    except _client.exceptions.InvalidParameterException:
        raise ValueError("No se detectó ninguna cara en la imagen.")

    face_matches = response.get("FaceMatches", [])

    if not face_matches:
        return None  # Alumno no identificado

    mejor = face_matches[0]

    return {
        "face_id": mejor["Face"]["FaceId"],
        "alumno_id": mejor["Face"].get("ExternalImageId"),
        "similitud": round(mejor["Similarity"], 2),
    }
