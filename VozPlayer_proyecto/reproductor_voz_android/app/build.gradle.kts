plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.yojanes.vozplayer"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.yojanes.vozplayer"
        minSdk = 26
        targetSdk = 35
        versionCode = 15
        versionName = "2.4"
    }

    // Firma fija para que cada actualización se instale encima de la anterior y conserve
    // los datos. La llave NO está en el repositorio: GitHub Actions la toma de los secretos
    // VOZPLAYER_KEYSTORE_B64 y VOZPLAYER_KEYSTORE_PASSWORD. Sin ellos se usa la firma de depuración.
    val fixedKeystore = System.getenv("VOZPLAYER_KEYSTORE")?.let { file(it) }?.takeIf { it.exists() }
    signingConfigs {
        if (fixedKeystore != null) {
            create("vozplayer") {
                storeFile = fixedKeystore
                storePassword = System.getenv("VOZPLAYER_KEYSTORE_PASSWORD")
                keyAlias = "vozplayer"
                keyPassword = System.getenv("VOZPLAYER_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            if (fixedKeystore != null) signingConfig = signingConfigs.getByName("vozplayer")
        }
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
    testOptions {
        unitTests.isIncludeAndroidResources = true
        unitTests.all {
            it.testLogging {
                events("passed", "failed")
                exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
                showStackTraces = true
                showCauses = true
                showStandardStreams = true
            }
            it.environment("LETRAS_EN_LINEA", System.getenv("LETRAS_EN_LINEA") ?: "0")
        }
    }
}

dependencies {
    val media3 = "1.5.1"
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
    implementation("androidx.media3:media3-exoplayer:$media3")
    implementation("androidx.media3:media3-session:$media3")
    implementation("androidx.media3:media3-ui:$media3")
    implementation("com.google.guava:guava:33.3.1-android")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
    testImplementation("androidx.test:core-ktx:1.6.1")
    testImplementation("androidx.test.ext:junit:1.2.1")
}
