# Guía de Seguridad y Auditoría para Salida a Producción - ParkLink

Este documento resume el análisis de seguridad exhaustivo de la arquitectura de microservicios de **ParkLink** (Gateway, Auth, Parking, Booking, Payment, Notifications y Mobile), identificando fortalezas, vulnerabilidades críticas para salida al mercado, medidas ya aplicadas y una **guía completa de opciones avanzadas para fortalecer al máximo la seguridad bajo el principio de Defense in Depth (Seguridad en Profundidad)**.

---

## 1. Diagnóstico del Estado Actual de Seguridad

### Lo que está bien resuelto (Fortalezas)
1. **Contraseñas y Tokens:** PBKDF2-SHA256 con passlib, hashing SHA-256 de refresh tokens y códigos OTP en base de datos.
2. **Gateway Centralizado:** Punto de entrada único que valida JWTs y propaga el `x-user-id` a los microservicios downstream.
3. **Manejo de Tiempos Criptográficos:** Uso de `timingSafeEqual` en verificación de claves internas (`INTERNAL_SERVICE_KEY`) y webhooks de pago.
4. **Almacenamiento Seguro Móvil:** Uso de `expo-secure-store` en la app móvil para tokens de sesión.
5. **Rate Limiting OTP:** Cooldown de 60 segundos entre reenvíos de códigos de verificación.

---

## 2. Medidas de Seguridad Ya Implementadas en el Repositorio

- [x] **Sanitización de Headers en Gateway:** `gateway/app/proxy.py` elimina `x-user-id` y `x-internal-key` de cualquier petición entrante externa para prevenir suplantación de identidad (spoofing).
- [x] **Security Headers HTTP (OWASP):** Inyección automática de `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy` y `Permissions-Policy` en `gateway/app/middleware.py`.
- [x] **Rate Limiting en Gateway:** `RateLimitMiddleware` con ventana deslizante por IP con cupos reducidos en `/auth/login`, `/auth/register`, OTPs y `/payments/create-preference`.
- [x] **Validación Fail-Fast en Producción:** `gateway`, `auth-service` y `payment-service` bloquean el inicio en `ENVIRONMENT=production` si las claves son menores a 32 caracteres o contienen valores por defecto inseguros.

---

## 3. Opciones para Fortalecer la Seguridad al Máximo (Defense in Depth / Zero Trust)

A continuación se detallan las opciones y patrones técnicos recomendados ordenados por capa arquitectónica para llevar el sistema a un estándar de grado bancario / fintech:

### Capa 1: Autenticación y Criptografía Asimétrica (Zero Trust Keys)
1. **Migración a JWT Asimétrico (RS256 / ES256 / EdDSA):**
   - **Esquema:** `auth-service` custodia una **clave privada (RSA/ECDSA)** y es el único componente capaz de firmar tokens.
   - **Verificación:** El Gateway, `payment-service` y cualquier microservicio downstream consumen exclusivamente la **clave pública** (o un endpoint estándar JWKS `/.well-known/jwks.json`).
   - **Beneficio:** Si un atacante compromete el Gateway o un microservicio interno, **jamás podrá forjar ni firmar tokens falsos**.
2. **Firmado de Peticiones Internas (Gateway Signature Token / HMAC):**
   - El Gateway, además de propagar `x-user-id`, firma una cabecera interna `X-Gateway-Signature` o un JWT interno de corta duración (TTL de 30 segundos) con `aud: [microservicio]` y `sub: [user_id]`.
   - Cada microservicio valida esta firma antes de procesar la solicitud, garantizando que nadie dentro de la red interna pueda saltarse al Gateway.

---

### Capa 2: Aislamiento de Red y Cifrado Este-Oeste (Network Layer)
1. **Redes Privadas / VPC Seguras:**
   - Cerrar el 100% de los puertos externos de las bases de datos (Postgres `5432-5436`), RabbitMQ (`5672`, `15672`) y microservicios downstream (`3001`, `8000`, `8004`, `8082`, `8085`).
   - El único contenedor/servicio con puerto público es el Gateway (`8080` / `443`).
2. **mTLS (Mutual TLS) entre Microservicios:**
   - En infraestructuras como Kubernetes o Docker Swarm con Service Mesh (Linkerd / Istio) o Envoy proxy, el tráfico interno va cifrado y autenticado con certificados x509 mutuos.
3. **Restricción Estricta de CORS:**
   - En producción, configurar `CORS_ORIGINS` para aceptar únicamente el dominio exacto del dashboard de administración (ej: `https://admin.parklink.com.ar`) y denegar comodines `*`.

---

