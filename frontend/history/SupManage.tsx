import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import maintenanceApi, { VehicleConsumable } from '../api/maintenanceApi';

export default function SupManage() {
    const navigation = useNavigation();
    const [consumables, setConsumables] = useState<VehicleConsumable[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadConsumables();
    }, []);

    const loadConsumables = async () => {
        setLoading(true);
        try {
            const stored = await AsyncStorage.getItem('primaryVehicle');
            if (stored) {
                const vehicle = JSON.parse(stored);
                const response = await maintenanceApi.getConsumableStatus(vehicle.id);
                if (response.success && response.data) {
                    setConsumables(response.data);
                } else {
                    setConsumables([]);
                }
            } else {
                console.warn("No primary vehicle found.");
                setConsumables([]);
            }
        } catch (e) {
            console.error("Failed to load consumables:", e);
            setConsumables([]);
        } finally {
            setLoading(false);
        }
    };

    // Helper to determine color based on remaining life
    const getStatusColor = (percentage: number) => {
        if (percentage <= 20) return '#ff6b6b'; // Error
        if (percentage <= 50) return '#f59e0b'; // Warning
        return '#0d7ff2'; // Primary
    };

    // Helper to determine status text
    const getStatusText = (percentage: number) => {
        if (percentage <= 20) return "즉시 교체 요망";
        if (percentage <= 50) return "점검 권장";
        return "상태 양호";
    };

    // Helper to map item code to icon
    const getIconInfo = (code: string) => {
        const map: Record<string, { icon: string, family: string }> = {
            'ENGINE_OIL': { icon: 'oil', family: 'MaterialCommunityIcons' },
            'WIPER': { icon: 'wiper', family: 'MaterialCommunityIcons' },
            'AIR_FILTER': { icon: 'air-filter', family: 'MaterialCommunityIcons' },
            'TIRE': { icon: 'car-tire-alert', family: 'MaterialCommunityIcons' },
            'BRAKE_PAD': { icon: 'disc-full', family: 'MaterialIcons' },
            'BATTERY': { icon: 'battery-charging-full', family: 'MaterialIcons' },
            'SPARK_PLUG': { icon: 'engine', family: 'MaterialCommunityIcons' },
            'BRAKE_FLUID': { icon: 'water-drop', family: 'MaterialIcons' },
            'COOLANT': { icon: 'thermostat', family: 'MaterialIcons' },
            'TRANSMISSION_FLUID': { icon: 'cog-transfer', family: 'MaterialCommunityIcons' },
            'TIRES': { icon: 'car-tire-alert', family: 'MaterialCommunityIcons' }
        };
        return map[code] || { icon: 'settings', family: 'MaterialIcons' };
    };

    const renderIcon = (item: VehicleConsumable, color: string) => {
        const { icon, family } = getIconInfo(item.item);
        if (family === "MaterialCommunityIcons") {
            return <MaterialCommunityIcons name={icon as any} size={24} color={color} />;
        }
        return <MaterialIcons name={icon as any} size={24} color={color} />;
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
            <View className="flex-row items-center justify-between px-4 py-3 border-b border-white/5 bg-surface-dark/95">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">소모품 관리</Text>
                <TouchableOpacity className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10">
                    <MaterialIcons name="more-vert" size={24} color="white" />
                </TouchableOpacity>
            </View>

            <ScrollView className="flex-1 px-6 pt-4" contentContainerStyle={{ paddingBottom: 100 }}>
                {consumables.length === 0 ? (
                    <View className="items-center justify-center py-20 gap-4">
                        <View className="w-16 h-16 rounded-full bg-gray-800 items-center justify-center mb-2">
                            <MaterialIcons name="inventory" size={32} color="#64748b" />
                        </View>
                        <Text className="text-gray-400 text-base font-medium text-center">
                            등록된 소모품 정보가 없습니다.
                        </Text>
                        <TouchableOpacity
                            onPress={loadConsumables}
                            className="px-4 py-2 bg-[#1e293b] rounded-lg border border-white/10 active:bg-[#334155]"
                        >
                            <Text className="text-primary font-bold text-sm">다시 불러오기</Text>
                        </TouchableOpacity>
                    </View>
                ) : (
                    <View className="gap-4">
                        {consumables.map((item, index) => {
                            const life = Math.round(item.remainingLifePercent);
                            const color = getStatusColor(life);
                            const statusAvailable = getStatusText(life);

                            return (
                                <View
                                    key={index}
                                    className="bg-white/5 border border-white/10 rounded-2xl p-4 overflow-hidden relative"
                                >
                                    {/* Side Color Bar */}
                                    <View
                                        className="absolute left-0 top-0 bottom-0 w-1.5"
                                        style={{ backgroundColor: color, shadowColor: color, shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.5, shadowRadius: 10, elevation: 5 }}
                                    />

                                    {/* Top Section */}
                                    <View className="flex-row justify-between items-start mb-4 pl-3">
                                        <View className="flex-row items-center gap-3">
                                            <View
                                                className="w-12 h-12 rounded-xl items-center justify-center border"
                                                style={{ backgroundColor: `${color}15`, borderColor: `${color}30` }}
                                            >
                                                {renderIcon(item, color)}
                                            </View>
                                            <View>
                                                <Text className="text-base font-bold text-white mb-0.5">
                                                    {item.itemDescription}
                                                </Text>
                                                <Text
                                                    className="text-xs font-medium"
                                                    style={{ color: life <= 20 ? color : '#9ca3af' }}
                                                >
                                                    {statusAvailable}
                                                </Text>
                                                {/* Tire Specific Warning */}
                                                {(item.item === 'TIRE' || item.item === 'TIRES') && item.unevenWearDetected && (
                                                    <View className="bg-red-500/20 px-2 py-0.5 rounded mt-1 self-start">
                                                        <Text className="text-red-400 text-[10px] font-bold">⚠️ 편마모 감지됨</Text>
                                                    </View>
                                                )}
                                            </View>
                                        </View>
                                        <Text
                                            className="text-xl font-bold"
                                            style={{ color: life <= 20 || life <= 50 ? color : 'white' }}
                                        >
                                            {life}%
                                        </Text>
                                    </View>

                                    {/* Progress Bar & Message */}
                                    <View className="pl-3">
                                        <View className="w-full bg-white/10 rounded-full h-1.5 mb-3 overflow-hidden">
                                            <View
                                                className="h-1.5 rounded-full"
                                                style={{
                                                    width: `${Math.max(life, 5)}%`, // Minimum visual width
                                                    backgroundColor: color,
                                                    shadowColor: color,
                                                    shadowOffset: { width: 0, height: 0 },
                                                    shadowOpacity: 0.5,
                                                    shadowRadius: 8
                                                }}
                                            />
                                        </View>
                                        <View className="flex-row items-center gap-2 bg-black/20 p-3 rounded-xl border border-white/5">
                                            <MaterialIcons
                                                name="smart-toy"
                                                size={16}
                                                color={color}
                                            />
                                            <Text className="text-xs text-text-muted flex-1">
                                                {item.predictedReplacementDate
                                                    ? `교체 예정일: ${item.predictedReplacementDate} (AI 예측)`
                                                    : "주행 데이터를 분석 중입니다."}
                                            </Text>
                                        </View>
                                    </View>
                                </View>
                            );
                        })}
                    </View>
                )}
            </ScrollView>
        </SafeAreaView >
    );
}
