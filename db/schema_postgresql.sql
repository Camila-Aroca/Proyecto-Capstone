-- =============================================================================
-- schema_postgresql.sql
-- Modelo fisico OBJETIVO PostgreSQL/PostGIS para el Item 15 del proyecto APT
-- (Sistema de Analisis y Anticipacion de Demanda de Urgencia en Salud Mental, RM).
--
-- Estado: este script crea un esquema VACIO. PostgreSQL/PostGIS AUN NO estan
-- desplegados en este proyecto (no hay AWS/RDS, Docker ni migrations reales).
-- Es el diseno objetivo de persistencia, coherente 1:1 con:
--   docs/07-diagramas/15-modelo-base-datos/modelo_datos_fisico_postgresql.mmd
--
-- Fuente de verdad de los datos actuales: archivos Parquet/CSV en data/processed/
-- (ver docs/07-diagramas/15-modelo-base-datos/README.md, seccion "Modelo logico").
-- Este DDL NO carga datos (sin INSERT/COPY), NO crea usuarios/roles/secrets y
-- NO implementa AWS/RDS/Docker/migrations.
--
-- Stack objetivo declarado en README.md raiz: "Base de Datos: PostgreSQL con
-- extension PostGIS". Por eso este script habilita PostGIS y usa tipos
-- geometry nativos para las capas de cartografia censal. La capa de
-- accesibilidad OSM/GTFS/isocronas permanece en backlog: no se modela aqui
-- porque el proyecto aun no la implementa, no por limitacion del stack.
--
-- Validacion realizada: sintaxis validada estaticamente con python:sqlparse
-- (ver docs/07-diagramas/15-modelo-base-datos/README.md, seccion 9). No se
-- ejecuto contra una instancia PostgreSQL/PostGIS real porque no existe una
-- disponible en este entorno local; no se afirma ejecucion real.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Extension PostGIS: requerida para las columnas geometry de censo.*.
-- Requiere privilegios de creacion de extensiones en la instancia de destino
-- (rol con CREATE EXTENSION, o extension pre-habilitada por el proveedor,
-- p.ej. RDS PostgreSQL soporta postgis via rds_superuser). No se asume ni
-- aprovisiona ese privilegio aqui; solo se declara el requisito.
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS postgis;

-- -----------------------------------------------------------------------------
-- Esquemas: replican 1:1 los subdirectorios de data/processed/ para
-- trazabilidad directa entre el dataset canonico y su tabla objetivo.
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS censo;
CREATE SCHEMA IF NOT EXISTS pobreza;
CREATE SCHEMA IF NOT EXISTS geo;
CREATE SCHEMA IF NOT EXISTS urgencias;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS egresos;

-- =============================================================================
-- censo.cartografia_comunal
-- Grain: 1 fila = 1 comuna RM (52 filas en data/processed/censo/Cartografia_censo2024_RM_Comunal.parquet).
-- Ancla territorial de todo el modelo (todas las tablas por comuna referencian esta tabla).
-- =============================================================================
CREATE TABLE censo.cartografia_comunal (
    comuna_codigo   CHAR(5)     NOT NULL,
    comuna_glosa    TEXT        NOT NULL,
    cod_region      SMALLINT    NOT NULL,
    provincia       TEXT,
    geom            geometry(MultiPolygon, 4674) NOT NULL,
    CONSTRAINT pk_cartografia_comunal PRIMARY KEY (comuna_codigo)
);

COMMENT ON TABLE censo.cartografia_comunal IS
    'Dimension geografica base (comuna). comuna_codigo se estandariza a CHAR(5) '
    'para mantener consistencia de tipos con el resto de las tablas ancladas en '
    'comuna; el Parquet fuente publica el mismo valor como CUT (INTEGER). '
    'Requiere cast + zero-pad en la etapa de carga.';
COMMENT ON COLUMN censo.cartografia_comunal.geom IS
    'SRID 4674 = SIRGAS 2000, CRS real observado en la fuente GeoParquet '
    '(ver reports/eda/eda_cartografia_censo2024_subcomunal.md). No se aplica '
    'ninguna reproyeccion.';

CREATE INDEX ix_cartografia_comunal_geom ON censo.cartografia_comunal USING GIST (geom);

