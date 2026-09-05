# Guía de Seguridad y Auditoría para Salida a Producción - ParkLink

Este documento resume el análisis de seguridad exhaustivo de la arquitectura de microservicios de **ParkLink** (Gateway, Auth, Parking, Booking, Payment, Notifications y Mobile), identificando fortalezas, vulnerabilidades críticas para salida al mercado y un plan de acción detallado paso a paso.

---

## 1. Diagnóstico del Estado Actual de Seguridad

### Lo que está bien resuelto (Fortalezas)
1. **Contraseñas y Tokens:** PBKDF2-SHA256 con passlib, hashing SHA-256 de refresh tokens y códigos OTP en base de datos.
2. **Gateway Centralizado:** Punto de entrada único que valida JWTs y propaga el `x-user-id` a los microservicios downstream.
3. **Manejo de Tiempos Criptográficos:** Uso de `timingSafeEqual` en verificación de claves internas (`INTERNAL_SERVICE_KEY`).
4. **Almacenamiento Seguro Móvil:** Uso de `expo-secure-store` en la app móvil para tokens de sesión.
5. **Rate Limiting OTP:** Cooldown de 60 segundos entre reenvíos de códigos de verificación.

---

## 2. Vulnerabilidades Críticas para Salida al Mercado

### 🚨 1. Aislamiento de Red y Suplantación de Identidad (`x-user-id`)
* **Problema:** Microservicios como `parking-service`, `booking-service` y `notifications-service` confían ciegamente en el header HTTP `x-user-id`. En el `compose.yaml` y en servicios en la nube no aislados, si los puertos de estos microservicios (`3001`, `8080`, `8085`, `8004`) están expuestos a Internet, cualquier atacante puede llamar directo al servicio inyectando cualquier `x-user-id` arbitrario (ej: saltarse la autenticación, suplantar dueños de cocheras o clientes).
* **Solución:**
  - Cerrar todos los puertos de los microservicios hacia el exterior (solo exponer el puerto del Gateway `8080` / `443` y los webhooks públicos).
  - Usar una red privada interna (VPC / Docker network interna no expuesta).
  - Validar un secreto compartido de Gateway (`X-Gateway-Secret`) o implementar **mTLS** (Mutual TLS) entre el gateway y los microservicios.

---

### 🚨 2. Claves y Secretos (Keys & Secrets Management)
* **Problema:** 
  - `JWT_SECRET` simétrico compartido entre `auth-service`, `gateway` y `payment-service`. Si uno se ve comprometido, toda la infraestructura queda expuesta para forjar tokens válidos.
  - Valores por defecto débiles en código (`dev-secret-change-me`, `dev-internal-key-change-me`, credenciales de base de datos como `parklink_auth`/`parklink_auth`).
  - No hay rotación automática de llaves ni validación estricta de variables en startup en modo producción.
* **Solución:**
  - **Migrar a Asymmetric JWT (RS256 o EdDSA / ES256):** `auth-service` firma con clave privada; `gateway`, `payment-service` y otros solo verifican con la clave pública (JWKS).
  - Usar un gestor de secretos (HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager o Render Secret Files/Env Groups).
  - Bloquear el arranque en producción (`ENVIRONMENT=production`) si los secretos contienen substrings como `dev-`, `change-me`, `REEMPLAZAR` o tienen longitud menor a 32 caracteres.

---

### 🚨 3. Falta de Rate Limiting y Protección DDoS/Brute-Force en el Gateway
* **Problema:** El Gateway no tiene limitador de tasa de peticiones (Rate Limiting) global ni por IP/endpoint. Rutas como `/auth/login`, `/auth/register`, `/auth/password-reset/confirm` y `/payments/create-preference` están abiertas a ataques de fuerza bruta, credential stuffing y denegación de servicio (DoS).
* **Solución:**
  - Implementar middleware de Rate Limiting en el Gateway (usando Redis o memoria con ventana deslizante/token bucket).
  - Proteger `/auth/login` a máx. 5 intentos por minuto por IP/usuario.
  - Colocar Cloudflare (WAF + DDoS Protection + SSL Termination + Bot Management) delante del Gateway.

