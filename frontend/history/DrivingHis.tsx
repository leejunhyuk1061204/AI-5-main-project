import React, { useEffect, useState, useMemo } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Platform, Dimensions, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import Svg, { Circle } from 'react-native-svg';
import tripApi, { TripSummary } from '../api/tripApi';
import VehicleSelectModal from '../components/VehicleSelectModal';
import { useAlertStore } from '../store/useAlertStore';
import { useVehicleStore } from '../store/useVehicleStore';
import { VehicleResponse } from '../api/vehicleApi';

const { width } = Dimensions.get('window');

// Helper to format date
const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    const mm = date.getMonth() + 1;
    const dd = date.getDate();
    const day = ['일', '월', '화', '수', '목', '금', '토'][date.getDay()];
    return `${date.getFullYear()}.${mm}.${dd} (${day})`;
};

export default function DrivingHis() {
    const navigation = useNavigation();
    const { vehicles, primaryVehicle } = useVehicleStore();
    const [selectedVehicle, setSelectedVehicle] = useState<Partial<VehicleResponse> | null>(null);
    const [trips, setTrips] = useState<TripSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [vehicleSelectModalVisible, setVehicleSelectModalVisible] = useState(false);
    const [vehicleChangeTripId, setVehicleChangeTripId] = useState<string | null>(null);
    const [changing, setChanging] = useState(false);
    const showAlert = useAlertStore((s) => s.showAlert);

    useEffect(() => {
        if (primaryVehicle) {
            setSelectedVehicle(primaryVehicle);
        } else if (vehicles.length > 0) {
            setSelectedVehicle(vehicles[0]);
        }
    }, [primaryVehicle, vehicles]);

    // Derived State using useMemo
    const stats = useMemo(() => {
        if (trips.length === 0) {
            return { totalDistance: 0, avgScore: 0, avgFuelEff: 0, safetyRate: 0 };
        }

        const totalDist = trips.reduce((acc, cur) => acc + (cur.distance || 0), 0);
        const totalScore = trips.reduce((acc, cur) => acc + (cur.driveScore || 0), 0);
        const totalFuel = trips.reduce((acc, cur) => acc + (cur.fuelConsumed || 0), 0);

        const avgScore = totalScore / trips.length;
        const avgFuelEff = totalFuel > 0 ? (totalDist / totalFuel) : 0;

        return {
            totalDistance: totalDist,
            avgScore: Math.round(avgScore),
            avgFuelEff: parseFloat(avgFuelEff.toFixed(1)),
            safetyRate: Math.round(avgScore)
        };
    }, [trips]);

    const weeklyData = useMemo(() => {
        if (trips.length === 0) return Array(7).fill(0);

        const today = new Date();
        const startOfWeek = new Date(today);
        const day = startOfWeek.getDay();
        const diff = startOfWeek.getDate() - day + (day === 0 ? -6 : 1);
        startOfWeek.setDate(diff);
        startOfWeek.setHours(0, 0, 0, 0);

        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setDate(startOfWeek.getDate() + 6);
        endOfWeek.setHours(23, 59, 59, 999);

        const dailyScores = Array(7).fill({ sum: 0, count: 0 });

        trips.forEach(trip => {
            const tripDate = new Date(trip.startTime);
            if (tripDate >= startOfWeek && tripDate <= endOfWeek) {
                let dayIdx = tripDate.getDay() - 1;
                if (dayIdx === -1) dayIdx = 6;
                dailyScores[dayIdx] = {
                    sum: dailyScores[dayIdx].sum + trip.driveScore,
                    count: dailyScores[dayIdx].count + 1
                };
            }
        });

        return dailyScores.map(d => d.count > 0 ? d.sum / d.count : 0);
    }, [trips]);

    useEffect(() => {
        if (selectedVehicle?.vehicleId) {
            loadTrips();
        } else {
            setTrips([]);
            setLoading(false);
        }
    }, [selectedVehicle?.vehicleId]);

    const loadTrips = async () => {
        if (!selectedVehicle?.vehicleId) return;
        setLoading(true);
        try {
            const response = await tripApi.getTrips(selectedVehicle.vehicleId);
            if (response.success && response.data) {
                const sorted = [...response.data].sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime());
                setTrips(sorted);
            } else {
                setTrips([]);
            }
        } catch (e) {
            console.error('Failed to load trips', e);
            setTrips([]);
        } finally {
            setLoading(false);
        }
    };

    const handleSelectVehicle = (vehicle: VehicleResponse) => {
        setSelectedVehicle(vehicle);
        setVehicleSelectModalVisible(false);
    };

    const handleChangeVehicleSelect = async (vehicle: { vehicleId: string }) => {
        if (!vehicleChangeTripId) return;
        setChanging(true);
        try {
            const res = await tripApi.changeTripVehicle(vehicleChangeTripId, vehicle.vehicleId);
            if (res.success) {
                showAlert('변경 완료', '해당 주행이 선택한 차량으로 재할당되었습니다.', 'SUCCESS');
                setVehicleChangeTripId(null);
                await loadTrips();
            }
        } catch (e) {
            console.error('Change trip vehicle failed', e);
            showAlert('변경 실패', '차량 재할당에 실패했습니다. 다시 시도해주세요.', 'ERROR');
        } finally {
            setChanging(false);
        }
    };

    // Removed processTrips, logic moved to useMemo


    // Calculate score color
    const getScoreColor = (score: number) => {
        if (score >= 90) return '#0d7ff2';
        if (score >= 70) return '#0d7ff2';
        return '#f59e0b';
    };

    if (loading) {
        return (
            <SafeAreaView className="flex-1 bg-background-dark items-center justify-center">
                <ActivityIndicator size="large" color="#0d7ff2" />
            </SafeAreaView>
        );
    }

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 py-3 border-b border-gray-800 bg-background-dark/95">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-gray-800"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">주행 이력 분석</Text>
                <TouchableOpacity
                    onPress={() => setVehicleSelectModalVisible(true)}
                    className="flex-row items-center gap-1.5 bg-white/5 py-2 px-3 rounded-xl border border-white/10 min-w-[80]"
                >
                    <Text className="text-white font-bold text-sm" numberOfLines={1}>
                        {selectedVehicle?.modelNameKo || selectedVehicle?.manufacturerKo || '차량 선택'}
                    </Text>
                    <MaterialIcons name="keyboard-arrow-down" size={16} color="#94a3b8" />
                </TouchableOpacity>
            </View>

            <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
                <View className="p-4 gap-6 pb-8">

                    {trips.length === 0 ? (
                        <View className="items-center justify-center py-20">
                            <MaterialIcons name="directions-car" size={64} color="#374151" />
                            <Text className="text-gray-500 mt-4 text-base">아직 주행 기록이 없습니다.</Text>
                        </View>
                    ) : (
                        <>
                            {/* Score Section */}
                            <View className="items-center justify-center py-2 relative">
                                {/* Background mesh effect approximation */}
                                <View className="absolute inset-0 opacity-10" style={{
                                    backgroundColor: 'transparent',
                                }} />

                                <Text className="text-gray-400 text-xs font-medium tracking-widest uppercase mb-2">종합 안전 점수</Text>

                                <View className="relative w-48 h-48 justify-center items-center">
                                    <View className="absolute inset-0 rounded-full border border-gray-800 border-dashed" style={{ opacity: 0.5 }} />

                                    <Svg height="180" width="180" viewBox="0 0 100 100" style={{ transform: [{ rotate: '-90deg' }] }}>
                                        <Circle
                                            cx="50"
                                            cy="50"
                                            r="40"
                                            stroke="#161F29"
                                            strokeWidth="8"
                                            fill="transparent"
                                        />
                                        <Circle
                                            cx="50"
                                            cy="50"
                                            r="40"
                                            stroke={getScoreColor(stats.avgScore)}
                                            strokeWidth="8"
                                            fill="transparent"
                                            strokeDasharray="251.2"
                                            strokeDashoffset={251.2 * (1 - stats.avgScore / 100)} // Dynamic Stroke
                                            strokeLinecap="round"
                                        />
                                    </Svg>

                                    <View className="absolute inset-0 items-center justify-center">
                                        <Text className="text-5xl font-bold text-white tracking-tighter" style={{ textShadowColor: 'rgba(13, 127, 242, 0.5)', textShadowOffset: { width: 0, height: 0 }, textShadowRadius: 10 }}>
                                            {stats.avgScore}
                                        </Text>
                                        <Text className="text-[#0d7ff2] text-xs font-bold mt-1 tracking-widest uppercase">
                                            {stats.avgScore >= 90 ? '최우수 등급' : stats.avgScore >= 70 ? '양호' : '주의 필요'}
                                        </Text>
                                    </View>
                                </View>

                                {/* Stats Row */}
                                <View className="flex-row justify-between w-full max-w-[300px] mt-4 px-4">
                                    <View className="items-center">
                                        <Text className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">총 주행 거리</Text>
                                        <Text className="text-lg font-bold text-white">{stats.totalDistance.toLocaleString()} <Text className="text-xs text-gray-400 font-normal">km</Text></Text>
                                    </View>
                                    <View className="w-px h-8 bg-gray-800" />
                                    <View className="items-center">
                                        <Text className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">안전 운행</Text>
                                        <Text className="text-lg font-bold text-[#0d7ff2]">{stats.safetyRate}%</Text>
                                    </View>
                                    <View className="w-px h-8 bg-gray-800" />
                                    <View className="items-center">
                                        <Text className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">평균 연비</Text>
                                        <Text className="text-lg font-bold text-[#1E90FF]">{stats.avgFuelEff} <Text className="text-xs text-gray-400 font-normal">km/L</Text></Text>
                                    </View>
                                </View>
                            </View>

                            {/* Chart Section - Simplified for MVP without full graph library */}
                            {/* Visual representation of weekly safety trend */}
                            <View className="bg-surface-dark border border-gray-800 rounded-xl p-4 overflow-hidden mb-2">
                                <View className="flex-row justify-between items-center mb-4">
                                    <Text className="text-white text-sm font-bold">주간 안전 지수 변화</Text>
                                    <View className="bg-primary/20 border border-primary/30 px-2 py-0.5 rounded">
                                        <Text className="text-[10px] text-primary">이번주</Text>
                                    </View>
                                </View>

                                <View className="h-24 w-full relative flex-row items-end justify-between px-2 pb-2">
                                    {/* Bars instead of complex path for creating simpler dynamic graph */}
                                    {weeklyData.map((score, idx) => (
                                        <View key={idx} className="items-center gap-1">
                                            <View
                                                className="w-2 rounded-full bg-blue-500"
                                                style={{
                                                    height: `${Math.max(score, 10)}%`, // Minimum height for visibility
                                                    backgroundColor: score >= 90 ? '#0d7ff2' : score > 0 ? '#0d7ff2' : '#374151'
                                                }}
                                            />
                                            <Text className="text-[10px] text-gray-500">
                                                {['월', '화', '수', '목', '금', '토', '일'][idx]}
                                            </Text>
                                        </View>
                                    ))}
                                </View>
                            </View>

                            {/* Recent History Section */}
                            <View>
                                <View className="flex-row items-center justify-between mb-4 px-1">
                                    <Text className="text-white text-lg font-bold">최근 주행 기록</Text>
                                    <TouchableOpacity onPress={() => navigation.navigate('DrivingList' as never)}>
                                        <Text className="text-[#0d7ff2] text-sm font-medium">전체보기</Text>
                                    </TouchableOpacity>
                                </View>

                                {/* List Mapping - Show only 1 recent */}
                                <View className="gap-3">
                                    {trips.slice(0, 5).map((trip, index) => (
                                        <TouchableOpacity
                                            key={index}
                                            activeOpacity={0.7}
                                            onPress={() => (navigation as any).navigate('TripDetail', { tripId: trip.tripId })}
                                            className="bg-surface-dark rounded-xl border border-primary/30 p-4 relative overflow-hidden"
                                        >
                                            <View className="flex-row justify-between items-center mb-4">
                                                <View className="flex-row items-center gap-3">
                                                    <View className="bg-primary/10 p-2 rounded-full border border-primary/20">
                                                        <MaterialIcons name="commute" size={24} color="#0d7ff2" />
                                                    </View>
                                                    <Text className="text-white font-bold text-lg">{formatDate(trip.startTime)}</Text>
                                                </View>
                                                {/* Score Badge */}
                                                <View className="flex-row items-center gap-1 bg-surface-highlight/20 px-3 py-1.5 rounded-full border border-gray-700">
                                                    <View className={`w-2 h-2 rounded-full ${trip.driveScore >= 80 ? 'bg-primary' : trip.driveScore >= 60 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ shadowColor: '#0d7ff2', shadowOpacity: 0.5, shadowRadius: 5 }} />
                                                    <Text className="text-sm font-bold text-white">{trip.driveScore}점</Text>
                                                </View>
                                            </View>

                                            <View className="flex-row flex-wrap gap-3">
                                                <View className="flex-1 min-w-[45%] bg-background-dark/50 p-3 rounded-lg border border-gray-800">
                                                    <Text className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">주행 거리</Text>
                                                    <Text className="text-white font-medium text-base">{trip.distance.toFixed(1)} <Text className="text-xs text-gray-400">km</Text></Text>
                                                </View>
                                                <View className="flex-1 min-w-[45%] bg-background-dark/50 p-3 rounded-lg border border-gray-800">
                                                    <Text className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">평균 속도</Text>
                                                    <Text className="text-white font-medium text-base">{trip.averageSpeed.toFixed(0)} <Text className="text-xs text-gray-400">km/h</Text></Text>
                                                </View>
                                            </View>
                                            <TouchableOpacity
                                                className="mt-3 flex-row items-center gap-1 self-start"
                                                onPress={() => setVehicleChangeTripId(trip.tripId)}
                                                disabled={changing}
                                            >
                                                <MaterialIcons name="swap-horiz" size={16} color="#0d7ff2" />
                                                <Text className="text-[#0d7ff2] text-xs font-medium">차량 변경</Text>
                                            </TouchableOpacity>
                                        </TouchableOpacity>
                                    ))}
                                </View>
                            </View>
                        </>
                    )}
                </View>
            </ScrollView>

            <VehicleSelectModal
                visible={vehicleSelectModalVisible}
                onClose={() => setVehicleSelectModalVisible(false)}
                onSelect={handleSelectVehicle}
                title="주행 이력 조회할 차량 선택"
                description="선택한 차량의 주행 기록을 표시합니다."
            />
            <VehicleSelectModal
                visible={vehicleChangeTripId !== null}
                onClose={() => !changing && setVehicleChangeTripId(null)}
                onSelect={handleChangeVehicleSelect}
                title="이 주행을 할당할 차량 선택"
                description="선택한 차량으로 해당 주행 기록이 재할당됩니다."
            />
        </SafeAreaView>
    );
}