-- =============================================================================
-- censo.cartografia_distrital
-- Grain: 1 fila = 1 distrito censal (451 filas RM, 52/52 comunas cubiertas).
-- =============================================================================
CREATE TABLE censo.cartografia_distrital (
    distrito_id     BIGINT      NOT NULL,
    comuna_codigo   CHAR(5)     NOT NULL,
    cod_distrito    SMALLINT    NOT NULL,
    distrito_glosa  TEXT,
    geom            geometry(MultiPolygon, 4674) NOT NULL,
    CONSTRAINT pk_cartografia_distrital PRIMARY KEY (distrito_id),
    CONSTRAINT fk_cartografia_distrital_comuna FOREIGN KEY (comuna_codigo)
        REFERENCES censo.cartografia_comunal (comuna_codigo)
);

COMMENT ON COLUMN censo.cartografia_distrital.distrito_id IS
    'Renombrado desde ID_DISTRITO (double) en el Parquet fuente; se castea a '
    'BIGINT (codigo entero, la fuente lo exporta como double por artefacto de '
    'origen Esri). Llave sin nulos ni duplicados verificada en la fuente.';

CREATE INDEX ix_cartografia_distrital_comuna ON censo.cartografia_distrital (comuna_codigo);
CREATE INDEX ix_cartografia_distrital_geom ON censo.cartografia_distrital USING GIST (geom);

-- =============================================================================
-- censo.cartografia_zonal
-- Grain: 1 fila = 1 zona urbana (1865 filas RM). Cobertura parcial: 51/52
-- comunas (San Pedro, 13505, no tiene zonas urbanas; hecho de la fuente, no
-- error de filtrado). AREA_C='URBANO' en el 100% de las filas.
-- =============================================================================
CREATE TABLE censo.cartografia_zonal (
    zona_id         BIGINT      NOT NULL,
    distrito_id     BIGINT      NOT NULL,
    n_per           NUMERIC,
    geom            geometry(MultiPolygon, 4674) NOT NULL,
    CONSTRAINT pk_cartografia_zonal PRIMARY KEY (zona_id),
    CONSTRAINT fk_cartografia_zonal_distrito FOREIGN KEY (distrito_id)
        REFERENCES censo.cartografia_distrital (distrito_id)
);

COMMENT ON TABLE censo.cartografia_zonal IS
    'Renombrado desde ID_ZONA (double); llave sin nulos ni duplicados '
    'verificada en la fuente. Solo se persisten aqui las columnas de grano y '
    'poblacion total (n_per); el Parquet fuente publica ademas ~150 columnas '
    'socioeconomicas (n_*/prom_*) no documentadas formalmente por el '
    'diccionario oficial del Censo 2024 (ver reports/eda/eda_cartografia_censo2024_subcomunal.md). '
    'No se modelan aqui para no inventar semantica no confirmada por la fuente; '
    'pueden anadirse en el futuro sin afectar PK/FK.';
COMMENT ON COLUMN censo.cartografia_zonal.n_per IS
    'Poblacion censada de la zona. Verificado por reconciliacion (2026-09-18): '
    'suma de manzanas urbanas coincide exactamente con Zonal en las 52 comunas.';

CREATE INDEX ix_cartografia_zonal_distrito ON censo.cartografia_zonal (distrito_id);
CREATE INDEX ix_cartografia_zonal_geom ON censo.cartografia_zonal USING GIST (geom);

-- =============================================================================
-- censo.cartografia_entidades
-- Grain: 1 fila = 1 entidad poblada rural dispersa (2072 filas RM). Cobertura
-- parcial: 26/52 comunas (ausente en las comunas mas urbanizadas; hecho de la
-- fuente). AREA_C='RURAL' en el 100% de las filas.
-- =============================================================================
CREATE TABLE censo.cartografia_entidades (
    entidad_id      BIGINT      NOT NULL,
    distrito_id     BIGINT      NOT NULL,
    entidad_glosa   TEXT,
    n_per           NUMERIC,
    geom            geometry(MultiPolygon, 4674) NOT NULL,
    CONSTRAINT pk_cartografia_entidades PRIMARY KEY (entidad_id),
    CONSTRAINT fk_cartografia_entidades_distrito FOREIGN KEY (distrito_id)
        REFERENCES censo.cartografia_distrital (distrito_id)
);

