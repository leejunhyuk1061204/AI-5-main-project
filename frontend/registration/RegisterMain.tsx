import React, { useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Platform, Linking, Alert } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import BaseScreen from '../components/layout/BaseScreen';

export default function RegisterMain() {
    const insets = useSafeAreaInsets();
    const navigation = useNavigation<any>();

    useEffect(() => {
        const handleDeepLink = async (event: { url: string }) => {
            const { url } = event;
            if (url && url.includes('smartcar/callback')) {
                // Extract access token from URL
                const regex = /[?&]accessToken=([^&#]*)/;
                const match = regex.exec(url);
                const accessToken = match && match[1];

                if (accessToken) {
                    try {
                        // Fetch vehicles
                        const backendUrl = Platform.OS === 'android' ? 'http://10.0.2.2:8080' : 'http://localhost:8080';
                        const response = await fetch(`${backendUrl}/api/smartcar/vehicles?accessToken=${accessToken}`);
                        const data = await response.json();

                        Alert.alert("Smartcar 연결 성공", `차량 정보를 가져왔습니다:\n${JSON.stringify(data, null, 2)}`);
                    } catch (error) {
                        Alert.alert("오류", "차량 정보를 가져오는 중 오류가 발생했습니다.");
                        console.error(error);
                    }
                }
            }
        };

        // Add event listener
        const subscription = Linking.addEventListener('url', handleDeepLink);

        // Check if app was opened by a link
        Linking.getInitialURL().then((url) => {
            if (url) handleDeepLink({ url });
        });

        return () => {
            subscription.remove();
        };
    }, []);

    // Custom Header for BaseScreen
    const renderHeader = () => (
        <View
            className="bg-background-dark/95 backdrop-blur-md z-50 border-b border-white/5"
            style={{ paddingTop: 10, paddingBottom: 16 }} // BaseScreen handles safe area, just add internal padding
        >
            <View className="flex-row items-center justify-between px-4">
                <TouchableOpacity
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                    activeOpacity={0.7}
                    onPress={() => navigation.goBack()}
                >
                    <MaterialIcons name="arrow-back" size={24} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">차량 등록</Text>
                <View className="w-10" />
            </View>
        </View>
    );

    return (
        <BaseScreen
            header={renderHeader()}
            scrollable={true}
            padding={false} // Custom padding handling in ScrollView
            bgColor="#101922"
        >
            <View className="px-5 pb-10">
                {/* Page Title */}
                <View className="mt-4 mb-8">
                    <Text className="text-2xl font-bold text-white leading-tight mb-2">
                        등록 방식을 선택해주세요
                    </Text>
                    <Text className="text-slate-400 text-sm">
                        정확한 진단을 위해 차량 정보가 필요합니다.
                    </Text>
                </View>

                {/* Selection Grid */}
                <View className="gap-4">
                    {/* Card 1: Manual Entry */}
                    <TouchableOpacity
                        className="group relative flex flex-col items-start gap-4 rounded-2xl border border-white/10 bg-white/5 p-6 active:bg-white/10 active:scale-[0.98]"
                        activeOpacity={0.9}
                        onPress={() => navigation.navigate('PassiveReg')}
                    >
                        <View className="rounded-full bg-surface-highlight p-3">
                            <MaterialIcons name="description" size={32} color="#94a3b8" className="text-slate-400" />
                        </View>
                        <View>
                            <Text className="text-lg font-bold text-white mb-1">수동 정보 입력</Text>
                            <Text className="text-sm text-slate-400 leading-relaxed">
                                차량 등록증을 보고{'\n'}연식, 모델명 등을 직접 입력합니다.
                            </Text>
                        </View>
                        {/* Arrow Icon */}
                        <View className="absolute top-6 right-6 opacity-50">
                            <MaterialIcons name="arrow-forward" size={24} color="#0d7ff2" />
                        </View>
                    </TouchableOpacity>

                    {/* Card 2: OBD-II Auto Connect */}
                    <TouchableOpacity
                        className="relative flex flex-col items-start gap-4 rounded-2xl border border-primary/30 bg-white/5 p-6 shadow-lg shadow-blue-500/10 active:bg-white/10 active:border-primary active:scale-[0.98]"
                        activeOpacity={0.9}
                        onPress={() => navigation.navigate('ActiveReg')}
                    >
                        {/* Recommended Badge */}
                        <View className="absolute top-0 right-0 rounded-bl-xl rounded-tr-xl bg-primary px-3 py-1 shadow-sm">
                            <Text className="text-[10px] font-bold text-white">RECOMMENDED</Text>
                        </View>

                        <View className="rounded-full bg-primary/10 p-3">
                            <MaterialIcons name="bluetooth" size={32} color="#0d7ff2" />
                        </View>
                        <View>
                            <Text className="text-lg font-bold text-white mb-1">OBD-II 자동 연결</Text>
                            <Text className="text-sm text-slate-400 leading-relaxed">
                                블루투스 스캐너를 연결하여{'\n'}차량 제원을 자동으로 불러옵니다.
                            </Text>
                        </View>
                    </TouchableOpacity>

                    {/* Card 3: Smartcar Connect (From Main) */}
                    <TouchableOpacity
                        className="group relative flex flex-col items-start gap-4 rounded-2xl border border-white/10 bg-white/5 p-6 active:bg-white/10 active:scale-[0.98]"
                        activeOpacity={0.9}
                        onPress={() => {
                            const backendUrl = Platform.OS === 'android' ? 'http://10.0.2.2:8080' : 'http://localhost:8080';
                            Linking.openURL(`${backendUrl}/api/smartcar/login`);
                        }}
                    >
                        <View className="absolute top-0 right-0 rounded-bl-xl rounded-tr-xl bg-green-500 px-3 py-1 shadow-sm">
                            <Text className="text-[10px] font-bold text-white">NEW</Text>
                        </View>
                        <View className="rounded-full bg-green-500/10 p-3">
                            <MaterialIcons name="electric-car" size={32} color="#22c55e" />
                        </View>
                        <View>
                            <Text className="text-lg font-bold text-white mb-1">Smartcar 연결</Text>
                            <Text className="text-sm text-slate-400 leading-relaxed">
                                Smartcar 계정을 연결하여{'\n'}차량 정보를 불러옵니다.
                            </Text>
                        </View>
                        <View className="absolute top-6 right-6 opacity-50">
                            <MaterialIcons name="arrow-forward" size={24} color="#22c55e" />
                        </View>
                    </TouchableOpacity>
                </View>

                {/* Info Panel */}
                <View className="mt-12">
                    <View className="flex flex-col gap-3 rounded-xl border border-surface-highlight bg-surface-dark/50 p-4">
                        <View className="flex-row items-center gap-2">
                            <MaterialIcons name="info" size={20} color="#0d7ff2" />
                            <Text className="text-sm font-bold text-white">차량 등록이 필요한 이유</Text>
                        </View>
                        <Text className="text-xs text-slate-400 leading-relaxed">
                            정확한 AI 진단과 소모품 교체 주기를 예측하기 위해 차량 정보가 필수적입니다. 등록된 데이터는 암호화되어 안전하게 보관됩니다.
                        </Text>
                    </View>
                </View>

                <View className="h-10" />
            </View>
        </BaseScreen>
    );
}
