import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import Svg, { Circle, Defs, LinearGradient, Stop } from 'react-native-svg';
import { useNavigation, useFocusEffect } from '@react-navigation/native';

import AsyncStorage from '@react-native-async-storage/async-storage';
import tripApi from '../api/tripApi';
import Header from '../header/Header';
import BaseScreen from '../components/layout/BaseScreen';
import { useVehicleStore } from '../store/useVehicleStore';
import ObdService from '../services/ObdService';
import NotificationOnboardingModal from '../components/NotificationOnboardingModal';
import VehicleSelectModal from '../components/VehicleSelectModal';
import { useUserStore } from '../store/useUserStore';

export default function MainPage() {
    const navigation = useNavigation<any>();
    const { primaryVehicle, fetchVehicles, setPrimaryVehicle } = useVehicleStore();
    const { nickname, membership, loadUser } = useUserStore();
    const [maintenanceScore, setMaintenanceScore] = useState(100);
    const [drivingScore, setDrivingScore] = useState<number | null>(null);

    const [isSelectModalVisible, setIsSelectModalVisible] = useState(false);

    // Consumables State (Hoisted)
    const [consumables, setConsumables] = useState<any[]>([]);




    // Auto-connect OBD on mount
    useEffect(() => {
        const initObd = async () => {
            // 잠시 지연 후 시도하여 네비게이션 트랜지션 부하 분산
            setTimeout(async () => {
                try {
                    await ObdService.ensureNotificationPermissionForPolling();
                    await ObdService.tryAutoConnect();
                    if (ObdService.isConnected()) {
                        ObdService.startPolling(1000);
                    }
                } catch {
                    // 자동 연결 실패는 조용히 무시
                }
            }, 1000);
        };
        initObd();
    }, []);

    // 화면이 포커스될 때마다 사용자 정보 및 차량 정보 갱신
    useFocusEffect(
        React.useCallback(() => {
            console.log('MainPage focused - reloading user data');
            fetchVehicles().catch(e => console.log('Silent fetch error in MainPage', e));
            loadUser();
        }, [])
    );


    // Vehicle ID Sync & Initial Load
    useEffect(() => {
        const { setVehicleId } = require('../store/useAiDiagnosisStore').useAiDiagnosisStore.getState();

        if (primaryVehicle && primaryVehicle.vehicleId) {
            fetchDrivingScore(primaryVehicle.vehicleId);
            loadConsumables(primaryVehicle.vehicleId); // Load here

            // Sync with AI Diagnosis Store
            setVehicleId(primaryVehicle.vehicleId);
            // Sync with ObdService (for Auto Trip)
            ObdService.setVehicleId(primaryVehicle.vehicleId);
        } else {
            // Clear stale ID if no primary vehicle
            setVehicleId(null);
            setConsumables([]);
        }
    }, [primaryVehicle]);

    const loadConsumables = async (vehicleId: string) => {
        try {
            const response = await require('../api/maintenanceApi').default.getConsumableStatus(vehicleId);
            if (response.success && response.data) {
                setConsumables(response.data);
            }
        } catch (e) {
            console.log('Failed to load consumables', e);
        }
    };




    // Calculate Driving Score
    const fetchDrivingScore = async (vehicleId: string) => {
        try {
            const tripsResponse = await tripApi.getTrips(vehicleId);
            const trips = Array.isArray(tripsResponse) ? tripsResponse : (tripsResponse as any).data;

            if (trips && trips.length > 0) {
                const totalScore = trips.reduce((sum: number, trip: any) => sum + (trip.driveScore || 0), 0);
                const avgScore = Math.round(totalScore / trips.length);
                setDrivingScore(avgScore);
            } else {
                setDrivingScore(null); // No data -> Display as -
            }
        } catch (tripError) {
            console.log('Failed to load trips for score:', tripError);
            setDrivingScore(null);
        }
    };

    // Calculate Comprehensive Health Score
    useEffect(() => {
        if (!consumables || consumables.length === 0) {
            // Only driving score available or default
            setMaintenanceScore(100);
            return;
        }

        // 1. Calculate Consumable Health (Average %)
        // Backend returns valid items for this vehicle
        const validConsumables = consumables.filter(c => c?.itemCode);

        let maintenanceScore = 100;
        if (validConsumables.length > 0) {
            const totalLife = validConsumables.reduce((sum, c) => sum + (c.remainingLifePercent || 0), 0);
            maintenanceScore = Math.round(totalLife / validConsumables.length);
        }

        // 2. Apply Penalties for Dangerous Items
        let penalty = 0;
        validConsumables.forEach(c => {
            if (c.remainingLifePercent <= 20) penalty += 15; // Heavy penalty for critical low life
            else if (c.remainingLifePercent <= 40) penalty += 5;
        });

        // 3. Weighted Average
        // Maintenance (60%) + Driving (40%) - If driving missing, use maintenance 100%
        const weightedScore = drivingScore === null
            ? maintenanceScore
            : (maintenanceScore * 0.6) + (drivingScore * 0.4);

        const finalScore = Math.max(0, Math.min(100, Math.round(weightedScore - penalty)));

        setMaintenanceScore(finalScore);

    }, [drivingScore, consumables]);



    const getStatusFor = (type: string) => {
        let item;

        if (type === 'BATTERY') {
            item = consumables.find(c => c.itemCode === 'BATTERY_12V' || c.itemCode === 'BATTERY');
        } else if (type === 'COOLANT') {
            item = consumables.find(c => c?.itemCode === 'COOLANT');
        } else {
            // Default lookups (ENGINE_OIL etc)
            item = consumables.find(c => c.itemCode === type);
        }

        if (!item) return { color: '#334155', text: '-', percent: 0, iconColor: '#475569' };

        const life = Math.round(item.remainingLifePercent);
        let color = '#0d7ff2'; // Primary Blue (Good)
        let statusText = '양호';

        if (life <= 20) {
            color = '#ef4444'; // Error
            statusText = '점검';
        } else if (life <= 50) {
            color = '#f59e0b'; // Warning
            statusText = '주의';
        }

        return { color, text: statusText, percent: life, iconColor: color };
    };

    const engineStatus = getStatusFor('ENGINE_OIL');
    const batteryStatus = getStatusFor('BATTERY');
    const coolantStatus = getStatusFor('COOLANT');

    // fallback for display
    const currentVehicle = primaryVehicle || {
        modelNameKo: '차량을 등록해주세요',
        carNumber: '- - -',
        totalMileage: 0,
        fuelType: null
    };

    // Notification Onboarding Logic
    const [showNotiOnboarding, setShowNotiOnboarding] = useState(false);

    useEffect(() => {
        const checkOnboarding = async () => {
            // Only show if user has vehicles (registration done)
            if (primaryVehicle) {
                const hasSeen = await AsyncStorage.getItem('hasSeenNotiOnboarding');
                if (!hasSeen) {
                    // Small delay to let entering animations finish
                    setTimeout(() => {
                        setShowNotiOnboarding(true);
                    }, 1500);
                }
            }
        };
        checkOnboarding();
    }, [primaryVehicle]);

    const handleOnboardingClose = async () => {
        setShowNotiOnboarding(false);
        await AsyncStorage.setItem('hasSeenNotiOnboarding', 'true');
    };

    // Helper for Gauge Color
    const getScoreColorStops = (score: number | null) => {
        if (score === null) {
            return [{ offset: "0%", color: "#334155" }, { offset: "100%", color: "#1e293b" }]; // Gray for no data
        }
        if (score < 30) {
            return [{ offset: "0%", color: "#ef4444" }, { offset: "100%", color: "#b91c1c" }]; // Red
        } else if (score < 70) {
            return [{ offset: "0%", color: "#f59e0b" }, { offset: "100%", color: "#d97706" }]; // Orange
        } else {
            return [{ offset: "0%", color: "#00f2fe" }, { offset: "100%", color: "#0d7ff2" }]; // Blue (Default)
        }
    };

    // Reusable Gauge Component
    const ScoreGauge = ({ score, label }: { score: number | null, label: string }) => {
        const radius = 42;
        const strokeWidth = 9;
        const circumference = 2 * Math.PI * radius;
        const colorStops = getScoreColorStops(score);

        const displayScore = score === null ? 0 : score;

        return (
            <View className="items-center justify-center">
                <View className="relative w-48 h-48 items-center justify-center">
                    <Svg width="100%" height="100%" viewBox="0 0 100 100" className="-rotate-90">
                        <Defs>
                            <LinearGradient id={`grad-${label}`} x1="0%" y1="0%" x2="100%" y2="0%">
                                {colorStops.map((stop, i) => <Stop key={i} offset={stop.offset} stopColor={stop.color} />)}
                            </LinearGradient>
                        </Defs>
                        <Circle cx="50" cy="50" r={radius} stroke="#17212b" strokeWidth={strokeWidth} fill="transparent" />
                        <Circle
                            cx="50"
                            cy="50"
                            r={radius}
                            stroke={`url(#grad-${label})`}
                            strokeWidth={strokeWidth}
                            fill="transparent"
                            strokeDasharray={`${circumference}`}
                            strokeDashoffset={`${circumference * (1 - displayScore / 100)}`}
                            strokeLinecap="round"
                        />
                    </Svg>
                    <View className="absolute inset-0 items-center justify-center z-10">
                        <Text className="text-text-muted text-sm font-medium tracking-wide mb-1">{label}</Text>
                        <Text className="text-4xl font-bold text-white tracking-tighter">
                            {score === null ? '-' : score}<Text className="text-base text-text-dim font-normal">점</Text>
                        </Text>
                    </View>
                </View>
            </View>
        );
    };

    return (
        <BaseScreen
            header={<Header />}
            padding={false}
            edges={['top', 'left', 'right']}
        >
            {/* Car Info Card */}
            <View className="px-6 py-3">
                <View className="relative overflow-hidden rounded-xl bg-white/5 border border-white/10 p-3 flex-row items-center justify-between shadow-lg">
                    <TouchableOpacity
                        className="flex-row items-center gap-3 z-10 flex-1"
                        activeOpacity={0.7}
                        onPress={() => setIsSelectModalVisible(true)}
                    >
                        <View className="w-10 h-10 rounded-lg bg-surface-card border border-white/10 items-center justify-center shadow-inner">
                            <MaterialIcons name="directions-car" size={20} color="#d1d5db" />
                        </View>
                        <View>
                            <View className="flex-row items-center gap-1.5">
                                <Text className="text-white text-base font-bold leading-tight">
                                    {currentVehicle.modelNameKo || (currentVehicle as any).modelName}
                                </Text>
                                <MaterialIcons name="keyboard-arrow-down" size={16} color="#94a3b8" />
                            </View>
                            <Text className="text-text-muted text-sm font-normal">{currentVehicle.carNumber}</Text>
                        </View>
                    </TouchableOpacity>
                    <TouchableOpacity
                        className="flex-row items-center gap-1 bg-primary/10 px-2.5 py-1 rounded-full border border-primary/20"
                        onPress={() => navigation.navigate('CarManage')}
                    >
                        <Text className="text-primary text-xs font-bold">상세</Text>
                        <MaterialIcons name="chevron-right" size={14} color="#0d7ff2" />
                    </TouchableOpacity>
                </View>
            </View>

            {/* Dual Score Gauges */}
            <View className="px-3 py-8 flex-row justify-center gap-2">
                <ScoreGauge
                    score={maintenanceScore}
                    label="차량 관리"
                />
                <View className="w-px bg-white/5 h-28 self-center mx-1" />
                <ScoreGauge
                    score={drivingScore}
                    label="주행 안전"
                />
            </View>

            {/* Status Grid */}
            <View className="px-6 mb-8">
                <View className="flex-row items-center mb-3">
                    <Text className="text-white text-lg font-bold">실시간 상태</Text>
                    <View className="h-px bg-white/5 flex-1 ml-4" />
                </View>
                <View className="flex-row gap-2.5">
                    {[
                        { label: '엔진오일', icon: 'water-drop', family: 'MaterialIcons', data: engineStatus },
                        { label: '배터리', icon: 'battery-charging-full', family: 'MaterialIcons', data: batteryStatus },
                        { label: '냉각수', icon: 'thermostat', family: 'MaterialIcons', data: coolantStatus }
                    ].map((item, index) => (
                        <TouchableOpacity
                            key={index}
                            className="flex-1 aspect-square rounded-2xl bg-white/5 border border-white/10 p-3 justify-between"
                            activeOpacity={0.7}
                            onPress={() => navigation.navigate('SupManage')}
                        >
                            <View className="flex-row justify-between items-start">
                                {item.family === 'MaterialCommunityIcons' ? (
                                    <MaterialCommunityIcons name={item.icon as any} size={24} color={item.data.iconColor} />
                                ) : (
                                    <MaterialIcons name={item.icon as any} size={24} color={item.data.iconColor} />
                                )}
                                <View className={`w-2 h-2 rounded-full`} style={{ backgroundColor: item.data.iconColor }} />
                            </View>

                            <View>
                                <Text className="text-gray-400 text-xs font-medium mb-1">{item.label}</Text>
                                <View className="flex-row items-baseline gap-1">
                                    <Text className="text-white text-lg font-bold">{item.data.text === '-' ? '-' : item.data.percent}</Text>
                                    {item.data.text !== '-' && <Text className="text-xs text-white/50">%</Text>}
                                </View>
                            </View>
                        </TouchableOpacity>
                    ))}
                </View>
            </View>

            {/* Membership Card - Dynamic based on level */}
            {membership === 'BUSINESS' ? (
                <View className="px-6 pb-3">
                    <TouchableOpacity
                        className="relative overflow-hidden rounded-xl border border-premium/30 p-4"
                        activeOpacity={0.9}
                        onPress={() => navigation.navigate('Membership')}
                    >
                        <View className="absolute inset-0 bg-premium/5" />
                        <View className="flex-row items-center justify-between mb-2">
                            <View className="flex-row items-center gap-2">
                                <MaterialIcons name="business-center" size={20} color="#c5a059" />
                                <Text className="text-premium text-xs font-bold tracking-wider uppercase">Business Membership</Text>
                            </View>
                            <MaterialIcons name="arrow-forward-ios" size={14} color="#c5a059" />
                        </View>
                        <Text className="text-white text-base font-bold mb-1">비즈니스 멤버십 혜택</Text>
                        <Text className="text-text-secondary text-xs mb-3 leading-relaxed">
                            다중 차량 관리와 전담 매니저 서비스 등 강력한 비즈니스 전용 기능을 이용 중입니다.
                        </Text>
                        <View className="flex-row gap-2">
                            <View className="bg-premium/10 px-2 py-1 rounded border border-premium/20">
                                <Text className="text-premium text-xs font-medium">다중 차량 관리</Text>
                            </View>
                            <View className="bg-premium/10 px-2 py-1 rounded border border-premium/20">
                                <Text className="text-premium text-xs font-medium">정비소 연동</Text>
                            </View>
                        </View>
                    </TouchableOpacity>
                </View>
            ) : membership === 'PREMIUM' ? (
                <View className="px-6 pb-3">
                    <TouchableOpacity
                        className="relative overflow-hidden rounded-xl border border-primary/30 p-4"
                        activeOpacity={0.9}
                        onPress={() => navigation.navigate('Membership')}
                    >
                        <View className="absolute inset-0 bg-primary/5" />
                        <View className="flex-row items-center justify-between mb-2">
                            <View className="flex-row items-center gap-2">
                                <MaterialIcons name="workspace-premium" size={20} color="#0d7ff2" />
                                <Text className="text-primary text-xs font-bold tracking-wider uppercase">Premium Membership</Text>
                            </View>
                            <MaterialIcons name="arrow-forward-ios" size={14} color="#0d7ff2" />
                        </View>
                        <Text className="text-white text-base font-bold mb-1">프리미엄 멤버십 혜택</Text>
                        <Text className="text-text-secondary text-xs mb-3 leading-relaxed">
                            AI 기반 정밀 진단과 무제한 리포트 등 모든 프리미엄 기능을 이용 중입니다.
                        </Text>
                        <View className="flex-row gap-2">
                            <View className="bg-primary/10 px-2 py-1 rounded border border-primary/20">
                                <Text className="text-primary text-xs font-medium">AI 정밀 진단</Text>
                            </View>
                            <View className="bg-primary/10 px-2 py-1 rounded border border-primary/20">
                                <Text className="text-primary text-xs font-medium">무제한 리포트</Text>
                            </View>
                        </View>
                    </TouchableOpacity>
                </View>
            ) : (
                <View className="px-6 pb-3">
                    <TouchableOpacity
                        className="relative overflow-hidden rounded-xl border border-white/10 p-4 bg-white/5"
                        activeOpacity={0.9}
                        onPress={() => navigation.navigate('Membership')}
                    >
                        <View className="flex-row items-center justify-between mb-2">
                            <View className="flex-row items-center gap-2">
                                <MaterialIcons name="stars" size={20} color="#6b7280" />
                                <Text className="text-gray-400 text-xs font-bold tracking-wider uppercase">Upgrade Membership</Text>
                            </View>
                            <MaterialIcons name="arrow-forward-ios" size={14} color="#6b7280" />
                        </View>
                        <Text className="text-white text-base font-bold mb-1">멤버십 업그레이드</Text>
                        <Text className="text-text-secondary text-xs mb-3 leading-relaxed">
                            AI 기반 정밀 진단과 더 많은 혜택을 위해 멤버십을 업그레이드해보세요.
                        </Text>
                    </TouchableOpacity>
                </View>
            )}
            <VehicleSelectModal
                visible={isSelectModalVisible}
                onClose={() => setIsSelectModalVisible(false)}
                onSelect={(vehicle) => {
                    setPrimaryVehicle(vehicle);
                    setIsSelectModalVisible(false);
                }}
                title="차량 선택"
                description="메인 화면에 표시할 차량을 선택해주세요."
            />
            {/* Notification Onboarding Modal */}
            <NotificationOnboardingModal
                visible={showNotiOnboarding}
                onClose={handleOnboardingClose}
            />
        </BaseScreen>
    );
}
