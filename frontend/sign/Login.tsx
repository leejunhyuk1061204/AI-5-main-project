import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, Platform, KeyboardAvoidingView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function Login() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);

    const handleLogin = () => {
        // Implement login logic here

        // Check if user came from SignUp (New User)
        if (route.params?.fromSignup) {
            navigation.navigate('RegisterMain');
        } else {
            navigation.navigate('MainPage');
        }
    };

    const handleReset = async () => {
        await AsyncStorage.clear();
        navigation.replace('Tos');
    };

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
                className="flex-1"
            >
                <ScrollView
                    contentContainerStyle={{ flexGrow: 1, justifyContent: 'center' }}
                    className="flex-1 px-6 w-full max-w-md mx-auto"
                    showsVerticalScrollIndicator={false}
                >
                    {/* Logo Section */}
                    <View className="items-center gap-6 mb-12">
                        <View className="relative items-center justify-center w-20 h-20 rounded-2xl bg-slate-900 border border-[#314d68] shadow-xl">
                            <MaterialIcons name="car-crash" size={40} color="#0d7ff2" />
                            {/* Decorative dot */}
                            <View className="absolute -top-1 -right-1 w-3 h-3 bg-primary rounded-full shadow-lg shadow-blue-500" />
                        </View>
                        <View className="items-center">
                            <Text className="text-white text-3xl font-bold tracking-tight mb-2">
                                AI Vehicle Guard
                            </Text>
                            <Text className="text-gray-400 text-base font-normal">
                                스마트한 차량 관리의 시작
                            </Text>
                        </View>
                    </View>

                    {/* Login Form */}
                    <View className="w-full gap-5">
                        {/* Email Field */}
                        <View className="gap-1.5">
                            <Text className="text-sm font-medium text-gray-300 ml-1">이메일</Text>
                            <View className="relative group">
                                <View className="absolute inset-y-0 left-0 pl-4 justify-center pointer-events-none z-10">
                                    <MaterialIcons name="mail" size={20} className="text-gray-500" color="#6b7280" />
                                </View>
                                <TextInput
                                    value={email}
                                    onChangeText={setEmail}
                                    className="block w-full rounded-xl border border-[#314d68] bg-[#182634]/80 text-white placeholder:text-gray-500 focus:border-primary px-4 py-3.5 pl-11"
                                    placeholder="example@email.com"
                                    placeholderTextColor="#6b7280"
                                    keyboardType="email-address"
                                    autoCapitalize="none"
                                />
                            </View>
                        </View>

                        {/* Password Field */}
                        <View className="gap-1.5">
                            <Text className="text-sm font-medium text-gray-300 ml-1">비밀번호</Text>
                            <View className="relative group">
                                <View className="absolute inset-y-0 left-0 pl-4 justify-center pointer-events-none z-10">
                                    <MaterialIcons name="lock" size={20} className="text-gray-500" color="#6b7280" />
                                </View>
                                <TextInput
                                    value={password}
                                    onChangeText={setPassword}
                                    className="block w-full rounded-xl border border-[#314d68] bg-[#182634]/80 text-white placeholder:text-gray-500 focus:border-primary px-4 py-3.5 pl-11 pr-12"
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
                                <Text className="text-sm font-medium text-gray-400">
                                    비밀번호를 잊으셨나요?
                                </Text>
                            </TouchableOpacity>
                        </View>

                        {/* Login Button */}
                        <TouchableOpacity
                            onPress={handleLogin}
                            className="w-full rounded-xl bg-primary py-4 items-center justify-center shadow-lg shadow-blue-500/20 active:opacity-90 mt-4"
                        >
                            <Text className="text-sm font-bold text-white">로그인</Text>
                        </TouchableOpacity>
                    </View>

                    {/* Divider */}
                    <View className="relative w-full my-8">
                        <View className="absolute inset-0 flex-row items-center">
                            <View className="w-full border-t border-[#314d68]" />
                        </View>
                        <View className="relative flex-row justify-center">
                            <Text className="bg-background-dark px-3 text-xs text-gray-500 uppercase tracking-wider">
                                또는
                            </Text>
                        </View>
                    </View>

                    {/* Social Login Options */}
                    <View className="flex-row gap-4 w-full">
                        <TouchableOpacity className="flex-1 flex-row items-center justify-center gap-3 rounded-xl bg-[#182634] border border-[#314d68] px-4 py-3 active:bg-[#203040]">
                            <Ionicons name="logo-google" size={20} color="white" />
                            <Text className="text-sm font-medium text-white">Google</Text>
                        </TouchableOpacity>
                        <TouchableOpacity className="flex-1 flex-row items-center justify-center gap-3 rounded-xl bg-[#182634] border border-[#314d68] px-4 py-3 active:bg-[#203040]">
                            <Ionicons name="logo-apple" size={20} color="white" />
                            <Text className="text-sm font-medium text-white">Apple</Text>
                        </TouchableOpacity>
                    </View>

                    {/* Sign Up Prompt */}
                    <View className="mt-10 flex-row justify-center gap-1">
                        <Text className="text-sm text-gray-400">아직 계정이 없으신가요?</Text>
                        <TouchableOpacity onPress={() => navigation.navigate('SignUp')}>
                            <Text className="text-sm font-semibold text-primary">회원가입</Text>
                        </TouchableOpacity>
                    </View>

                    {/* Reset Button (For Testing) */}
                    <TouchableOpacity
                        onPress={handleReset}
                        className="mt-8 mb-4 items-center"
                    >
                        <Text className="text-xs text-gray-600 underline">앱 초기화 (테스트용)</Text>
                    </TouchableOpacity>

                </ScrollView>
            </KeyboardAvoidingView>
        </SafeAreaView>
    );
}