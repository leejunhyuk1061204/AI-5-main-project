import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, Animated, Easing, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';

export default function EngineSoundDiag() {
    const navigation = useNavigation();

    // State for Diagnosis Flow
    const [step, setStep] = useState(1); // 1: Record, 2: Analyze, 3: Result
    const [isRecording, setIsRecording] = useState(false);

    // Animation values for each bar
    const animations = useRef([...Array(9)].map(() => new Animated.Value(1))).current;

    // Recording/Wave Animation Effect
    useEffect(() => {
        const activeAnimations: Animated.CompositeAnimation[] = [];

        // Only animate if in Step 1 or Step 2 (Analysis uses same wave for now)
        if (step <= 2) {
            animations.forEach((anim, index) => {
                const sequence = Animated.sequence([
                    Animated.timing(anim, {
                        toValue: step === 1 && !isRecording ? 1 : 1.6, // Static if not recording (Step 1), Moving if recording or analyzing
                        duration: 900,
                        easing: Easing.inOut(Easing.ease),
                        useNativeDriver: true,
                    }),
                    Animated.timing(anim, {
                        toValue: 1,
                        duration: 900,
                        easing: Easing.inOut(Easing.ease),
                        useNativeDriver: true,
                    }),
                ]);

                const loop = Animated.loop(sequence);
                if (step === 2 || isRecording) {
                    activeAnimations.push(loop);
                    setTimeout(() => {
                        loop.start();
                    }, index * 200);
                } else {
                    anim.setValue(1); // Reset to static
                }
            });
        }

        return () => {
            activeAnimations.forEach(anim => anim.stop());
        };
    }, [isRecording, step]);

    // Handle Record Button Toggle
    const handleRecordToggle = () => {
        if (!isRecording) {
            setIsRecording(true);
        } else {
            // Stop recording -> Go to Step 2
            setIsRecording(false);
            setStep(2);

            // Simulate Analysis Delay (e.g., 3 seconds) then go to Step 3
            setTimeout(() => {
                setStep(3);
            }, 3000);
        }
    };

    const barHeights = [32, 48, 64, 96, 56, 80, 40, 48, 24];

    return (
        <SafeAreaView className="flex-1 bg-[#101922]">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 py-3">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">엔진 소리 진단</Text>
                <View className="w-10" />
            </View>

            {/* Progress Indicator */}
            {step < 3 && (
                <View className="px-6 pb-2">
                    <View className="flex-row items-center justify-between mb-2">
                        <Text className="text-xs font-medium text-slate-400">{step}단계</Text>
                        <Text className="text-xs font-medium text-[#0d7ff2]">3단계 중 {step}</Text>
                    </View>
                    <View className="flex-row gap-2 h-1.5 w-full">
                        <View className={`flex-1 rounded-full ${step >= 1 ? 'bg-[#0d7ff2]' : 'bg-[#1a2430]'}`} />
                        <View className={`flex-1 rounded-full ${step >= 2 ? 'bg-[#0d7ff2]' : 'bg-[#1a2430]'}`} />
                        <View className={`flex-1 rounded-full ${step >= 3 ? 'bg-[#0d7ff2]' : 'bg-[#1a2430]'}`} />
                    </View>
                </View>
            )}

            {/* Main Content Area */}
            <View className="flex-1 items-center justify-center px-6 relative">

                {/* Step 1 & 2: Visualization UI */}
                {step <= 2 && (
                    <>
                        {/* Context Text */}
                        <View className="items-center mb-12 z-10">
                            <Text className="text-2xl font-bold text-white text-center leading-9 mb-3">
                                {step === 1
                                    ? (isRecording ? "소리를 녹음 중입니다..." : "엔진 시동을 걸고\n소리를 녹음해 주세요")
                                    : "AI가 소리를 분석 중입니다..."}
                            </Text>
                            <Text className="text-sm text-slate-400 text-center leading-5">
                                {step === 1
                                    ? "정확한 분석을 위해 주변 소음을\n최소화해 주시기 바랍니다."
                                    : "잠시만 기다려주세요\n엔진과 부품의 상태를 정밀 진단하고 있습니다."}
                            </Text>
                        </View>

                        {/* Waveform Visualization */}
                        <View className="relative items-center justify-center w-full h-40 mb-12">
                            {/* Background Glow */}
                            <View className={`absolute inset-0 rounded-full blur-3xl opacity-50 ${step === 2 ? 'bg-purple-500/20' : 'bg-[#0d7ff2]/10'}`} />

                            {/* Visual Bars */}
                            <View className="flex-row items-center justify-center gap-1.5 h-full z-10">
                                {animations.map((anim, index) => (
                                    <Animated.View
                                        key={index}
                                        style={{
                                            width: 6,
                                            height: barHeights[index],
                                            backgroundColor: step === 2 ? '#a855f7' : '#0d7ff2', // Purple for analysis
                                            borderRadius: 9999,
                                            transform: [{ scaleY: anim }],
                                            shadowColor: step === 2 ? '#a855f7' : '#0d7ff2',
                                            shadowOffset: { width: 0, height: 0 },
                                            shadowOpacity: 0.6,
                                            shadowRadius: 15,
                                            opacity: 0.8
                                        }}
                                    />
                                ))}
                            </View>
                        </View>

                        {/* Step 1 Extra: Distance Guide */}
                        {step === 1 && (
                            <View className="w-full max-w-sm bg-[#1a2430] rounded-xl p-4 flex-row items-center gap-4 border border-slate-800">
                                <View className="w-12 h-12 rounded-lg bg-[#0d7ff2]/10 items-center justify-center">
                                    <MaterialIcons name="straighten" size={24} color="#0d7ff2" />
                                </View>
                                <View className="flex-1">
                                    <Text className="text-sm font-semibold text-white">거리 유지</Text>
                                    <Text className="text-xs text-slate-400 mt-0.5">보닛에서 약 30cm 거리를 유지해 주세요</Text>
                                </View>
                            </View>
                        )}
                    </>
                )}

                {/* Step 3: Result UI */}
                {step === 3 && (
                    <View className="w-full items-center">
                        <View className="w-32 h-32 rounded-full border-4 border-[#0d7ff2] items-center justify-center mb-6 shadow-[0_0_30px_rgba(13,127,242,0.3)] bg-[#0d7ff2]/10">
                            <MaterialIcons name="check-circle" size={64} color="#0d7ff2" />
                        </View>

                        <Text className="text-3xl font-bold text-white mb-2">진단 결과: 정상</Text>
                        <View className="bg-[#1a2430] px-4 py-1.5 rounded-full border border-slate-700 mb-8">
                            <Text className="text-sm text-slate-300">종합 점수 <Text className="text-[#0d7ff2] font-bold">98점</Text></Text>
                        </View>

                        <View className="w-full bg-[#1a2430] rounded-2xl p-6 border border-slate-800 mb-8">
                            <Text className="text-lg font-bold text-white mb-3">상세 분석</Text>
                            <View className="gap-3">
                                <View className="flex-row items-start gap-3">
                                    <MaterialIcons name="check" size={20} color="#0d7ff2" className="mt-0.5" />
                                    <Text className="text-slate-300 flex-1 leading-5">엔진 구동음이 매우 부드럽고 규칙적입니다.</Text>
                                </View>
                                <View className="flex-row items-start gap-3">
                                    <MaterialIcons name="check" size={20} color="#0d7ff2" className="mt-0.5" />
                                    <Text className="text-slate-300 flex-1 leading-5">벨트 슬립이나 베어링 마모 소음이 감지되지 않았습니다.</Text>
                                </View>
                                <View className="flex-row items-start gap-3">
                                    <MaterialIcons name="check" size={20} color="#0d7ff2" className="mt-0.5" />
                                    <Text className="text-slate-300 flex-1 leading-5">점화 타이밍이 안정적입니다.</Text>
                                </View>
                            </View>
                        </View>

                        <TouchableOpacity
                            onPress={() => navigation.goBack()}
                            className="w-full bg-[#1b2127] border border-white/10 py-4 rounded-xl items-center active:bg-white/5"
                        >
                            <Text className="text-white font-bold text-base">메인으로 돌아가기</Text>
                        </TouchableOpacity>
                    </View>
                )}

            </View>

            {/* Footer / Action Area (Only for Step 1) */}
            {step === 1 && (
                <View className="p-6 items-center gap-4 bg-[#101922] pb-10">
                    {/* Record/Stop Button */}
                    <TouchableOpacity
                        onPress={handleRecordToggle}
                        className={`relative items-center justify-center w-20 h-20 rounded-full shadow-lg active:scale-95 transition-all ${isRecording ? 'bg-red-500 shadow-red-500/40' : 'bg-[#0d7ff2] shadow-blue-500/40'}`}
                    >
                        {isRecording && (
                            <View className="absolute inset-0 rounded-full border-2 border-white/30 animate-ping" />
                        )}
                        <MaterialIcons
                            name={isRecording ? "stop" : "mic"}
                            size={32}
                            color="white"
                        />
                    </TouchableOpacity>

                    <Text className={`text-sm font-medium ${isRecording ? 'text-red-400 animate-pulse' : 'text-slate-500'}`}>
                        {isRecording ? "녹음 중..." : "녹음 준비 완료"}
                    </Text>

                    {/* Safety Note */}
                    <View className="flex-row items-center gap-1.5 mt-2 opacity-60">
                        <MaterialIcons name="warning" size={16} color="#f59e0b" />
                        <Text className="text-[10px] text-slate-400">안전을 위해 주차 브레이크를 꼭 확인하세요</Text>
                    </View>
                </View>
            )}
        </SafeAreaView>
    );
}