COMMENT ON COLUMN censo.cartografia_entidades.entidad_id IS
    'Renombrado desde MANZENT (double) de la capa Entidades del GeoParquet '
    'fuente, NO desde ID_ENTIDAD: ID_ENTIDAD tiene 16 valores duplicados en RM '
    '(mismo nombre de entidad repetido entre distritos distintos, verificado '
    'directamente en el Parquet) y no es una llave valida. MANZENT si esta '
    'confirmado sin nulos ni duplicados en reports/eda/eda_cartografia_censo2024_subcomunal.md.';

CREATE INDEX ix_cartografia_entidades_distrito ON censo.cartografia_entidades (distrito_id);
CREATE INDEX ix_cartografia_entidades_geom ON censo.cartografia_entidades USING GIST (geom);

-- =============================================================================
-- censo.cartografia_manzanas
-- Grain: 1 fila = 1 manzana (urbana + aldea rural nucleada) (66873 filas RM,
-- cubre 52/52 comunas). Es la unica de las 3 capas subcomunales con cobertura
-- comunal completa.
-- =============================================================================
CREATE TABLE censo.cartografia_manzanas (
    manzana_id      BIGINT      NOT NULL,
    distrito_id     BIGINT      NOT NULL,
    tipo_mz         TEXT        NOT NULL,
    n_per           NUMERIC,
    geom            geometry(MultiPolygon, 4674) NOT NULL,
    CONSTRAINT pk_cartografia_manzanas PRIMARY KEY (manzana_id),
    CONSTRAINT fk_cartografia_manzanas_distrito FOREIGN KEY (distrito_id)
        REFERENCES censo.cartografia_distrital (distrito_id),
    CONSTRAINT ck_cartografia_manzanas_tipo_mz CHECK (tipo_mz IN ('URBANO', 'ALDEA'))
);

COMMENT ON COLUMN censo.cartografia_manzanas.manzana_id IS
    'Renombrado desde MANZENT (double) de la capa Manzanas. No se establece '
    'FK/relacion jerarquica hacia cartografia_zonal ni cartografia_entidades: '
    'la coincidencia entre Manzanas urbanas y Zonal esta verificada solo por '
    'agregacion (suma de n_per), no por una llave compartida a nivel de fila; '
    'modelar esa relacion como FK inventaria una llave que no existe en la fuente.';
COMMENT ON COLUMN censo.cartografia_manzanas.n_per IS
    '24.5% de las manzanas RM tienen MZ_BASE_CENSO=0 con n_per=0 (no nulo); no '
    'es posible determinar con esta fuente si son manzanas deshabitadas o '
    'supresion estadistica (ver EDA).';

CREATE INDEX ix_cartografia_manzanas_distrito ON censo.cartografia_manzanas (distrito_id);
CREATE INDEX ix_cartografia_manzanas_geom ON censo.cartografia_manzanas USING GIST (geom);

-- =============================================================================
-- censo.dim_poblacion_comuna_censo2024
-- Grain: 1 fila = 1 comuna RM, periodo unico 2024 (52 filas).
-- =============================================================================
CREATE TABLE censo.dim_poblacion_comuna_censo2024 (
    comuna_codigo       CHAR(5)     NOT NULL,
    ano_referencia      SMALLINT    NOT NULL,
    poblacion_censada   BIGINT      NOT NULL,
    fuente              TEXT,
    CONSTRAINT pk_dim_poblacion_comuna_censo2024 PRIMARY KEY (comuna_codigo),
    CONSTRAINT fk_dim_poblacion_comuna_censo2024_comuna FOREIGN KEY (comuna_codigo)
        REFERENCES censo.cartografia_comunal (comuna_codigo),
    CONSTRAINT ck_dim_poblacion_comuna_censo2024_poblacion CHECK (poblacion_censada >= 0)
);

COMMENT ON TABLE censo.dim_poblacion_comuna_censo2024 IS
    'Poblacion censada oficial (INE, tabulado D1) por comuna RM, periodo unico '
    '2024. Distinta de censo.dim_poblacion_comuna_anual (proyecciones INE '
    'base Censo 2017): no son intercambiables (PROJECT_CONTEXT.md).';

