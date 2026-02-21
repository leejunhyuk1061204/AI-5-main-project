import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, Platform, BackHandler } from 'react-native';
import { GoogleSignin, GoogleSigninButton } from '@react-native-google-signin/google-signin';
import { MaterialIcons, Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute, useFocusEffect } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useUserStore } from '../store/useUserStore';
import { useAlertStore } from '../store/useAlertStore';
import BaseScreen from '../components/layout/BaseScreen';
import fcmService from '../services/fcmService';
import ObdService from '../services/ObdService';
import Svg, { Path } from 'react-native-svg';

// 정석 다색 구글 로고 SVG 컴포넌트
const GoogleLogo = () => (
    <Svg width={18} height={18} viewBox="0 0 24 24">
        <Path
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31l3.59 2.79c2.1-1.94 3.3-4.8 3.3-8.11z"
            fill="#4285F4"
        />
        <Path
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.59-2.79c-1 .67-2.26 1.07-3.69 1.07-2.84 0-5.25-1.92-6.11-4.51H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            fill="#34A853"
        />
        <Path
            d="M5.89 14.11c-.22-.67-.35-1.39-.35-2.11s.13-1.44.35-2.11V7.05H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.95l3.71-2.84z"
            fill="#FBBC05"
        />
        <Path
            d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.05l3.71 2.84c.86-2.59 3.27-4.51 6.11-4.51z"
            fill="#EA4335"
        />
    </Svg>
);

// Kakao Login Import (Platform check)
let login: () => Promise<any>;
if (Platform.OS !== 'web') {
    login = require('@react-native-seoul/kakao-login').login;
} else {
    login = async () => { console.warn("Kakao Login not supported on web"); return null; };
}

