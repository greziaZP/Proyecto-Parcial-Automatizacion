"""
schema_creation.py
==================
Alineado 100% con el DBML v3 (todo UUID, campo nuevo estudiante.matricula_actual_uid).

═══════════════════════════════════════════════════════════════════
PATRONES DE CLAVE PRIMARIA:
  • Todo UUID con gen_random_uuid()
  • Perfiles 1:1 → uid UUID shared PK = usuario.uid

REFERENCIAS CIRCULARES (resueltas con ALTER TABLE diferido):
  ① estudiante.matricula_actual_uid → matricula.uid
     matricula.estudiante_uid       → estudiante.uid
     → estudiante se crea SIN la FK de matricula_actual_uid.
       Tras crear matricula, se añade con ALTER TABLE.

  ② justificacion.asistencia_clase_uid → asistencia_clase.uid
     asistencia_clase.justificacion_uid → justificacion.uid
     → justificacion se crea SIN la FK de asistencia_clase_uid.
       Tras crear asistencia_clase, se añade con ALTER TABLE.

ORDEN DE CREACIÓN:
   1.  ENUMs
   2.  ano_escolar        (UUID, sin FK)
   3.  curso              (UUID, sin FK)
   4.  usuario            (UUID, auth)
   5.  docente            (UUID shared PK → usuario, FK → curso)
   6.  auxiliar           (UUID shared PK → usuario)
   7.  padre_familia      (UUID shared PK → usuario)
   8.  estudiante         (UUID shared PK → usuario/padre) ← SIN FK a matricula
   9.  relacion_padre_estudiante
  10.  seccion            (UUID → ano_escolar)
  11.  periodo_trimestral (UUID → ano_escolar)
  12.  matricula          (UUID → estudiante, seccion)
  13.  ALTER TABLE estudiante ADD matricula_actual_uid FK → matricula
  14.  horario_clase      (UUID → seccion, curso, docente)
  15.  permiso_salida     (UUID → matricula, padre, auxiliar)
  16.  justificacion      (UUID → padre, docente) ← SIN FK a asistencia_clase
  17.  asistencia_clase   (UUID → matricula, estudiante, horario, docente, permiso, justificacion)
  18.  ALTER TABLE justificacion ADD asistencia_clase_uid FK → asistencia_clase
  19.  registro_ingreso   (UUID → matricula, estudiante, auxiliar, justificacion)
  20.  fuga               (UUID → asistencia_clase, auxiliar, justificacion)
  21.  nota_actitudinal   (UUID → matricula, periodo, docente)

Ejecutar standalone:
    .venv/bin/python schema_creation.py
"""

import sys
from config import get_connection, release_connection, close_pool