-- =============================================================================
-- censo.dim_poblacion_comuna_anual
-- Grain: 1 fila = comuna x ano x tipo_poblacion (260 filas = 52 comunas x 5
-- anos, 2021-2025, en este processed). tipo_poblacion incluido en la PK por
-- robustez de diseno aunque hoy solo existe el valor 'proyeccion'.
-- =============================================================================
CREATE TABLE censo.dim_poblacion_comuna_anual (
    comuna_codigo   CHAR(5)     NOT NULL,
    ano             SMALLINT    NOT NULL,
    tipo_poblacion  TEXT        NOT NULL,
    poblacion       BIGINT      NOT NULL,
    fuente          TEXT,
    CONSTRAINT pk_dim_poblacion_comuna_anual PRIMARY KEY (comuna_codigo, ano, tipo_poblacion),
    CONSTRAINT fk_dim_poblacion_comuna_anual_comuna FOREIGN KEY (comuna_codigo)
        REFERENCES censo.cartografia_comunal (comuna_codigo),
    CONSTRAINT ck_dim_poblacion_comuna_anual_poblacion CHECK (poblacion >= 0)
);

COMMENT ON TABLE censo.dim_poblacion_comuna_anual IS
    'Denominador poblacional anual (INE, estimaciones/proyecciones base Censo '
    '2017) usado por los marts de tasas de Urgencias. En el processed actual '
    'cubre 2021-2025 con tipo_poblacion="proyeccion" unicamente.';

CREATE INDEX ix_dim_poblacion_comuna_anual_comuna ON censo.dim_poblacion_comuna_anual (comuna_codigo);

-- =============================================================================
-- pobreza.dim_vulnerabilidad_comuna
-- Grain: 1 fila = 1 comuna RM, periodo unico Casen 2022 (52 filas). Dimension
-- estatica (no serie temporal): PK = comuna_codigo, sin componente de tiempo.
-- =============================================================================
CREATE TABLE pobreza.dim_vulnerabilidad_comuna (
    comuna_codigo                   CHAR(5)    NOT NULL,
    ano_referencia                  SMALLINT   NOT NULL,
    indicador_vulnerabilidad        NUMERIC    NOT NULL,
    direccion_indicador             TEXT       NOT NULL,
    intervalo_confianza_inferior    NUMERIC,
    intervalo_confianza_superior    NUMERIC,
    CONSTRAINT pk_dim_vulnerabilidad_comuna PRIMARY KEY (comuna_codigo),
    CONSTRAINT fk_dim_vulnerabilidad_comuna_comuna FOREIGN KEY (comuna_codigo)
        REFERENCES censo.cartografia_comunal (comuna_codigo)
);

COMMENT ON TABLE pobreza.dim_vulnerabilidad_comuna IS
    'Proxy oficial de vulnerabilidad socioeconomica comunal (MDS, Observatorio '
    'Social, metodologia SAE): tasa de pobreza por ingresos, NO un indice '
    'general de vulnerabilidad. Periodo unico 2022; no se mezcla con los '
    'marts temporales de Urgencias/Egresos.';
COMMENT ON COLUMN pobreza.dim_vulnerabilidad_comuna.direccion_indicador IS
    'Indica el sentido de interpretacion del indicador (valor observado: '
    '"mayor_valor_mayor_vulnerabilidad"); se preserva como texto libre porque '
    'el dominio completo de valores no esta confirmado por la fuente.';

-- =============================================================================
-- geo.dim_oferta_urgencia_rm
-- Grain: 1 fila = 1 establecimiento con oferta de urgencia RM (174 filas).
-- SNAPSHOT ACTUAL (no historico) de la oferta vigente, distinto en cobertura
-- temporal de los marts de urgencias.mart_establecimiento_monthly (historico
-- 2021-2025).
-- =============================================================================
CREATE TABLE geo.dim_oferta_urgencia_rm (
    establecimiento_codigo     BIGINT      NOT NULL,
    comuna_codigo               CHAR(5)     NOT NULL,
    tipo_establecimiento        TEXT,
    estado_funcionamiento       TEXT,
    latitud                      NUMERIC,
    longitud                     NUMERIC,
    reporto_id36_periodo         BOOLEAN,
    CONSTRAINT pk_dim_oferta_urgencia_rm PRIMARY KEY (establecimiento_codigo),
    CONSTRAINT fk_dim_oferta_urgencia_rm_comuna FOREIGN KEY (comuna_codigo)
        REFERENCES censo.cartografia_comunal (comuna_codigo),
    CONSTRAINT ck_dim_oferta_urgencia_rm_lat CHECK (latitud IS NULL OR latitud BETWEEN -90 AND 90),
    CONSTRAINT ck_dim_oferta_urgencia_rm_lon CHECK (longitud IS NULL OR longitud BETWEEN -180 AND 180)
);

