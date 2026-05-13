// schema-creation.seed.ts
// Crea todas las tablas del esquema en orden correcto de dependencias.
// ENUMs primero, luego tablas sin FK, luego las que dependen de otras.

import { pool } from "./config";

async function createSchema() {
  const client = await pool.connect();
  try {
    console.log("🏗️  Creando esquema...\n");

    // ── ENUMs ─────────────────────────────────────────────────────
    await client.query(`
      CREATE TYPE rol_usuario AS ENUM (
        'auxiliar','docente','estudiante','padre','admin'
      );
      CREATE TYPE estado_matricula AS ENUM (
        'activa','retirada','trasladada'
      );
      CREATE TYPE dia_semana AS ENUM (
        'lunes','martes','miercoles','jueves','viernes','sabado'
      );
      CREATE TYPE estado_ingreso AS ENUM (
        'presente','tardanza','inasistencia','justificado'
      );
      CREATE TYPE estado_asistencia AS ENUM (
        'presente','ausente','fuga','justificado'
      );
      CREATE TYPE estado_fuga AS ENUM (
        'pendiente','ubicado','no_ubicado','justificado'
      );
      CREATE TYPE tipo_justificacion AS ENUM (
        'retiro_apoderado','actividad_institucional',
        'certificado_medico','permiso_direccion','otro'
      );
      CREATE TYPE estado_justificacion AS ENUM (
        'pendiente','aprobada','rechazada'
      );
      CREATE TYPE canal_aviso AS ENUM (
        'verbal','app','sms','whatsapp','email'
      );
      CREATE TYPE estado_reporte AS ENUM (
        'borrador','publicado','entregado'
      );
      CREATE TYPE parentesco AS ENUM (
        'padre','madre','tutor_legal','otro'
      );
    `);
    console.log("✅ ENUMs creados");

    // ── BLOQUE 1: ESTRUCTURA ACADÉMICA ────────────────────────────
    await client.query(`
      CREATE TABLE ano_escolar (
        id           SERIAL PRIMARY KEY,
        nombre       VARCHAR(9)  NOT NULL UNIQUE,
        fecha_inicio DATE        NOT NULL,
        fecha_fin    DATE        NOT NULL,
        activo       BOOLEAN     NOT NULL DEFAULT FALSE,
        CONSTRAINT chk_ano_fechas CHECK (fecha_fin > fecha_inicio)
      );
      -- Solo un año activo a la vez
      CREATE UNIQUE INDEX uq_ano_activo ON ano_escolar(activo) WHERE activo = TRUE;
    `);
    console.log("✅ ano_escolar creada");

    await client.query(`
      CREATE TABLE periodo_trimestral (
        id             SERIAL PRIMARY KEY,
        ano_escolar_id INTEGER  NOT NULL REFERENCES ano_escolar(id) ON DELETE CASCADE,
        numero         SMALLINT NOT NULL CHECK (numero BETWEEN 1 AND 4),
        fecha_inicio   DATE     NOT NULL,
        fecha_fin      DATE     NOT NULL,
        CONSTRAINT uq_periodo_por_ano UNIQUE (ano_escolar_id, numero),
        CONSTRAINT chk_periodo_fechas CHECK (fecha_fin > fecha_inicio)
      );
    `);
    console.log("✅ periodo_trimestral creada");

    await client.query(`
      CREATE TABLE seccion (
        id             SERIAL PRIMARY KEY,
        ano_escolar_id INTEGER     NOT NULL REFERENCES ano_escolar(id) ON DELETE CASCADE,
        grado          VARCHAR(30) NOT NULL,
        nivel          VARCHAR(20) NOT NULL,
        codigo         VARCHAR(3)  NOT NULL,
        CONSTRAINT uq_seccion UNIQUE (ano_escolar_id, grado, codigo)
      );
    `);
    console.log("✅ seccion creada");

    await client.query(`
      CREATE TABLE curso (
        id     SERIAL PRIMARY KEY,
        nombre VARCHAR(80) NOT NULL UNIQUE,
        codigo VARCHAR(10) NOT NULL UNIQUE
      );
    `);
    console.log("✅ curso creada");

    // ── BLOQUE 2: PERSONAS Y ROLES ─────────────────────────────────
    await client.query(`
      CREATE TABLE usuario (
        id            SERIAL PRIMARY KEY,
        nombres       VARCHAR(80)  NOT NULL,
        apellidos     VARCHAR(80)  NOT NULL,
        email         VARCHAR(120) NOT NULL UNIQUE,
        rol           rol_usuario  NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        activo        BOOLEAN      NOT NULL DEFAULT TRUE,
        created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
      );
    `);
    console.log("✅ usuario creada");

    await client.query(`
      CREATE TABLE estudiante (
        id               SERIAL PRIMARY KEY,
        usuario_id       INTEGER     NOT NULL UNIQUE REFERENCES usuario(id) ON DELETE CASCADE,
        dni              VARCHAR(12) NOT NULL UNIQUE,
        fecha_nacimiento DATE        NOT NULL
      );
    `);
    console.log("✅ estudiante creada");

    await client.query(`
      CREATE TABLE docente (
        id           SERIAL PRIMARY KEY,
        usuario_id   INTEGER     NOT NULL UNIQUE REFERENCES usuario(id) ON DELETE CASCADE,
        especialidad VARCHAR(80)
      );
    `);
    console.log("✅ docente creada");

    await client.query(`
      CREATE TABLE padre_familia (
        id         SERIAL PRIMARY KEY,
        usuario_id INTEGER     NOT NULL UNIQUE REFERENCES usuario(id) ON DELETE CASCADE,
        dni        VARCHAR(12) NOT NULL UNIQUE,
        telefono   VARCHAR(20)
      );
    `);
    console.log("✅ padre_familia creada");

    await client.query(`
      CREATE TABLE relacion_padre_estudiante (
        id                     SERIAL PRIMARY KEY,
        padre_id               INTEGER    NOT NULL REFERENCES padre_familia(id) ON DELETE CASCADE,
        estudiante_id          INTEGER    NOT NULL REFERENCES estudiante(id)    ON DELETE CASCADE,
        parentesco             parentesco NOT NULL,
        es_apoderado_principal BOOLEAN    NOT NULL DEFAULT FALSE,
        CONSTRAINT uq_vinculo_padre_hijo UNIQUE (padre_id, estudiante_id)
      );
    `);
    console.log("✅ relacion_padre_estudiante creada");

    // ── BLOQUE 3: MATRÍCULA Y HORARIO ──────────────────────────────
    await client.query(`
      CREATE TABLE matricula (
        id              SERIAL PRIMARY KEY,
        estudiante_id   INTEGER          NOT NULL REFERENCES estudiante(id),
        seccion_id      INTEGER          NOT NULL REFERENCES seccion(id),
        fecha_matricula DATE             NOT NULL DEFAULT CURRENT_DATE,
        estado          estado_matricula NOT NULL DEFAULT 'activa',
        CONSTRAINT uq_matricula_por_seccion UNIQUE (estudiante_id, seccion_id)
      );
    `);
    console.log("✅ matricula creada");

    await client.query(`
      CREATE TABLE horario_clase (
        id          SERIAL PRIMARY KEY,
        seccion_id  INTEGER    NOT NULL REFERENCES seccion(id),
        curso_id    INTEGER    NOT NULL REFERENCES curso(id),
        docente_id  INTEGER    NOT NULL REFERENCES docente(id),
        dia_semana  dia_semana NOT NULL,
        hora_inicio TIME       NOT NULL,
        hora_fin    TIME       NOT NULL,
        es_tutoria  BOOLEAN    NOT NULL DEFAULT FALSE,
        CONSTRAINT uq_horario_seccion UNIQUE (seccion_id, dia_semana, hora_inicio),
        CONSTRAINT uq_horario_docente UNIQUE (docente_id, dia_semana, hora_inicio),
        CONSTRAINT chk_horario_horas  CHECK  (hora_fin > hora_inicio)
      );
      -- Solo una tutoría por sección
      CREATE UNIQUE INDEX uq_tutor_por_seccion
        ON horario_clase(seccion_id) WHERE es_tutoria = TRUE;
    `);
    console.log("✅ horario_clase creada");

    // ── BLOQUE 4: PERMISOS Y JUSTIFICACIONES ──────────────────────
    // permiso_salida y justificacion se crean ANTES de registro_ingreso
    // y asistencia_clase porque esas tablas las referencian.
    await client.query(`
      CREATE TABLE permiso_salida (
        id             SERIAL PRIMARY KEY,
        matricula_id   INTEGER      NOT NULL REFERENCES matricula(id),
        autorizado_por INTEGER      NOT NULL REFERENCES padre_familia(id),
        registrado_por INTEGER      NOT NULL REFERENCES usuario(id),
        fecha          DATE         NOT NULL,
        hora_salida    TIMESTAMPTZ  NOT NULL,
        motivo         VARCHAR(300) NOT NULL,
        observacion    VARCHAR(500),
        created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
      );
      CREATE INDEX idx_permiso_alumno_dia ON permiso_salida(matricula_id, fecha);
      CREATE INDEX idx_permiso_fecha      ON permiso_salida(fecha);
    `);
    console.log("✅ permiso_salida creada");

    await client.query(`
      CREATE TABLE justificacion (
        id                   SERIAL PRIMARY KEY,
        matricula_id         INTEGER              NOT NULL REFERENCES matricula(id),
        tipo                 tipo_justificacion   NOT NULL,
        estado               estado_justificacion NOT NULL DEFAULT 'pendiente',
        presentado_por       INTEGER              REFERENCES padre_familia(id),
        autorizado_por       INTEGER              REFERENCES usuario(id),
        fecha_presentacion   DATE                 NOT NULL,
        fecha_inicio_evento  DATE                 NOT NULL,
        fecha_fin_evento     DATE                 NOT NULL,
        descripcion          VARCHAR(500)         NOT NULL,
        documento_referencia VARCHAR(100),
        created_at           TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
        updated_at           TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_justif_fechas CHECK (fecha_fin_evento >= fecha_inicio_evento)
      );
      CREATE INDEX idx_justif_alumno_fecha ON justificacion(matricula_id, fecha_inicio_evento);
      CREATE INDEX idx_justif_estado       ON justificacion(estado);
      CREATE INDEX idx_justif_tipo         ON justificacion(tipo);
    `);
    console.log("✅ justificacion creada");

    // ── BLOQUE 5: REGISTROS DE ASISTENCIA ─────────────────────────
    await client.query(`
      CREATE TABLE registro_ingreso (
        id               SERIAL PRIMARY KEY,
        matricula_id     INTEGER        NOT NULL REFERENCES matricula(id),
        auxiliar_id      INTEGER        NOT NULL REFERENCES usuario(id),
        fecha            DATE           NOT NULL,
        hora_llegada     TIMESTAMPTZ,
        estado           estado_ingreso NOT NULL,
        justificacion_id INTEGER        REFERENCES justificacion(id),
        created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_ingreso_por_dia UNIQUE (matricula_id, fecha)
      );
      CREATE INDEX idx_ingreso_fecha   ON registro_ingreso(fecha);
      CREATE INDEX idx_ingreso_justif  ON registro_ingreso(justificacion_id);
    `);
    console.log("✅ registro_ingreso creada");

    await client.query(`
      CREATE TABLE asistencia_clase (
        id                SERIAL PRIMARY KEY,
        matricula_id      INTEGER           NOT NULL REFERENCES matricula(id),
        horario_clase_id  INTEGER           NOT NULL REFERENCES horario_clase(id),
        fecha             DATE              NOT NULL,
        estado            estado_asistencia NOT NULL,
        observacion       VARCHAR(500),
        registrado_por    INTEGER           NOT NULL REFERENCES usuario(id),
        registrado_en     TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
        permiso_salida_id INTEGER           REFERENCES permiso_salida(id),
        justificacion_id  INTEGER           REFERENCES justificacion(id),
        CONSTRAINT uq_asistencia_por_clase UNIQUE (matricula_id, horario_clase_id, fecha)
      );
      CREATE INDEX idx_asistencia_clase_dia ON asistencia_clase(horario_clase_id, fecha);
      CREATE INDEX idx_asistencia_estado    ON asistencia_clase(estado);
      CREATE INDEX idx_asistencia_permiso   ON asistencia_clase(permiso_salida_id);
      CREATE INDEX idx_asistencia_justif    ON asistencia_clase(justificacion_id);
    `);
    console.log("✅ asistencia_clase creada");

    // ── BLOQUE 6: FUGAS ────────────────────────────────────────────
    await client.query(`
      CREATE TABLE fuga (
        id                  SERIAL PRIMARY KEY,
        asistencia_clase_id INTEGER      NOT NULL UNIQUE REFERENCES asistencia_clase(id),
        reportado_por       INTEGER      NOT NULL REFERENCES usuario(id),
        detectado_en        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        estado              estado_fuga  NOT NULL DEFAULT 'pendiente',
        canal_aviso         canal_aviso  NOT NULL,
        resuelto_por        INTEGER      REFERENCES usuario(id),
        resuelto_en         TIMESTAMPTZ,
        justificacion_id    INTEGER      REFERENCES justificacion(id),
        observacion         VARCHAR(500)
      );
      CREATE INDEX idx_fuga_estado      ON fuga(estado);
      CREATE INDEX idx_fuga_detectado   ON fuga(detectado_en);
      CREATE INDEX idx_fuga_justif      ON fuga(justificacion_id);
    `);
    console.log("✅ fuga creada");

    // ── BLOQUE 7: NOTA ACTITUDINAL ─────────────────────────────────
    await client.query(`
      CREATE TABLE nota_actitudinal (
        id                  SERIAL PRIMARY KEY,
        matricula_id        INTEGER        NOT NULL REFERENCES matricula(id),
        periodo_id          INTEGER        NOT NULL REFERENCES periodo_trimestral(id),
        total_tardanzas     SMALLINT       NOT NULL DEFAULT 0 CHECK (total_tardanzas >= 0),
        total_inasistencias SMALLINT       NOT NULL DEFAULT 0 CHECK (total_inasistencias >= 0),
        total_fugas         SMALLINT       NOT NULL DEFAULT 0 CHECK (total_fugas >= 0),
        valor               DECIMAL(4,2)   NOT NULL CHECK (valor BETWEEN 0 AND 20),
        promedio_academico  DECIMAL(4,2)   CHECK (promedio_academico BETWEEN 0 AND 20),
        estado_reporte      estado_reporte NOT NULL DEFAULT 'borrador',
        generado_por        INTEGER        REFERENCES usuario(id),
        calculado_en        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_nota_por_periodo UNIQUE (matricula_id, periodo_id)
      );
      CREATE INDEX idx_nota_periodo ON nota_actitudinal(periodo_id);
    `);
    console.log("✅ nota_actitudinal creada");

    console.log("\n🎉 Esquema completo creado exitosamente!");
  } catch (error) {
    console.error("❌ Error creando el esquema:", error);
    throw error;
  } finally {
    client.release();
    await pool.end();
  }
}

createSchema()
  .then(() => process.exit(0))
  .catch(() => process.exit(1));
