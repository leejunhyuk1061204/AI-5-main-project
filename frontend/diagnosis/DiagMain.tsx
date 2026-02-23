import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Animated, Easing, ActivityIndicator, Alert } from 'react-native';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import Header from '../header/Header';
import BaseScreen from '../components/layout/BaseScreen';
import VehicleSelectModal from '../components/VehicleSelectModal';
import { useAiDiagnosisStore, DiagMode, DiagType } from '../store/useAiDiagnosisStore';
import { useVehicleStore } from '../store/useVehicleStore';
import { diagnoseObdOnly } from '../api/aiApi';

export default function DiagMain() {
    const navigation = useNavigation<any>();
    const pulseAnim = React.useRef(new Animated.Value(1)).current;

    // Store State
    const {
        sessions,
        startDiagnosis,
        setVehicleId,
        selectedVehicleId
    } = useAiDiagnosisStore();

    const { primaryVehicle } = useVehicleStore();

    // UI Local State
    const [vehicleSelectVisible, setVehicleSelectVisible] = useState(false);
    const [selectedVehicleName, setSelectedVehicleName] = useState<string | null>(
        primaryVehicle ? `${primaryVehicle.modelNameKo} (${primaryVehicle.carNumber})` : null
    );
    const [pendingAction, setPendingAction] = useState<'OBD' | 'SOUND' | 'PHOTO' | null>(null);

    // 초기 대표 차량 설정
    useEffect(() => {
        if (primaryVehicle && !useAiDiagnosisStore.getState().selectedVehicleId) {
            setVehicleId(primaryVehicle.vehicleId!);
        }
    }, [primaryVehicle]);

    React.useEffect(() => {
        Animated.loop(
            Animated.sequence([
                Animated.timing(pulseAnim, { toValue: 2, duration: 1000, useNativeDriver: true, easing: Easing.inOut(Easing.ease) }),
                Animated.timing(pulseAnim, { toValue: 1, duration: 1000, useNativeDriver: true, easing: Easing.inOut(Easing.ease) }),
            ])
        ).start();
    }, []);

    // Auto-redirect removed to allow back navigation without looping.
    // Users can resume active sessions securely via the main button now.

    // Polling Effect (메인에서 진단 시작 시)
    // Polling Effect 제거: SSE는 ObdDiagLoading에서 처리함
    /*
    useEffect(() => {
        let intervalId: NodeJS.Timeout;
        if (status === 'PROCESSING' && currentSessionId) {
            intervalId = setInterval(() => {
                updateStatus(currentSessionId);
            }, 2000);
        }
        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    }, [status, currentSessionId]);
    */

    const handleVehicleSelect = async (vehicle: any) => {
        setVehicleSelectVisible(false);
        setSelectedVehicleName(`${vehicle.modelNameKo} (${vehicle.carNumber})`);
        setVehicleId(vehicle.vehicleId);

        if (pendingAction === 'OBD') {
            const sessionId = await startDiagnosis('OBD', vehicle.vehicleId, () => diagnoseObdOnly(vehicle.vehicleId));
            navigation.navigate('ObdDiagLoading', { vehicleId: vehicle.vehicleId, diagType: 'OBD', sessionId: sessionId ?? undefined });
        } else if (pendingAction === 'SOUND') {
            navigation.navigate('EngineSoundDiag', { from: 'professional', vehicleId: vehicle.vehicleId, diagType: 'SOUND' });
        } else if (pendingAction === 'PHOTO') {
            navigation.navigate('Filming', { from: 'professional', vehicleId: vehicle.vehicleId, diagType: 'PHOTO' });
        }
        setPendingAction(null);
    };

    // 공통 이어서 하기 탐색기
    const handleResumeOrStart = (
        type: DiagType,
        status: DiagMode,
        sid: string | null,
        onStartNew: () => void
    ) => {
        if (status !== 'IDLE' && sid) {
            // 진행 중인 세션이 있으므로 상태에 맞게 화면으로 바로 이동
            if (status === 'PROCESSING' || status === 'REPLY_PROCESSING') {
                navigation.navigate('ObdDiagLoading', { vehicleId: selectedVehicleId, diagType: type, sessionId: sid ?? undefined });
            } else if (status === 'INTERACTIVE' || status === 'ACTION_REQUIRED') {
                navigation.navigate('AiDiagChat', { sessionId: sid, diagType: type });
            } else if (status === 'REPORT') {
                navigation.navigate('DiagnosisReport', { sessionId: sid, diagType: type });
            }
        } else {
            // 새 진단 시작
            onStartNew();
        }
    };

    return (
        <BaseScreen header={<Header />} padding={false} useBottomNav={true}>
            {/* Vehicle Selector */}
            <View className="px-6 my-4 mb-6">
                <TouchableOpacity
                    onPress={() => setVehicleSelectVisible(true)}
                    activeOpacity={0.7}
                    className="flex-row items-center justify-between bg-surface-card border border-white/10 rounded-2xl px-6 py-4 shadow-sm"
                >
                    <View>
                        <Text className="text-text-dim text-[10px] font-bold uppercase tracking-widest mb-0.5">Target Vehicle</Text>
                        <Text className="text-white font-bold text-base">
                            {selectedVehicleName || '차량을 선택해주세요'}
                        </Text>
                    </View>
                    <View className="flex-row items-center gap-1 bg-white/5 px-3 py-1.5 rounded-lg border border-white/5">
                        <Text className="text-text-muted text-xs font-medium">변경</Text>
                        <MaterialIcons name="swap-horiz" size={16} color="#64748b" />
                    </View>
                </TouchableOpacity>
            </View>

            {/* Main Menu */}
            <View className="flex-col gap-4 px-6">
                {/* 1. Data Diagnosis */}
                <TouchableOpacity
                    className="w-full bg-white/5 border border-white/10 rounded-2xl p-5 active:bg-white/10"
                    activeOpacity={0.8}
                    onPress={() => {
                        handleResumeOrStart('OBD', sessions.OBD.status, sessions.OBD.currentSessionId, () => {
                            if (selectedVehicleId) {
                                startDiagnosis('OBD', selectedVehicleId, () => diagnoseObdOnly(selectedVehicleId)).then((sessionId) => {
                                    navigation.navigate('ObdDiagLoading', { vehicleId: selectedVehicleId, diagType: 'OBD', sessionId: sessionId ?? undefined });
                                });
                            } else {
                                setPendingAction('OBD'); setVehicleSelectVisible(true);
                            }
                        });
                    }}
                >
                    <View className="flex-row items-center gap-4">
                        <View className="w-12 h-12 rounded-xl bg-primary/10 items-center justify-center border border-primary/20">
                            <MaterialIcons name="analytics" size={28} color="#0d7ff2" />
                        </View>
                        <View className="flex-1">
                            <Text className="text-white font-bold text-lg mb-0.5">데이터 진단</Text>
                            <Text className="text-xs text-text-muted">OBD 데이터 기반 시스템 종합 분석</Text>
                        </View>
                        {sessions.OBD.status !== 'IDLE' ? (
                            <View className="bg-primary/20 px-2 py-1 rounded-md border border-primary/30">
                                <Text className="text-primary text-[10px] font-bold">진행 중</Text>
                            </View>
                        ) : (
                            <MaterialIcons name="chevron-right" size={24} color="#64748b" />
                        )}
                    </View>
                </TouchableOpacity>

                {/* 2. Sound Diagnosis */}
                <TouchableOpacity
                    className="w-full bg-white/5 border border-white/10 rounded-2xl p-5 active:bg-white/10"
                    onPress={() => {
                        handleResumeOrStart('SOUND', sessions.SOUND.status, sessions.SOUND.currentSessionId, () => {
                            if (selectedVehicleId) {
                                navigation.navigate('EngineSoundDiag', { from: 'professional', vehicleId: selectedVehicleId, diagType: 'SOUND' });
                            } else {
                                setPendingAction('SOUND'); setVehicleSelectVisible(true);
                            }
                        });
                    }}
                >
                    <View className="flex-row items-center gap-4">
                        <View className="w-12 h-12 rounded-xl bg-primary/10 items-center justify-center border border-primary/20">
                            <MaterialIcons name="graphic-eq" size={28} color="#0d7ff2" />
                        </View>
                        <View className="flex-1">
                            <Text className="text-white font-bold text-lg mb-0.5">소리 진단</Text>
                            <Text className="text-xs text-text-muted">OBD 데이터 + 엔진 소음 융합 분석</Text>
                        </View>
                        {sessions.SOUND.status !== 'IDLE' ? (
                            <View className="bg-primary/20 px-2 py-1 rounded-md border border-primary/30">
                                <Text className="text-primary text-[10px] font-bold">진행 중</Text>
                            </View>
                        ) : (
                            <MaterialIcons name="chevron-right" size={24} color="#64748b" />
                        )}
                    </View>
                </TouchableOpacity>

                {/* 3. Photo Diagnosis */}
                <TouchableOpacity
                    className="w-full bg-white/5 border border-white/10 rounded-2xl p-5 active:bg-white/10"
                    onPress={() => {
                        handleResumeOrStart('PHOTO', sessions.PHOTO.status, sessions.PHOTO.currentSessionId, () => {
                            if (selectedVehicleId) {
                                navigation.navigate('Filming', { from: 'professional', vehicleId: selectedVehicleId, diagType: 'PHOTO' });
                            } else {
                                setPendingAction('PHOTO'); setVehicleSelectVisible(true);
                            }
                        });
                    }}
                >
                    <View className="flex-row items-center gap-4">
                        <View className="w-12 h-12 rounded-xl bg-primary/10 items-center justify-center border border-primary/20">
                            <MaterialIcons name="camera-alt" size={28} color="#0d7ff2" />
                        </View>
                        <View className="flex-1">
                            <Text className="text-white font-bold text-lg mb-0.5">사진 진단</Text>
                            <Text className="text-xs text-text-muted">OBD 데이터 + 부품 사진 시각 분석</Text>
                        </View>
                        {sessions.PHOTO.status !== 'IDLE' ? (
                            <View className="bg-primary/20 px-2 py-1 rounded-md border border-primary/30">
                                <Text className="text-primary text-[10px] font-bold">진행 중</Text>
                            </View>
                        ) : (
                            <MaterialIcons name="chevron-right" size={24} color="#64748b" />
                        )}
                    </View>
                </TouchableOpacity>
            </View>

            {/* Diagnosis Selection Modal */}
            <VehicleSelectModal
                visible={vehicleSelectVisible}
                onClose={() => setVehicleSelectVisible(false)}
                onSelect={handleVehicleSelect}
                description="진단을 진행할 차량을 선택해주세요."
            />

            {/* Global Loading Overlay Removed (Using ObdDiagLoading Screen Instead) */}
            {/* 
            {status === 'PROCESSING' && (
                <View className="absolute inset-0 bg-[#101922]/90 items-center justify-center z-[100]">
                    <ActivityIndicator size="large" color="#0d7ff2" className="mb-4" />
                    <Text className="text-white font-bold text-lg mb-2">{loadingMessage}</Text>
                    <Text className="text-slate-400 text-center px-10">AI 전문 분석가가 데이터를 검토 중입니다.</Text>
                </View>
            )}
            */}
        </BaseScreen>
    );
}
