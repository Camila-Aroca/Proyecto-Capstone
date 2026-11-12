#!/usr/bin/env bash
# Sube a S3 los outputs que lee la API y reinicia el servicio para que los cargue.
# El pipeline se ejecuta en el equipo; este script solo publica su resultado.
# Uso: infra/aws/scripts/subir_datos.sh [--sin-reinicio]
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"   # el perfil puede no tener región
PILA="${SAAD_STACK:-Saad}"
RAIZ="$(git rev-parse --show-toplevel)"
cd "$RAIZ"

salida() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$PILA" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
BUCKET="$(salida BucketDatos)"

# Lo que la API necesita: outputs procesados, reportes del modelo y el cuadro INE de población.
for ruta in data/processed reports data/raw/poblacion; do
  [[ -d "$ruta" ]] || { echo "Falta $ruta: ejecuta el pipeline antes de subir." >&2; exit 1; }
done

# Sin --delete: un archivo borrado en local sigue en S3 hasta que se elimine a mano.
aws s3 sync data/processed/   "s3://$BUCKET/data/processed/"   --region "$REGION" --exclude "*.tmp"
aws s3 sync reports/          "s3://$BUCKET/reports/"          --region "$REGION" --exclude "*.tmp"
aws s3 sync data/raw/poblacion/ "s3://$BUCKET/data/raw/poblacion/" --region "$REGION"
echo "Datos publicados en s3://$BUCKET desde el commit $(git rev-parse --short HEAD)."

if [[ "${1:-}" != "--sin-reinicio" ]]; then
  aws ecs update-service --region "$REGION" --cluster "$(salida Cluster)" \
    --service "$(salida Servicio)" --force-new-deployment >/dev/null
  echo "Nuevo despliegue de la API solicitado: cargará los datos al arrancar."
fi
