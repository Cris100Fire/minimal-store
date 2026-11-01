# MinimalStore

Tienda online minimalista desarrollada con **Python y Django**, orientada a la gestión de un catálogo de productos, un carrito de compras y el ciclo de vida de los pedidos.

El proyecto forma parte de mi formación en desarrollo Full Stack y busca aplicar buenas prácticas de desarrollo backend, organización por aplicaciones, validación de datos, control de inventario, autenticación y pruebas automatizadas.

## Características

- **Catálogo de productos:** listado, detalle y navegación por categorías.
- **Gestión de categorías y productos:** administración del catálogo y control de disponibilidad.
- **Autenticación de usuarios:** registro, inicio y cierre de sesión.
- **Carrito de compras:** gestión de los productos seleccionados y sus cantidades.
- **Checkout:** revisión del contenido del carrito y creación de pedidos.
- **Gestión de pedidos:** consulta de los pedidos del usuario y seguimiento de sus estados.
- **Control de inventario:** actualización de existencias al crear pedidos y recuperación del stock cuando se cancelan pedidos pendientes.
- **Administración:** gestión de los datos del sistema mediante Django Admin.
- **Pruebas automatizadas:** pruebas para verificar el comportamiento de las principales funcionalidades.

> **Nota:** el proyecto implementa un flujo de compra y gestión de pedidos; no incluye una pasarela de pago real.

## Tecnologías

| Tecnología            | Uso                                   |
| --------------------- | ------------------------------------- |
| Python                | Lenguaje principal                    |
| Django                | Framework backend                     |
| Django Templates      | Renderizado de páginas en el servidor |
| HTML y CSS            | Estructura y estilos de la interfaz   |
| JavaScript            | Interacciones del frontend            |
| MySQL                 | Base de datos                         |
| Django ORM            | Acceso y gestión de datos             |
| Django Authentication | Autenticación y gestión de usuarios   |
| Django Testing        | Pruebas automatizadas                 |
| Git                   | Control de versiones                  |

La aplicación utiliza una arquitectura tradicional de Django con vistas, modelos, formularios y plantillas. No utiliza React ni Django REST Framework en esta versión.

## Diseño de la interfaz

La interfaz sigue una dirección visual minimalista inspirada en los estilos Japandi, Wabi-Sabi y el diseño editorial suizo.

Principios del diseño:

- Jerarquía visual clara y composición ordenada.
- Paleta neutra con acentos terracota.
- Tipografía legible y consistente.
- Componentes reutilizables y estilos CSS organizados por áreas.
- Adaptación de la interfaz a distintos tamaños de pantalla.

## Estructura del proyecto

```text
mnimal-store/
├── apps/
│   ├── accounts/       # Autenticación y cuentas
│   ├── cart/           # Carrito de compras
│   ├── catalog/        # Productos y categorías
│   ├── core/           # Páginas generales
│   └── orders/         # Pedidos y checkout
├── config/             # Configuración principal de Django
├── static/             # CSS, JavaScript e imágenes
├── templates/          # Plantillas HTML compartidas
├── .env.example        # Plantilla de variables de entorno
├── .gitignore
├── manage.py
└── requirements.txt
```

## Requisitos previos

Antes de instalar el proyecto, necesitas:

- Python compatible con la versión de Django especificada en `requirements.txt`.
- MySQL instalado y en ejecución.
- `pip` para instalar las dependencias.
- Git para clonar o gestionar el repositorio.

## Instalación y configuración local

### 1. Clonar el repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd mnimal-store
```

Reemplaza `<URL_DEL_REPOSITORIO>` por la URL del repositorio cuando esté publicado.

### 2. Crear un entorno virtual

En Linux o WSL:

```bash
python -m venv .venv
source .venv/bin/activate
```

En Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Instalar las dependencias

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Crear la base de datos MySQL

Desde MySQL, crea una base de datos para el proyecto:

```sql
CREATE DATABASE minimalstore
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Utiliza un usuario de MySQL con permisos sobre esta base de datos y configura sus credenciales en el siguiente paso.

### 5. Configurar las variables de entorno

Copia `.env.example` a `.env`:

```bash
cp .env.example .env
```

En Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edita `.env` con tus propios valores:

```dotenv
DJANGO_ENV=development
DEBUG=True
SECRET_KEY=REEMPLAZAR_POR_UNA_CLAVE_SECRETA
ALLOWED_HOSTS=localhost,127.0.0.1,[::1]

DB_NAME=minimalstore
DB_USER=tu_usuario_mysql
DB_PASSWORD=tu_contraseña_mysql
DB_HOST=localhost
DB_PORT=3306

CSRF_TRUSTED_ORIGINS=
```

Genera una clave secreta para tu entorno local mediante:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copia el resultado en `SECRET_KEY`. No utilices una clave real compartida por otra persona ni publiques el archivo `.env`.

### 6. Aplicar las migraciones

```bash
python manage.py migrate
```

### 7. Crear un usuario administrador

```bash
python manage.py createsuperuser
```

Sigue las instrucciones para establecer las credenciales de acceso.

### 8. Importar productos de ejemplo (opcional)

El proyecto incluye un comando de gestión para importar categorías y productos desde DummyJSON.

```bash
python manage.py import_dummyjson
```

Este comando requiere conexión a Internet. Los datos importados sirven como contenido inicial de demostración; no representan un catálogo comercial real.

### 9. Ejecutar el servidor de desarrollo

```bash
python manage.py runserver
```

Abre [http://127.0.0.1:8000/](http://127.0.0.1:8000/) en el navegador.

## Pruebas automatizadas

Para ejecutar toda la suite de pruebas:

```bash
python manage.py test
```

Para comprobar la configuración general de Django:

```bash
python manage.py check
```

Para recopilar los archivos estáticos destinados al despliegue:

```bash
python manage.py collectstatic
```

Este último comando genera los archivos recopilados en la ubicación configurada mediante `STATIC_ROOT`. No es necesario ejecutarlo en cada sesión de desarrollo local.

## Seguridad y despliegue

La configuración local está separada de la configuración prevista para producción mediante variables de entorno.

Antes de desplegar la aplicación es necesario configurar correctamente, según el hosting elegido:

- `DEBUG=False`.
- `ALLOWED_HOSTS` con los dominios autorizados.
- `SECRET_KEY` segura y privada.
- HTTPS y los ajustes de cookies seguras.
- La base de datos de producción.
- La recopilación y el servicio de archivos estáticos.
- Las variables de entorno y los procesos de ejecución del servidor.

El archivo `.env` y las credenciales no deben subirse al repositorio.

## Estado del proyecto

Proyecto desarrollado localmente como parte de un proceso de aprendizaje de Django y desarrollo web.

La aplicación cuenta con funcionalidades de catálogo, carrito, pedidos y control de inventario, acompañadas de pruebas automatizadas.

La publicación del repositorio y el despliegue en un entorno de producción se realizarán por separado.

## Autor

Desarrollado como proyecto de formación en desarrollo Full Stack.