def create_schema() -> None:
    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("🏗️  Creando esquema v3 (todo UUID)...\n")

        # ══════════════════════════════════════════════════════════════════════
        # 1. ENUMs
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TYPE rol_usuario AS ENUM (
                'estudiante', 'docente', 'auxiliar', 'padre', 'admin'
            );
            CREATE TYPE parentesco AS ENUM (
                'padre', 'madre', 'abuelo', 'tio', 'hermano', 'otro'
            );
            CREATE TYPE estado_matricula AS ENUM (
                'activa', 'retirada', 'trasladada'
            );
            CREATE TYPE dia_semana AS ENUM (
                'lunes', 'martes', 'miercoles', 'jueves', 'viernes'
            );
            CREATE TYPE estado_asistencia AS ENUM (
                'presente', 'tardanza', 'falta', 'justificada'
            );
            CREATE TYPE estado_ingreso AS ENUM (
                'a_tiempo', 'tardanza', 'ausente'
            );
            CREATE TYPE estado_fuga AS ENUM (
                'detectada', 'notificada', 'resuelta'
            );
            CREATE TYPE tipo_justificacion AS ENUM (
                'medica', 'familiar', 'viaje', 'otra'
            );
            CREATE TYPE estado_justificacion AS ENUM (
                'pendiente', 'aprobada', 'rechazada'
            );
            CREATE TYPE estado_reporte AS ENUM (
                'borrador', 'publicado', 'cerrado'
            );
        """)
        print("✅ ENUMs creados")

        # ══════════════════════════════════════════════════════════════════════
        # 2-3. CATÁLOGOS BASE  (UUID PK, sin FK entre sí)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE ano_escolar (
                uid          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                nombre       VARCHAR(50) NOT NULL UNIQUE,
                fecha_inicio DATE        NOT NULL,
                fecha_fin    DATE        NOT NULL,
                activo       BOOLEAN     NOT NULL DEFAULT FALSE,
                CONSTRAINT chk_ano_fechas CHECK (fecha_fin > fecha_inicio)
            );
            CREATE UNIQUE INDEX uq_ano_activo
                ON ano_escolar(activo) WHERE activo = TRUE;
        """)
        print("✅ ano_escolar creada  [UUID]")

        cur.execute("""
            CREATE TABLE curso (
                uid    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
                nombre VARCHAR(100) NOT NULL,
                codigo VARCHAR(30)  NOT NULL UNIQUE
            );
        """)
        print("✅ curso creada  [UUID]")

        # ══════════════════════════════════════════════════════════════════════
        # 4. MASTER DE USUARIOS  (UUID PK)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE usuario (
                uid           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
                email         VARCHAR(150) NOT NULL UNIQUE,
                rol           rol_usuario  NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                activo        BOOLEAN      NOT NULL DEFAULT TRUE,
                creado_en     TIMESTAMP    NOT NULL DEFAULT now()
            );
        """)
        print("✅ usuario creada  [UUID]")

        # ══════════════════════════════════════════════════════════════════════
        # 5-7. PERFILES 1:1  (UUID shared PK = usuario.uid)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE docente (
                uid                   UUID         PRIMARY KEY
                                      REFERENCES usuario(uid) ON DELETE CASCADE,
                nombres               VARCHAR(100) NOT NULL,
                apellidos             VARCHAR(100) NOT NULL,
                curso_especialidad_uid UUID        REFERENCES curso(uid)
            );
        """)
        print("✅ docente creada  [UUID shared PK → usuario, curso_especialidad_uid → curso]")

        cur.execute("""
            CREATE TABLE auxiliar (
                uid            UUID         PRIMARY KEY
                               REFERENCES usuario(uid) ON DELETE CASCADE,
                nombres        VARCHAR(100) NOT NULL,
                apellidos      VARCHAR(100) NOT NULL,
                cargo_asignado VARCHAR(100) NOT NULL
            );
        """)
        print("✅ auxiliar creada  [UUID shared PK → usuario]")

        cur.execute("""
            CREATE TABLE padre_familia (
                uid               UUID         PRIMARY KEY
                                  REFERENCES usuario(uid) ON DELETE CASCADE,
                nombres           VARCHAR(100) NOT NULL,
                apellidos         VARCHAR(100) NOT NULL,
                dni_apoderado     VARCHAR(15)  UNIQUE,
                telefono_contacto VARCHAR(30)
            );
        """)
        print("✅ padre_familia creada  [UUID shared PK → usuario]")

        # ══════════════════════════════════════════════════════════════════════
        # 8. ESTUDIANTE  (UUID shared PK)
        # OJO: matricula_actual_uid se añade como columna SIN FK aquí.
        # La FK se añade con ALTER TABLE después de crear matricula (paso 13).
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE estudiante (
                uid                 UUID         PRIMARY KEY
                                    REFERENCES usuario(uid) ON DELETE CASCADE,
                nombres             VARCHAR(100) NOT NULL,
                apellidos           VARCHAR(100) NOT NULL,
                dni_estudiante      VARCHAR(15)  UNIQUE,
                fecha_nacimiento    DATE         NOT NULL,
                rekognition_face_id VARCHAR(255) UNIQUE,
                tutor_principal_uid UUID         REFERENCES padre_familia(uid),
                matricula_actual_uid UUID        -- FK diferida, se añade tras crear matricula
            );
        """)
        print("✅ estudiante creada  [UUID shared PK, matricula_actual_uid sin FK aún]")

        # ══════════════════════════════════════════════════════════════════════
        # 9. RELACIÓN PADRE-ESTUDIANTE M:N  (UUID PK propio)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE relacion_padre_estudiante (
                uid                    UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
                padre_apoderado_uid    UUID       NOT NULL REFERENCES padre_familia(uid),
                estudiante_uid         UUID       NOT NULL REFERENCES estudiante(uid),
                parentesco             parentesco NOT NULL,
                es_apoderado_principal BOOLEAN    NOT NULL DEFAULT FALSE,
                CONSTRAINT uq_vinculo_padre_hijo
                    UNIQUE (padre_apoderado_uid, estudiante_uid)
            );
        """)
        print("✅ relacion_padre_estudiante creada  [UUID PK propio]")

        # ══════════════════════════════════════════════════════════════════════
        # 10-11. ESTRUCTURA ACADÉMICA  (UUID PK, FK → ano_escolar UUID)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE seccion (
                uid             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                ano_escolar_uid UUID        NOT NULL REFERENCES ano_escolar(uid),
                grado_academico VARCHAR(30) NOT NULL,
                nivel_educativo VARCHAR(30) NOT NULL,
                codigo_seccion  VARCHAR(15) NOT NULL,
                CONSTRAINT uq_seccion
                    UNIQUE (ano_escolar_uid, grado_academico, codigo_seccion)
            );
        """)
        print("✅ seccion creada  [UUID]")

        cur.execute("""
            CREATE TABLE periodo_trimestral (
                uid              UUID     PRIMARY KEY DEFAULT gen_random_uuid(),
                ano_escolar_uid  UUID     NOT NULL REFERENCES ano_escolar(uid),
                numero_trimestre SMALLINT NOT NULL
                                 CHECK (numero_trimestre BETWEEN 1 AND 4),
                fecha_inicio     DATE     NOT NULL,
                fecha_fin        DATE     NOT NULL,
                CONSTRAINT uq_periodo_por_ano
                    UNIQUE (ano_escolar_uid, numero_trimestre),
                CONSTRAINT chk_periodo_fechas CHECK (fecha_fin > fecha_inicio)
            );
        """)
        print("✅ periodo_trimestral creada  [UUID]")

        # ══════════════════════════════════════════════════════════════════════
        # 12. MATRÍCULA  (UUID PK)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE matricula (
                uid              UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
                estudiante_uid   UUID             NOT NULL REFERENCES estudiante(uid),
                seccion_uid      UUID             NOT NULL REFERENCES seccion(uid),
                fecha_matricula  DATE             NOT NULL,
                estado_matricula estado_matricula NOT NULL DEFAULT 'activa',
                CONSTRAINT uq_matricula_por_seccion
                    UNIQUE (estudiante_uid, seccion_uid)
            );
        """)
        print("✅ matricula creada  [UUID]")

        # ══════════════════════════════════════════════════════════════════════
        # 13. FK DIFERIDA ①: estudiante.matricula_actual_uid → matricula
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            ALTER TABLE estudiante
                ADD CONSTRAINT fk_estudiante_matricula_actual
                    FOREIGN KEY (matricula_actual_uid)
                    REFERENCES matricula(uid)
                    ON DELETE SET NULL;
        """)
        print("✅ FK diferida ① añadida: estudiante.matricula_actual_uid → matricula")

        # ══════════════════════════════════════════════════════════════════════
        # 14. HORARIO DE CLASE  (UUID PK)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE horario_clase (
                uid                  UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
                seccion_uid          UUID       NOT NULL REFERENCES seccion(uid),
                curso_uid            UUID       NOT NULL REFERENCES curso(uid),
                docente_dictante_uid UUID       NOT NULL REFERENCES docente(uid),
                dia_semana           dia_semana NOT NULL,
                hora_inicio          TIME       NOT NULL,
                hora_fin             TIME       NOT NULL,
                es_hora_tutoria      BOOLEAN    NOT NULL DEFAULT FALSE,
                CONSTRAINT uq_horario_aula
                    UNIQUE (seccion_uid, dia_semana, hora_inicio),
                CONSTRAINT uq_horario_docente
                    UNIQUE (docente_dictante_uid, dia_semana, hora_inicio),
                CONSTRAINT chk_horario_horas CHECK (hora_fin > hora_inicio)
            );
            CREATE UNIQUE INDEX uq_tutoria_seccion
                ON horario_clase(seccion_uid) WHERE es_hora_tutoria = TRUE;
        """)
        print("✅ horario_clase creada  [UUID]")

        # ══════════════════════════════════════════════════════════════════════
        # 15. PERMISO DE SALIDA  (UUID PK, hora_salida=TIME)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE permiso_salida (
                uid                      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
                matricula_uid            UUID         NOT NULL REFERENCES matricula(uid),
                padre_solicitante_uid    UUID         NOT NULL REFERENCES padre_familia(uid),
                auxiliar_autorizador_uid UUID         REFERENCES auxiliar(uid),
                auxiliar_registrador_uid UUID         NOT NULL REFERENCES auxiliar(uid),
                fecha_permiso            DATE         NOT NULL,
                hora_salida              TIME         NOT NULL,
                motivo_salida            VARCHAR(300) NOT NULL,
                observaciones            VARCHAR(500),
                creado_en                TIMESTAMP    NOT NULL DEFAULT now()
            );
            CREATE INDEX idx_permiso_alumno_dia
                ON permiso_salida(matricula_uid, fecha_permiso);
        """)
        print("✅ permiso_salida creada  [UUID, hora_salida=TIME]")

        # ══════════════════════════════════════════════════════════════════════
        # 16. JUSTIFICACION  (UUID PK)
        # SIN la FK a asistencia_clase todavía (circular).
        # La columna asistencia_clase_uid existe pero sin CONSTRAINT aún.
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE justificacion (
                uid                      UUID                 PRIMARY KEY DEFAULT gen_random_uuid(),
                asistencia_clase_uid     UUID                 ,
                tipo_justificacion       tipo_justificacion   NOT NULL,
                estado_justificacion     estado_justificacion NOT NULL DEFAULT 'pendiente',
                padre_solicitante_uid    UUID                 NOT NULL
                                         REFERENCES padre_familia(uid),
                docente_autorizador_uid  UUID                 REFERENCES docente(uid),
                fecha_presentacion       DATE                 NOT NULL,
                fecha_inicio_incidencia  DATE                 NOT NULL,
                fecha_fin_incidencia     DATE                 NOT NULL,
                descripcion_motivo       VARCHAR(500)         NOT NULL,
                url_documento_referencia VARCHAR(400),
                creado_en                TIMESTAMP            NOT NULL DEFAULT now(),
                actualizado_en           TIMESTAMP            NOT NULL DEFAULT now(),
                CONSTRAINT chk_justif_fechas
                    CHECK (fecha_fin_incidencia >= fecha_inicio_incidencia)
            );
            CREATE INDEX idx_justif_estado ON justificacion(estado_justificacion);
            CREATE INDEX idx_justif_tipo   ON justificacion(tipo_justificacion);
        """)
        print("✅ justificacion creada  [UUID, FK a asistencia_clase pendiente]")

        # ══════════════════════════════════════════════════════════════════════
        # 17. ASISTENCIA CLASE  (UUID PK)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE asistencia_clase (
                uid                     UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
                matricula_uid           UUID              NOT NULL REFERENCES matricula(uid),
                estudiante_uid          UUID              NOT NULL REFERENCES estudiante(uid),
                horario_clase_uid       UUID              NOT NULL REFERENCES horario_clase(uid),
                fecha_asistencia        DATE              NOT NULL,
                estado_asistencia       estado_asistencia NOT NULL,
                observacion_docente     VARCHAR(500),
                docente_controlador_uid UUID              NOT NULL REFERENCES docente(uid),
                permiso_salida_uid      UUID              REFERENCES permiso_salida(uid),
                justificacion_uid       UUID              REFERENCES justificacion(uid),
                CONSTRAINT uq_asistencia_por_clase
                    UNIQUE (matricula_uid, horario_clase_uid, fecha_asistencia)
            );
            CREATE INDEX idx_asistencia_estudiante_dia
                ON asistencia_clase(estudiante_uid, fecha_asistencia);
            CREATE INDEX idx_asistencia_estado
                ON asistencia_clase(estado_asistencia);
        """)
        print("✅ asistencia_clase creada  [UUID]")

        # ══════════════════════════════════════════════════════════════════════
        # 18. FK DIFERIDA ②: justificacion.asistencia_clase_uid → asistencia_clase
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            ALTER TABLE justificacion
                ADD CONSTRAINT fk_justif_asistencia_clase
                    FOREIGN KEY (asistencia_clase_uid)
                    REFERENCES asistencia_clase(uid);
        """)
        print("✅ FK diferida ② añadida: justificacion.asistencia_clase_uid → asistencia_clase")

        # ══════════════════════════════════════════════════════════════════════
        # 19. REGISTRO DE INGRESO  (UUID PK, hora_llegada=TIMESTAMP)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE registro_ingreso (
                uid                   UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
                matricula_uid         UUID           NOT NULL REFERENCES matricula(uid),
                estudiante_uid        UUID           NOT NULL REFERENCES estudiante(uid),
                auxiliar_receptor_uid UUID           REFERENCES auxiliar(uid),
                fecha_ingreso         DATE           NOT NULL,
                hora_llegada          TIMESTAMP      NOT NULL,
                estado_ingreso        estado_ingreso NOT NULL,
                justificacion_uid     UUID           REFERENCES justificacion(uid),
                creado_en             TIMESTAMP      NOT NULL DEFAULT now(),
                CONSTRAINT uq_ingreso_por_dia UNIQUE (matricula_uid, fecha_ingreso)
            );
            CREATE INDEX idx_ingreso_estudiante ON registro_ingreso(estudiante_uid);
            CREATE INDEX idx_ingreso_fecha       ON registro_ingreso(fecha_ingreso);
        """)
        print("✅ registro_ingreso creada  [UUID, hora_llegada=TIMESTAMP]")

        # ══════════════════════════════════════════════════════════════════════
        # 20. FUGAS  (UUID PK, incluye justificacion_uid)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE fuga (
                uid                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                asistencia_clase_uid     UUID        NOT NULL REFERENCES asistencia_clase(uid),
                auxiliar_detector_uid    UUID        NOT NULL REFERENCES auxiliar(uid),
                auxiliar_registrador_uid UUID        NOT NULL REFERENCES auxiliar(uid),
                fecha_hora_deteccion     TIMESTAMP   NOT NULL,
                estado_fuga              estado_fuga NOT NULL DEFAULT 'detectada',
                auxiliar_resolutor_uid   UUID        REFERENCES auxiliar(uid),
                fecha_hora_resolucion    TIMESTAMP,
                justificacion_uid        UUID        REFERENCES justificacion(uid),
                observacion_caso         VARCHAR(500)
            );
            CREATE INDEX idx_fuga_estado    ON fuga(estado_fuga);
            CREATE INDEX idx_fuga_deteccion ON fuga(fecha_hora_deteccion);
        """)
        print("✅ fuga creada  [UUID, con justificacion_uid]")

        # ══════════════════════════════════════════════════════════════════════
        # 21. NOTA ACTITUDINAL  (UUID PK, DECIMAL(14,2))
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE nota_actitudinal (
                uid                   UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
                matricula_uid         UUID           NOT NULL REFERENCES matricula(uid),
                periodo_uid           UUID           NOT NULL REFERENCES periodo_trimestral(uid),
                total_tardanzas       SMALLINT       NOT NULL DEFAULT 0
                                      CHECK (total_tardanzas >= 0),
                total_inasistencias   SMALLINT       NOT NULL DEFAULT 0
                                      CHECK (total_inasistencias >= 0),
                total_fugas           SMALLINT       NOT NULL DEFAULT 0
                                      CHECK (total_fugas >= 0),
                calificacion_valor    DECIMAL(14,2)
                                      CHECK (calificacion_valor IS NULL
                                          OR calificacion_valor BETWEEN 0 AND 20),
                promedio_academico    DECIMAL(14,2)
                                      CHECK (promedio_academico IS NULL
                                          OR promedio_academico BETWEEN 0 AND 20),
                estado_reporte        estado_reporte NOT NULL DEFAULT 'borrador',
                docente_evaluador_uid UUID           REFERENCES docente(uid),
                calculado_en          TIMESTAMP      NOT NULL DEFAULT now(),
                CONSTRAINT uq_nota_por_periodo
                    UNIQUE (matricula_uid, periodo_uid)
            );
            CREATE INDEX idx_nota_periodo ON nota_actitudinal(periodo_uid);
        """)
        print("✅ nota_actitudinal creada  [UUID, DECIMAL(14,2)]")

        # ══════════════════════════════════════════════════════════════════════
        # 22. CITACIONES (UUID PK)
        # ══════════════════════════════════════════════════════════════════════
        cur.execute("""
            CREATE TABLE citacion (
                uid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                estudiante_uid UUID NOT NULL,
                padre_apoderado_uid UUID NOT NULL,
                docente_solicitante_uid UUID NOT NULL,
                motivo VARCHAR(255) NOT NULL,
                nivel_urgencia VARCHAR(50) NOT NULL,
                estado VARCHAR(50) DEFAULT 'programada' NOT NULL,
                fecha_citacion TIMESTAMP NOT NULL,
                creado_en TIMESTAMP DEFAULT now() NOT NULL,
                
                CONSTRAINT citacion_estudiante_fkey FOREIGN KEY (estudiante_uid) REFERENCES estudiante(uid) ON DELETE CASCADE,
                CONSTRAINT citacion_padre_fkey FOREIGN KEY (padre_apoderado_uid) REFERENCES padre_familia(uid) ON DELETE CASCADE,
                CONSTRAINT citacion_docente_fkey FOREIGN KEY (docente_solicitante_uid) REFERENCES docente(uid) ON DELETE CASCADE
            );
            CREATE INDEX idx_citacion_estudiante ON citacion(estudiante_uid);
            CREATE INDEX idx_citacion_estado ON citacion(estado);
        """)
        print("✅ citacion creada  [UUID]")

        conn.commit()
        print("\n🎉 Esquema v3 creado exitosamente en Supabase!")
        print("\n📋 Tablas creadas (todas UUID):")
        print("   Catálogos:    ano_escolar, curso")
        print("   Auth:         usuario")
        print("   Perfiles 1:1: docente, auxiliar, padre_familia, estudiante")
        print("   Puente M:N:   relacion_padre_estudiante")
        print("   Académicas:   seccion, periodo_trimestral, matricula, horario_clase")
        print("   Asistencia:   registro_ingreso, asistencia_clase")
        print("   Permisos:     permiso_salida, justificacion")
        print("   Conducta:     fuga")
        print("   Evaluación:   nota_actitudinal")
        print("\n   FKs diferidas resueltas:")
        print("   ① estudiante.matricula_actual_uid → matricula")
        print("   ② justificacion.asistencia_clase_uid → asistencia_clase")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error creando esquema: {e}")
        raise
    finally:
        cur.close()
        release_connection(conn)
        close_pool()


if __name__ == "__main__":
    create_schema()
    sys.exit(0)
