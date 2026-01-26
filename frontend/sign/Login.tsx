import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, Platform, BackHandler } from 'react-native';
import { GoogleSignin, GoogleSigninButton } from '@react-native-google-signin/google-signin';
import { MaterialIcons, Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute, useFocusEffect } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useUserStore } from '../store/useUserStore';
import { useAlertStore } from '../store/useAlertStore';
import BaseScreen from '../components/layout/BaseScreen';

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
            webClientId: '415824813180-to8ea5houck16m7as32t9cavi7aq87e5.apps.googleusercontent.com',
        });
    }, []);

    const handleNavigation = (result: any) => {
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
        await AsyncStorage.clear();
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
                                onChangeText={setEmail}
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
                    <GoogleSigninButton
                        style={{ width: '100%', height: 50 }}
                        size={GoogleSigninButton.Size.Wide}
                        color={GoogleSigninButton.Color.Light}
                        onPress={onGoogleButtonPress}
                    />
                    <TouchableOpacity
                        onPress={onKakaoButtonPress}
                        className="w-full flex-row items-center justify-center gap-3 rounded-xl bg-kakao-yellow border border-kakao-yellow px-4 py-3 active:bg-yellow-400"
                    >
                        <Ionicons name="chatbubble-ellipses" size={20} color="#000000" />
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

                {/* Reset Button (For Testing) */}
                <TouchableOpacity
                    onPress={handleReset}
                    className="mb-8 items-center"
                >
                    <Text className="text-xs text-gray-600 underline">앱 초기화 (테스트용)</Text>
                </TouchableOpacity>
            </View>
        </BaseScreen>
    );
}