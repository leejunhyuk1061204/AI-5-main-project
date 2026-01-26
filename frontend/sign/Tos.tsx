import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Pressable, BackHandler, Alert } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useNavigation } from '@react-navigation/native';
import { useAlertStore } from '../store/useAlertStore';

type Agreements = {
    service: boolean;
    privacy: boolean;
    location: boolean;
    marketing: boolean;
};

export default function Tos() {
    const navigation = useNavigation<any>();
    const insets = useSafeAreaInsets();
    const [agreements, setAgreements] = useState<Agreements>({
        service: false,
        privacy: false,
        location: false,
        marketing: false,
    });

    const allAgreed = Object.values(agreements).every(Boolean);

    // Handle hardware back button
    useEffect(() => {
        const backAction = () => {
            BackHandler.exitApp();
            return true;
        };

        const backHandler = BackHandler.addEventListener(
            'hardwareBackPress',
            backAction
        );

        return () => backHandler.remove();
    }, []);

    const toggleAll = () => {
        const newState = !allAgreed;
        setAgreements({
            service: newState,
            privacy: newState,
            location: newState,
            marketing: newState,
        });
    };

    const toggleAgreement = (key: keyof Agreements) => {
        setAgreements(prev => ({
            ...prev,
            [key]: !prev[key],
        }));
    };

    const handleStart = async () => {
        // Optional: Validate required agreements
        // For now, allowing proceed if user clicks start, or we can enforce service/privacy
        if (!agreements.service || !agreements.privacy || !agreements.location) {
            useAlertStore.getState().showAlert('알림', '필수 약관에 모두 동의해주세요.', 'WARNING');
            return;
        }

        try {
            await AsyncStorage.setItem('hasAgreedToTos', 'true');
            navigation.navigate('SignUp'); // Changed from 'Login' to 'SignUp' (navigate allows back)
        } catch (e) {
            console.error('Failed to save ToS status', e);
        }
    };

    const Checkbox = ({ checked }: { checked: boolean }) => (
        <View
            className={`w-5 h-5 rounded border-2 items-center justify-center transition-all ${checked
                ? 'bg-primary border-primary'
                : 'border-border-light bg-transparent'
                }`}
        >
            {checked && (
                <MaterialIcons name="check" size={14} color="white" style={{ fontWeight: 'bold' }} />
            )}
        </View>
    );

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between p-4 pb-2 bg-background-dark/95 border-b border-white/5 z-50 sticky top-0 backdrop-blur-md">
                <TouchableOpacity
                    className="w-12 h-12 items-center justify-center rounded-full active:bg-white/5"
                    activeOpacity={0.7}
                    onPress={() => BackHandler.exitApp()}
                >
                    <MaterialIcons name="arrow-back" size={24} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold flex-1 text-center pr-12">
                    약관 동의
                </Text>
            </View>

            <ScrollView
                className="flex-1 px-4 pt-6"
                contentContainerStyle={{ paddingBottom: 120 }}
                showsVerticalScrollIndicator={false}
            >
                {/* Headline */}
                <View className="mb-8">
                    <Text className="text-white text-[28px] font-bold leading-tight mb-2">
                        서비스 이용을 위해{'\n'}약관에 동의해 주세요
                    </Text>
                    <Text className="text-slate-400 text-sm">
                        안전하고 편리한 차량 관리를 시작해보세요.
                    </Text>
                </View>

                {/* Select All Section */}
                <Pressable
                    onPress={toggleAll}
                    className="bg-surface-dark rounded-xl border border-white/5 mb-6 overflow-hidden flex-row items-center gap-4 p-4 active:bg-white/5"
                >
                    <View className="w-6 h-6 items-center justify-center">
                        <Checkbox checked={allAgreed} />
                    </View>
                    <View className="flex-1">
                        <Text className="text-white text-lg font-bold">약관 전체 동의</Text>
                        <Text className="text-slate-400 text-xs mt-0.5">선택 항목 포함</Text>
                    </View>
                </Pressable>

                {/* Divider */}
                <View className="h-px w-full bg-white/5 mb-6 mx-2" />

                {/* List Items */}
                <View className="gap-2">
                    {/* Item 1: Required Service */}
                    <Pressable
                        onPress={() => toggleAgreement('service')}
                        className="flex-row items-center gap-4 p-2 rounded-lg active:bg-surface-dark"
                    >
                        <View className="flex-row items-center gap-4 flex-1">
                            <View className="w-7 h-7 items-center justify-center">
                                <Checkbox checked={agreements.service} />
                            </View>
                            <Text className="text-slate-200 text-base font-normal flex-1" numberOfLines={1}>
                                <Text className="text-primary font-bold">(필수) </Text>
                                서비스 이용약관
                            </Text>
                        </View>
                        <TouchableOpacity className="w-8 h-8 items-center justify-center rounded-full">
                            <MaterialIcons name="chevron-right" size={24} className="text-slate-500 hover:text-white" color="#64748b" />
                        </TouchableOpacity>
                    </Pressable>

                    {/* Item 2: Required Privacy */}
                    <Pressable
                        onPress={() => toggleAgreement('privacy')}
                        className="flex-row items-center gap-4 p-2 rounded-lg active:bg-surface-dark"
                    >
                        <View className="flex-row items-center gap-4 flex-1">
                            <View className="w-7 h-7 items-center justify-center">
                                <Checkbox checked={agreements.privacy} />
                            </View>
                            <Text className="text-slate-200 text-base font-normal flex-1" numberOfLines={1}>
                                <Text className="text-primary font-bold">(필수) </Text>
                                개인정보 처리방침
                            </Text>
                        </View>
                        <TouchableOpacity className="w-8 h-8 items-center justify-center rounded-full">
                            <MaterialIcons name="chevron-right" size={24} className="text-slate-500 hover:text-white" color="#64748b" />
                        </TouchableOpacity>
                    </Pressable>

                    {/* Item 3: Optional Location */}
                    <Pressable
                        onPress={() => toggleAgreement('location')}
                        className="flex-row items-center gap-4 p-2 rounded-lg active:bg-surface-dark"
                    >
                        <View className="flex-row items-center gap-4 flex-1">
                            <View className="w-7 h-7 items-center justify-center">
                                <Checkbox checked={agreements.location} />
                            </View>
                            <Text className="text-slate-200 text-base font-normal flex-1" numberOfLines={1}>
                                <Text className="text-primary font-bold">(필수) </Text>
                                위치기반 서비스 이용약관
                            </Text>
                        </View>
                        <TouchableOpacity className="w-8 h-8 items-center justify-center rounded-full">
                            <MaterialIcons name="chevron-right" size={24} className="text-slate-500 hover:text-white" color="#64748b" />
                        </TouchableOpacity>
                    </Pressable>

                    {/* Item 4: Optional Marketing */}
                    <Pressable
                        onPress={() => toggleAgreement('marketing')}
                        className="flex-row items-center gap-4 p-2 rounded-lg active:bg-surface-dark"
                    >
                        <View className="flex-row items-center gap-4 flex-1">
                            <View className="w-7 h-7 items-center justify-center">
                                <Checkbox checked={agreements.marketing} />
                            </View>
                            <Text className="text-slate-200 text-base font-normal flex-1" numberOfLines={1}>
                                <Text className="text-slate-500 mr-1">(선택) </Text>
                                마케팅 정보 수신 동의
                            </Text>
                        </View>
                        <TouchableOpacity className="w-8 h-8 items-center justify-center rounded-full">
                            <MaterialIcons name="chevron-right" size={24} className="text-slate-500 hover:text-white" color="#64748b" />
                        </TouchableOpacity>
                    </Pressable>
                </View>
            </ScrollView>

            {/* Bottom Fixed Button */}
            <View
                className="absolute bottom-0 left-0 w-full"
                style={{ paddingBottom: (insets.bottom || 10) + 16, paddingHorizontal: 16 }}
            >
                <View className="w-full bg-background-dark/80 backdrop-blur-xl absolute bottom-0 h-40 w-full -z-10" />

                <TouchableOpacity
                    className="w-full h-14 bg-primary rounded-xl items-center justify-center shadow-lg shadow-blue-500/30 active:bg-primary-dark"
                    activeOpacity={0.8}
                    onPress={handleStart}
                >
                    <Text className="text-white font-bold text-lg">시작하기</Text>
                </TouchableOpacity>
            </View>

        </SafeAreaView>
    );
}
