plugins {
    id("com.android.application")
}

android {
    namespace = "com.vanadiel.watchface"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.vanadiel.watchface"
        minSdk = 33
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}
