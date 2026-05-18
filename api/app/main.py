"""
Endpoints AWS Rekognition
=========================
Basado en los flujos n8n del sistema de asistencia.

Flujos implementados:
  POST /biometria/registrar        → Nodo "AWS Rekognition (IndexFaces)"
  POST /asistencia/registrar       → Nodo "Reconocimiento en AWS Rekognition (SearchFacesByImage)"
  GET  /alumnos                    → Nodo "GET Alumnos → Obtener Alumnos"
  GET  /cursos                     → Nodo "GET Cursos → Obtener Cursos"
  GET  /profesores                 → Nodo "GET Profesores → Obtener Profesores"
  POST /asistencia/cerrar-jornada  → Nodo "Notificación por Correo"
"""

import base64
import os
import smtplib
import logging
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sistema de Asistencia — Colegio Rafael Narváez Cadenillas",
    description="API de reconocimiento facial con AWS Rekognition",
    version="1.0.0",
)

# ─── Cliente AWS Rekognition ──────────────────────────────────────────────────
rekognition = boto3.client(
    "rekognition",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)

COLLECTION_ID = os.getenv("REKOGNITION_COLLECTION_ID", "colegio-faces")
SIMILARITY_THRESHOLD = float(os.getenv("REKOGNITION_SIMILARITY_THRESHOLD", "90.0"))


# ─── Schemas ──────────────────────────────────────────────────────────────────

class RegistrarBiometriaRequest(BaseModel):
    alumno_id: int
    imagen_base64: str   # Foto frontal del alumno, sin prefijo "data:image/..."


class RegistrarAsistenciaRequest(BaseModel):
    curso_id: int
    imagen_base64: str   # Foto capturada en el momento, sin prefijo "data:image/..."


# ─────────────────────────────────────────────────────────────────────────────
# FLUJO 1: Registro de Biometría
# n8n: Webhook → AWS Rekognition (IndexFaces) → HTTP Request → Code JS → Confirmar
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/biometria/registrar",
    status_code=status.HTTP_201_CREATED,
    summary="Enrolar biometría facial de un alumno (IndexFaces)",
    tags=["Biometría"],
)
def registrar_biometria(payload: RegistrarBiometriaRequest):
    """
    Recibe la foto del alumno en Base64 y la indexa en la colección de
    AWS Rekognition usando IndexFaces.
    Guarda el face_id devuelto para usarlo luego en el reconocimiento.
    """
    # Decodificar imagen de Base64 a bytes (nodo "Decodifica Base64" del n8n)
    try:
        imagen_bytes = base64.b64decode(payload.imagen_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen no es un Base64 válido.",
        )

    # Llamar a IndexFaces (nodo "AWS Rekognition (IndexFaces)")
    try:
        response = rekognition.index_faces(
            CollectionId=COLLECTION_ID,
            Image={"Bytes": imagen_bytes},
            ExternalImageId=str(payload.alumno_id),  # Vincula el face al alumno
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

    # Nodo "Code in JavaScript" en n8n: validar si se detectó cara
    if not face_records:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se detectó ninguna cara en la imagen. Use una foto frontal con buena iluminación.",
        )

    face_id = face_records[0]["Face"]["FaceId"]
    logger.info(f"Biometría enrolada: alumno_id={payload.alumno_id}, face_id={face_id}")

    # Nodo "Confirmar enrolamiento" en n8n
    return {
        "success": True,
        "alumno_id": payload.alumno_id,
        "face_id": face_id,
        "mensaje": f"Biometría registrada exitosamente. face_id: {face_id}",
    }


# ─────────────────────────────────────────────────────────────────────────────
# FLUJO 2: Endpoints REST — Alumnos / Cursos / Profesores
# n8n: GET Alumnos → Obtener Alumnos | GET Cursos → Obtener Cursos | etc.
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/alumnos", summary="Listar alumnos", tags=["REST"])
def obtener_alumnos():
    """
    Devuelve todos los alumnos registrados.
    Equivale al nodo n8n: GET Alumnos → Obtener Alumnos.
    Conectar aquí a la base de datos real (PostgreSQL).
    """
    # TODO: reemplazar con consulta a DB real
    # Ejemplo: return db.query(Alumno).all()
    return {"mensaje": "Conectar con la base de datos PostgreSQL"}


@app.get("/cursos", summary="Listar cursos", tags=["REST"])
def obtener_cursos():
    """
    Devuelve todos los cursos registrados.
    Equivale al nodo n8n: GET Cursos → Obtener Cursos.
    """
    # TODO: reemplazar con consulta a DB real
    return {"mensaje": "Conectar con la base de datos PostgreSQL"}


