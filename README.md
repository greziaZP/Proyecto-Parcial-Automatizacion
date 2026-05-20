# Proyecto Parcial - Automatizacion


## Levantar servicios (DB y Qdrant)

Desde la raiz del proyecto:

```
docker compose up -d
```

## Preparar base de datos (schema + seeds)

```
./env/bin/python db/schema_creation.py
./env/bin/python db/manager.py
```

## Levantar backend (API)

Desde `api/app`:

```
uvicorn main:app --reload --port 8000
```

## Levantar frontend (Streamlit)

Desde la raiz del proyecto:

```
streamlit run ui/asistencia.py
```

si no 

```
streamlit run asistencia.py
```