COMMENT ON TABLE geo.dim_oferta_urgencia_rm IS
    'Snapshot ACTUAL (no historico) de establecimientos con oferta de '
    'atencion de urgencia RM vigente. reporto_id36_periodo es evidencia '
    'descriptiva del periodo canonico cerrado 2021-2025, no el criterio de '
    'inclusion en esta tabla.';

CREATE INDEX ix_dim_oferta_urgencia_rm_comuna ON geo.dim_oferta_urgencia_rm (comuna_codigo);

-- =============================================================================
-- urgencias.mart_comuna_weekly
-- Grain: 1 fila = comuna x ano x semana, calendario DEIS (no ISO). 13362
-- filas; 51/52 comunas reportan (Vitacura sin reporte de Urgencias).
-- =============================================================================
CREATE TABLE urgencias.mart_comuna_weekly (
    comuna_codigo                       CHAR(5)     NOT NULL,
    ano                                  SMALLINT    NOT NULL,
    semana                               SMALLINT    NOT NULL,
    atenciones_id1                       INTEGER,
    atenciones_id36                      INTEGER,
    tasa_atenciones_id36_por_10000       NUMERIC,
    CONSTRAINT pk_mart_comuna_weekly PRIMARY KEY (comuna_codigo, ano, semana),
    CONSTRAINT fk_mart_comuna_weekly_comuna FOREIGN KEY (comuna_codigo)
        REFERENCES censo.cartografia_comunal (comuna_codigo),
    CONSTRAINT ck_mart_comuna_weekly_atenciones CHECK (
        (atenciones_id1 IS NULL OR atenciones_id1 >= 0) AND
        (atenciones_id36 IS NULL OR atenciones_id36 >= 0)
    )
);

COMMENT ON TABLE urgencias.mart_comuna_weekly IS
    'atenciones_id36 (agregado DEIS de salud mental) NO equivale estrictamente '
    'al capitulo CIE-10 F00-F99 de Egresos: incluye ID37 (Ideacion Suicida, '
    'R45.8). semana seguye el calendario semanal publicado por DEIS, no se '
    'convierte a semana ISO.';

-- =============================================================================
-- urgencias.mart_comuna_monthly
-- Grain: 1 fila = comuna x ano x mes. 3060 filas; 51/52 comunas reportan.
-- =============================================================================
CREATE TABLE urgencias.mart_comuna_monthly (
    comuna_codigo                       CHAR(5)     NOT NULL,
    ano                                  SMALLINT    NOT NULL,
    mes                                  SMALLINT    NOT NULL,
    atenciones_id1                       INTEGER,
    atenciones_id36                      INTEGER,
    tasa_atenciones_id36_por_10000       NUMERIC,
    CONSTRAINT pk_mart_comuna_monthly PRIMARY KEY (comuna_codigo, ano, mes),
    CONSTRAINT fk_mart_comuna_monthly_comuna FOREIGN KEY (comuna_codigo)
        REFERENCES censo.cartografia_comunal (comuna_codigo),
    CONSTRAINT ck_mart_comuna_monthly_mes CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT ck_mart_comuna_monthly_atenciones CHECK (
        (atenciones_id1 IS NULL OR atenciones_id1 >= 0) AND
        (atenciones_id36 IS NULL OR atenciones_id36 >= 0)
    )
);