@app.get("/profesores", summary="Listar profesores", tags=["REST"])
def obtener_profesores():
    """
    Devuelve todos los profesores registrados.
    Equivale al nodo n8n: GET Profesores → Obtener Profesores.
    """
    # TODO: reemplazar con consulta a DB real
    return {"mensaje": "Conectar con la base de datos PostgreSQL"}


# ─────────────────────────────────────────────────────────────────────────────
# FLUJO 3: Registro de Asistencia
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

@app.post(
    "/asistencia/registrar",
    summary="Registrar asistencia por reconocimiento facial (SearchFacesByImage)",
    tags=["Asistencia"],
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
    try:
        response = rekognition.search_faces_by_image(
            CollectionId=COLLECTION_ID,
            Image={"Bytes": imagen_bytes},
            MaxFaces=1,
            FaceMatchThreshold=SIMILARITY_THRESHOLD,
        )
    except rekognition.exceptions.InvalidParameterException:
        # Rekognition no detectó cara en la imagen
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

    # Nodo "Parse data → json" + nodo "¿Identidad identificada?"
    face_matches = response.get("FaceMatches", [])

    if not face_matches:
        # Rama NO → nodo "Retorno de error"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Alumno no identificado. "
                "Verifique que esté enrolado en el sistema o mejore la calidad de la imagen."
            ),
        )

    # Mejor coincidencia (Rekognition los devuelve ordenados por similitud desc)
    mejor_match = face_matches[0]
    face_id = mejor_match["Face"]["FaceId"]
    similitud = mejor_match["Similarity"]
    alumno_id_externo = mejor_match["Face"].get("ExternalImageId")  # El alumno_id que indexamos

    logger.info(f"Alumno identificado: alumno_id={alumno_id_externo}, face_id={face_id}, similitud={similitud:.2f}%")

    # ── Nodo "Buscar rostro identificado" ─────────────────────────────────────
    # TODO: consultar en DB por face_id o alumno_id_externo
    # alumno = db.query(Alumno).filter(Alumno.face_id == face_id).first()
    # if not alumno: raise HTTPException(404, "Alumno no encontrado en DB")

    # ── Nodo "Buscar marcación de asistencia" (¿ya registró hoy?) ────────────
    # TODO: verificar si ya hay asistencia del día para alumno + curso
    # hoy = date.today()
    # marcacion_previa = db.query(Asistencia).filter(
    #     Asistencia.alumno_id == alumno.id,
    #     Asistencia.curso_id == payload.curso_id,
    #     func.date(Asistencia.fecha) == hoy,
    # ).first()
    #
    # if marcacion_previa:
    #     return {"success": True, "mensaje": "El alumno ya registró asistencia hoy.", "ya_registrado": True}

    # ── Nodo "Marcar asistencia" ──────────────────────────────────────────────
    # TODO: insertar registro en la tabla asistencias
    # nueva = Asistencia(alumno_id=alumno.id, curso_id=payload.curso_id, estado="PRESENTE", similitud_rekognition=similitud)
    # db.add(nueva); db.commit()

    # ── Nodo "Obtener curso" ──────────────────────────────────────────────────
    # TODO: consultar datos del curso para incluirlos en la respuesta
    # curso = db.query(Curso).filter(Curso.id == payload.curso_id).first()

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

@app.post(
    "/asistencia/cerrar-jornada",
    summary="Cerrar jornada y enviar folio por correo",
    tags=["Asistencia"],
)
def cerrar_jornada():
    """
    Genera el folio de asistencia del día y lo envía por correo.
    Equivale al flujo n8n: Webhook Click Cerrar → Generar folio → Enviar Correos.
    """
    hoy = date.today().strftime("%d/%m/%Y")

    # Nodo "Obtener Alumnos + Cursos + Usuarios + Asistencias de Hoy"
    # TODO: consultar en DB
    # alumnos = db.query(Alumno).all()
    # cursos = db.query(Curso).all()
    # asistencias_hoy = db.query(Asistencia).filter(func.date(Asistencia.fecha) == date.today()).all()

    # Nodo "Generar folio de corte"
    # TODO: cruzar matriculados vs presentes y construir resumen_cursos
    resumen_cursos = []  # llenar con datos reales de la DB

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
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password or not destinatarios:
        logger.warning("SMTP no configurado o sin destinatarios. Se omite envío.")
        return []

    html = _generar_html_folio(fecha, resumen_cursos)
    enviados = []

    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", 587))) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            for dest in destinatarios:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"Folio de Asistencia — {fecha}"
                msg["From"] = smtp_user
                msg["To"] = dest
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
