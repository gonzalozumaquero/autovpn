# AutoVPN Platform

**AutoVPN** es una plataforma para desplegar y gestionar servidores VPN personales de forma automatizada. Combina Ansible y Docker para ofrecer un flujo guiado en dos fases: instalación asistida desde tu equipo y posterior uso del panel web del servidor para crear clientes WireGuard (QR/.conf).

---

## Características

- Despliegue reproducible con **Ansible** (bootstrap del host y stack de contenedores).
- Servidor VPN **WireGuard** (plan para añadir OpenVPN/SoftEther).
- **Frontend** web para onboarding en 3 pasos (admin + 2FA → crear servidor → alta de cliente).
- **Instalación asistida**: backend y frontend locales que orquestan Ansible y muestran el progreso.
- Dos modos de TLS en el proxy:
  - **ACME/Let’s Encrypt** (con dominio).
  - **TLS interno** con **Caddy** (sin dominio, CA interna).
- Seguridad por defecto: UFW, SSH endurecido, JWT secreto, 2FA (TOTP), volúmenes persistentes.

---

## Arquitectura (resumen)

```
[Equipo del usuario]                         [EC2 Ubuntu 22.04]
installer-local/frontend  ----->  installer-local/backend
          |                                 |                     | (SSE/HTTP)                      |            \  ansible-playbook
          v                                 |                Progreso instalación                      +----> roles (common, docker, reverse_proxy, autovpn_stack)
                                                                                             +----> docker compose (caddy, backend, frontend, wireguard)
```

---

## Estructura del repositorio

```
autovpn/
├─ ansible/                    # Infra y app como código (un directorio, dos playbooks)
│  ├─ inventories/
│  │  ├─ cloud.ini.example
│  │  └─ local.ini.example
│  ├─ group_vars/
│  │  ├─ cloud.yml.example
│  │  └─ local.yml.example
│  ├─ roles/
│  │  ├─ common/              # UFW, SSH hardening, ip_forward, timezone
│  │  ├─ docker/              # Docker CE + compose plugin
│  │  ├─ reverse_proxy/       # Caddy + volúmenes + Caddyfile (interno/ACME)
│  │  ├─ autovpn_stack/       # Copia stack/, genera .env y docker compose up -d
│  │  └─ backup/              # (opcional) service/timer para S3/rclone
│  ├─ site-deploy.yml         # Bootstrap del host (common, docker)
│  └─ site-stack.yml          # Despliegue de la app (reverse_proxy, autovpn_stack, backup)
├─ deploy/                    # Instalación asistida (local)
│  ├─ api/                    # FastAPI: genera inventario y vars, lanza Ansible, expone logs
│  └─ frontend/               # UI local para pedir IP/PEM y pulsar “Instalar”
├─ stack/                     # Artefactos de la app desplegados en /opt/autovpn del servidor
│  ├─ docker-compose.yml
│  └─ reverse-proxy/
│     ├─ Caddyfile            # dominio + ACME
│     └─ Caddyfile.internal   # :443 + tls internal
└─ README.md
```

---

## Flujo de instalación (asistida)

**Fase 1 – Instalación asistida desde tu equipo**
1. Levanta el installer-local:
   - `deploy/api`: expone endpoints para:
     - Generar `ansible/inventories/cloud.ini` desde `cloud.ini.example` y rellenar IP + ruta al `.pem`.
     - Escribir `ansible/group_vars/cloud.yml` desde `cloud.yml.example` (sustituye `wg_public_host`, puertos, `jwt_secret`, etc.).
     - Ejecutar `ansible/site-deploy.yml` y luego `ansible/site-stack.yml`, emitiendo logs (SSE/WebSocket).
   - `deploy/frontend`: formulario para Elastic IP, usuario SSH (ubuntu), PEM y parámetros (TLS interno, WG_*…); botón **Instalar** y visor de progreso.
2. Al finalizar, el backend devuelve la URL del panel remoto (`https://<IP-o-dominio>/`).
3. Si usas **TLS interno**, exporta la CA del servidor:
   - En la EC2: `/opt/autovpn/caddy_data/pki/authorities/local/root.crt`.
   - Instálala como CA de confianza en tus dispositivos para evitar avisos.

