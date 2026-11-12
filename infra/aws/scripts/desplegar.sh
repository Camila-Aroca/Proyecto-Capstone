#!/usr/bin/env bash
# Despliega (o actualiza) la pila CDK del SAAD.
# Uso: infra/aws/scripts/desplegar.sh <etiqueta-imagen> [api_desired_count]
#   etiqueta-imagen: la que imprime publicar_imagen.sh (SHA corto del commit)
# Tamaño de la tarea (opcional): SAAD_API_CPU=4096 SAAD_API_MEMORY=8192 desplegar.sh <etiqueta>
# Pronóstico guardado aunque no esté vigente (opcional): SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1 desplegar.sh <etiqueta>
set -euo pipefail

TAG="${1:?Indica la etiqueta de la imagen (salida de publicar_imagen.sh)}"
DESEADAS="${2:-1}"
REGION="${AWS_REGION:-us-east-1}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"   # el perfil puede no tener región
RAIZ="$(git rev-parse --show-toplevel)"
SECRETO_ARCHIVO="$RAIZ/infra/aws/cdk/.origin-secret"

PREFIX_LIST="$(aws ec2 describe-managed-prefix-lists --region "$REGION" \
  --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
  --query 'PrefixLists[0].PrefixListId' --output text)"

# El encabezado secreto CloudFront → ALB se genera una vez y se guarda fuera de Git.
if [[ ! -s "$SECRETO_ARCHIVO" ]]; then
  openssl rand -hex 24 > "$SECRETO_ARCHIVO"
  chmod 600 "$SECRETO_ARCHIVO"
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
  -c origin_secret="$(cat "$SECRETO_ARCHIVO")"
