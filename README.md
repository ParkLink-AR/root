# ParkLink AR - root

Este es el repositorio raiz de ParkLink. Contiene la configuración global para levantar el entorno local y agrupa todos los microservicios del sistema usando Git Submodules.

---

## Cómo empezar (Primer clonado)

Si es la primera vez que te bajás el proyecto, no uses el git clone común porque te van a quedar las carpetas de los servicios vacías. 

Tenés que clonar la raíz y descargar el código de los submódulos todo junto con este comando:

```bash
git clone --recurse-submodules git@github.com:ParkLink-AR/root.git
```

---

## Flujo de trabajo diario

Cada carpeta de un microservicio es un repositorio independiente metido adentro de este repo padre. 

### 1. Traer lo último que se subió
Antes de arrancar a programar, para bajarte los últimos cambios que subieron los chicos en todos los microservicios a la vez, parate en la raíz y tirá:

```bash
git submodule update --remote --merge
```

### 2. Modificar código en un servicio
Si tenés que tocar código de un servicio específico (por ejemplo, auth-service):
1. Entrás a la carpeta: `cd auth-service`
2. Te parás en la rama en la que estén laburando: `git checkout main`
3. Modificás el código y hacés el push **adentro de esa carpeta**:
   ```bash
   git add .
   git commit -m "fix: Arreglo el error de signup."
   git push
   ```

### 3. Actualizar el puntero en la raíz (Clave)
Como actualizaste el microservicio, ese repo avanzó a un nuevo commit. Tenés que avisarle al repo root que use esta nueva versión. Volvés a la raíz y tirás:

```bash
cd ..
git add auth-service
git commit -m "Actualiza puntero de auth-service"
git push main
```
---

## Despliegue Local con Docker

Una vez que tengas todo el código en las carpetas, levantás todo el ecosistema de ParkLink corriendo en la raíz:

```bash
docker-compose up --build
```
