# Implementación de Tipos de Cuenta (Conductor / Propietario / Ambos)

## Contexto del sistema

La app actualmente tiene un único stack de navegación `(driver)` que mezcla funcionalidad de conductor y propietario. No existe distinción de "tipo de cuenta" ni en el backend (`auth-service`) ni en el frontend (`mobile`). El objetivo es:

- Agregar un paso **"¿Cómo vas a usar la app?"** al final del flujo de registro.
- Persistir la preferencia del usuario como `account_type` en el backend.
- Mostrar **3 interfaces de navegación distintas** (tabs diferentes) según el tipo.
- Permitir cambiar el tipo de cuenta en cualquier momento desde el **perfil**.

---

## Tipos de cuenta

| Valor | Icono | Descripción visible |
|-------|-------|---------------------|
| `driver` | 🚗 | **Solo Conductor** — busca y reserva cocheras |
| `owner` | 🏠 | **Solo Propietario** — publica y gestiona cocheras |
| `both` | ✨ | **Conductor y Propietario** — hace las dos cosas |

---

## TODO List de Implementación

### 1. Backend — `auth-service`

- [ ] **Agregar columna `account_type` al modelo `User`**
  - Archivo: `auth-service/app/models/user.py`
  - Crear `enum AccountType` con valores `DRIVER`, `OWNER`, `BOTH`
  - Agregar `account_type = Column(Enum(...), default=AccountType.DRIVER, nullable=False)`

- [ ] **Agregar campo `account_type` a los schemas Pydantic**
  - Archivo: `auth-service/app/schemas/schemas.py`
  - `UserCreate`: agregar `account_type: AccountType = AccountType.DRIVER` (opcional con default)
  - `UserOut`: exponer `account_type` en la respuesta
  - `UserUpdate`: agregar `account_type: Optional[AccountType] = None` para permitir cambiarlo desde el perfil

- [ ] **Generar y aplicar migración de base de datos (Alembic)**
  - Crear nueva revisión: `alembic revision --autogenerate -m "add_account_type_to_users"`
  - Revisar el script generado y asegurar que el `server_default` sea `'DRIVER'`
  - Aplicar: `alembic upgrade head`

- [ ] **Verificar que el endpoint `PATCH /users/{id}` acepta `account_type`**
  - Archivo: `auth-service/app/services/` (servicio de usuarios)
  - El campo ya debería persistirse con el `UserUpdate` extendido; confirmar que el handler lo propague al ORM

---

### 2. Mobile — Tipos y Store

- [ ] **Actualizar el tipo `AuthUser` en `mobile/src/types/index.ts`**
  - Agregar `accountType: 'driver' | 'owner' | 'both'`
  - Esto alinea el tipo frontend con el nuevo campo del backend

- [ ] **Crear store `useAccountTypeStore.ts` en `mobile/src/store/`**
  - Persistir en `AsyncStorage` la selección con `zustand/persist`
  - Estado: `accountType: 'driver' | 'owner' | 'both'`
  - Acción: `setAccountType(t)` — también llama a `PATCH /users/{id}` para sincronizar con el backend
  - Al hacer `setSession` en `useSessionStore`, inicializar este store con el valor que viene del backend (`user.accountType`)

- [ ] **Actualizar `useSessionStore` (`mobile/src/store/useSessionStore.ts`)**
  - Cuando `setSession` recibe un `AuthUser` con `accountType`, llamar a `useAccountTypeStore.getState().setAccountType(...)` para sincronizar ambos stores

---

### 3. Mobile — Pantalla de selección de tipo de cuenta (registro)

- [ ] **Crear `mobile/app/(auth)/account-type.tsx`**
  - Pantalla nueva que aparece **después** del paso `personal` del wizard de registro
  - UI: 3 tarjetas grandes, una por tipo, con ícono grande + título + descripción corta de 1 línea
  - Al tocar una tarjeta se marca con borde coloreado (feedback visual inmediato)
  - Botón "Continuar" habilitado solo cuando hay una selección activa
  - Al confirmar: llama a `PATCH /users/{id}` con `{ account_type: selección }` y navega al tab correcto

