import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Dimensions, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import Svg, { Circle, Defs, LinearGradient, Stop } from 'react-native-svg';
import { useNavigation } from '@react-navigation/native';
import BottomNav from '../nav/BottomNav';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getVehicleList, VehicleResponse } from '../api/vehicleApi';
import Header from '../header/Header';

export default function MainPage() {
    const navigation = useNavigation<any>();

    // 기본 차량 정보 (API 타입에 맞게 초기화 필요하지만, UI 표시용으로만 남김)
    const [vehicle, setVehicle] = useState<Partial<VehicleResponse>>({
        modelName: '차량을 등록해주세요',
        carNumber: '- - -',
        totalMileage: 0,
        fuelType: null
    });

    // 대표 차량 정보 불러오기 (API 연동)
    const loadPrimaryVehicle = async () => {

        try {
            const vehicles = await getVehicleList();
            const primary = vehicles.find(v => v.isPrimary) || vehicles[0]; // 대표 차량 없으면 첫 번째 차량

            if (primary) {
                setVehicle(primary);
                // 캐싱을 위해 로컬 저장 (선택 사항)
                await AsyncStorage.setItem('primaryVehicle', JSON.stringify(primary));
            } else {
                // 차량이 아예 없는 경우 초기화
                setVehicle({
                    modelName: '차량을 등록해주세요',
                    carNumber: '- - -',
                    totalMileage: 0,
                    fuelType: null
                });
            }
        } catch (e) {
            console.error('차량 목록 불러오기 실패:', e);
        }
    };

    useEffect(() => {
        loadPrimaryVehicle();

        // 화면 포커스 시마다 새로 불러오기
        const unsubscribe = navigation.addListener('focus', loadPrimaryVehicle);
        return unsubscribe;
    }, [navigation]);

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />
            <SafeAreaView className="flex-1" edges={['top']}>
                <Header />

                {/* Main Content ScrollView */}
                {/* Added bottom padding for navigation bar space */}
                <ScrollView
                    className="flex-1"
                    contentContainerStyle={{ paddingBottom: 250 }}
                    showsVerticalScrollIndicator={false}
                >

                    {/* Car Info Card */}
                    <View className="px-6 py-4">
                        <View className="relative overflow-hidden rounded-xl bg-[#ffffff08] border border-[#ffffff14] p-4 flex-row items-center justify-between shadow-lg">
                            {/* Background Glow simulation Removed */}

                            <View className="flex-row items-center gap-4 z-10">
                                <View className="w-12 h-12 rounded-lg bg-[#1b2127] border border-white/10 items-center justify-center shadow-inner">
                                    <MaterialIcons name="directions-car" size={24} color="#d1d5db" />
                                </View>
                                <View>
                                    <Text className="text-white text-base font-bold leading-tight">{vehicle.modelName}</Text>
                                    <Text className="text-[#9cabba] text-sm font-normal">{vehicle.carNumber}</Text>

                                </View>
                            </View>

                            <TouchableOpacity
                                className="flex-row items-center gap-1 bg-primary/10 px-3 py-1.5 rounded-full border border-primary/20 hover:bg-primary/20 z-10"
                                onPress={() => navigation.navigate('Spec')}
                            >
                                <Text className="text-primary text-sm font-bold">상세</Text>
                                <MaterialIcons name="chevron-right" size={16} color="#0d7ff2" />
                            </TouchableOpacity>
                        </View>
                    </View>

                    {/* Health Score Circular Chart */}
                    <View className="items-center justify-center py-6 relative">
                        {/* Background Glow Removed */}

                        <View className="relative w-64 h-64 items-center justify-center">
                            <Svg width="100%" height="100%" viewBox="0 0 100 100" className="-rotate-90">
                                <Defs>
                                    <LinearGradient id="blueGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                        <Stop offset="0%" stopColor="#00f2fe" />
                                        <Stop offset="100%" stopColor="#0d7ff2" />
                                    </LinearGradient>
                                </Defs>
                                {/* Background Circle */}
                                <Circle
                                    cx="50"
                                    cy="50"
                                    r="42"
                                    stroke="#1b2127"
                                    strokeWidth="6"
                                    fill="transparent"
                                />
                                {/* Progress Circle (approx 85% for 95 score look) */}
                                <Circle
                                    cx="50"
                                    cy="50"
                                    r="42"
                                    stroke="url(#blueGradient)"
                                    strokeWidth="6"
                                    fill="transparent"
                                    strokeDasharray="264"
                                    strokeDashoffset="13"
                                    strokeLinecap="round"
                                />
                            </Svg>

                            <View className="absolute inset-0 items-center justify-center z-10">
                                <Text className="text-[#9cabba] text-sm font-medium tracking-wide mb-1">종합 점수</Text>
                                <Text className="text-6xl font-bold text-white tracking-tighter">
                                    95<Text className="text-2xl text-gray-500 font-normal">점</Text>
                                </Text>

                                <View className="mt-3 flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-[#0bda5b]/10 border border-[#0bda5b]/20">
                                    <View className="w-1.5 h-1.5 rounded-full bg-[#0bda5b]" />
                                    <Text className="text-[#0bda5b] text-xs font-bold">상태 최상</Text>
                                </View>
                            </View>
                        </View>
                    </View>

                    {/* Status Grid */}
                    <View className="px-6 mb-6">
                        <View className="flex-row items-center mb-4">
                            <Text className="text-white text-lg font-bold">실시간 상태</Text>
                            <View className="h-px bg-slate-800 flex-1 ml-4" />
                        </View>

                        <View className="flex-row gap-3">
                            {[
                                { label: '엔진', icon: 'settings', lib: MaterialIcons },
                                { label: '배터리', icon: 'battery-full', lib: MaterialIcons },
                                { label: '타이어', icon: 'car-repair', lib: MaterialIcons } // tire-repair not in basic material
                            ].map((item, index) => (
                                <TouchableOpacity
                                    key={index}
                                    className="flex-1 aspect-square rounded-xl bg-[#ffffff08] border border-[#ffffff14] items-center justify-center gap-3 active:bg-white/5"
                                    activeOpacity={0.7}
                                >
                                    <item.lib name={item.icon as any} size={32} color="#0d7ff2" style={{ textShadowColor: 'rgba(13, 127, 242, 0.5)', textShadowRadius: 10 }} />
                                    <Text className="text-gray-300 text-sm font-medium">{item.label}</Text>
                                </TouchableOpacity>
                            ))}
                        </View>
                    </View>

                    {/* Membership Promotion Card */}
                    <View className="px-6 pb-4">
                        <TouchableOpacity
                            className="relative overflow-hidden rounded-xl border border-[#c5a059]/30 p-5 active:scale-[0.99]"
                            activeOpacity={0.9}
                            onPress={() => navigation.navigate('Membership')}
                        >
                            {/* Gradient Background */}
                            <View className="absolute inset-0 bg-gradient-to-br from-[#1c1917] to-[#0c0a09]" />
                            <View className="absolute inset-0 bg-[#c5a059]/5" />

                            <View className="flex-row items-center justify-between mb-2">
                                <View className="flex-row items-center gap-2">
                                    <MaterialIcons name="workspace-premium" size={20} color="#c5a059" />
                                    <Text className="text-[#c5a059] text-xs font-bold tracking-wider uppercase">Premium Membership</Text>
                                </View>
                                <MaterialIcons name="arrow-forward-ios" size={14} color="#78716c" />
                            </View>

                            <Text className="text-white text-lg font-bold mb-1">프리미엄 멤버십 혜택</Text>
                            <Text className="text-[#a8a29e] text-sm mb-4 leading-relaxed">
                                AI 기반 정밀 진단과 무제한 리포트, 더 많은 혜택을 누려보세요.
                            </Text>

                            <View className="flex-row gap-2">
                                <View className="bg-[#c5a059]/10 px-2 py-1 rounded border border-[#c5a059]/20">
                                    <Text className="text-[#c5a059] text-xs font-medium">AI 정밀 진단</Text>
                                </View>
                                <View className="bg-[#c5a059]/10 px-2 py-1 rounded border border-[#c5a059]/20">
                                    <Text className="text-[#c5a059] text-xs font-medium">무제한 리포트</Text>
                                </View>
                            </View>
                        </TouchableOpacity>
                    </View>

                </ScrollView>
            </SafeAreaView>
            <BottomNav />

        </View>
    );
}
