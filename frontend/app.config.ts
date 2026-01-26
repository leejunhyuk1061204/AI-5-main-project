import { ExpoConfig, ConfigContext } from 'expo/config';

export default ({ config }: ConfigContext): ExpoConfig => ({
    ...config,
    name: "차봄",
    slug: "chabom",
    version: "1.0.0",
    orientation: "portrait",
    icon: "./assets/Gemini_Generated_Image_v1i03bv1i03bv1i0.png",
    userInterfaceStyle: "dark",
    newArchEnabled: true,
    splash: {
        image: "./assets/splash.png",
        resizeMode: "contain",
        backgroundColor: "#101922"
    },
    backgroundColor: "#101922",
    ios: {
        supportsTablet: true
    },
    android: {
        adaptiveIcon: {
            foregroundImage: "./assets/adaptive_icon_fixed.png",
            backgroundColor: "#101922"
        },
        edgeToEdgeEnabled: true,
        predictiveBackGestureEnabled: false,
        permissions: [
            "android.permission.BLUETOOTH",
            "android.permission.BLUETOOTH_ADMIN",
            "android.permission.BLUETOOTH_CONNECT",
            "android.permission.CAMERA",
            "android.permission.RECORD_AUDIO",
            "android.permission.FOREGROUND_SERVICE",
            "android.permission.FOREGROUND_SERVICE_CONNECTED_DEVICE",
            "android.permission.WAKE_LOCK"
        ],
        package: "com.lee_kang_hyun.frontend",
        softwareKeyboardLayoutMode: "resize"
    },
    web: {
        favicon: "./assets/Gemini_Generated_Image_v1i03bv1i03bv1i0.png"
    },
    plugins: [
        "expo-font",
        [
            "expo-camera",
            {
                "cameraPermission": "Allow $(PRODUCT_NAME) to access your camera",
                "microphonePermission": "Allow $(PRODUCT_NAME) to access your microphone",
                "recordAudioAndroid": true
            }
        ],
        "./plugins/withBleManager",
        "./plugins/withAndroidForegroundService",
        "./plugins/withNotifeeRepo",
        [
            "expo-build-properties",
            {
                "android": {
                    "bridgelessEnabled": false,
                    "extraMavenRepos": [
                        "https://devrepo.kakao.com/nexus/content/groups/public/"
                    ],
                    "kotlinVersion": "2.0.20"
                },
                "ios": {
                    "bridgelessEnabled": false
                }
            }
        ],
        [
            "@react-native-google-signin/google-signin",
            {
                "iosUrlScheme": "com.googleusercontent.apps.PLACEHOLDER",
                "ios": {
                    "bundleIdentifier": "com.lee-kang-hyun.frontend"
                },
                "android": {
                    "googleServicesFile": "./google-services.json"
                }
            }
        ],
        [
            "@react-native-seoul/kakao-login",
            {
                "kakaoAppKey": process.env.KAKAO_NATIVE_APP_KEY ?? "",
                "kotlinVersion": "2.0.20"
            }
        ]
    ],
    extra: {
        eas: {
            projectId: "0c0101ed-c848-4c23-893d-64609323b4d4"
        }
    }
});
