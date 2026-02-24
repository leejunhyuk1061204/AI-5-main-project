import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { MaterialIcons, FontAwesome5, Ionicons } from '@expo/vector-icons';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import tripApi, { TripSummary, TripObdLogDto } from '../api/tripApi';
import BaseScreen from '../components/layout/BaseScreen';
import { useAlertStore } from '../store/useAlertStore';

// 블루투스 OBD가 수집하는 PID만 (highPids: rpm,speed,throttle + normalPids)
const CSV_HEADER = 'timestamp,rpm,speed,voltage,coolantTemp,engineLoad,fuelTrimShort,fuelTrimLong,throttle,map,maf,intakeTemp,engineRuntime';

function obdLogToCsvRow(d: TripObdLogDto): string {
    const t = d.timestamp ?? '';
    const rpm = d.rpm ?? '';
    const speed = d.speed ?? '';
    const voltage = d.voltage ?? '';
    const coolantTemp = d.coolantTemp ?? '';
    const engineLoad = d.engineLoad ?? '';
    const fuelTrimShort = d.fuelTrimShort ?? '';
    const fuelTrimLong = d.fuelTrimLong ?? '';
    const throttle = d.throttlePos ?? '';
    const map = d.map ?? '';
    const maf = d.maf ?? '';
    const intakeTemp = d.intakeTemp ?? '';
    const engineRuntime = d.engineRuntime ?? '';
    return [t, rpm, speed, voltage, coolantTemp, engineLoad, fuelTrimShort, fuelTrimLong, throttle, map, maf, intakeTemp, engineRuntime].join(',');
}

