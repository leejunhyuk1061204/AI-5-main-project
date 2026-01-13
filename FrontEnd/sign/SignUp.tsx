import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, Platform, KeyboardAvoidingView, Alert, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function SignUp() {
    const navigation = useNavigation<any>();
    const insets = useSafeAreaInsets();
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [passwordConfirm, setPasswordConfirm] = useState('');
    const [loading, setLoading] = useState(false);

    const [showPassword, setShowPassword] = useState(false);
    const [showPasswordConfirm, setShowPasswordConfirm] = useState(false);

    const handleSignUp = async () => {
        // Validation
        if (!name || !email || !password || !passwordConfirm) {
            Alert.alert('알림', '모든 필드를 입력해주세요.');
            return;
        }

        if (password !== passwordConfirm) {
            Alert.alert('알림', '비밀번호가 일치하지 않습니다.');
            return;
        }

        if (password.length < 8) {
            Alert.alert('알림', '비밀번호는 8자 이상이어야 합니다.');
            return;
        }

        setLoading(true);
        try {
            // Android emulator uses 10.0.2.2 for localhost, web uses localhost
            const baseUrl = Platform.OS === 'android' ? 'http://10.0.2.2:8080' : 'http://localhost:8080';

            const response = await fetch(`${baseUrl}/api/v1/auth/signup`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: email,
                    password: password,
                    nickname: name,
                }),
            });

            const result = await response.json();

            if (response.ok) {
                Alert.alert('성공', '회원가입이 완료되었습니다.', [
                    { text: '확인', onPress: () => navigation.navigate('Login') }
                ]);
            } else {
                Alert.alert('실패', result.message || '회원가입에 실패했습니다.');
            }
        } catch (error) {
            Alert.alert('오류', '서버와의 연결에 실패했습니다.');
            console.error('SignUp Error:', error);
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
                    onPress={() => navigation.goBack()}
                    className="flex items-center justify-center w-10 h-10 rounded-full hover:bg-white/10"
                    activeOpacity={0.7}
                >
                    <MaterialIcons name="arrow-back-ios-new" size={24} color="white" />
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
                        <Text className="text-slate-400 text-base font-normal">
                            AI 차량 관리 서비스를 시작해보세요.
                        </Text>
                    </View>

                    {/* Form Fields */}
                    <View className="space-y-6">

                        {/* Name Field */}
                        <View className="flex flex-col gap-2 group">
                            <Text className="text-sm font-medium text-slate-300 ml-1">
                                성함 (닉네임)
                            </Text>
                            <View className="relative">
                                <TextInput
                                    value={name}
                                    onChangeText={setName}
                                    className="w-full bg-surface-dark border border-slate-700/50 rounded-xl px-4 py-3.5 text-base text-white placeholder:text-slate-500 focus:outline-none focus:border-primary"
                                    placeholder="이름을 입력해주세요"
                                    placeholderTextColor="#64748b"
                                />
                            </View>
                        </View>

                        {/* Email Field */}
                        <View className="flex flex-col gap-2 group">
                            <Text className="text-sm font-medium text-slate-300 ml-1">
                                이메일
                            </Text>
                            <View className="relative justify-center">
                                <TextInput
                                    value={email}
                                    onChangeText={setEmail}
                                    className="w-full bg-surface-dark border border-slate-700/50 rounded-xl px-4 py-3.5 text-base text-white placeholder:text-slate-500 focus:outline-none focus:border-primary pr-12"
                                    placeholder="example@email.com"
                                    placeholderTextColor="#64748b"
                                    keyboardType="email-address"
                                    autoCapitalize="none"
                                />
                                <View className="absolute right-4 pointer-events-none">
                                    <MaterialIcons name="mail" size={20} color="#64748b" />
                                </View>
                            </View>
                        </View>

                        {/* Password Field */}
                        <View className="flex flex-col gap-2 group">
                            <Text className="text-sm font-medium text-slate-300 ml-1">
                                비밀번호
                            </Text>
                            <View className="relative justify-center">
                                <TextInput
                                    value={password}
                                    onChangeText={setPassword}
                                    className="w-full bg-surface-dark border border-slate-700/50 rounded-xl px-4 py-3.5 text-base text-white placeholder:text-slate-500 focus:outline-none focus:border-primary pr-12"
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
                            <Text className="text-sm font-medium text-slate-300 ml-1">
                                비밀번호 확인
                            </Text>
                            <View className="relative justify-center">
                                <TextInput
                                    value={passwordConfirm}
                                    onChangeText={setPasswordConfirm}
                                    className="w-full bg-surface-dark border border-slate-700/50 rounded-xl px-4 py-3.5 text-base text-white placeholder:text-slate-500 focus:outline-none focus:border-primary pr-12"
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
                        onPress={handleSignUp}
                        disabled={loading}
                        className={`w-full ${loading ? 'bg-primary/50' : 'bg-primary'} rounded-xl h-14 flex-row items-center justify-center gap-2 shadow-lg shadow-blue-500/30 active:opacity-90 mb-4`}
                        activeOpacity={0.8}
                    >
                        {loading ? (
                            <ActivityIndicator color="white" />
                        ) : (
                            <>
                                <Text className="text-white font-bold text-lg">
                                    다음
                                </Text>
                                <MaterialIcons name="arrow-forward" size={20} color="white" />
                            </>
                        )}
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