- [ ] **Agregar el paso `account-type` al flujo de registro en `mobile/app/(auth)/register.tsx`**
  - Agregar `'account-type'` al tipo `Step` y al arreglo `STEP_ORDER`
  - En `handleFinishRegistration`: después de crear la cuenta y el login, redirigir a `/(auth)/account-type` en vez de directamente al tab

- [ ] **Registrar la nueva pantalla en el layout de auth `mobile/app/(auth)/_layout.tsx`**
  - Agregar `<Stack.Screen name="account-type" options={{ headerShown: false }} />`

---

### 4. Mobile — Tres stacks de navegación separados

- [ ] **Crear grupo `mobile/app/(owner)/`** con su propio `_layout.tsx` y `(tabs)/`
  - Tabs del propietario: **Inicio** (resumen), **Mis Cocheras**, **Reservas**, **Perfil**
  - Reusar las pantallas existentes de `(driver)/spots/`, `(driver)/settlements/`, etc.

- [ ] **Crear grupo `mobile/app/(both)/`** con su propio `_layout.tsx` y `(tabs)/`
  - Tabs: **Buscar** (conductor), **Mis Reservas**, **Mis Cocheras**, **Perfil**
  - El tab de perfil en este modo muestra ambas secciones (mis reservas como conductor + mis cocheras como propietario)

- [ ] **Renombrar/clarificar el grupo existente `mobile/app/(driver)/`**
  - Reducir sus tabs a solo lo relevante para conductores: **Buscar**, **Favoritos**, **Mis Reservas**, **Notificaciones**, **Perfil**
  - Quitar del perfil del modo conductor la sección "Mis Cocheras" y "Liquidaciones" (esas son para propietario)

- [ ] **Actualizar `mobile/app/_layout.tsx`**
  - Registrar `<Stack.Screen name="(owner)" />` y `<Stack.Screen name="(both)" />`

---

### 5. Mobile — Redirección inteligente post-login

- [ ] **Actualizar `mobile/app/index.tsx`**
  - Leer `accountType` desde el store (o desde `user.accountType`)
  - Redirigir a `/(driver)/(tabs)`, `/(owner)/(tabs)` o `/(both)/(tabs)` según corresponda
  - Ejemplo:
    ```ts
    if (accountType === 'owner') return <Redirect href="/(owner)/(tabs)" />;
    if (accountType === 'both')  return <Redirect href="/(both)/(tabs)" />;
    return <Redirect href="/(driver)/(tabs)" />;
    ```

---

### 6. Mobile — Cambio de tipo de cuenta desde el Perfil

- [ ] **Crear componente `AccountTypePicker.tsx` en `mobile/src/components/`**
  - Modal o sección inline con las 3 opciones (mismas tarjetas que en el registro)
  - Muestra cuál está activa actualmente con un check
  - Al seleccionar uno distinto: llama a `setAccountType(nuevo)`, que persiste y navega al nuevo stack

- [ ] **Integrar `AccountTypePicker` en las pantallas de perfil de los 3 modos**
  - `mobile/app/(driver)/(tabs)/profile.tsx`
  - `mobile/app/(owner)/(tabs)/profile.tsx`
  - `mobile/app/(both)/(tabs)/profile.tsx`
  - Agregar una fila en la sección "Preferencias" con label "Tipo de cuenta" → abre el picker

- [ ] **Navegar al stack correcto después de cambiar el tipo**
  - Después de `setAccountType`, usar `router.replace` al nuevo tab root
  - Ejemplo: si estaba en `/(driver)` y elige `owner`, hacer `router.replace('/(owner)/(tabs)')`

---

### 7. Mobile — Internacionalización (i18n)

