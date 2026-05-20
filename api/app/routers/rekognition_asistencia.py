"""
Router: Asistencia por Reconocimiento Facial + Cierre de Jornada
=================================================================
Flujos n8n implementados:
  POST /asistencia/registrar      → Nodo "Reconocimiento en AWS Rekognition (SearchFacesByImage)"
  POST /asistencia/cerrar-jornada → Nodo "Notificación por Correo"
"""

import base64
import logging
import os
import smtplib
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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

COLLECTION_ID        = os.getenv("REKOGNITION_COLLECTION_ID", "colegio_faces")
SIMILARITY_THRESHOLD = float(os.getenv("REKOGNITION_SIMILARITY_THRESHOLD", "90.0"))


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

# ─── Schemas ──────────────────────────────────────────────────────────────────

class RegistrarAsistenciaRequest(BaseModel):
    curso_id: int
    imagen_base64: str  # Foto capturada en el momento, sin prefijo "data:image/..."


# ─────────────────────────────────────────────────────────────────────────────
# FLUJO 3: Registro de Asistencia por Reconocimiento Facial
# n8n: Webhook Identificación → Decodifica Base64
#      → Reconocimiento AWS Rekognition (SearchFacesByImage)
#      → Parse data → json
#      → ¿Identidad identificada?
#          ├─ NO  → Retorno de error
#          └─ SÍ  → Buscar rostro identificado
#                   → Buscar marcación previa (¿ya registrado hoy?)
#                   → Marcar asistencia / Enviar mensaje de error
#                   → Obtener curso
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/asistencia", tags=["Asistencia — Rekognition"])


@router.post(
    "/registrar",
    summary="Registrar asistencia por reconocimiento facial (SearchFacesByImage)",
)
def registrar_asistencia(payload: RegistrarAsistenciaRequest):
    """
    Identifica al alumno en la imagen usando AWS Rekognition SearchFacesByImage
    y registra su asistencia en el curso indicado.
    """
    # Nodo "Decodifica Base64"
    try:
        imagen_bytes = base64.b64decode(payload.imagen_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen no es un Base64 válido.",
        )

    # Nodo "Reconocimiento en AWS Rekognition (SearchFacesByImage)"
    _ensure_collection_exists(COLLECTION_ID)
    try:
        response = rekognition.search_faces_by_image(
            CollectionId=COLLECTION_ID,
            Image={"Bytes": imagen_bytes},
            MaxFaces=1,
            FaceMatchThreshold=SIMILARITY_THRESHOLD,
        )
    except rekognition.exceptions.InvalidParameterException:
        # Nodo n8n → rama "Retorno de error"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se detectó ninguna cara en la imagen proporcionada.",
        )
    except ClientError as e:
        logger.error(f"Error AWS Rekognition SearchFacesByImage: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al comunicarse con AWS Rekognition: {e.response['Error']['Message']}",
        )

    # Nodo "Parse data → json" + "¿Identidad identificada?"
    face_matches = response.get("FaceMatches", [])

    if not face_matches:
        # Rama NO → "Retorno de error"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Alumno no identificado. "
                "Verifique que esté enrolado en el sistema o mejore la calidad de la imagen."
            ),
        )

    # Mejor coincidencia (ordenados por similitud desc)
    mejor_match       = face_matches[0]
    face_id           = mejor_match["Face"]["FaceId"]
    similitud         = mejor_match["Similarity"]
    alumno_id_externo = mejor_match["Face"].get("ExternalImageId")

    logger.info(f"Alumno identificado: alumno_id={alumno_id_externo}, similitud={similitud:.2f}%")

    # Nodo "Buscar rostro identificado"
    # TODO: alumno = db.query(Alumno).filter(Alumno.face_id == face_id).first()

    # Nodo "Buscar marcación de asistencia" (¿ya registró hoy?)
    # TODO:
    # hoy = date.today()
    # marcacion_previa = db.query(Asistencia).filter(
    #     Asistencia.alumno_id == alumno.id,
    #     Asistencia.curso_id == payload.curso_id,
    #     func.date(Asistencia.fecha) == hoy,
    # ).first()
    # if marcacion_previa:
    #     return {"success": True, "mensaje": "El alumno ya registró asistencia hoy.", "ya_registrado": True}

    # Nodo "Marcar asistencia"
    # TODO: nueva = Asistencia(alumno_id=alumno.id, curso_id=payload.curso_id, estado="PRESENTE", similitud_rekognition=similitud)
    # db.add(nueva); db.commit()

    # Nodo "Obtener curso"
    # TODO: curso = db.query(Curso).filter(Curso.id == payload.curso_id).first()

    return {
        "success": True,
        "mensaje": "Asistencia registrada correctamente.",
        "alumno_id": alumno_id_externo,
        "face_id": face_id,
        "similitud": round(similitud, 2),
        "curso_id": payload.curso_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# FLUJO 4: Notificación por Correo — Cierre de Jornada
# n8n: Webhook Click Cerrar → Obtener Alumnos + Cursos + Usuarios + Asistencias
#      → Generar folio de corte → Enviar Correos
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/cerrar-jornada",
    summary="Cerrar jornada y enviar folio por correo",
)
def cerrar_jornada():
    """
    Genera el folio de asistencia del día y lo envía por correo.
    Equivale al flujo n8n: Webhook Click Cerrar → Generar folio → Enviar Correos.
    """
    hoy = date.today().strftime("%d/%m/%Y")

    # Nodo "Obtener Alumnos + Cursos + Usuarios + Asistencias de Hoy"
    # TODO: alumnos = db.query(Alumno).all()
    # TODO: asistencias_hoy = db.query(Asistencia).filter(func.date(Asistencia.fecha) == date.today()).all()

    # Nodo "Generar folio de corte"
    resumen_cursos = []  # TODO: construir con datos reales de la DB

    # Nodo "Enviar Correos"
    correos_enviados = _enviar_correo_cierre(
        destinatarios=_obtener_destinatarios(),
        fecha=hoy,
        resumen_cursos=resumen_cursos,
    )

    return {
        "success": True,
        "fecha": hoy,
        "correos_enviados": correos_enviados,
        "mensaje": f"Jornada cerrada. Notificaciones enviadas a {len(correos_enviados)} destinatario(s).",
    }


