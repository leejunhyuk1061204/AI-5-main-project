import React, { useEffect, useState, useMemo } from 'react';
import { View, Text, TouchableOpacity, SectionList, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import tripApi, { TripSummary } from '../api/tripApi';
import VehicleSelectModal from '../components/VehicleSelectModal';
import { useAlertStore } from '../store/useAlertStore';
import { useVehicleStore } from '../store/useVehicleStore';
import { VehicleResponse } from '../api/vehicleApi';

// Helper to format date
const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    const mm = date.getMonth() + 1;
    const dd = date.getDate();
    const day = ['일', '월', '화', '수', '목', '금', '토'][date.getDay()];
    return `${date.getFullYear()}.${mm}.${dd} (${day})`;
};

const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
};

export default function DrivingList() {
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

    // Group trips by date
    const sections = useMemo(() => {
        const grouped: { [key: string]: TripSummary[] } = {};
        trips.forEach(trip => {
            const dateStr = formatDate(trip.startTime);
            if (!grouped[dateStr]) grouped[dateStr] = [];
            grouped[dateStr].push(trip);
        });

        return Object.keys(grouped).map(date => ({
            title: date,
            data: grouped[date]
        }));
    }, [trips]);

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
                <Text className="text-white text-lg font-bold">주행 기록 전체보기</Text>
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

            <SectionList
                sections={sections}
                keyExtractor={(item) => item.tripId}
                contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
                stickySectionHeadersEnabled={false}
                renderSectionHeader={({ section: { title } }) => (
                    <View className="mb-3 mt-4">
                        <Text className="text-primary font-bold text-base px-1">{title}</Text>
                    </View>
                )}
                renderItem={({ item }) => (
                    <TouchableOpacity
                        activeOpacity={0.7}
                        onPress={() => (navigation as any).navigate('TripDetail', { tripId: item.tripId })}
                        className="bg-surface-dark rounded-xl border border-primary/30 p-4 mb-3 relative overflow-hidden"
                    >
                        <View className="flex-row justify-between items-center mb-4">
                            <View className="flex-row items-center gap-3">
                                <View className="bg-primary/10 p-2 rounded-full border border-primary/20">
                                    <MaterialIcons name="commute" size={24} color="#0d7ff2" />
                                </View>
                                <View>
                                    <Text className="text-white font-bold text-lg">{formatTime(item.startTime)}</Text>
                                    <Text className="text-gray-500 text-xs">주행 기록</Text>
                                </View>
                            </View>
                            {/* Score Badge - Fixed text color */}
                            <View className="flex-row items-center gap-1 bg-surface-highlight/20 px-3 py-1.5 rounded-full border border-gray-700">
                                <View className={`w-2 h-2 rounded-full ${item.driveScore >= 80 ? 'bg-primary' : item.driveScore >= 60 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ shadowColor: item.driveScore >= 80 ? '#0d7ff2' : item.driveScore >= 60 ? '#f59e0b' : '#ef4444', shadowOpacity: 0.5, shadowRadius: 5 }} />
                                <Text className="text-sm font-bold text-white">{item.driveScore}점</Text>
                            </View>
                        </View>

                        <View className="flex-row flex-wrap gap-3">
                            <View className="flex-1 min-w-[45%] bg-background-dark/50 p-3 rounded-lg border border-gray-800">
                                <Text className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">주행 거리</Text>
                                <Text className="text-white font-medium text-base">{item.distance.toFixed(1)} <Text className="text-xs text-gray-400">km</Text></Text>
                            </View>
                            <View className="flex-1 min-w-[45%] bg-background-dark/50 p-3 rounded-lg border border-gray-800">
                                <Text className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">평균 속도</Text>
                                <Text className="text-white font-medium text-base">{item.averageSpeed.toFixed(0)} <Text className="text-xs text-gray-400">km/h</Text></Text>
                            </View>
                        </View>

                        <TouchableOpacity
                            className="mt-3 flex-row items-center gap-1 self-start"
                            onPress={() => setVehicleChangeTripId(item.tripId)}
                            disabled={changing}
                        >
                            <MaterialIcons name="swap-horiz" size={16} color="#0d7ff2" />
                            <Text className="text-[#0d7ff2] text-xs font-medium">차량 변경</Text>
                        </TouchableOpacity>
                    </TouchableOpacity>
                )}
                ListEmptyComponent={
                    <View className="items-center justify-center py-20">
                        <MaterialIcons name="directions-car" size={64} color="#374151" />
                        <Text className="text-gray-500 mt-4 text-base">아직 주행 기록이 없습니다.</Text>
                    </View>
                }
            />

            <VehicleSelectModal
                visible={vehicleSelectModalVisible}
                onClose={() => setVehicleSelectModalVisible(false)}
                onSelect={handleSelectVehicle}
                title="주행 기록 조회할 차량 선택"
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
