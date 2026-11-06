# VozPlayer — reproductor de música y video con búsqueda por voz (Android)

Proyecto independiente del sistema ESPY: no comparte código con el backend ni con el frontend.

## Qué hace
- Muestra en **una sola lista** todos los audios (MP3, M4A, AAC, FLAC, WAV, OGG, OPUS…) y videos (MP4, MKV, WEBM, 3GP…) del teléfono.
- **Búsqueda por voz**: botón del micrófono → se dice el nombre de la canción o del video → se reproduce la mejor coincidencia.
  - Ignora tildes, mayúsculas y palabras de orden ("pon", "reproduce la canción de…").
  - Tolera errores de dictado y confusiones del español (b/v, s/z/c, ll/y, h muda).
  - Busca en título, artista, álbum **y nombre del archivo** (útil para ensayos y grabaciones sin etiquetas).
  - Si hay varias opciones parecidas, filtra la lista para elegir.
- Búsqueda escrita con los mismos criterios y filtro Todos / Audio / Video.
- Reproducción en segundo plano con la pantalla apagada, notificación con controles, pausa al desconectar audífonos.
- Aparece en "Abrir con…" para cualquier archivo de audio o video.

## Obtener el APK
Cada push que toque `reproductor_voz_android/` ejecuta el flujo **VozPlayer Android (APK)** en GitHub Actions.
Al terminar, descargar el artefacto `VozPlayer-apk` (pestaña *Actions* del repositorio), descomprimirlo y
pasar `app-debug.apk` al teléfono (permitir "instalar apps de origen desconocido").

## Compilar localmente
Requiere Android Studio (o el SDK de Android con `ANDROID_HOME`) y JDK 17:

```bash
cd reproductor_voz_android
./gradlew testDebugUnitTest   # pruebas del buscador por voz
./gradlew assembleDebug       # APK en app/build/outputs/apk/debug/
```

## Requisitos del teléfono
- Android 8.0 o superior.
- Para la voz: la app de Google (o cualquier servicio de reconocimiento de voz) instalada. Usa el idioma del teléfono.

## Estructura
| Archivo | Función |
|---|---|
| `VoiceSearchMatcher.kt` | Motor de búsqueda difusa (Kotlin puro, con pruebas JUnit) |
| `MediaRepository.kt` | Lectura de audios y videos desde MediaStore |
| `PlaybackService.kt` | Servicio de reproducción (Media3/ExoPlayer) en segundo plano |
| `MainActivity.kt` | Lista, filtros, micrófono y reproductor |
