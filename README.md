# AutoVPN Platform

**AutoVPN** es una plataforma para desplegar y gestionar servidores VPN personales de forma automatizada. Orquesta **Ansible** y **Docker** para ofrecer un flujo guiado en dos fases: instalación asistida desde tu equipo y posterior uso del panel web del servidor para crear clientes WireGuard (QR y `.conf`).

---

## Características

- **Despliegue reproducible** con Ansible: bootstrap del host y stack de contenedores.
- **WireGuard** como VPN principal. Diseño extensible para protocolos adicionales.
- **UI del servidor** para alta de administrador, 2FA TOTP, creación de peers y descarga de perfiles.
- **Instalación asistida**: UI+API locales que ejecutan Ansible y muestran logs en vivo.
- **TLS** en el proxy Caddy:
  - **ACME/Let’s Encrypt** cuando hay dominio público.
  - **TLS interno** con CA propia de **Caddy** cuando solo hay IP.
- Seguridad por defecto: UFW, SSH endurecido, secreto JWT, 2FA, volúmenes persistentes.

---

## Requisitos

- **Máquina de control** (tu equipo):
  - Python 3.10+, Ansible ≥ 9, Docker y Docker Compose.
  - Clave SSH `.pem` con permisos `600`.
- **Servidor destino** (p. ej., AWS EC2 Ubuntu 22.04/24.04):
  - Security Group / firewall con **22/tcp**, **443/tcp**, **51820/udp** abiertos.
  - **80/tcp** temporal si vas a usar ACME.
- (Opcional) **FQDN** apuntando a la IP pública si eliges ACME.

---

## Estructura principal del repositorio y contenido del proyecto

```
autovpn/                                 # Raíz del proyecto
├── ansible/                             # Playbooks, inventarios y roles para el despliegue con Ansible
│   ├── group_vars/                      # Variables de grupo (p.ej. cloud.yml) usadas por los playbooks
│   ├── inventories/                     # Inventarios de hosts
│   │   └── cloud/                       # Inventario/plantillas para el host “cloud” (EC2 u otro VPS)
│   └── roles/                           # Roles Ansible (tareas reutilizables)
│       ├── autovpn_stack/               # Copia/plantillas del stack, render de .env y ‘docker compose up’
│       ├── backup/                      # Tareas de backup (rclone/awscli, cron/timers, sincronización de volúmenes)
│       ├── common/                      # Endurecimiento base: UFW, SSH, sysctl, timezone, paquetes básicos
│       ├── docker/                      # Instalación y configuración de Docker Engine + plugin compose
│       └── reverse_proxy/               # Despliegue de Caddy y Caddyfile (interno/ACME), volúmenes y validaciones
├── deploy/                              # “Installer” local (fase 1): API + UI + composables para orquestar Ansible
│   ├── api/                             # Backend del instalador (p.ej. FastAPI)
│   │   ├── routers/                     # Endpoints: check-ssh, config, run, logs, download-cert, etc.
│   │   └── state/                       # Estado de ejecuciones (run_id, colas de logs, caché temporal)
│   ├── compose/                         # Archivos docker-compose para levantar el instalador local
│   │   ├── ansible/                     # Servicios/volúmenes específicos para la CLI de Ansible dentro del installer
│   │   ├── deploy/                      # Composes/ficheros asociados a la fase “deploy” (bootstrap del host)
│   │   └── stack/                       # Composes/ficheros asociados a la fase “stack” (contenedores del servidor)
│   └── frontend/                        # UI del instalador (React)
│       └── src/                         # Código fuente (App.jsx, componentes, estilos, utilidades)
└── stack/                               # Artefactos del stack remoto (fase 2): backend, proxy, etc.
    ├── backend/                         # Backend del servidor (API + lógica de panel)
    │   └── app/                         # Código de la aplicación (routers, modelos, servicios, requirements, etc.)
    └── reverse-proxy/                   # Configuración de Caddy para el servidor (Caddyfile / Caddyfile.internal)


```

---

## Instalación asistida con Docker

1) Clona y entra al repositorio:
```bash
git clone <URL_DEL_REPOSITORIO>
cd autovpn
```

2) Arranca el instalador local:
```bash
docker compose -f deploy/compose/docker-compose.yml up -d --build
```

3) Abre el **Installer UI** en tu navegador (p. ej. `http://localhost:5173`) y completa:
- IP del servidor, usuario SSH, credencial (password o `.pem`).
- Parámetros del stack: `use_internal_tls`, `wg_public_host`, `wg_port`, `wg_subnet`, `wg_dns`, `jwt_secret`, `timezone`, etc.
- **Probar SSH** → **Guardar configuración** → **Instalar**. Verás los logs en vivo.

