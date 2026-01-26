import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Animated } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { CommonActions } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import ObdService from '../../services/ObdService';

export default function ObdResult({ navigation }: any) {
    const [scoreAnim] = useState(new Animated.Value(0));
    const [isSimulating, setIsSimulating] = useState(false);

    // State for Real-time Data
    const [liveData, setLiveData] = useState<any>({
        rpm: 0,
        speed: 0,
        temp: 0,
        voltage: 0,
        load: 0,
        fuelShort: 0,
        fuelLong: 0
    });

    useEffect(() => {
        Animated.timing(scoreAnim, {
            toValue: 94,
            duration: 2000,
            useNativeDriver: false,
        }).start();

        // Subscribe to Real-time Data
        console.log("[ObdResult] Subscribing to live data...");
        const unsubscribe = ObdService.onData((data) => {
            setLiveData({
                rpm: data.rpm ?? 0,
                speed: data.speed ?? 0,
                temp: data.coolant_temp ?? 0,
                voltage: data.voltage ?? 0,
                load: data.engine_load ?? 0,
                fuelShort: data.fuel_trim_short ?? 0,
                fuelLong: data.fuel_trim_long ?? 0
            });
        });

        // Cleanup: Only stop simulation if it was running locally
        return () => {
            unsubscribe();
            // Note: We don't stop polling here because we want it to persist if we just background?
            // Actually, if we leave this screen (unmount), we PROBABLY want to disconnect
            // UNLESS we are navigating to another dashboard screen.
            // For now, let's keep connection ALIVE only if needed, but per user request "main으로 이동" stops it.
            // If component unmounts (e.g. back button), we should probably stop to be safe.
            // But let's check handleGoMain.
            ObdService.stopSimulation();
        };
    }, []);

    const handleGoMain = async () => {
        console.log("[ObdResult] Exiting to Main... Stopping Service.");
        ObdService.stopSimulation();
        await ObdService.disconnect(); // Explicitly disconnect and flush
        navigation.dispatch(
            CommonActions.reset({
                index: 0,
                routes: [{ name: 'MainPage' }],
            })
        );
    };

    const toggleSimulation = async () => {
        if (isSimulating) {
            ObdService.stopSimulation();
            setIsSimulating(false);
        } else {
            // Get primary vehicle ID
            const stored = await AsyncStorage.getItem('primaryVehicle');
            if (stored) {
                const vehicle = JSON.parse(stored);
                ObdService.setVehicleId(vehicle.id);
                ObdService.startSimulation();
                setIsSimulating(true);
            } else {
                console.warn('[ObdResult] No primary vehicle set');
            }
        }
    };

    const ResultItem = ({ icon, label, status, isGood, value }: { icon: any, label: string, status: string, isGood: boolean, value?: string }) => (
        <View className="flex-row items-center justify-between p-4 mb-3 rounded-2xl bg-white/5 border border-white/10">
            <View className="flex-row items-center gap-3">
                <View className={`w-10 h-10 rounded-xl items-center justify-center ${isGood ? 'bg-primary/10' : 'bg-error/10'}`}>
                    <MaterialIcons name={icon} size={20} color={isGood ? '#0d7ff2' : '#ff6b6b'} />
                </View>
                <View>
                    <Text className="text-white font-bold text-[15px]">{label}</Text>
                    <Text className="text-slate-400 text-xs">{isGood ? '정상 작동 중' : '점검 필요'}</Text>
                </View>
            </View>
            <View className="items-end">
                {value && <Text className="text-white font-bold text-base mb-0.5">{value}</Text>}
                <View className={`px-2 py-0.5 rounded-full ${isGood ? 'bg-primary/10' : 'bg-error/10'}`}>
                    <Text className={`text-[10px] font-bold ${isGood ? 'text-primary' : 'text-error'}`}>
                        {status}
                    </Text>
                </View>
            </View>
        </View>
    );

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />
            <SafeAreaView className="flex-1">
                <View className="flex-row items-center justify-between px-6 py-4">
                    <TouchableOpacity onPress={handleGoMain} className="w-10 h-10 items-center justify-center rounded-full bg-white/5">
                        <MaterialIcons name="close" size={20} color="white" />
                    </TouchableOpacity>
                    <Text className="text-white text-lg font-bold">실시간 진단 대시보드</Text>
                    <View className="w-10" />
                </View>

                <ScrollView className="flex-1 px-6 pt-4" showsVerticalScrollIndicator={false}>
                    {/* Score Section */}
                    <View className="items-center justify-center py-8 mb-8">
                        <View className="w-48 h-48 rounded-full items-center justify-center border-4 border-primary/30 shadow-[0_0_40px_rgba(13,127,242,0.2)] bg-surface-dark">
                            <Text className="text-slate-400 text-sm font-medium mb-1">엔진 회전수 (RPM)</Text>
                            <View className="flex-row items-baseline">
                                <Text className="text-5xl font-bold text-white tracking-tighter">{liveData.rpm}</Text>
                                <Text className="text-xl font-medium text-slate-500 ml-1">rpm</Text>
                            </View>
                            <View className="mt-2 flex-row gap-2">
                                <Text className="text-slate-400 text-xs">Speed: {liveData.speed} km/h</Text>
                            </View>
                        </View>
                    </View>

                    {/* Report Summary */}
                    <View className="mb-8">
                        <Text className="text-white text-lg font-bold mb-4 px-1">실시간 센서 데이터</Text>
                        <ResultItem icon="speed" label="엔진 부하" status="Load" isGood={liveData.load < 80} value={`${liveData.load}%`} />
                        <ResultItem icon="settings-input-component" label="연료 보정 (Short)" status="Trim" isGood={Math.abs(liveData.fuelShort) < 10} value={`${liveData.fuelShort}%`} />
                        <ResultItem icon="battery-charging-full" label="배터리 전압" status={liveData.voltage > 13 ? "정상" : "주의"} isGood={liveData.voltage > 12.0} value={`${liveData.voltage}V`} />
                        <ResultItem icon="thermostat" label="냉각수 온도" status={liveData.temp < 100 ? "정상" : "과열"} isGood={liveData.temp < 100} value={`${liveData.temp}°C`} />
                    </View>

                    {/* Simulation Mode Button */}
                    <TouchableOpacity
                        onPress={toggleSimulation}
                        className={`p-4 rounded-xl mb-4 flex-row items-center justify-center gap-2 border ${isSimulating ? 'bg-warning/20 border-warning/50' : 'bg-white/5 border-white/10'}`}
                    >
                        <MaterialIcons name={isSimulating ? 'stop' : 'play-arrow'} size={20} color={isSimulating ? '#f97316' : '#0d7ff2'} />
                        <Text className={`font-bold ${isSimulating ? 'text-orange-400' : 'text-[#0d7ff2]'}`}>
                            {isSimulating ? '시뮬레이션 중지' : '🚗 가상 주행 시작 (테스트)'}
                        </Text>
                    </TouchableOpacity>

                    {/* AI Recommendation */}
                    <View className="bg-gradient-to-br from-[#1e293b] to-[#0f172a] p-5 rounded-2xl border border-[#0d7ff2]/30 mb-8 relative overflow-hidden">
                        <View className="absolute top-0 right-0 w-20 h-20 bg-[#0d7ff2]/20 blur-xl rounded-full translate-x-10 -translate-y-10" />
                        <View className="flex-row items-center gap-2 mb-3">
                            <MaterialIcons name="auto-awesome" size={20} color="#0d7ff2" />
                            <Text className="text-[#0d7ff2] font-bold text-sm">AI 맞춤 분석</Text>
                        </View>
                        <Text className="text-slate-300 text-sm leading-relaxed">
                            전반적인 차량 상태는 매우 양호합니다. 다만 <Text className="text-red-400 font-bold">흡기 필터</Text>의 공기 흐름이 다소 제한적입니다.
                            연비 저하를 방지하기 위해 다음 엔진오일 교환 시 에어필터를 함께 형검하시는 것을 권장합니다.
                        </Text>
                    </View>
                </ScrollView>

                {/* Bottom Button */}
                <View className="p-6 pt-2 bg-background-dark/90 backdrop-blur-md">
                    <TouchableOpacity
                        onPress={handleGoMain}
                        className="w-full shadow-lg shadow-blue-500/30"
                        activeOpacity={0.9}
                    >
                        <LinearGradient
                            colors={['#0d7ff2', '#0062cc']}
                            start={{ x: 0, y: 0 }}
                            end={{ x: 1, y: 0 }}
                            className="w-full py-4 rounded-xl items-center justify-center"
                        >
                            <Text className="text-white font-bold text-lg">메인으로 이동</Text>
                        </LinearGradient>
                    </TouchableOpacity>
                </View>
            </SafeAreaView>
        </View>
    );
}

