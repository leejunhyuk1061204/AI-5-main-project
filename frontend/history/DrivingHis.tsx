import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Platform, Dimensions, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import Svg, { Circle, Path, Defs, LinearGradient, Stop } from 'react-native-svg';
import AsyncStorage from '@react-native-async-storage/async-storage';
import tripApi, { TripSummary } from '../api/tripApi';

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
    const [trips, setTrips] = useState<TripSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({
        totalDistance: 0,
        avgScore: 0,
        avgFuelEff: 0,
        safetyRate: 0 // Simply using avgScore as safety rate for now
    });

    // Weekly Graph Data (Mon-Sun)
    const [weeklyData, setWeeklyData] = useState<number[]>(Array(7).fill(0));

    useEffect(() => {
        loadTrips();
    }, []);

    const loadTrips = async () => {
        try {
            const stored = await AsyncStorage.getItem('primaryVehicle');
            if (stored) {
                const vehicle = JSON.parse(stored);
                // Fetch trips for ONLY the primary vehicle
                const response = await tripApi.getTrips(vehicle.vehicleId);
                if (response.success && response.data) {
                    processTrips(response.data);
                }
            } else {
                // Handle no primary vehicle
            }
        } catch (e) {
            console.error('Failed to load trips', e);
        } finally {
            setLoading(false);
        }
    };

    const processTrips = (data: TripSummary[]) => {
        if (data.length === 0) {
            setTrips([]);
            return;
        }

        // Sort by date desc
        const sorted = [...data].sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime());
        setTrips(sorted);

        // Calculate Totals
        const totalDist = data.reduce((acc, cur) => acc + (cur.distance || 0), 0);
        const totalScore = data.reduce((acc, cur) => acc + (cur.driveScore || 0), 0);
        const totalFuel = data.reduce((acc, cur) => acc + (cur.fuelConsumed || 0), 0);

        const avgScore = totalScore / data.length;
        const avgFuelEff = totalFuel > 0 ? (totalDist / totalFuel) : 0;

        setStats({
            totalDistance: totalDist,
            avgScore: Math.round(avgScore),
            avgFuelEff: parseFloat(avgFuelEff.toFixed(1)),
            safetyRate: Math.round(avgScore) // Using score as safety percentage
        });

        // Process Weekly Data
        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - today.getDay() + 1); // Get Monday
        monday.setHours(0, 0, 0, 0);

        const dailyScores = Array(7).fill({ sum: 0, count: 0 });

        data.forEach(trip => {
            const tripDate = new Date(trip.startTime);
            // Check if trip is within this week (roughly)
            // Ideally should check correctly against week start
            // For simplicity, mapping day of week (0=Sun, 1=Mon...)
            let dayIdx = tripDate.getDay() - 1;
            if (dayIdx === -1) dayIdx = 6; // Sun is 6

            // Accumulate
            dailyScores[dayIdx] = {
                sum: dailyScores[dayIdx].sum + trip.driveScore,
                count: dailyScores[dayIdx].count + 1
            };
        });

        const chartData = dailyScores.map(d => d.count > 0 ? d.sum / d.count : 0); // Default to 0 if no data
        setWeeklyData(chartData);
    };

    // Calculate score color
    const getScoreColor = (score: number) => {
        if (score >= 90) return '#0d7ff2';
        if (score >= 70) return '#0bda5b';
        return '#f59e0b';
    };

    if (loading) {
        return (
            <SafeAreaView className="flex-1 bg-[#10151A] items-center justify-center">
                <ActivityIndicator size="large" color="#0d7ff2" />
            </SafeAreaView>
        );
    }

    return (
        <SafeAreaView className="flex-1 bg-[#10151A]">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 py-3 border-b border-gray-800 bg-[#10151A]/95">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-gray-800"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">주행 이력 분석</Text>
                <TouchableOpacity className="w-10 h-10 items-center justify-center rounded-full active:bg-gray-800">
                    <MaterialIcons name="more-vert" size={24} color="white" />
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
                            <View className="items-center justify-center py-6 relative">
                                {/* Background mesh effect approximation */}
                                <View className="absolute inset-0 opacity-10" style={{
                                    backgroundColor: 'transparent',
                                }} />

                                <Text className="text-gray-400 text-xs font-medium tracking-widest uppercase mb-6">종합 안전 점수</Text>

                                <View className="relative w-64 h-64 justify-center items-center">
                                    <View className="absolute inset-0 rounded-full border border-gray-800 border-dashed" style={{ opacity: 0.5 }} />

                                    <Svg height="250" width="250" viewBox="0 0 100 100" style={{ transform: [{ rotate: '-90deg' }] }}>
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
                                        <Text className="text-6xl font-bold text-white tracking-tighter" style={{ textShadowColor: 'rgba(13, 127, 242, 0.5)', textShadowOffset: { width: 0, height: 0 }, textShadowRadius: 10 }}>
                                            {stats.avgScore}
                                        </Text>
                                        <Text className="text-[#0d7ff2] text-sm font-bold mt-1 tracking-widest uppercase">
                                            {stats.avgScore >= 90 ? '최우수 등급' : stats.avgScore >= 70 ? '양호' : '주의 필요'}
                                        </Text>
                                    </View>
                                </View>

                                {/* Stats Row */}
                                <View className="flex-row justify-between w-full max-w-[300px] mt-6 px-4">
                                    <View className="items-center">
                                        <Text className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">총 주행 거리</Text>
                                        <Text className="text-lg font-bold text-white">{stats.totalDistance.toLocaleString()} <Text className="text-xs text-gray-400 font-normal">km</Text></Text>
                                    </View>
                                    <View className="w-px h-10 bg-gray-800" />
                                    <View className="items-center">
                                        <Text className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">안전 운행</Text>
                                        <Text className="text-lg font-bold text-[#0bda5b]">{stats.safetyRate}%</Text>
                                    </View>
                                    <View className="w-px h-10 bg-gray-800" />
                                    <View className="items-center">
                                        <Text className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">평균 연비</Text>
                                        <Text className="text-lg font-bold text-[#1E90FF]">{stats.avgFuelEff} <Text className="text-xs text-gray-400 font-normal">km/L</Text></Text>
                                    </View>
                                </View>
                            </View>

                            {/* Chart Section - Simplified for MVP without full graph library */}
                            {/* Visual representation of weekly safety trend */}
                            <View className="bg-[#161F29] border border-gray-800 rounded-xl p-5 overflow-hidden">
                                <View className="flex-row justify-between items-center mb-6">
                                    <Text className="text-white text-base font-bold">주간 안전 지수 변화</Text>
                                    <View className="bg-[#0d7ff2]/20 border border-[#0d7ff2]/30 px-2 py-1 rounded">
                                        <Text className="text-xs text-[#0d7ff2]">이번주</Text>
                                    </View>
                                </View>

                                <View className="h-40 w-full relative flex-row items-end justify-between px-2 pb-6">
                                    {/* Bars instead of complex path for creating simpler dynamic graph */}
                                    {weeklyData.map((score, idx) => (
                                        <View key={idx} className="items-center gap-2">
                                            <View
                                                className="w-2 rounded-full bg-blue-500"
                                                style={{
                                                    height: `${Math.max(score, 10)}%`, // Minimum height for visibility
                                                    backgroundColor: score >= 90 ? '#0d7ff2' : score > 0 ? '#0bda5b' : '#374151'
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
                                    <TouchableOpacity>
                                        <Text className="text-[#0d7ff2] text-sm font-medium">전체보기</Text>
                                    </TouchableOpacity>
                                </View>

                                {/* List Mapping */}
                                <View className="gap-3">
                                    {trips.slice(0, 5).map((trip, index) => (
                                        <View key={index} className="bg-[#161F29] rounded-xl border border-[#0d7ff2]/30 p-4 relative overflow-hidden">
                                            <View className="flex-row justify-between items-center mb-4">
                                                <View className="flex-row items-center gap-3">
                                                    <View className="bg-[#0d7ff2]/10 p-2 rounded-full border border-[#0d7ff2]/20">
                                                        <MaterialIcons name="commute" size={24} color="#0d7ff2" />
                                                    </View>
                                                    <Text className="text-white font-bold text-lg">{formatDate(trip.startTime)}</Text>
                                                </View>
                                                <View className="flex-row items-center gap-1 bg-gray-800/50 px-2 py-1 rounded border border-gray-700">
                                                    <View className="w-2 h-2 rounded-full bg-[#0bda5b]" style={{ shadowColor: '#0bda5b', shadowOpacity: 0.5, shadowRadius: 5 }} />
                                                    <Text className="text-xs font-medium text-gray-300">{trip.driveScore}점</Text>
                                                </View>
                                            </View>

                                            <View className="flex-row flex-wrap gap-3">
                                                <View className="flex-1 min-w-[45%] bg-[#10151A]/50 p-3 rounded-lg border border-gray-800">
                                                    <Text className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">주행 거리</Text>
                                                    <Text className="text-white font-medium text-base">{trip.distance.toFixed(1)} <Text className="text-xs text-gray-400">km</Text></Text>
                                                </View>
                                                <View className="flex-1 min-w-[45%] bg-[#10151A]/50 p-3 rounded-lg border border-gray-800">
                                                    <Text className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">평균 속도</Text>
                                                    <Text className="text-white font-medium text-base">{trip.averageSpeed.toFixed(0)} <Text className="text-xs text-gray-400">km/h</Text></Text>
                                                </View>
                                            </View>
                                        </View>
                                    ))}
                                </View>
                            </View>
                        </>
                    )}
                </View>
            </ScrollView>
        </SafeAreaView>
    );
}