# ─── Helpers privados ─────────────────────────────────────────────────────────

def _obtener_destinatarios() -> list:
    """Devuelve la lista de emails a notificar (director + profesores)."""
    destinatarios = []
    email_director = os.getenv("EMAIL_DIRECTOR", "")
    if email_director:
        destinatarios.append(email_director)
    # TODO: agregar emails de profesores desde DB
    return destinatarios


def _enviar_correo_cierre(destinatarios: list, fecha: str, resumen_cursos: list) -> list:
    """Envía el folio HTML por SMTP. Equivale al nodo n8n 'Enviar Correos'."""
    smtp_user     = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password or not destinatarios:
        logger.warning("SMTP no configurado o sin destinatarios. Se omite envío.")
        return []

    html     = _generar_html_folio(fecha, resumen_cursos)
    enviados = []

    try:
        with smtplib.SMTP(
            os.getenv("SMTP_HOST", "smtp.gmail.com"),
            int(os.getenv("SMTP_PORT", 587)),
        ) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            for dest in destinatarios:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"Folio de Asistencia — {fecha}"
                msg["From"]    = smtp_user
                msg["To"]      = dest
                msg.attach(MIMEText(html, "html"))
                server.sendmail(smtp_user, dest, msg.as_string())
                enviados.append(dest)
    except smtplib.SMTPException as e:
        logger.error(f"Error SMTP: {e}")

    return enviados


def _generar_html_folio(fecha: str, resumen_cursos: list) -> str:
    """Genera el HTML del folio de cierre de jornada."""
    filas = "".join(
        f"<tr><td>{c['nombre_curso']}</td><td>{c['presentes']}</td><td>{c['ausentes']}</td></tr>"
        for c in resumen_cursos
    )
    return f"""
    <html><body style="font-family:Arial,sans-serif;">
        <h2>Folio de Asistencia — {fecha}</h2>
        <h3>Colegio Rafael Narváez Cadenillas</h3>
        <table border="1" cellpadding="8" cellspacing="0">
            <thead><tr><th>Curso</th><th>Presentes</th><th>Ausentes</th></tr></thead>
            <tbody>{filas if filas else "<tr><td colspan='3'>Sin datos</td></tr>"}</tbody>
        </table>
        <p style="color:#888;font-size:12px;">Generado automáticamente por el sistema.</p>
    </body></html>
    """
