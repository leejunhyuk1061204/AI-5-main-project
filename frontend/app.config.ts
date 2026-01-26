import { ExpoConfig, ConfigContext } from 'expo/config';

export default ({ config }: ConfigContext): ExpoConfig => ({
    ...config,
    name: "frontend",
    slug: "frontend",
    version: "1.0.0",
    orientation: "portrait",
    icon: "./assets/icon.png",
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
            foregroundImage: "./assets/adaptive-icon.png",
            backgroundColor: "#101922"
        },
        edgeToEdgeEnabled: true,
        predictiveBackGestureEnabled: false,
        permissions: [
            "android.permission.BLUETOOTH",
            "android.permission.BLUETOOTH_ADMIN",
            "android.permission.BLUETOOTH_CONNECT",
            "android.permission.CAMERA",
            "android.permission.RECORD_AUDIO"
        ],
        package: "com.lee_kang_hyun.frontend",
        softwareKeyboardLayoutMode: "resize"
    },
    web: {
        favicon: "./assets/favicon.png"
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
