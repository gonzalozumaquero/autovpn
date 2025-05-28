# AutoVPN Platform

**AutoVPN** es una plataforma automatizada para la creación y gestión de redes privadas virtuales (VPNs) personales, orientada a usuarios sin conocimientos técnicos avanzados. Su objetivo es democratizar el acceso a comunicaciones privadas y seguras mediante el despliegue rápido y sencillo de servidores VPN autogestionados.

## 🚀 Características principales

- 🐳 Despliegue automatizado con Docker y Ansible.
- 🔐 Soporte para WireGuard, con futura integración de OpenVPN y SoftEther.
- 🌐 Interfaz web intuitiva para crear y descargar configuraciones de cliente.
- 📡 Servidor intermedio en la nube que actúa como puente seguro hacia redes domésticas.
- 🔒 Seguridad por diseño: autenticación 2FA, cifrado extremo a extremo y firewall integrado.
- 📚 Compatible con Windows, macOS, Linux, Android y iOS.

## 📁 Estructura del proyecto

El proyecto está organizado tal y como se describe a continuación:
autovpn-platform/
autovpn-platform/
├── backend/        # API REST en FastAPI para gestionar peers y el estado del servidor
├── frontend/       # Interfaz web desarrollada con React para usuarios finales
├── docker/         # Dockerfiles y configuraciones docker-compose para WireGuard y servicios relacionados
├── ansible/        # Scripts de automatización con Ansible para desplegar AutoVPN en la nube
├── scripts/        # Scripts utilitarios (crear peer, generar QR, limpieza, etc.)
├── config/         # Archivos de entorno de ejemplo y configuración compartida
├── docs/           # Documentación sobre arquitectura, seguridad y casos de uso
├── .gitignore      # Archivos y carpetas excluidos del control de versiones
├── README.md       # Descripción general del proyecto e instrucciones de uso
├── LICENSE         # Licencia del proyecto

## 📦 Casos de uso

- Acceso remoto a una Raspberry Pi, NAS o servicios en red local.
- Teletrabajo seguro sin depender de proveedores comerciales.
- Evitación de censura mediante técnicas anti-DPI.
- Laboratorios de ciberseguridad autogestionados.
- Escenarios DevOps con túneles entre entornos de desarrollo y producción.

## 📚 Tecnologías utilizadas

- Docker & Docker Compose
- WireGuard
- Ansible (automatización)
- FastAPI (backend)
- React (frontend)
- TLS / 2FA / UFW (seguridad)

## 🛠️ Estado del proyecto

Proyecto en desarrollo como parte del Trabajo de Fin de Máster en Ciberseguridad (Universidad Europea, curso 2024-2025). Actualmente en fase de validación de arquitectura y pruebas funcionales con WireGuard.

## 📄 Licencia

Este proyecto es de código abierto bajo la licencia MIT.
