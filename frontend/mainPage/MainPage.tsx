import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import Svg, { Circle, Defs, LinearGradient, Stop } from 'react-native-svg';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import tripApi from '../api/tripApi';
import Header from '../header/Header';
import BaseScreen from '../components/layout/BaseScreen';
import { useVehicleStore } from '../store/useVehicleStore';
import ObdService from '../services/ObdService';

export default function MainPage() {
    const navigation = useNavigation<any>();
    const { primaryVehicle, fetchVehicles } = useVehicleStore();
    const [safetyScore, setSafetyScore] = useState(95);

    // Auto-connect OBD on mount
    // Auto-connect OBD on mount
    useEffect(() => {
        const initObd = async () => {
            // 잠시 지연 후 시도하여 네비게이션 트랜지션 부하 분산
            setTimeout(() => {
                ObdService.tryAutoConnect();
            }, 1000);
        };
        initObd();
    }, []);

    useEffect(() => {
        fetchVehicles();
        const unsubscribe = navigation.addListener('focus', fetchVehicles);
        return unsubscribe;
    }, [navigation]);

    useEffect(() => {
        if (primaryVehicle && primaryVehicle.vehicleId) {
            calculateSafetyScore(primaryVehicle.vehicleId);
        }
    }, [primaryVehicle]);

    const calculateSafetyScore = async (vehicleId: string) => {
        try {
            const tripsResponse = await tripApi.getTrips(vehicleId);
            const trips = Array.isArray(tripsResponse) ? tripsResponse : (tripsResponse as any).data;

            if (trips && trips.length > 0) {
                const totalScore = trips.reduce((sum: number, trip: any) => sum + (trip.driveScore || 0), 0);
                const avgScore = Math.round(totalScore / trips.length);
                setSafetyScore(avgScore);
            } else {
                setSafetyScore(95);
            }
        } catch (tripError) {
            console.log('Failed to load trips for score:', tripError);
        }
    };

    // fallback for display
    const currentVehicle = primaryVehicle || {
        modelName: '차량을 등록해주세요',
        carNumber: '- - -',
        totalMileage: 0,
        fuelType: null
    };

    return (
        <BaseScreen
            header={<Header />}
            padding={false}
        >
            {/* Car Info Card */}
            <View className="px-6 py-4">
                <View className="relative overflow-hidden rounded-xl bg-white/5 border border-white/10 p-4 flex-row items-center justify-between shadow-lg">
                    <View className="flex-row items-center gap-4 z-10">
                        <View className="w-12 h-12 rounded-lg bg-surface-card border border-white/10 items-center justify-center shadow-inner">
                            <MaterialIcons name="directions-car" size={24} color="#d1d5db" />
                        </View>
                        <View>
                            <Text className="text-white text-base font-bold leading-tight">{currentVehicle.modelName}</Text>
                            <Text className="text-text-muted text-sm font-normal">{currentVehicle.carNumber}</Text>
                        </View>
                    </View>
                    <TouchableOpacity
                        className="flex-row items-center gap-1 bg-primary/10 px-3 py-1.5 rounded-full border border-primary/20"
                        onPress={() => navigation.navigate('Spec')}
                    >
                        <Text className="text-primary text-sm font-bold">상세</Text>
                        <MaterialIcons name="chevron-right" size={16} color="#0d7ff2" />
                    </TouchableOpacity>
                </View>
            </View>

            {/* Health Score Circular Chart */}
            <View className="items-center justify-center py-6 relative">
                <View className="relative w-64 h-64 items-center justify-center">
                    <Svg width="100%" height="100%" viewBox="0 0 100 100" className="-rotate-90">
                        <Defs>
                            <LinearGradient id="blueGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                <Stop offset="0%" stopColor="#00f2fe" />
                                <Stop offset="100%" stopColor="#0d7ff2" />
                            </LinearGradient>
                        </Defs>
                        <Circle
                            cx="50"
                            cy="50"
                            r="42"
                            stroke="#17212b"
                            strokeWidth="6"
                            fill="transparent"
                        />

                    </Svg>
                    <View className="absolute inset-0 items-center justify-center z-10">
                        <Text className="text-text-muted text-sm font-medium tracking-wide mb-1">종합 점수</Text>
                        <Text className="text-6xl font-bold text-white tracking-tighter">
                            {safetyScore}<Text className="text-2xl text-text-dim font-normal">점</Text>
                        </Text>
                        <View className="mt-3 flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-success/10 border border-success/20">
                            <View className="w-1.5 h-1.5 rounded-full bg-success" />
                            <Text className="text-success text-xs font-bold">상태 최상</Text>
                        </View>
                    </View>
                </View>
            </View>

            {/* Status Grid */}
            <View className="px-6 mb-6">
                <View className="flex-row items-center mb-4">
                    <Text className="text-white text-lg font-bold">실시간 상태</Text>
                    <View className="h-px bg-white/5 flex-1 ml-4" />
                </View>
                <View className="flex-row gap-3">
                    {[
                        { label: '엔진', icon: 'settings' },
                        { label: '배터리', icon: 'battery-full' },
                        { label: '타이어', icon: 'car-repair' }
                    ].map((item, index) => (
                        <TouchableOpacity
                            key={index}
                            className="flex-1 aspect-square rounded-xl bg-white/5 border border-white/10 items-center justify-center gap-3"
                            activeOpacity={0.7}
                        >
                            <MaterialIcons name={item.icon as any} size={32} color="#0d7ff2" />
                            <Text className="text-gray-300 text-sm font-medium">{item.label}</Text>
                        </TouchableOpacity>
                    ))}
                </View>
            </View>

            {/* Membership Promotion Card */}
            <View className="px-6 pb-4">
                <TouchableOpacity
                    className="relative overflow-hidden rounded-xl border border-premium/30 p-5"
                    activeOpacity={0.9}
                    onPress={() => navigation.navigate('Membership')}
                >
                    <View className="absolute inset-0 bg-premium/5" />
                    <View className="flex-row items-center justify-between mb-2">
                        <View className="flex-row items-center gap-2">
                            <MaterialIcons name="workspace-premium" size={20} color="#c5a059" />
                            <Text className="text-premium text-xs font-bold tracking-wider uppercase">Premium Membership</Text>
                        </View>
                        <MaterialIcons name="arrow-forward-ios" size={14} color="#78716c" />
                    </View>
                    <Text className="text-white text-lg font-bold mb-1">프리미엄 멤버십 혜택</Text>
                    <Text className="text-text-secondary text-sm mb-4 leading-relaxed">
                        AI 기반 정밀 진단과 무제한 리포트, 더 많은 혜택을 누려보세요.
                    </Text>
                    <View className="flex-row gap-2">
                        <View className="bg-premium/10 px-2 py-1 rounded border border-premium/20">
                            <Text className="text-premium text-xs font-medium">AI 정밀 진단</Text>
                        </View>
                        <View className="bg-premium/10 px-2 py-1 rounded border border-premium/20">
                            <Text className="text-premium text-xs font-medium">무제한 리포트</Text>
                        </View>
                    </View>
                </TouchableOpacity>
            </View>
        </BaseScreen>
    );
}