### Capa 3: Control de Acceso y Autorización a Nivel de Objeto (BOLA / IDOR Defense)
1. **Validación de Propiedad en Cada Operación:**
   - Nunca confiar en que el ID del objeto en la URL pertenece al solicitante. En cada `UPDATE`, `DELETE` o `GET` sensible:
     - `parking-service`: Comprobar `WHERE id = :spot_id AND owner_id = :caller_user_id`.
     - `booking-service`: Comprobar que el usuario sea el inquilino (`user_id`) o el propietario de la cochera (`spot.owner_id`).
     - `payment-service`: Impedir que un usuario consulte transacciones ajenas por `external_reference` si no es el pagador o el dueño de la reserva.
2. **Modelado de Roles y Permisos (RBAC):**
   - Incorporar en el JWT y en la base de datos de Auth roles explícitos (`role: user | owner | admin | auditor`) para que los endpoints administrativos verifiquen permisos a nivel de decorador/middleware en cada microservicio.

---

### Capa 4: Revocación de Sesiones y Cache Distribuido
1. **Invalidación Instantánea con Redis (Token Blacklist / Versioning):**
   - Actualmente los Access Tokens duran 15 minutos sin consultar base de datos.
   - **Opción A (Token Versioning):** Agregar un `token_version` al payload del JWT y mantener un contador en Redis por usuario. Si el usuario hace logout, cambia contraseña o es bloqueado, se incrementa su `token_version` y cualquier token anterior queda rechazado al instante.
   - **Opción B (Event-Driven Revocation):** Publicar eventos RabbitMQ `auth.session_revoked` consumidos por el Gateway para guardar el `jti` (JWT ID) en una lista negra en memoria/Redis durante el tiempo remanente del TTL.

---

### Capa 5: Seguridad en la App Móvil (Mobile App Hardening)
1. **SSL/TLS Certificate Pinning:**
   - En la app Expo/React Native, fijar las huellas SHA-256 de los certificados SSL del Gateway para prevenir ataques de intermediario (Man-in-the-Middle) en redes Wi-Fi públicas no seguras.
2. **Detección de Root/Jailbreak y Entorno Emulado:**
   - Utilizar librerías como `react-native-device-info` o `expo-crypto` / SafetyNet / Play Integrity para alertar o restringir pagos en dispositivos rooteados o adulterados.
3. **Biometría para Operaciones Críticas:**
   - Exigir `expo-local-authentication` (FaceID / Fingerprint) antes de autorizar pagos o modificar contraseñas y teléfonos.

---

### Capa 6: Perímetro, WAF y Monitoreo (Edge & Observability)
1. **Cloudflare WAF + Bot Management + DDoS Shield:**
   - Colocar Cloudflare frente al dominio del Gateway para mitigar ataques volumetricos L3/L4/L7, bloquear scrapers y forzar HTTPS con TLS 1.3.
2. **Sanitización de Logs y PII (Data Masking):**
   - Implementar filtros en loggers para enmascarar automáticamente tarjetas, contraseñas, tokens JWT, DNIs y teléfonos (`[REDACTED]`).
3. **Auditoría Continua de Vulnerabilidades en CI/CD:**
   - Integrar en GitHub Actions:
     - `pip-audit` / `safety` (Python)
     - `npm audit` / `snyk` (Node.js & Mobile)
     - `govulncheck` (Go / Booking Service)
     - `Trivy` (Escaneo de vulnerabilidades en imágenes Docker)

---

## 4. Matriz de Prioridad de Implementación

| Medida de Seguridad | Nivel de Complejidad | Impacto en Seguridad | Recomendado para |
| :--- | :---: | :---: | :--- |
| **Aislamiento de puertos en Cloud/VPC** | Bajo | 🔴 Crítico | Día 1 de Despliegue |
| **Secrets Reales en Gestor (Vault/Render)** | Bajo | 🔴 Crítico | Día 1 de Despliegue |
| **Validación de Firma HMAC en Webhooks MP** | Bajo | 🔴 Crítico | Inmediato |
| **JWT Asimétrico (RS256 / ES256)** | Medio | 🟠 Alto | Fase 1 Pre-Lanzamiento |
| **Cloudflare WAF + SSL Pinning en App** | Medio | 🟠 Alto | Lanzamiento en Stores |
| **Revocación Instantánea de Sesiones (Redis)** | Medio | 🟡 Medio | Post-Lanzamiento |
| **mTLS / Service Mesh Interno** | Alto | 🟡 Medio | Escalamiento / Kubernetes |

---

## 5. Checklist para Salida al Mercado

- [x] Sanitización de headers anti-spoofing en Gateway.
- [x] Security headers HTTP configurados en Gateway.
- [x] Rate limiting en rutas sensibles implementado.
- [x] Bloqueo fail-fast en modo producción para claves inseguras.
- [ ] Aislamiento de red: solo el Gateway expone puertos hacia Internet.
- [ ] Generación de secretos criptográficos aleatorios (mínimo 32 bytes).
- [ ] Credenciales de producción de Mercado Pago configuradas con firma de webhooks obligatoria.
- [ ] Cloudflare configurado con terminación SSL y WAF activo.
- [ ] Auditoría de dependencias y escaneo de imágenes Docker en CI/CD.
