from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.queries.entities_queries import query_get_estudiantes, query_get_cursos, query_get_profesores

router = APIRouter(tags=["REST - Entities"])

@router.get("/estudiantes", summary="Listar estudiantes reales")
def obtener_estudiantes() -> List[Dict[str, Any]]:
    """Obtiene todos los estudiantes activos consultando las tablas estudiante y usuario."""
    try:
        return query_get_estudiantes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando estudiantes: {str(e)}")

@router.get("/cursos", summary="Listar cursos reales")
def obtener_cursos() -> List[Dict[str, Any]]:
    """Obtiene los cursos consultando la tabla curso."""
    try:
        return query_get_cursos()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando cursos: {str(e)}")

@router.get("/profesores", summary="Listar profesores reales")
def obtener_profesores() -> List[Dict[str, Any]]:
    """Obtiene todos los profesores activos consultando las tablas docente, usuario y curso."""
    try:
        return query_get_profesores()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando profesores: {str(e)}")
