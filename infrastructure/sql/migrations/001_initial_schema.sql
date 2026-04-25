-- =============================================================================
-- PrevencionApp — Esquema PostgreSQL Completo
-- Privacy by Design · RLS · Auditoría · Performance
-- Ejecutar en Supabase SQL Editor (como superuser)
-- =============================================================================

-- ── Extensiones ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Búsqueda fuzzy por nombre
CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- Cifrado PII (fase 2)

-- =============================================================================
-- TABLAS CATÁLOGO
-- =============================================================================

CREATE TABLE paises (
    id          SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    codigo_iso  CHAR(2)      NOT NULL UNIQUE,
    nombre      VARCHAR(100) NOT NULL
);

CREATE TABLE ciudades (
    id       INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    nombre   VARCHAR(100) NOT NULL,
    pais_id  SMALLINT     NOT NULL REFERENCES paises(id),
    UNIQUE (nombre, pais_id)
);

CREATE TABLE sexos (
    id     SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    nombre VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE estados_civiles (
    id     SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    nombre VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE tipos_identificacion (
    id     SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    codigo VARCHAR(10)  NOT NULL UNIQUE,
    nombre VARCHAR(60)  NOT NULL
);

CREATE TABLE pertenencias_etnicas (
    id     SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    nombre VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE poblaciones_especiales (
    id     SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    nombre VARCHAR(80) NOT NULL UNIQUE
);

-- =============================================================================
-- TABLA PACIENTES (PII hasheada)
-- =============================================================================

CREATE TABLE pacientes (
    id                      UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID         REFERENCES auth.users(id) ON DELETE SET NULL,
    primer_nombre           VARCHAR(100) NOT NULL,
    segundo_nombre          VARCHAR(100),
    primer_apellido         VARCHAR(100) NOT NULL,
    segundo_apellido        VARCHAR(100),
    -- PII hasheada SHA-256 + sal dinámica (Secret Manager)
    identificacion_hash     VARCHAR(64)  NOT NULL,
    telefono_hash           VARCHAR(64),
    -- Dirección: BYTEA para cifrado pgcrypto futuro
    direccion               BYTEA,
    fecha_nacimiento        DATE,
    sexo_id                 SMALLINT     REFERENCES sexos(id),
    estado_civil_id         SMALLINT     REFERENCES estados_civiles(id),
    tipo_identificacion_id  SMALLINT     REFERENCES tipos_identificacion(id),
    pais_id                 SMALLINT     REFERENCES paises(id),
    ciudad_id               INTEGER      REFERENCES ciudades(id),
    pertenencia_etnica_id   SMALLINT     REFERENCES pertenencias_etnicas(id),
    poblacion_especial_id   SMALLINT     REFERENCES poblaciones_especiales(id),
    activo                  BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    fecha_actualizacion     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Índices estratégicos
CREATE UNIQUE INDEX idx_pacientes_identificacion_hash
    ON pacientes(identificacion_hash);

CREATE INDEX idx_pacientes_user_activo
    ON pacientes(user_id, activo)
    WHERE activo = TRUE;

CREATE INDEX idx_pacientes_nombre_trgm
    ON pacientes USING GIN ((primer_nombre || ' ' || primer_apellido) gin_trgm_ops);

-- =============================================================================
-- TABLA EVALUACIONES (núcleo transaccional)
-- =============================================================================

CREATE TABLE evaluaciones (
    id                      UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id              UUID        NOT NULL DEFAULT uuid_generate_v4() UNIQUE,
    user_id                 UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
    paciente_id             UUID        REFERENCES pacientes(id) ON DELETE SET NULL,

    -- Desnormalizado para optimizar RLS (evita JOINs en cada query)
    paciente_activo         BOOLEAN     DEFAULT FALSE,

    -- Metadatos del formulario
    consentimiento          BOOLEAN     NOT NULL,
    version_cuestionario    VARCHAR(10) NOT NULL DEFAULT '1.0',
    fecha_creacion          TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_expiracion        TIMESTAMPTZ,

    -- Respuestas completas en JSONB (schema flexible)
    respuestas_completas    JSONB,

    -- Columnas desnormalizadas para queries analíticos rápidos
    p12a  BOOLEAN,    -- dolor_articular
    p13a  BOOLEAN,    -- rigidez_matutina
    p14   INTEGER,    -- duracion_rigidez_minutos
    p15   BOOLEAN,    -- inflamacion_visible

    -- Resultado ML
    nivel_inflamacion       VARCHAR(20),  -- bajo|moderado|alto|critico
    probabilidad            NUMERIC(5,4),
    confianza               NUMERIC(5,4),
    gradcam_url             TEXT,
    imagen_path_temp        TEXT,

    CONSTRAINT chk_probabilidad CHECK (probabilidad BETWEEN 0 AND 1),
    CONSTRAINT chk_confianza    CHECK (confianza BETWEEN 0 AND 1),
    CONSTRAINT chk_nivel        CHECK (nivel_inflamacion IN ('bajo','moderado','alto','critico'))
);

CREATE INDEX idx_evaluaciones_rls_composite
    ON evaluaciones(user_id, paciente_activo);

CREATE INDEX idx_evaluaciones_session
    ON evaluaciones(session_id);

CREATE INDEX idx_evaluaciones_respuestas_fast
    ON evaluaciones USING GIN (respuestas_completas jsonb_path_ops);

CREATE INDEX idx_evaluaciones_fecha
    ON evaluaciones(fecha_creacion DESC);

-- =============================================================================
-- AUDITORÍA (particionada por año)
-- =============================================================================

CREATE TABLE auditoria_logs (
    id              BIGINT       GENERATED ALWAYS AS IDENTITY,
    tabla           VARCHAR(50)  NOT NULL,
    operacion       CHAR(6)      NOT NULL CHECK (operacion IN ('INSERT', 'UPDATE', 'DELETE')),
    registro_id     UUID         NOT NULL,
    user_id         UUID,
    datos_delta     JSONB,       -- Solo el delta en UPDATEs (10x menos volumen)
    ip_address      INET,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
) PARTITION BY RANGE (created_at);

-- Particiones por año
CREATE TABLE auditoria_logs_2026
    PARTITION OF auditoria_logs
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

CREATE TABLE auditoria_logs_default
    PARTITION OF auditoria_logs
    DEFAULT;

CREATE INDEX idx_auditoria_registro ON auditoria_logs(registro_id, created_at);

-- =============================================================================
-- VISTA MATERIALIZADA ANALÍTICA
-- =============================================================================

CREATE MATERIALIZED VIEW mv_analitica_riesgo AS
SELECT
    e.id                    AS evaluacion_id,
    e.fecha_creacion,
    e.nivel_inflamacion,
    e.probabilidad,
    e.confianza,
    e.version_cuestionario,
    e.p12a                  AS dolor_articular,
    e.p13a                  AS rigidez_matutina,
    e.p14                   AS duracion_rigidez,
    e.p15                   AS inflamacion_visible,
    p.pais_id,
    p.sexo_id,
    date_part('year', age(p.fecha_nacimiento)) AS edad_anios
FROM evaluaciones e
LEFT JOIN pacientes p ON p.id = e.paciente_id
WHERE e.nivel_inflamacion IS NOT NULL;

CREATE UNIQUE INDEX ON mv_analitica_riesgo(evaluacion_id);

-- Refrescar sin bloqueos (requiere unique index)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_analitica_riesgo;

-- =============================================================================
-- FUNCIÓN RPC ATÓMICA: registrar_paciente_full
-- Una sola transacción ACID para upsert paciente
-- =============================================================================

CREATE OR REPLACE FUNCTION registrar_paciente_full(
    p_user_id               UUID,
    p_primer_nombre         VARCHAR,
    p_primer_apellido       VARCHAR,
    p_segundo_nombre        VARCHAR    DEFAULT NULL,
    p_segundo_apellido      VARCHAR    DEFAULT NULL,
    p_identificacion_hash   VARCHAR    DEFAULT NULL,
    p_tipo_identificacion_id SMALLINT  DEFAULT NULL,
    p_telefono_hash         VARCHAR    DEFAULT NULL,
    p_fecha_nacimiento      DATE       DEFAULT NULL,
    p_sexo_id               SMALLINT  DEFAULT NULL,
    p_pais_id               SMALLINT  DEFAULT NULL,
    p_ciudad_id             INTEGER   DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER  -- Ejecuta con privilegios del owner, no del caller
SET search_path = public
AS $$
DECLARE
    v_paciente_id UUID;
BEGIN
    -- Upsert: actualiza si ya existe un paciente activo para el user_id
    INSERT INTO pacientes (
        user_id, primer_nombre, segundo_nombre,
        primer_apellido, segundo_apellido,
        identificacion_hash, tipo_identificacion_id,
        telefono_hash, fecha_nacimiento,
        sexo_id, pais_id, ciudad_id
    )
    VALUES (
        p_user_id, p_primer_nombre, p_segundo_nombre,
        p_primer_apellido, p_segundo_apellido,
        p_identificacion_hash, p_tipo_identificacion_id,
        p_telefono_hash, p_fecha_nacimiento,
        p_sexo_id, p_pais_id, p_ciudad_id
    )
    ON CONFLICT (identificacion_hash)
    DO UPDATE SET
        primer_nombre         = EXCLUDED.primer_nombre,
        primer_apellido       = EXCLUDED.primer_apellido,
        telefono_hash         = EXCLUDED.telefono_hash,
        fecha_nacimiento      = EXCLUDED.fecha_nacimiento,
        sexo_id               = EXCLUDED.sexo_id,
        pais_id               = EXCLUDED.pais_id,
        ciudad_id             = EXCLUDED.ciudad_id,
        fecha_actualizacion   = now()
    RETURNING id INTO v_paciente_id;

    -- Marcar evaluaciones previas del usuario con paciente_activo = true
    UPDATE evaluaciones
    SET paciente_id = v_paciente_id, paciente_activo = TRUE
    WHERE user_id = p_user_id AND paciente_id IS NULL;

    RETURN v_paciente_id;
END;
$$;

-- =============================================================================
-- TRIGGER: jsonb_diff() para auditoría delta
-- =============================================================================

CREATE OR REPLACE FUNCTION jsonb_diff(old_data JSONB, new_data JSONB)
RETURNS JSONB AS $$
SELECT jsonb_object_agg(key, new_data->key)
FROM jsonb_each(new_data)
WHERE new_data->key IS DISTINCT FROM old_data->key;
$$ LANGUAGE SQL IMMUTABLE;

CREATE OR REPLACE FUNCTION audit_trigger_fn()
RETURNS TRIGGER AS $$
DECLARE
    v_delta JSONB;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO auditoria_logs(tabla, operacion, registro_id, datos_delta)
        VALUES (TG_TABLE_NAME, 'INSERT', NEW.id, to_jsonb(NEW));
    ELSIF TG_OP = 'UPDATE' THEN
        v_delta := jsonb_diff(to_jsonb(OLD), to_jsonb(NEW));
        IF v_delta != '{}'::jsonb THEN
            INSERT INTO auditoria_logs(tabla, operacion, registro_id, datos_delta)
            VALUES (TG_TABLE_NAME, 'UPDATE', NEW.id, v_delta);
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO auditoria_logs(tabla, operacion, registro_id, datos_delta)
        VALUES (TG_TABLE_NAME, 'DELETE', OLD.id, to_jsonb(OLD));
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Activar auditoría en tablas críticas
CREATE TRIGGER audit_pacientes
    AFTER INSERT OR UPDATE OR DELETE ON pacientes
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_fn();

CREATE TRIGGER audit_evaluaciones
    AFTER INSERT OR UPDATE OR DELETE ON evaluaciones
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_fn();

-- =============================================================================
-- TRIGGER: sincronizar paciente_activo al actualizar pacientes
-- =============================================================================

CREATE OR REPLACE FUNCTION sync_paciente_status()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.activo IS DISTINCT FROM NEW.activo THEN
        UPDATE evaluaciones
        SET paciente_activo = NEW.activo
        WHERE paciente_id = NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_paciente_status
    AFTER UPDATE ON pacientes
    FOR EACH ROW EXECUTE FUNCTION sync_paciente_status();

-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- =============================================================================

-- Activar RLS
ALTER TABLE pacientes    ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluaciones ENABLE ROW LEVEL SECURITY;

-- Pacientes: solo el propio usuario puede ver/modificar sus datos
CREATE POLICY "paciente_select_own"
    ON pacientes FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "paciente_insert_own"
    ON pacientes FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "paciente_update_own"
    ON pacientes FOR UPDATE
    USING (user_id = auth.uid());

CREATE POLICY "paciente_delete_own"
    ON pacientes FOR DELETE
    USING (user_id = auth.uid());

-- Evaluaciones: el usuario ve sus evaluaciones vinculadas
CREATE POLICY "evaluacion_select_own"
    ON evaluaciones FOR SELECT
    USING (user_id = auth.uid() OR user_id IS NULL);

-- Inserción anónima permitida (service_role bypass desde backend)
CREATE POLICY "evaluacion_insert_anon"
    ON evaluaciones FOR INSERT
    WITH CHECK (TRUE);

CREATE POLICY "evaluacion_update_own"
    ON evaluaciones FOR UPDATE
    USING (user_id = auth.uid());

-- =============================================================================
-- DATOS INICIALES (SEEDS)
-- =============================================================================

INSERT INTO paises(codigo_iso, nombre) VALUES
    ('CO', 'Colombia'),
    ('AR', 'Argentina'),
    ('ES', 'España'),
    ('MX', 'México'),
    ('US', 'Estados Unidos');

INSERT INTO sexos(nombre) VALUES ('Masculino'), ('Femenino'), ('No binario'), ('Prefiero no decir');
INSERT INTO estados_civiles(nombre) VALUES ('Soltero/a'), ('Casado/a'), ('Divorciado/a'), ('Viudo/a'), ('Unión libre');
INSERT INTO tipos_identificacion(codigo, nombre) VALUES
    ('CC', 'Cédula de Ciudadanía'),
    ('CE', 'Cédula de Extranjería'),
    ('PAS', 'Pasaporte'),
    ('DNI', 'Documento Nacional de Identidad'),
    ('NIT', 'NIT');
