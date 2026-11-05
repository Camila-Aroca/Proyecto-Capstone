# EDA: `mart_urgencias_establecimiento_weekly`

Generado por `scripts/eda_mart_urgencias_establecimiento_weekly.py` (stage `eda_mart_urgencias_establecimiento_weekly`). No editar a mano. Diccionario: `reports/dictionary/diccionario_mart_urgencias_establecimiento_weekly.md`.

## 1. Grano y cobertura

- Grano: `establecimiento_codigo` × `ano` × `semana` DEIS. Filas: 38.641; establecimientos: 152; período 2021-2025.
- Grilla regular: 260 semanas (se excluyen 295 filas de semana 53, fragmentos de pocos días).
- **137 establecimientos reportan todas las semanas** y 144 reportan al menos el 95%.
- Conteos nulos: 0. Cuando un establecimiento reporta una semana publica todas las causas del contrato, con cero si corresponde; **una semana sin fila es ausencia de reporte y no se imputa**.

| tipo de establecimiento | establecimientos | con_todas_las_semanas | id36_semanal_medio |
|---|---|---|---|
| CEAR | 1 | 0 | 0,1 |
| Hospital | 26 | 24 | 31,6 |
| SAPU | 92 | 89 | 8,5 |
| SAR | 23 | 18 | 14,1 |
| SUR | 10 | 6 | 2,9 |

## 2. Volumen semanal: qué series son modelables

Establecimientos según su promedio semanal en 2025. Una serie con menos de una atención por semana es casi solo ruido; un pronóstico individual sobre ella aporta poco.

| umbral (promedio semanal) | ID36 en 2025 | ID42 en 2025 |
|---|---|---|
| >= 1 | 144 | 13 |
| >= 5 | 123 | 9 |
| >= 10 | 67 | 6 |

## 3. ID42: hospitalizaciones derivadas desde urgencia (F00-F99)

- Filas con ID42 positivo por tipo de establecimiento: {'Hospital': 3185}. Los demás establecimientos publican la fila con cero.
- **Hecho observado:** la proporción ID42 / ID36 sube en los primeros años y se estabiliza después. **Hipótesis (no verificada):** maduración del registro de la sección 2; con estos datos no es posible distinguirla de un cambio real en la práctica de hospitalización.

| ano | id36 | id42 | ID42 / ID36 (%) | hospitales con ID42 > 0 |
|---|---|---|---|---|
| 2021 | 80.894 | 2.744 | 3,39 | 23 |
| 2022 | 95.194 | 4.465 | 4,69 | 22 |
| 2023 | 104.919 | 6.645 | 6,33 | 22 |
| 2024 | 107.648 | 6.420 | 5,96 | 22 |
| 2025 | 111.284 | 6.724 | 6,04 | 23 |

Hospitales con más ID42 en 2025:

| establecimiento_codigo | establecimiento | promedio semanal |
|---|---|---|
| 109102 | Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 26,2 |
| 111101 | Hospital Clínico Metropolitano El Carmen Doctor Luis Valentín Ferrada | 17,8 |
| 114101 | Complejo Hospitalario Dr. Sótero del Río (Santiago, Puente Alto) | 17,2 |
| 112102 | Hospital de Niños Dr. Luis Calvo Mackenna | 13,8 |
| 112100 | Hospital Del Salvador de Santiago | 11,8 |
| 113180 | Hospital El Pino (Santiago, San Bernardo) | 11,7 |
| 110150 | Hospital San José (Melipilla) | 7,2 |
| 114105 | Hospital Clínico Metropolitano La Florida Dra. Eloísa Díaz Insunza | 6,2 |
| 113150 | Hospital San Luis (Buin) | 5,3 |
| 109101 | Hospital Clínico de Niños Dr. Roberto del Río (Santiago, Independencia) | 3,3 |

## 4. Establecimientos con semanas sin reporte

Ordenados de menor a mayor número de semanas reportadas. La causa de la ausencia (apertura, cierre o interrupción del reporte) no es determinable con este mart.

| establecimiento_codigo | establecimiento | tipo | semanas | primera | ultima |
|---|---|---|---|---|---|
| 202221 | SAR Dr. Gustavo Molina | SAR | 6 | 2025-11-02 | 2025-12-21 |
| 201712 | SAR ELSA ROMO ARAVENA | SAR | 58 | 2024-01-01 | 2025-12-21 |
| 201632 | SAR Michelle Bachelet | SAR | 74 | 2024-01-01 | 2025-12-21 |
| 201438 | Servicio de Urgencia Rural SUR Irene Frei Montalva | SUR | 104 | 2024-01-01 | 2025-12-21 |
| 112320 | Centro de Salud Familiar Juan Pablo II ( La Reina) | CEAR | 143 | 2021-01-03 | 2025-07-20 |
| 201015 | SAR Violeta Parra | SAR | 158 | 2021-04-18 | 2025-12-21 |
| 200744 | SUR Huertos Familiares | SUR | 175 | 2021-01-03 | 2025-12-21 |
| 109804 | SAPU Valdivieso | SAPU | 227 | 2021-01-03 | 2025-12-21 |
| 109102 | Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | Hospital | 250 | 2021-03-14 | 2025-12-21 |
| 109821 | SAPU Juan Antonio Ríos | SAPU | 250 | 2021-01-03 | 2025-12-21 |
| 114828 | SAPU Poetisa Gabriela Mistral | SAPU | 253 | 2021-01-03 | 2025-12-21 |
| 111100 | Hospital Clínico San Borja Arriarán | Hospital | 255 | 2021-01-03 | 2025-12-21 |
| 200966 | SUR Alto Jahuel | SUR | 257 | 2021-01-03 | 2025-11-30 |
| 200968 | SUR Maipo | SUR | 257 | 2021-01-03 | 2025-11-30 |
| 109809 | SAR Conchalí | SAR | 259 | 2021-01-03 | 2025-12-21 |

## 5. Implicancias para el pronóstico por establecimiento

- La grilla regular permite reutilizar la construcción del panel del modelo comunal para los establecimientos con cobertura completa en la ventana de entrenamiento.
- Los establecimientos de bajo volumen no justifican un pronóstico individual; se evaluará en el benchmark desde qué volumen el modelo supera al baseline.
- ID42 debe modelarse solo sobre hospitales y considerando el cambio de nivel de los primeros años antes de fijar la ventana de entrenamiento.
