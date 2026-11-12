# Configuración común de los scripts de despliegue. Se incluye con `source`, no se ejecuta.
# Lee infra/aws/.env (fuera de Git) sin pisar variables ya definidas en la terminal.
RAIZ="$(git rev-parse --show-toplevel)"
ENV_AWS="$RAIZ/infra/aws/.env"
if [[ -f "$ENV_AWS" ]]; then
  while IFS='=' read -r clave valor || [[ -n "$clave" ]]; do
    [[ "$clave" =~ ^[A-Z_][A-Z0-9_]*$ ]] || continue   # ignora comentarios y líneas vacías
    if [[ -z "${!clave:-}" && -n "$valor" ]]; then export "$clave=$valor"; fi
  done < "$ENV_AWS"
fi
REGION="${AWS_REGION:-us-east-1}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"   # el perfil puede no tener región
