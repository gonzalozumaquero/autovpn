# AutoVPN Platform

**AutoVPN** es una plataforma automatizada para la creación y gestión de redes privadas virtuales (VPNs) personales, orientada a usuarios sin conocimientos técnicos avanzados. Su objetivo es democratizar el acceso a comunicaciones privadas y seguras mediante el despliegue rápido y sencillo de servidores VPN autogestionados.

## 🚀 Características principales

- 🐳 Despliegue automatizado con Docker y Ansible.
- 🔐 Soporte para WireGuard, con futura integración de OpenVPN y SoftEther.
- 🌐 Interfaz web intuitiva para crear y descargar configuraciones de cliente.
- 📡 Servidor intermedio en la nube que actúa como puente seguro hacia redes domésticas.
- 🔒 Seguridad por diseño: autenticación 2FA, cifrado extremo a extremo y firewall integrado.
- 📁 Compatible con Windows, macOS, Linux, Android y iOS.

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
