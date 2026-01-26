import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, Platform, KeyboardAvoidingView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { cssInterop } from 'nativewind';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { authService } from '../services/auth';
import { useAlertStore } from '../store/useAlertStore';

export default function SignUp() {
    const navigation = useNavigation<any>();
    const insets = useSafeAreaInsets();
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [passwordConfirm, setPasswordConfirm] = useState('');
    const [loading, setLoading] = useState(false);
    const showAlert = useAlertStore(state => state.showAlert);

    const [showPassword, setShowPassword] = useState(false);
    const [showPasswordConfirm, setShowPasswordConfirm] = useState(false);

    const handleSignup = async () => {
        // Validation
        if (!name || !email || !password || !passwordConfirm) {
            showAlert("입력 오류", "모든 정보를 입력해주세요.", "WARNING");
            return;
        }

        if (password !== passwordConfirm) {
            showAlert("비밀번호 불일치", "비밀번호가 일치하지 않습니다.", "WARNING");
            return;
        }

        if (password.length < 8) {
            showAlert("비밀번호 오류", "비밀번호는 8자 이상이어야 합니다.", "WARNING");
            return;
        }

        try {
            setLoading(true);
            const response = await authService.signup({
                email,
                password,
                nickname: name // Map 'name' to 'nickname' as per API spec
            });

            console.log('Signup Response:', response);
            if (response.success) {
                showAlert(
                    "가입 완료",
                    "회원가입이 완료되었습니다. 로그인해주세요.",
                    "SUCCESS",
                    () => navigation.navigate('Login', { fromSignup: true })
                );
            } else {
                showAlert("가입 실패", response.error?.message || "회원가입 중 오류가 발생했습니다.", "ERROR");
            }
        } catch (error: any) {
            console.log('Signup Error Full:', JSON.stringify(error.response || error, null, 2));
            console.log('Signup Error Status:', error.response?.status);

            // Check for conflict (409) or other errors
            if (error.response?.status === 409) {
                showAlert("가입 실패", "이미 가입된 이메일입니다.\n다른 이메일을 사용하거나 로그인해주세요.", "ERROR");
            } else {
                const errorMsg = error.response?.data?.message || error.response?.data?.error?.message || "회원가입 중 오류가 발생했습니다.";
                showAlert("오류", errorMsg, "ERROR");
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Top App Bar */}
            <View className="flex-row items-center justify-between p-4 bg-background-dark/90 backdrop-blur-md z-50 sticky top-0">
                <TouchableOpacity
                    className="flex items-center justify-center w-10 h-10 rounded-full hover:bg-white/10"
                    activeOpacity={0.7}
                    onPress={() => navigation.goBack()}
                >
                    <MaterialIcons name="arrow-back-ios-new" size={24} className="text-white" />
                </TouchableOpacity>
                <Text className="text-lg font-bold leading-tight tracking-tight flex-1 text-center pr-10 text-white">
                    회원가입
                </Text>
            </View>

            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
                className="flex-1"
            >
                <ScrollView
                    contentContainerStyle={{ paddingBottom: 150 }}
                    className="flex-1 px-6 w-full max-w-lg mx-auto"
                    showsVerticalScrollIndicator={false}
                >
                    {/* Header Section */}
                    <View className="pt-6 pb-8">
                        <Text className="text-3xl font-bold tracking-tight mb-2 text-white">
                            계정 생성
                        </Text>
                        <Text className="text-text-muted text-base font-normal">
                            AI 차량 관리 서비스를 시작해보세요.
                        </Text>
                    </View>

                    {/* Form Fields */}
                    <View className="space-y-6">

                        {/* Name Field */}
                        <View className="flex flex-col gap-2 group">
                            <Text className="text-sm font-medium text-text-secondary ml-1">
                                성함
                            </Text>
                            <View className="relative">
                                <TextInput
                                    value={name}
                                    onChangeText={setName}
                                    className="w-full bg-surface-dark border border-border-muted/50 rounded-xl px-4 py-3.5 text-base text-white placeholder:text-text-dim focus:outline-none focus:border-primary"
                                    placeholder="이름을 입력해주세요"
                                    placeholderTextColor="#64748b"
                                />
                            </View>
                        </View>

                        {/* Email Field */}
                        <View className="flex flex-col gap-2 group">
                            <Text className="text-sm font-medium text-text-secondary ml-1">
                                이메일
                            </Text>
                            <View className="relative justify-center">
                                <TextInput
                                    value={email}
                                    onChangeText={setEmail}
                                    className="w-full bg-surface-dark border border-border-muted/50 rounded-xl px-4 py-3.5 text-base text-white placeholder:text-text-dim focus:outline-none focus:border-primary pr-12"
                                    placeholder="example@email.com"
                                    placeholderTextColor="#64748b"
                                    keyboardType="email-address"
                                    autoCapitalize="none"
                                />
                                <View
                                    className="absolute right-4"
                                    pointerEvents={Platform.OS === 'web' ? undefined : 'none'}
                                    style={Platform.OS === 'web' ? { pointerEvents: 'none' } : undefined}
                                >
                                    <MaterialIcons name="mail" size={20} className="text-text-dim" color="#64748b" />
                                </View>
                            </View>
                        </View>

                        {/* Password Field */}
                        <View className="flex flex-col gap-2 group">
                            <Text className="text-sm font-medium text-text-secondary ml-1">
                                비밀번호
                            </Text>
                            <View className="relative justify-center">
                                <TextInput
                                    value={password}
                                    onChangeText={setPassword}
                                    className="w-full bg-surface-dark border border-white/10 rounded-xl px-4 py-3.5 text-base text-white placeholder:text-text-dim focus:outline-none focus:border-primary pr-12"
                                    placeholder="영문, 숫자 포함 8자 이상"
                                    placeholderTextColor="#64748b"
                                    secureTextEntry={!showPassword}
                                />
                                <TouchableOpacity
                                    className="absolute right-0 h-full px-4 items-center justify-center"
                                    onPress={() => setShowPassword(!showPassword)}
                                >
                                    <MaterialIcons
                                        name={showPassword ? "visibility" : "visibility-off"}
                                        size={20}
                                        color="#64748b"
                                    />
                                </TouchableOpacity>
                            </View>
                        </View>

                        {/* Password Confirm Field */}
                        <View className="flex flex-col gap-2 group">
                            <Text className="text-sm font-medium text-text-secondary ml-1">
                                비밀번호 확인
                            </Text>
                            <View className="relative justify-center">
                                <TextInput
                                    value={passwordConfirm}
                                    onChangeText={setPasswordConfirm}
                                    className="w-full bg-surface-dark border border-white/10 rounded-xl px-4 py-3.5 text-base text-white placeholder:text-text-dim focus:outline-none focus:border-primary pr-12"
                                    placeholder="비밀번호를 다시 입력해주세요"
                                    placeholderTextColor="#64748b"
                                    secureTextEntry={!showPasswordConfirm}
                                />
                                <TouchableOpacity
                                    className="absolute right-0 h-full px-4 items-center justify-center"
                                    onPress={() => setShowPasswordConfirm(!showPasswordConfirm)}
                                >
                                    <MaterialIcons
                                        name={showPasswordConfirm ? "visibility" : "visibility-off"}
                                        size={20}
                                        color="#64748b"
                                    />
                                </TouchableOpacity>
                            </View>
                        </View>

                    </View>
                </ScrollView>
            </KeyboardAvoidingView>

            {/* Bottom Action Area */}
            <View
                className="absolute bottom-0 left-0 w-full bg-background-dark/80 backdrop-blur-lg border-t border-white/5 z-40"
                style={{ paddingBottom: insets.bottom + 10, paddingHorizontal: 16, paddingTop: 16 }}
            >
                <View className="max-w-lg mx-auto w-full">
                    <TouchableOpacity
                        className={`w-full bg-primary hover:bg-primary/90 rounded-xl h-14 flex-row items-center justify-center gap-2 shadow-lg shadow-primary/30 active:opacity-90 mb-4 ${loading ? 'opacity-70' : ''}`}
                        activeOpacity={0.8}
                        onPress={handleSignup}
                        disabled={loading}
                    >
                        <Text className="text-white font-bold text-lg">
                            {loading ? "처리중..." : "회원가입 완료"}
                        </Text>
                        {!loading && <MaterialIcons name="arrow-forward" size={20} color="white" />}
                    </TouchableOpacity>

                    {/* Login Link */}
                    <View className="flex-row justify-center items-center pb-2">
                        <Text className="text-gray-400 text-sm">이미 계정이 있으신가요? </Text>
                        <TouchableOpacity onPress={() => navigation.navigate('Login')}>
                            <Text className="text-primary font-bold text-sm ml-1">로그인</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            </View>

        </SafeAreaView>
    );
}