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

    useEffect(() => {
        Animated.timing(scoreAnim, {
            toValue: 94,
            duration: 2000,
            useNativeDriver: false,
        }).start();

        // Cleanup simulation on unmount
        return () => {
            ObdService.stopSimulation();
        };
    }, []);

    const handleGoMain = () => {
        ObdService.stopSimulation();
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

    const ResultItem = ({ icon, label, status, isGood }: { icon: any, label: string, status: string, isGood: boolean }) => (
        <View className="flex-row items-center justify-between p-4 mb-3 rounded-2xl bg-[#ffffff08] border border-[#ffffff0d]">
            <View className="flex-row items-center gap-3">
                <View className={`w-10 h-10 rounded-xl items-center justify-center ${isGood ? 'bg-[#0d7ff2]/10' : 'bg-red-500/10'}`}>
                    <MaterialIcons name={icon} size={20} color={isGood ? '#0d7ff2' : '#ef4444'} />
                </View>
                <View>
                    <Text className="text-white font-bold text-[15px]">{label}</Text>
                    <Text className="text-slate-400 text-xs">{isGood ? '정상 작동 중' : '점검 필요'}</Text>
                </View>
            </View>
            <View className={`px-3 py-1 rounded-full ${isGood ? 'bg-[#0d7ff2]/10' : 'bg-red-500/10'}`}>
                <Text className={`text-xs font-bold ${isGood ? 'text-[#0d7ff2]' : 'text-red-400'}`}>
                    {status}
                </Text>
            </View>
        </View>
    );

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />
            <SafeAreaView className="flex-1">
                <View className="flex-row items-center justify-between px-6 py-4">
                    <TouchableOpacity onPress={handleGoMain} className="w-10 h-10 items-center justify-center rounded-full bg-[#ffffff08]">
                        <MaterialIcons name="close" size={20} color="white" />
                    </TouchableOpacity>
                    <Text className="text-white text-lg font-bold">진단 결과</Text>
                    <View className="w-10" />
                </View>

                <ScrollView className="flex-1 px-6 pt-4" showsVerticalScrollIndicator={false}>
                    {/* Score Section */}
                    <View className="items-center justify-center py-8 mb-8">
                        <View className="w-48 h-48 rounded-full items-center justify-center border-4 border-[#0d7ff2]/30 shadow-[0_0_40px_rgba(13,127,242,0.2)] bg-[#101922]">
                            <Text className="text-slate-400 text-sm font-medium mb-1">차량 종합 점수</Text>
                            <View className="flex-row items-baseline">
                                <Text className="text-6xl font-bold text-white tracking-tighter">94</Text>
                                <Text className="text-2xl font-medium text-slate-500 ml-1">점</Text>
                            </View>
                            <View className="mt-3 px-3 py-1 bg-[#0d7ff2]/20 rounded-full border border-[#0d7ff2]/30">
                                <Text className="text-[#0d7ff2] text-xs font-bold">상태 매우 좋음</Text>
                            </View>
                        </View>
                    </View>

                    {/* Report Summary */}
                    <View className="mb-8">
                        <Text className="text-white text-lg font-bold mb-4 px-1">상세 진단 내역</Text>
                        <ResultItem icon="speed" label="엔진 시스템" status="정상" isGood={true} />
                        <ResultItem icon="settings-input-component" label="변속기 (미션)" status="정상" isGood={true} />
                        <ResultItem icon="battery-charging-full" label="배터리 전압" status="14.2V (정상)" isGood={true} />
                        <ResultItem icon="thermostat" label="냉각수 온도" status="90°C (적정)" isGood={true} />
                        <ResultItem icon="air" label="흡기 시스템" status="주의" isGood={false} />
                    </View>

                    {/* Simulation Mode Button */}
                    <TouchableOpacity
                        onPress={toggleSimulation}
                        className={`p-4 rounded-xl mb-4 flex-row items-center justify-center gap-2 border ${isSimulating ? 'bg-orange-500/20 border-orange-500/50' : 'bg-[#ffffff08] border-[#ffffff0d]'}`}
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

