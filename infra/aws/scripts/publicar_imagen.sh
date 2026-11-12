#!/usr/bin/env bash
# Construye la imagen de la API y la publica en ECR con la etiqueta del commit actual.
# Uso: infra/aws/scripts/publicar_imagen.sh   (desde cualquier carpeta del repo)
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_entorno.sh"   # RAIZ, REGION e infra/aws/.env
REPO="${SAAD_ECR_REPO:-saad-api}"
cd "$RAIZ"

if [[ -n "$(git status --porcelain -- src scripts requirements.txt Dockerfile)" ]]; then
  echo "Hay cambios sin commit en src/, scripts/, requirements.txt o Dockerfile." >&2
  echo "La etiqueta no identificaría el código de la imagen. Haz commit primero." >&2
  exit 1
fi

TAG="$(git rev-parse --short HEAD)"
CUENTA="$(aws sts get-caller-identity --query Account --output text)"
REGISTRO="$CUENTA.dkr.ecr.$REGION.amazonaws.com"
IMAGEN="$REGISTRO/$REPO:$TAG"

if ! aws ecr describe-repositories --region "$REGION" --repository-names "$REPO" >/dev/null 2>&1; then
  echo "Creando repositorio ECR $REPO..."
  aws ecr create-repository --region "$REGION" --repository-name "$REPO" \
    --image-tag-mutability IMMUTABLE --image-scanning-configuration scanOnPush=true >/dev/null
  aws ecr put-lifecycle-policy --region "$REGION" --repository-name "$REPO" --lifecycle-policy-text \
    '{"rules":[{"rulePriority":1,"description":"Conservar las 5 imágenes más recientes","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":5},"action":{"type":"expire"}}]}' >/dev/null
fi

if aws ecr describe-images --region "$REGION" --repository-name "$REPO" --image-ids imageTag="$TAG" >/dev/null 2>&1; then
  echo "La imagen $REPO:$TAG ya existe en ECR; no se vuelve a publicar."
else
  aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRO"
  docker build --platform linux/amd64 --target api -t "$IMAGEN" .
  docker push "$IMAGEN"
fi

echo "Etiqueta para desplegar: $TAG"
