import React, { useState, useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, Animated, LayoutAnimation, Platform, UIManager } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';

import maintenanceApi, { VehicleConsumable } from '../api/maintenanceApi';
import { useVehicleStore } from '../store/useVehicleStore';
import { VehicleResponse } from '../api/vehicleApi';
import VehicleSelectModal from '../components/VehicleSelectModal';
import Header from '../header/Header';

if (Platform.OS === 'android') {
    if (UIManager.setLayoutAnimationEnabledExperimental) {
        UIManager.setLayoutAnimationEnabledExperimental(true);
    }
}

// Animated Progress Bar Component
const ProgressBar = ({ percent, color, delay = 0 }: { percent: number; color: string; delay?: number }) => {
    const widthAnim = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        Animated.timing(widthAnim, {
            toValue: percent,
            duration: 1000,
            delay: delay,
            useNativeDriver: false,
        }).start();
    }, [percent, delay]);

    const widthInterpolated = widthAnim.interpolate({
        inputRange: [0, 100],
        outputRange: ['0%', '100%'],
    });

    return (
        <View className="h-2 bg-white/10 rounded-full overflow-hidden">
            <Animated.View
                style={{
                    width: widthInterpolated,
                    backgroundColor: color,
                    height: '100%',
                    borderRadius: 999,
                    shadowColor: color,
                    shadowOffset: { width: 0, height: 0 },
                    shadowOpacity: 0.8,
                    shadowRadius: 8,
                    elevation: 5
                }}
            />
        </View>
    );
};