-- =============================================================================
-- urgencias.mart_establecimiento_monthly
-- Grain: 1 fila = establecimiento x ano x mes. 8857 filas; 152
-- establecimientos con reporte 2021-2025 (no una cifra especifica de 2025).
-- =============================================================================
CREATE TABLE urgencias.mart_establecimiento_monthly (
    establecimiento_codigo     BIGINT      NOT NULL,
    ano                          SMALLINT    NOT NULL,
    mes                          SMALLINT    NOT NULL,
    comuna_codigo                CHAR(5)     NOT NULL,
    atenciones_id36               INTEGER,
    CONSTRAINT pk_mart_establecimiento_monthly PRIMARY KEY (establecimiento_codigo, ano, mes),
    CONSTRAINT fk_mart_establecimiento_monthly_comuna FOREIGN KEY (comuna_codigo)
        REFERENCES censo.cartografia_comunal (comuna_codigo),
    CONSTRAINT ck_mart_establecimiento_monthly_mes CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT ck_mart_establecimiento_monthly_atenciones CHECK (atenciones_id36 IS NULL OR atenciones_id36 >= 0)
);

COMMENT ON TABLE urgencias.mart_establecimiento_monthly IS
    'establecimiento_codigo NO tiene FK fisica hacia geo.dim_oferta_urgencia_rm: '
    'verificado que 3 de los 152 establecimientos historicos 2021-2025 no '
    'estan en el snapshot actual de oferta (174 establecimientos vigentes), '
    'porque dim_oferta_urgencia_rm es un snapshot ACTUAL y esta tabla es '
    'historica. Declarar esa FK rompería la carga real; se documenta como '
    'relacion logica no forzada. comuna_codigo si tiene FK: se verifico que '
    'el dominio completo esta contenido en las 52 comunas RM.';

CREATE INDEX ix_mart_establecimiento_monthly_comuna ON urgencias.mart_establecimiento_monthly (comuna_codigo);

-- =============================================================================
-- urgencias.mart_comuna_etario_monthly
-- Grain: 1 fila = comuna x ano x mes x grupo_etario_urgencia (formato largo).
-- 15300 filas; 51/52 comunas reportan; 5 grupos etarios publicados por DEIS.
-- =============================================================================
CREATE TABLE urgencias.mart_comuna_etario_monthly (
    comuna_codigo            CHAR(5)     NOT NULL,
    ano                       SMALLINT    NOT NULL,
    mes                       SMALLINT    NOT NULL,
    grupo_etario_urgencia     TEXT        NOT NULL,
    atenciones_id36            INTEGER,
    CONSTRAINT pk_mart_comuna_etario_monthly PRIMARY KEY (comuna_codigo, ano, mes, grupo_etario_urgencia),
    CONSTRAINT fk_mart_comuna_etario_monthly_comuna FOREIGN KEY (comuna_codigo)
        REFERENCES censo.cartografia_comunal (comuna_codigo),
    CONSTRAINT ck_mart_comuna_etario_monthly_mes CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT ck_mart_comuna_etario_monthly_grupo CHECK (grupo_etario_urgencia IN (
        'menores_1', 'de_1_a_4', 'de_5_a_14', 'de_15_a_64', 'de_65_y_mas'
    )),
    CONSTRAINT ck_mart_comuna_etario_monthly_atenciones CHECK (atenciones_id36 IS NULL OR atenciones_id36 >= 0)
);

COMMENT ON TABLE urgencias.mart_comuna_etario_monthly IS
    'Sin columna de sexo/genero: Urgencias no publica esa desagregacion. Los '
    '5 valores de grupo_etario_urgencia son exactamente los publicados por DEIS.';

-- =============================================================================
-- marts.mart_mvp_territorial_comuna
-- Grain: 1 fila = 1 comuna RM (52 filas, corte unico MVP). Mart derivado/
-- materializado: integra demanda 2025, poblacion, vulnerabilidad y oferta sin
-- mezclar temporalidades. Vitacura (13132) esta incluida con metricas de
-- demanda NULL (no reporta Urgencias 2025), nunca en cero.
-- =============================================================================
CREATE TABLE marts.mart_mvp_territorial_comuna (
    comuna_codigo                   CHAR(5)     NOT NULL,
    tiene_reporte_urgencias         BOOLEAN     NOT NULL,
    atenciones_id36_2025             BIGINT,
    poblacion_2025                    BIGINT,
    poblacion_censada_2024            BIGINT,
    indicador_vulnerabilidad          NUMERIC,
    n_oferta_urgencia_actual          BIGINT,
    CONSTRAINT pk_mart_mvp_territorial_comuna PRIMARY KEY (comuna_codigo),
    CONSTRAINT fk_mart_mvp_territorial_comuna_comuna FOREIGN KEY (comuna_codigo)
        REFERENCES censo.cartografia_comunal (comuna_codigo)
);