4) Cuando termine, abre el panel remoto: `https://<IP-o-dominio>/`.

5) Si usas **TLS interno**, instala la CA del servidor para evitar avisos:
- Descarga desde el propio instalador si aparece el botón **Descargar certificado**; o bien:
```bash
scp ubuntu@<IP_SERVIDOR>:/opt/autovpn/caddy_data/caddy/pki/authorities/local/root.crt ./autovpn-root.crt
```
- Importa esa CA en tu sistema (Keychain en macOS, `update-ca-certificates` en Debian/Ubuntu, almacén de certificados en Windows).

---

## Ejecución manual (sin instalador)

1) Copia y ajusta inventario y variables:
```bash
cp ansible/inventories/cloud.ini.example ansible/inventories/cloud.ini
cp ansible/group_vars/cloud.yml.example ansible/group_vars/cloud.yml
```
Edita:
- `cloud.ini`: IP pública y ruta al `.pem`.
- `cloud.yml`: `use_internal_tls`, `wg_public_host`, `wg_port`, `wg_subnet`, `wg_dns`, `jwt_secret`, `timezone`, etc.

2) Bootstrap del host:
```bash
ansible-playbook -i ansible/inventories/cloud.ini ansible/site-deploy.yml
```

3) Despliegue del stack:
```bash
ansible-playbook -i ansible/inventories/cloud.ini ansible/site-stack.yml
```

4) Verificación rápida en el servidor:
```bash
ssh -i ~/.ssh/clave.pem ubuntu@<IP_SERVIDOR> \
  "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' ; ss -lntp | egrep ':(22|80|443|51820)'"
```

---

## Verificación de TLS interno

**Desde el servidor**:
```bash
CA=/opt/autovpn/caddy_data/caddy/pki/authorities/local/root.crt
curl -4ksS --fail --max-time 5 --http1.1 \
  --cacert "$CA" \
  https://localhost/health
# → ok
```

**Desde tu equipo** (tras copiar la CA):
```bash
# Copia de la CA
scp ubuntu@<IP_SERVIDOR>:/opt/autovpn/caddy_data/caddy/pki/authorities/local/root.crt ./autovpn-root.crt

# Sonda con SNI=localhost y resolución a la IP pública
curl -4sS --fail --max-time 5 --http1.1 \
  --resolve "localhost:443:<IP_SERVIDOR>" \
  --cacert ./autovpn-root.crt \
  https://localhost/health
# → ok
```

> Nota: con TLS interno, Caddy emite certificados para **localhost** y **127.0.0.1**. Para pruebas remotas con solo IP, fuerza `SNI=localhost` usando `--resolve`.

---

## Notas de seguridad

- No subas claves `.pem`, inventarios reales ni secretos al control de versiones. Versiona solo los `.example`.
- Usa **Ansible Vault** para cifrar `group_vars/cloud.yml` si contiene secretos.
- Restringe **22/tcp** en el Security Group a tu IP de administración.
- Si usas TLS interno, deshabilitar **80/tcp** tras el despliegue es recomendable.
- Minimiza capacidades del contenedor de WireGuard. Evita `SYS_MODULE` si no es imprescindible.

---

## Solución de problemas comunes

- **El instalador muestra 422 en `/install/config`**  
  Algún campo requerido no llega al API. Revisa en la UI que exista **una sola** credencial SSH (password o `.pem`) y que `admin_email` sea válido y contraseñas coincidan.

- **Caddy responde “TLS alert internal error” al probar `https://127.0.0.1/health`**  
  Usa `https://localhost/health` con la CA interna. Con una IP, el SNI no coincide y el handshake puede fallar; por eso en el cliente usamos `--resolve "localhost:443:<IP_SERVIDOR>"`.

- **Caddy no se levanta o no escucha 443**  
  Comprueba:
  ```bash
  docker compose logs caddy
  ss -lntp | grep ':443'
  ```
  Revisa el `Caddyfile` montado en `/opt/autovpn/reverse-proxy/Caddyfile` dentro del contenedor:
  ```bash
  docker compose exec -T caddy caddy adapt --config /etc/caddy/Caddyfile --pretty
  ```

- **UFW bloquea tráfico**  
  Verifica reglas:
  ```bash
  sudo ufw status numbered
  ```
  Deben estar permitidos `22/tcp`, `443/tcp` y `51820/udp`.

---

## Estado del proyecto

Proyecto de TFM (Universidad Europea, 2024–2025). Arquitectura validada; despliegue funcional con WireGuard y TLS interno/ACME.

---

## Contribuir

¡PRs y propuestas bienvenidas! Abre un issue para discusión y describe claramente el caso de uso, cambios y pruebas.

---

## Licencia

Distribuido bajo **MIT**. Consulta `LICENSE`.