export default function TripDetail() {
    const navigation = useNavigation();
    const route = useRoute<any>();
    const { tripId } = route.params || {};
    const [trip, setTrip] = useState<TripSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [exporting, setExporting] = useState(false);
    const showAlert = useAlertStore((s) => s.showAlert);

    useEffect(() => {
        if (tripId) {
            loadTripDetail();
        }
    }, [tripId]);

    const loadTripDetail = async () => {
        try {
            const res = await tripApi.getTripDetail(tripId);
            if (res.success && res.data) {
                setTrip(res.data);
            }
        } catch (e) {
            console.error('Failed to load trip detail', e);
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (isoString?: string) => {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일`;
    };

    const formatTimeRange = (start?: string, end?: string) => {
        if (!start) return '-';
        const s = new Date(start);
        const startTime = `${String(s.getHours()).padStart(2, '0')}:${String(s.getMinutes()).padStart(2, '0')}`;

        if (!end) return startTime;
        const e = new Date(end);
        const endTime = `${String(e.getHours()).padStart(2, '0')}:${String(e.getMinutes()).padStart(2, '0')}`;
        return `${startTime} ~ ${endTime}`;
    };

    const getScoreColor = (score: number) => {
        if (score >= 80) return '#0d7ff2'; // Blue (Primary)
        if (score >= 60) return '#fbbf24'; // Yellow
        return '#ef4444'; // Red
    };

    const getScoreLabel = (score: number) => {
        if (score >= 90) return '최우수';
        if (score >= 80) return '우수';
        if (score >= 60) return '보통';
        return '주의';
    };

    const handleExportCsv = useCallback(async () => {
        if (!tripId) return;
        setExporting(true);
        try {
            const res = await tripApi.getTripObdLogs(tripId);
            if (!res.success || !res.data || res.data.length === 0) {
                showAlert('내보내기 실패', '이 주행에 OBD 데이터가 없습니다.', 'ERROR');
                return;
            }
            const lines = [CSV_HEADER, ...res.data.map(obdLogToCsvRow)];
            const csvString = lines.join('\n');
            const filename = `trip_${tripId}_${new Date().toISOString().replace(/[:.]/g, '-')}.csv`;
            const path = `${FileSystem.documentDirectory}${filename}`;
            const encoding = (FileSystem.EncodingType && FileSystem.EncodingType.UTF8) ?? 'utf8';
            await FileSystem.writeAsStringAsync(path, csvString, { encoding });
            await Sharing.shareAsync(path);
            showAlert('내보내기 완료', `${res.data.length}행의 OBD 데이터를 CSV로 저장했습니다.`, 'SUCCESS');
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            showAlert('내보내기 실패', msg, 'ERROR');
        } finally {
            setExporting(false);
        }
    }, [tripId, showAlert]);

    if (loading) {
        return (
            <View className="flex-1 bg-background-dark items-center justify-center">
                <ActivityIndicator size="large" color="#0d7ff2" />
            </View>
        );
    }

    if (!trip) {
        return (
            <View className="flex-1 bg-background-dark items-center justify-center">
                <Text className="text-white">데이터를 불러올 수 없습니다.</Text>
                <TouchableOpacity onPress={() => navigation.goBack()} className="mt-4 p-3 bg-surface-dark rounded-lg">
                    <Text className="text-primary font-bold">돌아가기</Text>
                </TouchableOpacity>
            </View>
        );
    }

    const CustomHeader = (
        <View className="flex-row items-center justify-between px-4 py-3 border-b border-gray-800 bg-background-dark/95">
            <TouchableOpacity
                onPress={() => navigation.goBack()}
                className="w-10 h-10 items-center justify-center rounded-full active:bg-gray-800"
            >
                <MaterialIcons name="arrow-back-ios" size={20} color="white" />
            </TouchableOpacity>
            <Text className="text-white text-lg font-bold">주행 상세 리포트</Text>
            <View className="w-10" />
        </View>
    );

    return (
        <BaseScreen header={CustomHeader} padding={false}>
            <ScrollView className="flex-1 p-4 mb-10">
                {/* 1. Date & Time Header Card */}
                <View className="bg-surface-dark p-5 rounded-2xl mb-4 border border-gray-800">
                    <View className="flex-row items-center gap-3 mb-2">
                        <MaterialIcons name="calendar-today" size={18} color="#9ca3af" />
                        <Text className="text-gray-300 text-base font-medium">{formatDate(trip.startTime)}</Text>
                    </View>
                    <View className="flex-row items-center gap-3">
                        <MaterialIcons name="access-time" size={18} color="#9ca3af" />
                        <Text className="text-white text-xl font-bold">{formatTimeRange(trip.startTime, trip.endTime)}</Text>
                    </View>
                </View>

                {/* 2. Score Section */}
                <View className="flex-row gap-4 mb-4">
                    <View className="flex-1 bg-surface-dark p-5 rounded-2xl border border-gray-800 items-center justify-center">
                        <View className="relative items-center justify-center w-28 h-28 mb-2">
                            {/* Circular Background */}
                            <View className="absolute w-full h-full rounded-full border-4 border-gray-800 opacity-30" />
                            {/* Score Text */}
                            <Text className="text-4xl font-black" style={{ color: getScoreColor(trip.driveScore) }}>
                                {trip.driveScore}
                            </Text>
                            <Text className="text-gray-400 text-xs mt-1">점</Text>
                        </View>
                        <View className={`px-3 py-1 rounded-full bg-opacity-20`} style={{ backgroundColor: getScoreColor(trip.driveScore) + '33' }}>
                            <Text className="font-bold text-sm" style={{ color: getScoreColor(trip.driveScore) }}>
                                {getScoreLabel(trip.driveScore)} 등급
                            </Text>
                        </View>
                    </View>

                    {/* Key Stats Grid */}
                    <View className="flex-1 gap-3">
                        <View className="flex-1 bg-surface-dark p-3 rounded-xl border border-gray-800 justify-center">
                            <Text className="text-gray-500 text-xs mb-1">주행 거리</Text>
                            <View className="flex-row items-end gap-1">
                                <Text className="text-white text-xl font-bold">{trip.distance.toFixed(1)}</Text>
                                <Text className="text-gray-400 text-xs mb-1">km</Text>
                            </View>
                        </View>
                        <View className="flex-1 bg-surface-dark p-3 rounded-xl border border-gray-800 justify-center">
                            <Text className="text-gray-500 text-xs mb-1">연료 소모</Text>
                            <View className="flex-row items-end gap-1">
                                <Text className="text-white text-xl font-bold">{trip.fuelConsumed ? trip.fuelConsumed.toFixed(2) : '-'}</Text>
                                <Text className="text-gray-400 text-xs mb-1">L</Text>
                            </View>
                        </View>
                        <View className="flex-1 bg-surface-dark p-3 rounded-xl border border-gray-800 justify-center">
                            <Text className="text-gray-500 text-xs mb-1">평균 연비</Text>
                            <View className="flex-row items-end gap-1">
                                <Text className="text-white text-xl font-bold">
                                    {trip.fuelConsumed > 0 ? (trip.distance / trip.fuelConsumed).toFixed(1) : '-'}
                                </Text>
                                <Text className="text-gray-400 text-xs mb-1">km/L</Text>
                            </View>
                        </View>
                    </View>
                </View>

                {/* 3. Speed Stats */}
                <View className="bg-surface-dark p-5 rounded-2xl mb-4 border border-gray-800">
                    <Text className="text-white font-bold text-lg mb-4 flex-row items-center gap-2">
                        <MaterialIcons name="speed" size={20} color="#0d7ff2" /> 속도 분석
                    </Text>
                    <View className="flex-row divide-x divide-gray-800">
                        <View className="flex-1 items-center">
                            <Text className="text-gray-500 text-xs mb-1">평균 속도</Text>
                            <Text className="text-white text-2xl font-bold">{trip.averageSpeed.toFixed(0)} <Text className="text-sm font-normal text-gray-400">km/h</Text></Text>
                        </View>
                        <View className="flex-1 items-center">
                            <Text className="text-gray-500 text-xs mb-1">최고 속도</Text>
                            <Text className="text-white text-2xl font-bold">{trip.topSpeed.toFixed(0)} <Text className="text-sm font-normal text-gray-400">km/h</Text></Text>
                        </View>
                    </View>
                </View>

                {/* 4. Safety & Habits */}
                <View className="bg-surface-dark p-5 rounded-2xl mb-4 border border-gray-800">
                    <Text className="text-white font-bold text-lg mb-4 flex-row items-center gap-2">
                        <MaterialIcons name="warning" size={20} color="#fbbf24" /> 운전 습관
                    </Text>

                    <View className="gap-4">
                        <View className="flex-row items-center justify-between">
                            <View className="flex-row items-center gap-2">
                                <View className="w-8 h-8 rounded-full bg-red-500/20 items-center justify-center">
                                    <FontAwesome5 name="tachometer-alt" size={14} color="#ef4444" />
                                </View>
                                <Text className="text-gray-300">급가속 횟수</Text>
                            </View>
                            <Text className="text-white font-bold text-lg">{trip.hardAccelCount ?? 0}회</Text>
                        </View>

                        <View className="h-[1px] bg-gray-800" />

                        <View className="flex-row items-center justify-between">
                            <View className="flex-row items-center gap-2">
                                <View className="w-8 h-8 rounded-full bg-orange-500/20 items-center justify-center">
                                    <MaterialIcons name="priority-high" size={16} color="#f97316" />
                                </View>
                                <Text className="text-gray-300">급감속 횟수</Text>
                            </View>
                            <Text className="text-white font-bold text-lg">{trip.hardBrakeCount ?? 0}회</Text>
                        </View>

                        <View className="h-[1px] bg-gray-800" />

                        <View className="flex-row items-center justify-between">
                            <View className="flex-row items-center gap-2">
                                <View className="w-8 h-8 rounded-full bg-blue-500/20 items-center justify-center">
                                    <MaterialIcons name="hourglass-empty" size={16} color="#3b82f6" />
                                </View>
                                <Text className="text-gray-300">공회전 시간</Text>
                            </View>
                            <Text className="text-white font-bold text-lg">
                                {Math.floor((trip.idleTime ?? 0) / 60)}분 {(trip.idleTime ?? 0) % 60}초
                            </Text>
                        </View>
                    </View>
                </View>

                {/* 5. Vehicle Health Stats */}
                <View className="bg-surface-dark p-5 rounded-2xl mb-8 border border-gray-800">
                    <Text className="text-white font-bold text-lg mb-4 flex-row items-center gap-2">
                        <FontAwesome5 name="car-crash" size={18} color="#0d7ff2" /> 차량 상태
                    </Text>

                    <View className="flex-row flex-wrap gap-3">
                        {/* Coolant Temp */}
                        <View className="w-[48%] bg-background-dark/50 p-3 rounded-xl border border-gray-700">
                            <View className="flex-row justify-between items-start mb-2">
                                <Text className="text-gray-500 text-xs">최고 냉각수 온도</Text>
                                <FontAwesome5 name="thermometer-half" size={12} color={trip.maxCoolantTemp && trip.maxCoolantTemp > 100 ? '#ef4444' : '#0d7ff2'} />
                            </View>
                            <Text className="text-white font-bold text-lg">{trip.maxCoolantTemp ? trip.maxCoolantTemp.toFixed(1) : '-'} °C</Text>
                        </View>

                        {/* Battery Voltage */}
                        <View className="w-[48%] bg-background-dark/50 p-3 rounded-xl border border-gray-700">
                            <View className="flex-row justify-between items-start mb-2">
                                <Text className="text-gray-500 text-xs">최저 배터리 전압</Text>
                                <MaterialIcons name="battery-std" size={14} color={trip.minBatteryVoltage && trip.minBatteryVoltage < 11.5 ? '#ef4444' : '#0d7ff2'} />
                            </View>
                            <Text className="text-white font-bold text-lg">{trip.minBatteryVoltage ? trip.minBatteryVoltage.toFixed(1) : '-'} V</Text>
                        </View>

                        {/* Engine Load */}
                        <View className="w-[48%] bg-background-dark/50 p-3 rounded-xl border border-gray-700">
                            <View className="flex-row justify-between items-start mb-2">
                                <Text className="text-gray-500 text-xs">최고 엔진 부하</Text>
                                <FontAwesome5 name="cogs" size={12} color="#fbbf24" />
                            </View>
                            <Text className="text-white font-bold text-lg">{trip.maxEngineLoad ? trip.maxEngineLoad.toFixed(1) : '-'} %</Text>
                        </View>

                        {/* Battery Voltage */}
                        <View className="w-[48%] bg-background-dark/50 p-3 rounded-xl border border-gray-700">
                            <View className="flex-row justify-between items-start mb-2">
                                <Text className="text-gray-500 text-xs">평균 RPM</Text>
                                <Ionicons name="speedometer-outline" size={14} color="#a855f7" />
                            </View>
                            <Text className="text-white font-bold text-lg">{trip.avgRpm ? trip.avgRpm.toFixed(0) : '-'} rpm</Text>
                        </View>
                    </View>
                </View>

                {/* 6. CSV 내보내기 */}
                <TouchableOpacity
                    onPress={handleExportCsv}
                    disabled={exporting}
                    className="flex-row items-center justify-center gap-2 py-4 bg-primary/20 border border-primary/40 rounded-xl active:bg-primary/30"
                >
                    {exporting ? (
                        <ActivityIndicator size="small" color="#0d7ff2" />
                    ) : (
                        <MaterialIcons name="file-download" size={22} color="#0d7ff2" />
                    )}
                    <Text className="text-primary font-bold text-base">
                        {exporting ? '내보내는 중...' : 'OBD 데이터 CSV 내보내기'}
                    </Text>
                </TouchableOpacity>
            </ScrollView>
        </BaseScreen>
    );
}