COMMENT ON TABLE marts.mart_mvp_territorial_comuna IS
    'Mart MVP de corte unico (no serie temporal). No reemplaza a '
    'urgencias.mart_comuna_monthly/weekly ni a geo.dim_oferta_urgencia_rm; es '
    'una integracion comunal derivada para el MVP analitico, no fuente '
    'primaria. atenciones_id36_2025 y demas metricas de demanda son NULL '
    '(nunca 0) cuando tiene_reporte_urgencias = FALSE.';

-- =============================================================================
-- egresos.egresos_f00_f99_nacional
-- Grain: 1 fila = 1 registro de egreso hospitalario F00-F99 publicado por
-- DEIS (218794 filas). Alcance NACIONAL, no filtrado a RM. Dataset disociado
-- y anonimizado (sin identificador de paciente); no se deduplica.
-- SIN relacion de llave con ninguna otra tabla de este esquema (invariante
-- del proyecto: Urgencias y Egresos no se enlazan por paciente ni por
-- establecimiento; ver AGENTS.md).
-- =============================================================================
CREATE TABLE egresos.egresos_f00_f99_nacional (
    egreso_id                            BIGINT GENERATED ALWAYS AS IDENTITY,
    ano_egreso                            SMALLINT    NOT NULL,
    sexo                                   TEXT,
    grupo_edad                             TEXT,
    region_residencia                      SMALLINT,
    comuna_residencia                      INTEGER,
    diag1                                   TEXT        NOT NULL,
    pertenencia_establecimiento_salud      TEXT,
    dias_estada                             INTEGER,
    residente_rm                            BOOLEAN,
    CONSTRAINT pk_egresos_f00_f99_nacional PRIMARY KEY (egreso_id),
    CONSTRAINT ck_egresos_f00_f99_nacional_diag1 CHECK (diag1 LIKE 'F%'),
    CONSTRAINT ck_egresos_f00_f99_nacional_dias_estada CHECK (dias_estada IS NULL OR dias_estada >= 0)
);

COMMENT ON TABLE egresos.egresos_f00_f99_nacional IS
    'Alcance NACIONAL (no filtrado a RM); residente_rm es booleana derivada de '
    'region_residencia (NULL si region_residencia es nula en origen). No tiene '
    'identificador de establecimiento: pertenencia_establecimiento_salud solo '
    'indica pertenencia SNSS del establecimiento, no cual ni donde. sexo y '
    'grupo_edad de 2021 usan esquemas incompatibles con el resto de los anos '
    '(no homologado, ver reports/dictionary/diccionario_egresos_f00_f99_nacional.md).';
COMMENT ON COLUMN egresos.egresos_f00_f99_nacional.egreso_id IS
    'Clave tecnica (surrogate key) generada en la carga a PostgreSQL. NO '
    'existe en la fuente DEIS, NO identifica a una persona y NO habilita '
    'joins por paciente con ningun otro dataset.';
COMMENT ON COLUMN egresos.egresos_f00_f99_nacional.region_residencia IS
    'Residencia del PACIENTE, no ubicacion del hospital. Alcance nacional: '
    'sin FK a censo.cartografia_comunal (esa dimension es exclusiva RM y el '
    'dominio territorial de esta columna no coincide).';
COMMENT ON COLUMN egresos.egresos_f00_f99_nacional.comuna_residencia IS
    'Residencia del PACIENTE, no ubicacion del hospital. Alcance nacional: '
    'sin FK a censo.cartografia_comunal (esa dimension es exclusiva RM y el '
    'dominio territorial de esta columna no coincide; crear esa FK '
    'invalidaria filas de residentes fuera de RM).';

CREATE INDEX ix_egresos_f00_f99_nacional_ano ON egresos.egresos_f00_f99_nacional (ano_egreso);
CREATE INDEX ix_egresos_f00_f99_nacional_comuna_residencia ON egresos.egresos_f00_f99_nacional (comuna_residencia);
CREATE INDEX ix_egresos_f00_f99_nacional_diag1 ON egresos.egresos_f00_f99_nacional (diag1);
