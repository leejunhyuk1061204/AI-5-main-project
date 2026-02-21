import { ExpoConfig, ConfigContext } from 'expo/config';

export default ({ config }: ConfigContext): ExpoConfig => ({
    ...config,
    name: "차봄",
    slug: "chabom",
    version: "1.0.0",
    scheme: "frontend",
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
        supportsTablet: true,
        bundleIdentifier: "com.lee-kang-hyun.frontend"
    },
    android: {
        package: "com.lee_kang_hyun.frontend",
        googleServicesFile: process.env.GOOGLE_SERVICES_JSON || "./google-services.json",
        adaptiveIcon: {
            foregroundImage: "./assets/adaptive_icon_fixed.png",
            backgroundColor: "#101922"
        },

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
        softwareKeyboardLayoutMode: "resize",
        // @ts-ignore
        launchMode: "singleTask"
    },
    web: {
        favicon: "./assets/Gemini_Generated_Image_v1i03bv1i03bv1i0.png"
    },
    plugins: [
        "@react-native-firebase/app",
        "@react-native-firebase/messaging",
        "expo-font",
        "expo-sqlite",
        "expo-web-browser",

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
            "@react-native-google-signin/google-signin",
            {
                "iosUrlScheme": "com.googleusercontent.apps.PLACEHOLDER",
                "ios": {
                    "bundleIdentifier": "com.lee-kang-hyun.frontend"
                },
                "android": {
                    googleServicesFile: process.env.GOOGLE_SERVICES_JSON || "./google-services.json"
                }
            }
        ],
        [
            "@react-native-seoul/kakao-login",
            {
                "kakaoAppKey": process.env.KAKAO_NATIVE_APP_KEY ?? "",
                "kotlinVersion": "2.1.20"
            }
        ],
        [
            "expo-build-properties",
            {
                "android": {
                    "bridgelessEnabled": false,
                    "extraMavenRepos": [
                        "https://devrepo.kakao.com/nexus/content/groups/public/"
                    ],
                    "kotlinVersion": "2.1.20"
                },
                "ios": {
                    "bridgelessEnabled": false
                }
            }
        ]
    ],
    extra: {
        eas: {
            projectId: "47fc3708-0a7c-4843-aacf-7a9719b8a636"
        }
    }
});