---

### 🚨 4. Configuración Permisiva de CORS
* **Problema:** El Gateway y `payment-service` tienen `CORS_ORIGINS=*` por defecto.
* **Solución:**
  - En producción, restringir los orígenes permitidos estrictamente al dominio de la web/dashboard de administración y cerrar CORS para clientes móviles nativos (o restringir headers).

---

### 🚨 5. Validación de Webhooks de Pago (Mercado Pago)
* **Problema:** La ruta `/payments/webhook` recibe notificaciones sin autenticación de usuario. Si las credenciales `MERCADOPAGO_WEBHOOK_SECRET` no se configuran adecuadamente o no se valida la firma HMAC del header `x-signature`, un atacante puede falsificar aprobaciones de pago.
* **Solución:**
  - Forzar la validación estricta de la firma HMAC de Mercado Pago en cada webhook antes de cambiar el estado de reservas o pagos.
  - Rechazar cualquier webhook con código 401/403 si la firma no coincide o si no hay secret configurada.

---

### 🚨 6. Autorización a Nivel de Objeto (BOLA / IDOR)
* **Problema:** En varios endpoints, si bien se valida que el usuario esté autenticado (`x-user-id`), se debe auditar que cada microservicio verifique la propiedad del recurso:
  - ¿Puede un usuario modificar o borrar una cochera que no le pertenece? (`parking-service`)
  - ¿Puede un usuario cancelar o ver reservas de otro? (`booking-service`)
  - ¿Puede un usuario consultar pagos ajenos pasando otro ID o external reference? (`payment-service`)
* **Solución:**
  - Garantizar pruebas automáticas de autorización IDOR en cada microservicio donde siempre se compare `resource.owner_id == caller_user_id`.

---

### 🚨 7. Revocación de Sesiones y Blacklist de Tokens
* **Problema:** El Gateway decodifica el JWT de forma estática (firma + expiración). Si un usuario cambia su contraseña, hace logout o su cuenta es suspendida/eliminada, su Access Token sigue siendo válido en el Gateway hasta que expire.
* **Solución:**
  - Mantener tiempos de expiración cortos para Access Token (ej: 5 a 15 minutos).
  - Para revocación instantánea: implementar un canal de invalidación en Redis compartido o evento RabbitMQ `user.session_revoked` que el Gateway consulte en memoria/cache.

---

### 🚨 8. Headers de Seguridad HTTP y OWASP Top 10
* **Problema:** El Gateway no inyecta headers de seguridad estándar (HSTS, Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy).
* **Solución:**
  - Agregar un middleware de Security Headers en el Gateway (`gateway/app/middleware.py`).

---

## 3. Checklist de Implementación para Salir al Mercado

- [ ] **Red:** Aislar la red interna: solo el Gateway expone puertos hacia Internet.
- [ ] **Secretos:** Generar contraseñas y secrets criptográficos aleatorios de alta entropía (mínimo 32 bytes en base64 / hex).
- [ ] **JWT:** Migrar a algoritmo asimétrico (RS256 / ES256) con clave privada exclusiva en `auth-service`.
- [ ] **WAF & Rate Limiting:** Añadir Cloudflare + rate limiting en el Gateway.
- [ ] **Webhooks:** Activar validación criptográfica de firmas HMAC en `payment-service`.
- [ ] **Logs y Auditoría:** Asegurar que ningún log contenga contraseñas, tokens JWT, números de tarjetas o datos personales (PII).
- [ ] **Validación de Entorno:** Fail-fast al arrancar en producción si faltan variables o si usan valores por defecto.
- [ ] **Auditoría de Dependencias:** Ejecutar `pip-audit` / `safety`, `npm audit` y `govulncheck` en CI/CD.