**Fase 2 – Onboarding en el servidor**
1. Accede al frontend del servidor.
2. Alta de admin + 2FA/TOTP.
3. Crear servidor WireGuard (wg0) y añadir cliente.
4. Descarga `.conf` o escanea QR; conecta desde la app WireGuard.

---

## Requisitos

- Máquina de control (tu equipo) con:
  - Python 3.10+, Ansible ≥ 9, Docker (si pruebas local).
  - Clave SSH `.pem` con permisos `600`.
- AWS EC2 Ubuntu 22.04, Security Group con **22/tcp**, **443/tcp**, **51820/udp** (y **80/tcp** solo si usas ACME).
- (Opcional) Dominio apuntando a la Elastic IP (si usas ACME).

---

## Configuración

1. Copia los ejemplos y complétalos:
   ```bash
   cp ansible/inventories/cloud.ini.example ansible/inventories/cloud.ini
   cp ansible/group_vars/cloud.yml.example ansible/group_vars/cloud.yml
   ```
   - Sustituye `ELASTIC_IP` y la ruta del `.pem` en `cloud.ini`.
   - En `cloud.yml` define:
     - `use_internal_tls: true|false`
     - `wg_public_host: "<Elastic_IP|dominio>"`
     - `wg_port`, `wg_subnet`, `wg_dns`, `jwt_secret`, `timezone`, `s3_bucket`

2. (Opcional) Cifra `cloud.yml` con Ansible Vault:
   ```bash
   ansible-vault encrypt ansible/group_vars/cloud.yml
   # y ejecuta con --ask-vault-pass o --vault-password-file
   ```

---

## Ejecución manual (sin instalador)

Bootstrap del host
```bash
ansible-playbook -i ansible/inventories/cloud.ini ansible/site-deploy.yml --ask-vault-pass
```

Despliegue del stack
```bash
ansible-playbook -i ansible/inventories/cloud.ini ansible/site-stack.yml --ask-vault-pass
```

Verificación en la EC2
```bash
ssh -i ~/.ssh/clave.pem ubuntu@ELASTIC_IP   "ss -lntup | egrep ':(22|80|443|51820)';    docker ps --format 'table {{.Names}}	{{.Status}}	{{.Ports}}'"
```

---

## Detalles técnicos

- reverse_proxy: copia Caddyfile según `use_internal_tls`:
  - `Caddyfile` (ACME): requiere `domain` y `email_tls`.
  - `Caddyfile.internal`: escucha en `:443` y usa `tls internal` (CA propia de Caddy).
- autovpn_stack:
  - Copia `stack/docker-compose.yml` y `.env.example` a `/opt/autovpn`.
  - Inyecta variables (`WG_HOST`, `WG_PORT`, `WG_SUBNET`, `WG_DNS`, `JWT_SECRET`, `TZ`, `TOTP_ISSUER`).
  - Ejecuta `docker compose up -d` para caddy, backend, frontend, wireguard.
- backup (opcional): instala rclone/awscli, script y systemd timer para sincronizar `/opt/autovpn/{data,wireguard,reverse-proxy}` y ficheros clave.

---

## Notas de seguridad

- .gitignore ignora inventarios y variables reales; versiona solo los `.example`. No subas claves `.pem`.
- Usa Vault para secretos o `encrypt_string` para cifrar campos individuales.
- Limita 22/tcp en SG a tu IP. Con TLS interno, cierra 80/tcp tras el despliegue.
- Minimiza capacidades del contenedor de WireGuard:
  - `NET_ADMIN` es suficiente si el módulo está en el host (`modprobe wireguard`); evita `SYS_MODULE`.
- Si los peers deben salir a Internet vía el servidor, añade NAT/MASQUERADE persistente.

---

## Roadmap

- Integración OpenVPN/SoftEther opcional.
- Healthchecks y métricas básicas en la UI (peers activos, última conexión).
- Instalación self-hosted desde el propio servidor (sin máquina de control).
- Rotación de claves y perfiles desde UI/cron.
- Pipeline CI/CD para imágenes y roles.

---

## Estado del proyecto

Proyecto de TFM (Universidad Europea, 2024–2025). Arquitectura validada; despliegue funcional con WireGuard y TLS interno/ACME.

---

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consultar `LICENSE`.