- [ ] **Agregar claves en `mobile/src/i18n/es/castellano.json`**
  ```json
  "accountType.title": "¿Cómo vas a usar la app?",
  "accountType.subtitle": "Podés cambiarlo cuando quieras desde tu perfil",
  "accountType.driver.title": "Solo Conductor",
  "accountType.driver.description": "Buscá y reservá cocheras cerca tuyo",
  "accountType.owner.title": "Solo Propietario",
  "accountType.owner.description": "Publicá y gestioná tus cocheras",
  "accountType.both.title": "Conductor y Propietario",
  "accountType.both.description": "Hacé las dos cosas desde un solo lugar",
  "accountType.continue": "Continuar",
  "accountType.change": "Tipo de cuenta",
  "tabs.owner.home": "Inicio",
  "tabs.owner.spots": "Cocheras",
  "tabs.owner.bookings": "Reservas",
  "tabs.owner.profile": "Perfil",
  "tabs.both.search": "Buscar",
  "tabs.both.bookings": "Mis Reservas",
  "tabs.both.spots": "Mis Cocheras",
  "tabs.both.profile": "Perfil"
  ```

- [ ] **Replicar claves en `mobile/src/i18n/en/english.json`** (versión en inglés)

- [ ] **Replicar claves en `mobile/src/i18n/ja/` si existe** (versión en japonés)

---

### 8. Pruebas

- [ ] **Backend — tests unitarios**
  - Agregar test que `UserCreate` con `account_type=OWNER` persiste correctamente
  - Agregar test que `PATCH /users/{id}` actualiza `account_type` y devuelve el nuevo valor
  - Archivo destino: `auth-service/tests/`

- [ ] **Mobile — tests del store**
  - Agregar test de `useAccountTypeStore`: `setAccountType` actualiza el estado y persiste
  - Archivo destino: `mobile/src/store/__tests__/`

- [ ] **Mobile — smoke test del flujo de registro completo**
  - Verificar que al terminar el registro aparece la pantalla `account-type`
  - Verificar que tras elegir un tipo, la navegación aterriza en el tab correcto

---

### 9. Consideraciones de UX / Diseño

- [ ] **La pantalla `account-type.tsx` debe seguir el design system existente**
  - Usar `useThemeColors()` para colores y `useTypography()` para tipografía (como el resto de las pantallas)
  - Tarjetas: `borderRadius: 16`, borde coloreado con `colors.teal` cuando está seleccionada
  - Sin scrolling — las 3 tarjetas caben en pantalla sin necesidad de scroll

- [ ] **Accesibilidad**
  - Cada tarjeta debe tener `accessibilityRole="radio"` y `accessibilityState={{ checked: isSelected }}`
  - El botón "Continuar" debe tener `accessibilityHint` descriptivo

- [ ] **Evitar estado inconsistente**
  - Si el backend devuelve error en el `PATCH account_type`, mostrar un toast de error y no navegar
  - Si el usuario mata la app entre el registro y la selección del tipo, al relanzar detectar que `accountType` es `null` (o no está seteado) y redirigir de vuelta a `/(auth)/account-type`

---

## Diagrama de flujo simplificado

```
Registro (wizard existente)
    └─> Paso nuevo: "¿Cómo vas a usar la app?" (account-type.tsx)
            ├─ Solo Conductor  ──> /(driver)/(tabs)
            ├─ Solo Propietario ─> /(owner)/(tabs)
            └─ Ambos ───────────> /(both)/(tabs)

Login (existente)
    └─> index.tsx lee accountType del user
            ├─ driver  ──> /(driver)/(tabs)
            ├─ owner   ──> /(owner)/(tabs)
            └─ both    ──> /(both)/(tabs)

Cambio desde Perfil (AccountTypePicker)
    └─> PATCH /users/{id} { account_type }
    └─> router.replace al nuevo stack
```

---

## Orden de ejecución recomendado

1. Backend: modelo + schema + migración + endpoint (pasos 1)
2. Mobile types + stores (pasos 2)
3. Pantalla `account-type.tsx` + ajuste al wizard (pasos 3)
4. Stacks `(owner)` y `(both)` (pasos 4)
5. Redirección en `index.tsx` (paso 5)
6. `AccountTypePicker` en perfiles (paso 6)
7. i18n (paso 7)
8. Tests (paso 8)
9. Revisión de UX / accesibilidad (paso 9)
