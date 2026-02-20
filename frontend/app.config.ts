import { ExpoConfig, ConfigContext } from 'expo/config';

const API_URL = process.env.EXPO_PUBLIC_API_URL || "https://api.carbom.store";

export default ({ config }: ConfigContext): ExpoConfig => ({
    ...config,
    name: "차봄",
    slug: "chabom",
    owner: "choisoungbin",
    version: "1.0.0",
    scheme: "frontend",
    orientation: "portrait",
    icon: "./assets/Gemini_Generated_Image_v1i03bv1i03bv1i0.png",
    userInterfaceStyle: "dark",
    jsEngine: 'jsc',
    newArchEnabled: false,
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
    updates: {
        enabled: true,
        checkAutomatically: 'ON_LOAD'
    },
    android: {
        adaptiveIcon: {
            foregroundImage: "./assets/adaptive_icon_fixed.png",
            backgroundColor: "#101922"
        },
        package: "com.lee_kang_hyun.frontend",
        permissions: [],
        googleServicesFile: process.env.GOOGLE_SERVICES_JSON || "./google-services.json",
        softwareKeyboardLayoutMode: "resize"
    },
    web: {
        favicon: "./assets/Gemini_Generated_Image_v1i03bv1i03bv1i0.png"
    },
    plugins: [
        "expo-font",
        "expo-sqlite",
        [
            "expo-build-properties",
            {
                "android": {
                    "newArchEnabled": false,
                    "bridgelessEnabled": false,
                    "usesCleartextTraffic": true,
                    "extraMavenRepos": [
                        "https://devrepo.kakao.com/nexus/content/groups/public/"
                    ],
                    "kotlinVersion": "2.0.21"
                },
                "ios": {
                    "bridgelessEnabled": false
                }
            }
        ]
    ],
    extra: {
        eas: {
            projectId: "62f1e1fc-2999-4e4c-b44f-ad5801fc4d4c"
        }
    }
});
