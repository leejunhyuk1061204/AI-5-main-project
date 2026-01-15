import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';

export default function FindPW() {
    const [email, setEmail] = useState('');
    const [isSent, setIsSent] = useState(false);

    const handleSendLink = () => {
        // Simulate API call
        console.log('Sending reset link to:', email);
        setIsSent(true);
    };

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 py-3 bg-background-dark/95 backdrop-blur-md sticky top-0 z-10">
                <TouchableOpacity
                    className="w-10 h-10 items-center justify-center rounded-full hover:bg-slate-800"
                    activeOpacity={0.7}
                >
                    <MaterialIcons name="arrow-back" size={24} className="text-white" />
                </TouchableOpacity>
                <Text className="text-lg font-bold flex-1 text-center pr-10 text-white">
                    비밀번호 재설정
                </Text>
            </View>

            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
                className="flex-1"
            >
                <ScrollView
                    className="flex-1 px-6 pt-4 pb-8"
                    contentContainerStyle={{ paddingBottom: 50 }}
                    showsVerticalScrollIndicator={false}
                >
                    {/* Hero Icon */}
                    <View className="items-center py-8">
                        <View className="relative items-center justify-center w-20 h-20 rounded-2xl bg-slate-800 border border-slate-700/50 shadow-inner overflow-hidden">
                            {/* Gradient Background simulation */}
                            <View className="absolute inset-0 bg-slate-900 opacity-50" />
                            <MaterialCommunityIcons name="lock-reset" size={40} color="#0d7ff2" />

                            {/* Glow effect */}
                            <View className="absolute inset-0 bg-primary/20 blur-xl rounded-full -z-10" />
                        </View>
                    </View>

                    {/* Description */}
                    <View className="mb-8 items-center">
                        <Text className="text-xl font-bold mb-3 text-white text-center">
                            비밀번호를 잊으셨나요?
                        </Text>
                        <Text className="text-sm font-normal leading-relaxed text-text-secondary text-center">
                            가입하신 이메일 주소를 입력하시면{'\n'}비밀번호 재설정 링크를 보내드립니다.
                        </Text>
                    </View>

                    {/* Form */}
                    <View className="gap-6 w-full">
                        <View className="gap-2 group">
                            <Text className="text-sm font-medium text-white pl-1">
                                이메일
                            </Text>
                            <View className="relative">
                                <View className="absolute inset-y-0 left-0 pl-4 justify-center pointer-events-none z-10">
                                    <MaterialIcons name="mail" size={20} className="text-slate-400 group-focus-within:text-primary" color="#94a3b8" />
                                </View>
                                <TextInput
                                    value={email}
                                    onChangeText={setEmail}
                                    className="block w-full rounded-xl border-0 py-4 pl-11 pr-4 text-white bg-surface-dark focus:ring-2 focus:ring-primary shadow-sm"
                                    placeholder="example@email.com"
                                    placeholderTextColor="#94a3b8"
                                    keyboardType="email-address"
                                    autoCapitalize="none"
                                    style={{ borderWidth: 1, borderColor: '#334155' }}
                                />
                            </View>
                        </View>

                        {/* Submit Button */}
                        <TouchableOpacity
                            onPress={handleSendLink}
                            className="w-full h-14 bg-primary hover:bg-primary-dark rounded-xl flex-row items-center justify-center shadow-lg shadow-primary/25 active:scale-[0.98]"
                            activeOpacity={0.9}
                        >
                            <Text className="text-base font-bold text-white mr-2">링크 전송</Text>
                            <MaterialIcons name="send" size={20} color="white" />
                        </TouchableOpacity>
                    </View>

                    {/* Success Feedback */}
                    {isSent && (
                        <View className="mt-8 pt-8 border-t border-slate-800/50">
                            <View className="bg-green-900/20 border border-green-500/20 rounded-xl p-4 flex-row items-start gap-3">
                                <MaterialIcons name="check-circle" size={20} color="#16a34a" className="text-green-400" />
                                <View className="flex-1">
                                    <Text className="text-sm font-bold text-green-300 mb-1">
                                        전송 완료
                                    </Text>
                                    <Text className="text-xs text-green-400/80 leading-relaxed">
                                        이메일이 성공적으로 전송되었습니다. 메일함을 확인해주세요.
                                    </Text>
                                </View>
                            </View>
                        </View>
                    )}

                </ScrollView>
            </KeyboardAvoidingView>

            {/* Footer Help Link */}
            <View className="p-6 items-center">
                <Text className="text-xs text-slate-600">
                    도움이 필요하신가요?{' '}
                    <Text className="text-primary hover:text-primary-dark underline">
                        고객센터 문의하기
                    </Text>
                </Text>
            </View>

        </SafeAreaView>
    );
}