export default function SupManage() {
    const navigation = useNavigation();
    const { vehicles, primaryVehicle } = useVehicleStore();

    // State
    const [selectedVehicle, setSelectedVehicle] = useState<Partial<VehicleResponse> | null>(null);
    const [consumables, setConsumables] = useState<VehicleConsumable[]>([]);
    const [loading, setLoading] = useState(true);
    const [modalVisible, setModalVisible] = useState(false);
    const [pinnedItems, setPinnedItems] = useState<string[]>([]);

    const STORAGE_KEY_PREFIX = 'pinned_consumables_';

    // Initial Load & Pinned Items Load
    useEffect(() => {
        if (primaryVehicle) {
            setSelectedVehicle(primaryVehicle);
        } else if (vehicles.length > 0) {
            setSelectedVehicle(vehicles[0]);
        }
    }, [primaryVehicle, vehicles]);

    // 선택된 차량이 변경되면 소모품 조회 (초기 마운트 시 selectedVehicle은 아직 null일 수 있음)
    // Fetch Data on Vehicle Change
    useEffect(() => {
        if (selectedVehicle?.vehicleId) {
            loadPinnedItems(selectedVehicle.vehicleId);
            loadConsumables(selectedVehicle.vehicleId);
        }
    }, [selectedVehicle]);

    const loadPinnedItems = async (vehicleId: string) => {
        try {
            const saved = await AsyncStorage.getItem(`${STORAGE_KEY_PREFIX}${vehicleId}`);
            if (saved) {
                setPinnedItems(JSON.parse(saved));
            } else {
                setPinnedItems([]);
            }
        } catch (e) {
            console.error("Failed to load pinned items", e);
        }
    };

    const togglePin = async (itemCode: string) => {
        if (!selectedVehicle?.vehicleId) return;

        const newPinned = pinnedItems.includes(itemCode)
            ? pinnedItems.filter(code => code !== itemCode)
            : [...pinnedItems, itemCode];

        setPinnedItems(newPinned);
        LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);

        try {
            await AsyncStorage.setItem(`${STORAGE_KEY_PREFIX}${selectedVehicle.vehicleId}`, JSON.stringify(newPinned));
        } catch (e) {
            console.error("Failed to save pinned items", e);
        }
    };

    const loadConsumables = async (vehicleId: string) => {
        try {
            setLoading(true);
            const response = await maintenanceApi.getConsumableStatus(vehicleId);
            if (response.success && response.data) {
                // Filter redundant items: Only filter 'OTHER', show TIRES and BRAKE_PADS
                const filtered = response.data.filter(item =>
                    item.itemCode !== 'OTHER'
                );
                setConsumables(filtered);
            } else {
                setConsumables([]);
            }
        } catch (e) {
            console.error("Failed to load consumables:", e);
            setConsumables([]);
        } finally {
            setLoading(false);
            LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
        }
    };

    // Sorting Logic: Pinned -> Urgency
    const sortedConsumables = React.useMemo(() => {
        return [...consumables].sort((a, b) => {
            const aPinned = pinnedItems.includes(a.itemCode);
            const bPinned = pinnedItems.includes(b.itemCode);

            // 1. Pinned items first
            if (aPinned && !bPinned) return -1;
            if (!aPinned && bPinned) return 1;

            // 2. Both pinned or both unpinned -> Sort by remaining life (ascending, lower is more urgent)
            return a.remainingLifePercent - b.remainingLifePercent;
        });
    }, [consumables, pinnedItems]);


    // Helper: Status Color
    const getStatusColor = (percentage: number) => {
        if (percentage <= 20) return '#ef4444'; // Red (Danger)
        if (percentage <= 50) return '#f59e0b'; // Amber (Warning)
        return '#0d7ff2'; // Primary Blue (Good/Safe)
    };

    // Helper: Status Text & Icon
    const getStatusInfo = (percentage: number) => {
        if (percentage <= 20) return { text: "교체 시급", icon: "error-outline" as const };
        if (percentage <= 50) return { text: "점검 권장", icon: "warning-amber" as const };
        return { text: "상태 양호", icon: "check-circle-outline" as const };
    };

    // Helper: Item Icon
    const getIconInfo = (code: string) => {
        const map: Record<string, { icon: string, family: string }> = {
            'ENGINE_OIL': { icon: 'water-drop', family: 'MaterialIcons' },
            'WIPER': { icon: 'wiper', family: 'MaterialCommunityIcons' },
            'AIR_FILTER': { icon: 'air-filter', family: 'MaterialCommunityIcons' },
            'CABIN_FILTER': { icon: 'air-filter', family: 'MaterialCommunityIcons' },
            'TIRE': { icon: 'tire', family: 'MaterialCommunityIcons' },
            'TIRES': { icon: 'tire', family: 'MaterialCommunityIcons' },
            'TIRE_FL': { icon: 'tire', family: 'MaterialCommunityIcons' },
            'TIRE_FR': { icon: 'tire', family: 'MaterialCommunityIcons' },
            'TIRE_RL': { icon: 'tire', family: 'MaterialCommunityIcons' },
            'TIRE_RR': { icon: 'tire', family: 'MaterialCommunityIcons' },
            'TIRE_FRONT': { icon: 'tire', family: 'MaterialCommunityIcons' },
            'TIRE_REAR': { icon: 'tire', family: 'MaterialCommunityIcons' },
            'BRAKE_PAD': { icon: 'stop-circle', family: 'MaterialIcons' },
            'BRAKE_PAD_FRONT': { icon: 'stop-circle', family: 'MaterialIcons' },
            'BRAKE_PAD_REAR': { icon: 'stop-circle', family: 'MaterialIcons' },
            'BATTERY': { icon: 'car-battery', family: 'MaterialCommunityIcons' },
            'BATTERY_12V': { icon: 'car-battery', family: 'MaterialCommunityIcons' },
            'SPARK_PLUG': { icon: 'flash-on', family: 'MaterialIcons' },
            'BRAKE_FLUID': { icon: 'water-drop', family: 'MaterialIcons' },
            'COOLANT': { icon: 'thermostat', family: 'MaterialIcons' },
            'TRANSMISSION_FLUID': { icon: 'cog-transfer', family: 'MaterialCommunityIcons' },
            'DRIVE_BELT': { icon: 'settings-input-component', family: 'MaterialIcons' },
            'MISSION_OIL': { icon: 'cog-transfer', family: 'MaterialCommunityIcons' },
            'AIR_CON_REFRIGERANT': { icon: 'snowflake', family: 'MaterialCommunityIcons' },
            'BRAKE_PADS': { icon: 'stop-circle', family: 'MaterialIcons' },
            'FUEL_FILTER': { icon: 'filter', family: 'MaterialCommunityIcons' },
            'WHEEL_ALIGNMENT': { icon: 'tune', family: 'MaterialIcons' },
            'OTHER': { icon: 'construction', family: 'MaterialIcons' }
        };
        return map[code.toUpperCase()] || { icon: 'settings', family: 'MaterialIcons' };
    };

    const renderIcon = (item: VehicleConsumable, color: string) => {
        const { icon, family } = getIconInfo(item.itemCode);
        const IconComponent: any = family === 'MaterialCommunityIcons' ? MaterialCommunityIcons : MaterialIcons;
        return <IconComponent name={icon} size={24} color={color} />;
    };

    // Vehicle Selection
    const handleSelectVehicle = (vehicle: VehicleResponse) => {
        setSelectedVehicle(vehicle);
        setModalVisible(false);
    };

    // Calculate Summary
    const urgentCount = consumables.filter(c => c.remainingLifePercent <= 20).length;
    const warningCount = consumables.filter(c => c.remainingLifePercent > 20 && c.remainingLifePercent <= 50).length;

    const insets = useSafeAreaInsets();

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />
            <SafeAreaView className="flex-1" edges={['top', 'bottom']}>

                {/* Header */}
                <Header title="소모품 관리" />

                <ScrollView className="flex-1 px-5" contentContainerStyle={{ paddingBottom: 100, paddingTop: 10 }}>

                    {/* Dashboard Header Text & Vehicle Selector */}
                    <View className="mb-6 flex-row justify-between items-start">
                        <View className="flex-1">
                            <Text className="text-text-dim text-sm mb-1">내 차의 건강 상태</Text>
                            <Text className="text-white text-2xl font-bold leading-8">
                                {loading ? "상태 확인 중..." :
                                    urgentCount > 0 ? `${urgentCount}개의 항목이\n교체가 시급합니다.` :
                                        warningCount > 0 ? `${warningCount}개의 항목을\n점검해보세요.` :
                                            "모든 소모품 상태가\n양호합니다. 👍"}
                            </Text>
                        </View>

                        {/* Vehicle Selector */}
                        <TouchableOpacity
                            className="flex-row items-center gap-1.5 bg-white/5 py-2 px-3 rounded-xl border border-white/10 mt-1"
                            activeOpacity={0.7}
                            onPress={() => setModalVisible(true)}
                        >
                            <Text className="text-white font-bold text-sm">
                                {selectedVehicle?.modelNameKo || selectedVehicle?.modelNameKo || '차량 선택'}
                            </Text>
                            <MaterialIcons name="keyboard-arrow-down" size={16} color="#94a3b8" />
                        </TouchableOpacity>
                    </View>

                    {loading ? (
                        <View className="py-20 items-center">
                            <ActivityIndicator size="large" color="#0d7ff2" />
                            <Text className="text-text-dim mt-4">데이터 분석 중...</Text>
                        </View>
                    ) : sortedConsumables.length === 0 ? (
                        <View className="items-center justify-center py-20">
                            <View className="w-20 h-20 rounded-full bg-surface-card border border-white/5 items-center justify-center mb-6">
                                <MaterialIcons name="no-sim" size={40} color="#64748b" />
                            </View>
                            <Text className="text-text-dim font-bold text-lg mb-2">데이터가 없습니다</Text>
                            <TouchableOpacity
                                onPress={() => selectedVehicle?.vehicleId && loadConsumables(selectedVehicle.vehicleId)}
                                className="mt-4 px-6 py-3 bg-primary rounded-xl"
                            >
                                <Text className="text-white font-bold">다시 시도</Text>
                            </TouchableOpacity>
                        </View>
                    ) : (
                        <View className="gap-4">
                            {sortedConsumables.map((item, index) => {
                                const life = Math.round(item.remainingLifePercent);
                                const color = getStatusColor(life);
                                const { text: statusText, icon: statusIcon } = getStatusInfo(life);
                                const isPinned = pinnedItems.includes(item.itemCode);

                                return (
                                    <TouchableOpacity
                                        key={item.itemCode}
                                        activeOpacity={0.9}
                                    // 상세 페이지 이동 등 확장 가능
                                    >
                                        <LinearGradient
                                            colors={isPinned
                                                ? ['rgba(255, 215, 0, 0.15)', 'rgba(255, 215, 0, 0.05)'] // Gold tint for pinned
                                                : ['rgba(255, 255, 255, 0.08)', 'rgba(255, 255, 255, 0.02)']}
                                            start={{ x: 0, y: 0 }}
                                            end={{ x: 1, y: 1 }}
                                            className={`rounded-3xl p-[1px] ${isPinned ? 'border border-yellow-500/30' : ''}`}
                                        >
                                            <View className="bg-surface-card/90 rounded-[23px] p-5 backdrop-blur-md">
                                                <View className="flex-row justify-between items-start mb-4">
                                                    <View className="flex-row items-center gap-4">
                                                        <View className={`w-12 h-12 rounded-2xl items-center justify-center shadow-lg bg-black/20 border border-white/5`}>
                                                            {renderIcon(item, color)}
                                                        </View>
                                                        <View>
                                                            <Text className="text-white font-bold text-lg">{item.itemDescription}</Text>
                                                            <View className="flex-row items-center gap-1 mt-0.5">
                                                                <MaterialIcons name={statusIcon} size={12} color={color} />
                                                                <Text className="text-xs font-medium" style={{ color }}>{statusText}</Text>
                                                            </View>
                                                        </View>
                                                    </View>

                                                    {/* Life % */}
                                                    <View className="items-end">
                                                        <Text className="text-white font-bold text-2xl">{life}<Text className="text-sm text-text-dim">%</Text></Text>
                                                    </View>
                                                </View>

                                                {/* Progress Bar */}
                                                <ProgressBar percent={life} color={color} delay={index * 100} />

                                                {/* Footer Info & Pin Button */}
                                                <View className="flex-row justify-between items-center mt-4 pt-4 border-t border-white/5">
                                                    <View>
                                                        <Text className="text-text-dim text-xs">
                                                            {item.predictedReplacementDate ? `예상 교체: ${item.predictedReplacementDate}` : '분석 중...'}
                                                        </Text>
                                                        {item.itemCode.includes('TIRE') && item.unevenWearDetected && (
                                                            <View className="bg-red-500/20 px-2 py-0.5 rounded border border-red-500/20 mt-1 self-start">
                                                                <Text className="text-red-400 text-[10px] font-bold">⚠️ 편마모 주의</Text>
                                                            </View>
                                                        )}
                                                    </View>

                                                    {/* Pin Button - Moved to bottom right & styled */}
                                                    <TouchableOpacity
                                                        onPress={() => togglePin(item.itemCode)}
                                                        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                                                    >
                                                        <MaterialIcons
                                                            name={isPinned ? "star" : "star-border"}
                                                            size={22}
                                                            color={isPinned ? "#fbbf24" : "#94a3b8"}
                                                        />
                                                    </TouchableOpacity>
                                                </View>
                                            </View>
                                        </LinearGradient>
                                    </TouchableOpacity>
                                );
                            })}
                        </View>
                    )}
                </ScrollView>

                {/* Shared Vehicle Modal */}
                <VehicleSelectModal
                    visible={modalVisible}
                    onClose={() => setModalVisible(false)}
                    onSelect={handleSelectVehicle}
                />

            </SafeAreaView>
            {insets.bottom > 0 && (
                <View
                    style={{
                        position: 'absolute',
                        bottom: 0,
                        left: 0,
                        right: 0,
                        height: insets.bottom,
                        backgroundColor: '#101922',
                    }}
                />
            )}
        </View>
    );
}
