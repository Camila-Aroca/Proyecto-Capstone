#!/usr/bin/env bash
# Imprime los argumentos `-c` de CDK con la configuración de la API que está en servicio
# (imagen, tareas deseadas, CPU, memoria y pronóstico no vigente), para que un despliegue
# automático de infraestructura no la cambie. Solo lee; no modifica nada.
set -euo pipefail

CLUSTER="${SAAD_ECS_CLUSTER:-saad}"
SERVICIO="${SAAD_ECS_SERVICE:-saad-api}"

read -r DEFINICION DESEADAS <<< "$(aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICIO" \
  --query 'services[0].[taskDefinition,desiredCount]' --output text)"
read -r CPU MEMORIA IMAGEN <<< "$(aws ecs describe-task-definition --task-definition "$DEFINICION" \
  --query 'taskDefinition.[cpu,memory,containerDefinitions[0].image]' --output text)"
PRONOSTICO="$(aws ecs describe-task-definition --task-definition "$DEFINICION" \
  --query "taskDefinition.containerDefinitions[0].environment[?name=='SAAD_USAR_PRONOSTICO_DESACTUALIZADO'].value | [0]" \
  --output text)"
[[ "$PRONOSTICO" == "None" ]] && PRONOSTICO=0

echo " -c api_tag=${IMAGEN##*:} -c api_desired_count=$DESEADAS -c api_cpu=$CPU -c api_memory=$MEMORIA -c api_pronostico_desactualizado=$PRONOSTICO"