export default function Login() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const { loginAction, socialLoginAction } = useUserStore();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);

    // Handle Hardware Back Button (Exit App instead of warning)
    useFocusEffect(
        React.useCallback(() => {
            const onBackPress = () => {
                BackHandler.exitApp();
                return true;
            };

            const subscription = BackHandler.addEventListener('hardwareBackPress', onBackPress);

            return () => subscription.remove();
        }, [])
    );

    useEffect(() => {
        GoogleSignin.configure({
            webClientId: '540652803257-cl4t2p9tsvd0lbffrck17rq2sjs7i0k1.apps.googleusercontent.com',
        });
    }, []);

    const handleNavigation = async (result: any) => {
        // FCM 토큰 등록/갱신
        await fcmService.registerFcmToken();

        // 로그인 성공 시, 이미 등록된 OBD 기기 목록을 새로 불러와 캐시에 반영하고
        // 백그라운드 재연결 서비스를 시작한다.
        console.log('[Login] Login success. Loading OBD devices and starting background reconnect');
        await ObdService.loadAndCacheDevices();
        ObdService.startBackgroundReconnectIfNeeded().catch((e) => {
            console.warn('[Login] startBackgroundReconnectIfNeeded failed', e);
        });

        if (route.params?.fromSignup) {
            navigation.navigate('RegisterMain');
        } else if (result.hasVehicle) {
            navigation.navigate('MainPage');
        } else {
            navigation.navigate('RegisterMain');
        }
    };

    const onGoogleButtonPress = async () => {
        try {
            await GoogleSignin.hasPlayServices();
            const signInResult = await GoogleSignin.signIn();

            if (signInResult.data?.idToken) {
                setLoading(true);
                const result = await socialLoginAction('google', signInResult.data.idToken);

                if (result.success) {
                    handleNavigation(result);
                } else {
                    useAlertStore.getState().showAlert("로그인 실패", result.errorMessage || "소셜 로그인 실패", "ERROR");
                }
            } else {
                useAlertStore.getState().showAlert("로그인 실패", "Google 계정 정보를 가져오지 못했습니다.", "ERROR");
            }
        } catch (error: any) {
            if (error.code !== 'SIGN_IN_CANCELLED') {
                console.error("Google Sign-In Error", error);
                useAlertStore.getState().showAlert("오류", "구글 로그인 중 오류가 발생했습니다.", "ERROR");
            }
        } finally {
            setLoading(false);
        }
    };

    const onKakaoButtonPress = async () => {
        try {
            if (Platform.OS === 'web') {
                useAlertStore.getState().showAlert("알림", "카카오 로그인(네이티브)은 앱에서만 가능합니다.", "INFO");
                return;
            }

            const token = await login();

            if (token) {
                setLoading(true);
                const result = await socialLoginAction('kakao', token.accessToken);

                if (result.success) {
                    handleNavigation(result);
                } else {
                    useAlertStore.getState().showAlert("로그인 실패", result.errorMessage || "카카오 로그인 실패", "ERROR");
                }
            }
        } catch (error: any) {
            if (error.message !== 'user cancelled.') {
                console.error("Kakao Login Error", error);
                useAlertStore.getState().showAlert("로그인 실패", "카카오 로그인 중 오류가 발생했습니다.", "ERROR");
            }
        } finally {
            setLoading(false);
        }
    };

    const handleLogin = async () => {
        if (!email || !password) {
            useAlertStore.getState().showAlert("입력 오류", "이메일과 비밀번호를 입력해주세요.", "WARNING");
            return;
        }

        try {
            setLoading(true);
            const result = await loginAction(email, password);

            if (result.success) {
                handleNavigation(result);
            } else {
                useAlertStore.getState().showAlert("로그인 실패", result.errorMessage || "로그인 실패", "ERROR");
            }
        } catch (error: any) {
            console.error("Login Error:", error);
            useAlertStore.getState().showAlert("오류", "로그인 중 오류가 발생했습니다.", "ERROR");
        } finally {
            setLoading(false);
        }
    };

    const handleReset = async () => {
        const { logout } = useUserStore.getState();
        await logout();
        const { clearStorageForLogout } = await import('../utils/storageLogout');
        await clearStorageForLogout();
        navigation.replace('Tos');
    };

    return (
        <BaseScreen scrollable={true} padding={false} useBottomNav={false}>
            <View className="flex-1 px-6 w-full max-w-md mx-auto justify-center min-h-screen">
                {/* Logo Section */}
                <View className="items-center gap-6 mb-12 mt-10">
                    <View className="relative items-center justify-center w-20 h-20 rounded-2xl bg-surface-dark border border-border-light shadow-xl">
                        <MaterialIcons name="car-crash" size={40} color="#0d7ff2" />
                        <View className="absolute -top-1 -right-1 w-3 h-3 bg-primary rounded-full shadow-lg shadow-primary" />
                    </View>
                    <View className="items-center">
                        <Text className="text-white text-3xl font-bold tracking-tight mb-2">
                            AI Vehicle Guard
                        </Text>
                        <Text className="text-text-muted text-base font-normal">
                            스마트한 차량 관리의 시작
                        </Text>
                    </View>
                </View>

                {/* Login Form */}
                <View className="w-full gap-5">
                    {/* Email Field */}
                    <View className="gap-1.5">
                        <Text className="text-sm font-medium text-text-secondary ml-1">이메일</Text>
                        <View className="relative group">
                            <View className="absolute inset-y-0 left-0 pl-4 justify-center z-10 pointer-events-none">
                                <MaterialIcons name="mail" size={20} className="text-text-dim" color="#6b7280" />
                            </View>
                            <TextInput
                                value={email}
                                onChangeText={(t) => setEmail(t.trim())}
                                className="block w-full rounded-xl border border-border-light bg-input-dark/80 text-white placeholder:text-text-dim focus:border-primary px-4 py-3.5 pl-11"
                                placeholder="example@email.com"
                                placeholderTextColor="#6b7280"
                                keyboardType="email-address"
                                autoCapitalize="none"
                            />
                        </View>
                    </View>

                    {/* Password Field */}
                    <View className="gap-1.5">
                        <Text className="text-sm font-medium text-text-secondary ml-1">비밀번호</Text>
                        <View className="relative group">
                            <View className="absolute inset-y-0 left-0 pl-4 justify-center z-10 pointer-events-none">
                                <MaterialIcons name="lock" size={20} className="text-text-dim" color="#6b7280" />
                            </View>
                            <TextInput
                                value={password}
                                onChangeText={setPassword}
                                className="block w-full rounded-xl border border-border-light bg-input-dark/80 text-white placeholder:text-text-dim focus:border-primary px-4 py-3.5 pl-11 pr-12"
                                placeholder="비밀번호를 입력하세요"
                                placeholderTextColor="#6b7280"
                                secureTextEntry={!showPassword}
                            />
                            <TouchableOpacity
                                className="absolute inset-y-0 right-0 pr-4 justify-center"
                                onPress={() => setShowPassword(!showPassword)}
                            >
                                <MaterialIcons
                                    name={showPassword ? "visibility" : "visibility-off"}
                                    size={20}
                                    color="#6b7280"
                                />
                            </TouchableOpacity>
                        </View>
                    </View>

                    {/* Forgot Password Link */}
                    <View className="flex-row justify-end pt-1">
                        <TouchableOpacity onPress={() => navigation.navigate('FindPW')}>
                            <Text className="text-sm font-medium text-text-muted">
                                비밀번호를 잊으셨나요?
                            </Text>
                        </TouchableOpacity>
                    </View>

                    {/* Login Button */}
                    <TouchableOpacity
                        onPress={handleLogin}
                        className={`w-full rounded-xl bg-primary py-4 items-center justify-center shadow-lg shadow-primary/20 active:opacity-90 mt-4 ${loading ? 'opacity-70' : ''}`}
                        disabled={loading}
                    >
                        <Text className="text-sm font-bold text-white">
                            {loading ? "로그인 중..." : "로그인"}
                        </Text>
                    </TouchableOpacity>
                </View>

                {/* Divider */}
                <View className="relative w-full my-8">
                    <View className="absolute inset-0 flex-row items-center">
                        <View className="w-full border-t border-border-light" />
                    </View>
                    <View className="relative flex-row justify-center">
                        <Text className="bg-background-dark px-3 text-xs text-text-dim uppercase tracking-wider">
                            또는
                        </Text>
                    </View>
                </View>

                {/* Social Login Options */}
                <View className="gap-3 w-full">
                    {/* Custom Google Login Button - Perfectly matched */}
                    <TouchableOpacity
                        onPress={onGoogleButtonPress}
                        activeOpacity={0.8}
                        className="w-full flex-row items-center justify-center gap-3 rounded-xl bg-white border border-border-light py-3.5 shadow-sm active:bg-gray-50"
                    >
                        <GoogleLogo />
                        <Text className="text-sm font-bold text-gray-700">Google 계정으로 로그인</Text>
                    </TouchableOpacity>

                    {/* Custom Kakao Login Button - Perfectly matched */}
                    <TouchableOpacity
                        onPress={onKakaoButtonPress}
                        activeOpacity={0.8}
                        className="w-full flex-row items-center justify-center gap-3 rounded-xl bg-kakao-yellow border border-kakao-yellow py-3.5 shadow-sm active:bg-yellow-400"
                    >
                        <Ionicons name="chatbubble" size={18} color="#000000" />
                        <Text className="text-sm font-bold text-[#000000]">카카오 로그인</Text>
                    </TouchableOpacity>
                </View>

                {/* Sign Up Prompt */}
                <View className="mt-10 mb-10 flex-row justify-center gap-1">
                    <Text className="text-sm text-text-muted">아직 계정이 없으신가요?</Text>
                    <TouchableOpacity onPress={() => navigation.navigate('SignUp')}>
                        <Text className="text-sm font-semibold text-primary">회원가입</Text>
                    </TouchableOpacity>
                </View>

                {/* ELM327 블루투스 테스트 */}
                {/* <TouchableOpacity
                    onPress={() => navigation.navigate('Elm327Test')}
                    className="mb-2 items-center"
                >
                    <Text className="text-xs text-text-muted">ELM327 테스트 (로그인 없이)</Text>
                </TouchableOpacity> */}

                {/* Reset Button (For Testing) */}
                {/* <TouchableOpacity
                    onPress={handleReset}
                    className="mb-8 items-center"
                >
                    <Text className="text-xs text-gray-600 underline">앱 초기화 (테스트용)</Text>
                </TouchableOpacity> */}
            </View>
        </BaseScreen>
    );
}