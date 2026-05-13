# Seeder — Sistema de Control de Asistencia
## Colegio Rafael Narváez Cadenillas

Genera datos de prueba masivos para la base de datos del sistema de asistencia.

---

## Requisitos previos

- Node.js v18+
- pnpm (`npm install -g pnpm`)
- PostgreSQL corriendo localmente o en Docker

---

## Instalación

```bash
pnpm install
```

---

## Configuración

Copia el archivo de ejemplo y llena tus datos:

```bash
cp .env.example .env
```

Edita `.env`:
```
PG_HOST=localhost
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=tu_contraseña
PG_DATABASE=asistencia_colegio
```

---

## Flujo completo

```bash
# 1. Limpiar la base de datos (DROP + CREATE schema)
pnpm clean

# 2. Crear todas las tablas
pnpm seed:schema

# 3. Sembrar todos los datos
pnpm seed:manager
```

---

## Scripts individuales (para pruebas parciales)

```bash
pnpm seed:ano           # Años escolares
pnpm seed:periodos      # Períodos trimestrales
pnpm seed:cursos        # Catálogo de materias
pnpm seed:secciones     # Secciones del año activo
pnpm seed:usuarios      # Usuarios (2 reales + faker)
pnpm seed:estudiantes   # Subtipo estudiante
pnpm seed:docentes      # Subtipo docente
pnpm seed:padres        # Subtipo padre_familia
pnpm seed:vinculos      # Relaciones padre-estudiante
pnpm seed:matriculas    # Matrículas activas
pnpm seed:horarios      # Horarios de clase
pnpm seed:ingresos      # Registros de ingreso (Auxiliar)
pnpm seed:asistencias   # Asistencias por clase (Docente)
pnpm seed:fugas         # Eventos de fuga
pnpm seed:permisos      # Permisos de salida
pnpm seed:justificaciones # Justificaciones
pnpm seed:notas         # Notas actitudinales
```

---

## Patrón "2 somos nosotros"

En `src/entities/usuario.seed.ts`, los primeros 2 registros son los integrantes del equipo (hardcodeados). El resto son generados con Faker.

**Cambia estos campos antes de ejecutar:**
```typescript
usuarios.push(
  ['TuNombre',        'TuApellido',        'tu.email@...', 'admin', DEFAULT_HASH],
  ['NombreCompañero', 'ApellidoCompañero', 'comp@...',     'admin', DEFAULT_HASH],
);
```

---

## Datos generados (aproximado)

| Tabla                      | Registros aprox. |
|----------------------------|-----------------|
| ano_escolar                | 2               |
| periodo_trimestral         | 3               |
| seccion                    | 10              |
| curso                      | 12              |
| usuario                    | ~113            |
| estudiante                 | 80              |
| docente                    | 15              |
| padre_familia              | 15              |
| relacion_padre_estudiante  | ~100            |
| matricula                  | ~80             |
| horario_clase              | ~60             |
| registro_ingreso           | ~4,800          |
| asistencia_clase           | ~10,000         |
| fuga                       | ~400            |
| permiso_salida             | ~30             |
| justificacion              | ~40             |
| nota_actitudinal           | ~240            |
| **TOTAL**                  | **~15,000+**    |

---

## Tecnologías

- TypeScript
- PostgreSQL (`pg`)
- Faker.js (`@faker-js/faker`)
- tsx (ejecución directa de TS)
- dotenv
