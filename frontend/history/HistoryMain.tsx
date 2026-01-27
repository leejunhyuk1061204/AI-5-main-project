import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Header from '../header/Header';
import tripApi from '../api/tripApi';
import BaseScreen from '../components/layout/BaseScreen';

export default function HistoryMain() {
    const navigation = useNavigation();
    const [tripStats, setTripStats] = useState<{
        totalScore: number;
        avgSpeed: number;
        totalFuel: number;
        hasData: boolean;
    }>({ totalScore: 0, avgSpeed: 0, totalFuel: 0, hasData: false });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadTripStats();
        const unsubscribe = navigation.addListener('focus', loadTripStats);
        return unsubscribe;
    }, [navigation]);

    const loadTripStats = async () => {
        try {
            const stored = await AsyncStorage.getItem('primaryVehicle');
            if (stored) {
                const vehicle = JSON.parse(stored);
                const response = await tripApi.getTrips(vehicle.vehicleId);
                if (response.success && response.data && response.data.length > 0) {
                    const trips = response.data;
                    const totalScore = Math.round(
                        trips.reduce((acc, t) => acc + (t.driveScore || 0), 0) / trips.length
                    );
                    const avgSpeed = Math.round(
                        trips.reduce((acc, t) => acc + (t.averageSpeed || 0), 0) / trips.length
                    );
                    const totalFuel = parseFloat(
                        trips.reduce((acc, t) => acc + (t.fuelConsumed || 0), 0).toFixed(1)
                    );
                    setTripStats({ totalScore, avgSpeed, totalFuel, hasData: true });
                } else {
                    setTripStats({ totalScore: 0, avgSpeed: 0, totalFuel: 0, hasData: false });
                }
            }
        } catch (e) {
            console.error('Failed to load trip stats', e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <BaseScreen
            header={<Header />}
            padding={false}
            useBottomNav={true}
        >
            <View className="px-6 gap-5 pb-6 mt-4">
                {/* Card 1: Driving History Analysis */}
                <TouchableOpacity
                    onPress={() => navigation.navigate('DrivingHis' as never)}
                    className="w-full bg-white/5 border border-white/10 rounded-2xl p-6 active:bg-white/10"
                >
                    <View className="flex-row justify-between items-start mb-6">
                        <View className="flex-col gap-1">
                            <View className="flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 self-start">
                                <View className="w-1.5 h-1.5 rounded-full bg-primary" />
                                <Text className="text-xs font-bold text-primary uppercase tracking-wider">Analysis</Text>
                            </View>
                            <Text className="text-lg font-bold text-white mt-2">주행 이력 분석</Text>
                            <Text className="text-sm font-medium text-text-muted mt-0.5">
                                {tripStats.hasData ? '최근 주행 기반 데이터' : '주행 기록 없음'}
                            </Text>
                        </View>
                        <View className="flex-col items-center justify-center mr-10">
                            {loading ? (
                                <ActivityIndicator size="small" color="#0d7ff2" />
                            ) : tripStats.hasData ? (
                                <>
                                    <Text className="text-7xl font-bold text-primary tracking-tighter leading-none">
                                        {tripStats.totalScore}
                                    </Text>
                                    <Text className="text-xs text-white font-bold uppercase tracking-widest mt-1">Total Score</Text>
                                </>
                            ) : (
                                <>
                                    <Text className="text-4xl font-bold text-text-dim tracking-tighter leading-none">--</Text>
                                    <Text className="text-xs text-text-muted font-bold uppercase tracking-widest mt-1">No Data</Text>
                                </>
                            )}
                        </View>
                    </View>

                    <View className="flex-row gap-3 mt-4">
                        <View className="flex-1 bg-surface-card rounded-xl p-4 border border-white/10 flex-col gap-1">
                            <Text className="text-text-muted text-sm font-medium mb-1">평균 속도</Text>
                            <View className="flex-row items-baseline gap-1">
                                <Text className="text-xl font-bold text-white">
                                    {tripStats.hasData ? tripStats.avgSpeed : '--'}
                                </Text>
                                <Text className="text-xs text-text-dim font-semibold">km/h</Text>
                            </View>
                        </View>
                        <View className="flex-1 bg-surface-card rounded-xl p-4 border border-white/10 flex-col gap-1">
                            <Text className="text-text-muted text-sm font-medium mb-1">소모 연료량</Text>
                            <View className="flex-row items-baseline gap-1">
                                <Text className="text-xl font-bold text-white">
                                    {tripStats.hasData ? tripStats.totalFuel : '--'}
                                </Text>
                                <Text className="text-xs text-text-dim font-semibold">L</Text>
                            </View>
                        </View>
                    </View>
                </TouchableOpacity>

                {/* Card 2: Consumables Management */}
                <TouchableOpacity
                    onPress={() => navigation.navigate('SupManage' as never)}
                    className="w-full bg-white/5 border border-white/10 rounded-2xl p-6 active:bg-white/10"
                >
                    <View className="flex-row justify-between items-center">
                        <View className="flex-col gap-1">
                            <View className="flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 self-start">
                                <MaterialIcons name="build" size={10} color="#0d7ff2" />
                                <Text className="text-xs font-bold text-primary uppercase tracking-wider">Prediction</Text>
                            </View>
                            <Text className="text-lg font-bold text-white mt-2">소모품 관리 및 예지</Text>
                            <Text className="text-sm text-text-muted">엔진 오일 잔여 수명 예측</Text>
                        </View>
                    </View>
                </TouchableOpacity>

                {/* Card 2.5: AI Diagnosis History (NEW) */}
                <TouchableOpacity
                    onPress={() => navigation.navigate('DiagnosisHistory' as never)}
                    className="w-full bg-white/5 border border-white/10 rounded-2xl p-6 active:bg-white/10"
                >
                    <View className="flex-row justify-between items-center">
                        <View className="flex-col gap-1">
                            <View className="flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 self-start">
                                <MaterialIcons name="auto-awesome" size={10} color="#0d7ff2" />
                                <Text className="text-xs font-bold text-primary uppercase tracking-wider">AI Report</Text>
                            </View>
                            <Text className="text-lg font-bold text-white mt-2">AI 진단 내역</Text>
                            <Text className="text-sm text-text-muted">진행했던 모든 AI 분석 보고서 보기</Text>
                        </View>
                        <MaterialIcons name="chevron-right" size={24} color="#64748b" />
                    </View>
                </TouchableOpacity>

                {/* Card 3: Vehicle Detailed Specs */}
                <TouchableOpacity
                    onPress={() => navigation.navigate('Spec' as never)}
                    className="w-full bg-white/5 border border-white/10 rounded-2xl p-6 active:bg-white/10"
                >
                    <View className="flex-row justify-between items-center">
                        <View className="flex-col gap-1">
                            <View className="flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 self-start">
                                <MaterialIcons name="fact-check" size={10} color="primary" />
                                <Text className="text-xs font-bold text-primary uppercase tracking-wider">Specs</Text>
                            </View>
                            <Text className="text-lg font-bold text-white mt-2">차량 상세 제원</Text>
                            <Text className="text-sm text-text-muted">제조사 공식 데이터베이스</Text>
                        </View>
                        <MaterialIcons name="arrow-forward-ios" size={16} color="text-dim" />
                    </View>
                </TouchableOpacity>

                {/* Card 4: Regular Inspection */}
                <TouchableOpacity
                    onPress={() => navigation.navigate('RecallHis' as never)}
                    className="w-full bg-white/5 border border-white/10 rounded-2xl p-6 flex-row items-center justify-between active:bg-white/10"
                >
                    <View className="flex-col gap-1 z-10 flex-1">
                        <View className="flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 self-start mb-2">
                            <MaterialIcons name="verified-user" size={10} color="primary" />
                            <Text className="text-sm font-bold text-primary uppercase tracking-wider">Official</Text>
                        </View>
                        <Text className="text-lg font-bold text-white">정기 검사 및 리콜</Text>
                        <Text className="text-sm text-text-muted">다음 정기 검사까지</Text>
                    </View>
                    <View className="relative flex-col items-center justify-center p-3">
                        <Text className="text-3xl font-extrabold text-white tracking-tight">D-14</Text>
                        <Text className="text-sm font-bold text-primary uppercase tracking-wider mt-1">Days left</Text>
                    </View>
                </TouchableOpacity>
            </View>
        </BaseScreen>
    );
}
