#!/usr/bin/env bash
# Despliega (o actualiza) la pila CDK del SAAD.
# Uso: infra/aws/scripts/desplegar.sh <etiqueta-imagen> [api_desired_count]
#   etiqueta-imagen: la que imprime publicar_imagen.sh (SHA corto del commit)
# Tamaño de la tarea (opcional): SAAD_API_CPU=4096 SAAD_API_MEMORY=8192 desplegar.sh <etiqueta>
# Pronóstico guardado aunque no esté vigente (opcional): SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1 desplegar.sh <etiqueta>
set -euo pipefail

TAG="${1:?Indica la etiqueta de la imagen (salida de publicar_imagen.sh)}"
DESEADAS="${2:-1}"
source "$(dirname "${BASH_SOURCE[0]}")/_entorno.sh"   # RAIZ, REGION e infra/aws/.env

PREFIX_LIST="$(aws ec2 describe-managed-prefix-lists --region "$REGION" \
  --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
  --query 'PrefixLists[0].PrefixListId' --output text)"

# El encabezado secreto CloudFront → ALB se genera una vez y se guarda en infra/aws/.env.
if [[ -z "${SAAD_ORIGIN_SECRET:-}" ]]; then
  SAAD_ORIGIN_SECRET="$(openssl rand -hex 24)"
  touch "$ENV_AWS" && chmod 600 "$ENV_AWS"
  printf '\nSAAD_ORIGIN_SECRET=%s\n' "$SAAD_ORIGIN_SECRET" >> "$ENV_AWS"
fi

(cd "$RAIZ/frontend" && npm ci && npm run build)

cd "$RAIZ/infra/aws/cdk"
if [[ ! -x .venv/bin/python ]]; then
  echo "Falta el venv de CDK: python3 -m venv infra/aws/cdk/.venv && infra/aws/cdk/.venv/bin/pip install -r infra/aws/cdk/requirements.txt" >&2
  exit 1
fi
export PATH="$PWD/.venv/bin:$PATH"   # cdk.json ejecuta "python3 app.py" con este venv
export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
npx --yes aws-cdk@2 deploy Saad --require-approval never \
  -c api_tag="$TAG" \
  -c api_desired_count="$DESEADAS" \
  -c api_cpu="${SAAD_API_CPU:-512}" \
  -c api_memory="${SAAD_API_MEMORY:-2048}" \
  -c api_pronostico_desactualizado="${SAAD_USAR_PRONOSTICO_DESACTUALIZADO:-0}" \
  -c cloudfront_prefix_list="$PREFIX_LIST" \
  -c origin_secret="$SAAD_ORIGIN_SECRET"
